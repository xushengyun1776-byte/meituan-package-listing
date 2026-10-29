#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""美团「选择商品」弹窗批量勾选工具（**分组树导航**方案）。

★ 为什么不用搜索框：
  弹窗左侧是**菜单分组树**，右侧只列「当前选中分组」下的商品。
  实测搜索框在弹窗里怎么输入都不触发检索（onChange/onKeyDown 都挂了，
  但服务端检索就是不动），而**直接点左侧分组**100% 可靠。
  所以：先扫一遍分组树建立「商品名 -> 分组」映射，再按分组导航勾选。

★ 弹窗布局（实测，992x720 的 iframe）：
  - 左侧分组树  x <  205
  - 中间商品列表 x = 205 .. 625   （未选商品）
  - 右侧已选区  x >= 625           （已选商品，会随勾选实时变化）

用法:
  python pick.py scan                       # 扫描分组树，输出 商品->分组 映射
  python pick.py pick <分组名> <商品名>...  # 切分组并勾选
  python pick.py clear                      # 清空已选（含二次确认）
  python pick.py selected                   # 打印已选商品
"""
import sys, json, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clicktext import CDP, get_page

KEY = "选择商品"
CARD = "div[class*=product-card]"
SEARCH_IN = 'input[placeholder="搜索商品名称"]'

# 中间商品列表 / 右侧已选区的 x 分界（实测 625）
SEL_X = 600


# ---------------------------------------------------------------- 上下文定位
def _group_count(cdp, cid):
    """该 context 里左侧分组树的数量（0 表示还没渲染 / 是残留的空 iframe）。"""
    js = "(()=>document.querySelectorAll('div[class*=tag-list-item]').length)()"
    try:
        return int(cdp.evaluate(js, cid) or 0)
    except Exception:
        return -1


def modal_ctx(cdp, tries=6):
    """找到「选择商品」弹窗所在 context。

    ★ 判据要够严，否则会**误把表单 iframe 当成弹窗**：
      表单的规格组里也有 `span.custom-checkbox`（商品行勾选框），
      只用「有 checkbox」探测会命中表单，导致后续所有操作跑在表单上。

    ★ 页面里可能同时存在**多个** selectProduct iframe
      （React 复用/叠加，旧的不销毁），它们的 context 都在列表里。
      必须挑**分组树最多**（= 真正渲染好的那个），不能拿第一个就返回。
    """
    for attempt in range(tries):
        cands = cdp.contexts()
        best = None
        best_n = -1
        for c in cands:
            try:
                u = cdp.evaluate("location.href", c["id"]) or ""
            except Exception:
                continue
            if "selectProduct" not in u and "selectGoods" not in u:
                continue
            n = _group_count(cdp, c["id"])
            if n > best_n:
                best_n = n
                best = c
        if best is not None and best_n > 0:
            best["text"] = KEY
            return best
        # 没有可用的 selectProduct iframe 时，退回按文本/探针找
        for c in cands:
            if "店内商品" in c["text"]:
                c["text"] = KEY
                if _group_count(cdp, c["id"]) > 0:
                    return c
        probe = ("(() => { const i=document.querySelector('input[placeholder=\"搜索商品名称\"]');"
                 " const t=document.body?(document.body.innerText||''):'';"
                 " return (i && /店内商品/.test(t)) ? 'YES' : ''; })()")
        for c in cands:
            try:
                if cdp.evaluate(probe, c["id"]) == "YES":
                    c["text"] = KEY
                    if _group_count(cdp, c["id"]) > 0:
                        return c
            except Exception:
                continue
        time.sleep(1.0)
    return None


class Modal:
    """管理「选择商品」弹窗的 context。

    ★ 弹窗是独立 iframe，**会被 React 重建**，contextId 随之失效，
      evaluate 会报 "Cannot find context with specified id"。
      所以每次操作前都要 refresh()，失败也要 refresh 后重试。
    """

    def __init__(self, cdp):
        self.cdp = cdp
        self.cid = None
        self.refresh()

    def refresh(self, verbose=False):
        c = modal_ctx(self.cdp, tries=4)
        if verbose:
            print("    [Modal.refresh] 候选:", [
                (x["id"], (self.cdp.evaluate("location.href", x["id"]) or "?")[-28:])
                for x in self.cdp.contexts()])
        if c:
            self.cid = c["id"]
        elif verbose:
            print("    [Modal.refresh] 未找到弹窗")
        return self.cid

    def alive(self):
        if self.cid is None:
            return False
        try:
            self.cdp.evaluate("(()=>1)()", self.cid)
            return True
        except Exception:
            self.cid = None
            return False

    def ev(self, js, tries=3, default=None):
        """在弹窗 context 里求值。JS 抛错时**打日志**（避免静默返回 None）。"""
        for _ in range(tries):
            if not self.alive() and not self.refresh():
                time.sleep(0.5)
                continue
            try:
                return self.cdp.evaluate(js, self.cid, strict=True)
            except Exception as e:
                msg = str(e)
                if "Cannot find context" in msg:
                    self.cid = None
                    time.sleep(0.5)
                    continue
                print("    [Modal.ev] JS 错误:", msg[:200])
                return default
        return default

    def click(self, expr, tries=3):
        for _ in range(tries):
            if not self.alive() and not self.refresh():
                time.sleep(0.5)
                continue
            try:
                r = self.cdp.js_click(self.cid, expr)
                if r and not str(r).startswith("err:"):
                    return r
            except Exception:
                pass
            self.cid = None
            time.sleep(0.6)
        return None


# ---------------------------------------------------------------- 分组树
# ★ 分组名提取：注意 `.filter()` 必须作用在 **map 的结果数组**上，
#   写成 `{...}.filter(Boolean)` 会变成对函数体调用 filter —— 语法/运行时错误，
#   而 CDP 的 Runtime.evaluate 对 JS 错误**不抛 Python 异常**，
#   只会静默返回 None，于是表现为「分组列表永远是空的」。
JS_GROUP_NAMES = ("(()=>{const a=[...document.querySelectorAll('div[class*=tag-list-item]')]"
                  ".map(e=>{const c=e.querySelector('div[class*=content]');"
                  "return c?(c.innerText||'').trim():'';}).filter(Boolean);"
                  "return JSON.stringify(a);})()")


def group_names(cdp, cid):
    """左侧分组树的全部分组名（按显示顺序）。"""
    return json.loads(cdp.evaluate(JS_GROUP_NAMES, cid, strict=True) or "[]")


def switch_group(md, group):
    """点击左侧分组树上的某个分组，返回 js_click 结果。"""
    js = ("(()=>{for(const e of document.querySelectorAll('div[class*=tag-list-item]')){"
          "const c=e.querySelector('div[class*=content]');"
          "if(c&&(c.innerText||'').trim()===%s) return e;} return null;})()"
          % json.dumps(group))
    r = md.click(js)
    time.sleep(1.3)
    return r


# ---------------------------------------------------------------- 商品列表
def _cards_js(min_x, max_x=10 ** 9):
    return ("(()=>{const o=[];for(const e of document.querySelectorAll(%s)){"
            "const r=e.getBoundingClientRect(); if(r.x<%d||r.x>=%d) continue;"
            "const t=(e.innerText||'').trim().split('\\n')[0].trim(); if(t) o.push(t);}"
            "return o.join(' | ');})()" % (json.dumps(CARD), min_x, max_x))


def list_names(cdp, cid, selected=False):
    """当前分组下的商品列表（selected=True 时读右侧已选区）。"""
    js = _cards_js(SEL_X) if selected else _cards_js(0, SEL_X)
    r = cdp.evaluate(js, cid)
    try:
        out = []
        for x in (r or "").split("|"):
            x = x.strip()
            if x and x not in out:
                out.append(x)
        return out
    except Exception:
        return []


def selected_names(cdp, cid):
    """右侧「已选商品」区里的商品名列表。"""
    return list_names(cdp, cid, selected=True)


def item_checkbox_expr(name):
    """中间商品列表中某个商品的勾选框表达式。"""
    return ("(()=>{for(const e of document.querySelectorAll(%s)){"
            "const r=e.getBoundingClientRect(); if(r.x>=%d) continue;"
            "const t=(e.innerText||'').trim().split('\\n')[0].trim();"
            "if(t===%s){const cb=e.querySelector('span.custom-checkbox'); if(cb) return cb;}}"
            "return null;})()" % (json.dumps(CARD), SEL_X, json.dumps(name)))


# ---------------------------------------------------------------- 操作
def clear_selected(md):
    """清空已选商品。

    ★ 「清空」会弹**二次确认框**「确认清空所选商品吗？」，必须点掉它。
      不点掉的话，这层 backdrop 即使 opacity=0 也会盖满弹窗，
      把后续所有坐标点击全部吞掉（合成事件不受影响，所以特别难查）。

    ★ 确认框的按钮文本是「确 定」（中间一个半角空格），
      所以比较前要去掉所有空白字符。
    """
    from form import purge_modals
    purge_modals(md.cdp, md.cid)
    md.refresh()
    r1 = md.click("(()=>{const b=[...document.querySelectorAll('button')]"
                  ".find(e=>(e.innerText||'').replace(/\\s+/g,'')==='清空');return b||null;})()")
    time.sleep(1.2)
    # 二次确认框：含「清空」但不含「店内商品」（后者是商品选择弹窗本体）
    js = ("(()=>{for(const m of document.querySelectorAll('div.roo-modal')){"
          "const t=(m.innerText||'');"
          "if(!/清空/.test(t)||/店内商品/.test(t)) continue;"
          "for(const b of m.querySelectorAll('button')){"
          "const s=(b.innerText||'').replace(/\\s+/g,'');"
          "if(s==='确定'||s==='确认') return b;}}} return null;})()")
    r2 = md.click(js)
    time.sleep(1.2)
    purge_modals(md.cdp, md.cid)
    return "clear:%s confirm:%s" % (r1, r2)


def check_item(md, name):
    """勾选中间列表里的某个商品（合成事件，不依赖坐标）。"""
    r = md.click(item_checkbox_expr(name))
    time.sleep(0.5)
    return r


def confirm_modal(cdp, cid):
    """点弹窗底部「确定」。"""
    js = ("(()=>{for(const b of document.querySelectorAll('button')){"
          "const t=(b.innerText||'').replace(/\\s+/g,''); if(t==='确定') return b;} return null;})()")
    r = cdp.js_click(cid, js)
    time.sleep(1.5)
    return r


def scan_groups(cdp, cid, gap=1.2):
    """遍历所有分组，输出 {分组名: [商品名]}。"""
    names = group_names(cdp, cid)
    mapping = {}
    for i, nm in enumerate(names):
        js = "(document.querySelectorAll('div[class*=tag-list-item]')[%d])" % i
        cdp.js_click(cid, js)
        time.sleep(gap)
        mapping[nm] = list_names(cdp, cid)
    return mapping


def wait_ready(md, timeout=18.0):
    """等弹窗真正渲染好（左侧分组树出现），返回分组名列表。

    ★ 弹窗 iframe 是异步加载的：点开按钮后 DOM 还没渲染，
      这时读分组树只会得到空列表 —— 表现为「分组定位 {}」。
    """
    t0 = time.time()
    names = []
    while time.time() - t0 < timeout:
        raw = md.ev(JS_GROUP_NAMES, default="__ERR__")
        print("    [wait_ready] raw=%r alive=%s cid=%s" % (str(raw)[:160], md.alive(), md.cid))
        try:
            names = json.loads(raw or "[]")
        except Exception:
            names = []
        if names:
            return names
        time.sleep(0.8)
    return names


def find_groups_for(md, items, gap=1.1):
    """扫描分组树，返回 {商品名: 分组名}（只含目标商品）。

    ★ 弹窗默认只列「当前分组」的商品，跨分组必须先切分组，
      所以这是唯一可靠的定位方式（搜索框在弹窗里不触发检索）。
    """
    want = set(items)
    hit = {}
    names = wait_ready(md)
    for i, nm in enumerate(names):
        md.click("(document.querySelectorAll('div[class*=tag-list-item]')[%d])" % i)
        time.sleep(gap)
        for nm2 in list_names(md.cdp, md.cid):
            if nm2 in want and nm2 not in hit:
                hit[nm2] = nm
        if len(hit) == len(want):
            break
    return hit


def pick_auto(cdp, items, clear=True, gap=1.1, log=print):
    """在弹窗内按分组导航勾选一组商品。

    ★ 商品选择弹窗是独立 iframe，**会被重建**（contextId 随之失效），
      所以全程用 Modal 会话对象托管 context。

    返回 (ok, bad)。已在已选区的商品视为成功（避免 toggle 取消）。
    """
    md = Modal(cdp)
    print("  [pick_auto] Modal.cid =", md.cid,
          "group_count =", _group_count(cdp, md.cid) if md.cid else None)
    if md.cid is None:
        md.refresh(verbose=True)
        print("  [pick_auto] 重试后 Modal.cid =", md.cid)
    if md.cid is None:
        return [], list(items)

    # ★ 「清空」只在**已选区非空**时才做。
    #   每次新开的商品选择弹窗都是「已选商品 0」，此时点「清空」反而会：
    #     - 找不到按钮（返回 no-element）
    #     - 触发二次确认框，留下隐形遮罩
    #   所以默认跳过，只有真的残留了已选商品才清。
    if clear:
        cur_sel = selected_names(md.cdp, md.cid) if md.cid else []
        if cur_sel:
            log("  clear:", clear_selected(md))
            md.refresh()
        else:
            log("  clear: 已选区为空，跳过")

    before = set(selected_names(md.cdp, md.cid)) if md.cid else set()
    where = find_groups_for(md, items, gap=gap)
    log("  分组定位:", where)
    ok, bad = [], []
    by_group = {}
    for it in items:
        if it in before:
            ok.append(it)
            continue
        g = where.get(it)
        if not g:
            bad.append(it)
            continue
        by_group.setdefault(g, []).append(it)
    for g, its in by_group.items():
        md.refresh()
        switch_group(md, g)
        avail = set(list_names(md.cdp, md.cid)) if md.cid else set()
        for it in its:
            md.refresh()
            if it not in avail:
                bad.append(it)
                continue
            check_item(md, it)
            md.refresh()
            if md.cid and it in selected_names(md.cdp, md.cid):
                ok.append(it)
            else:
                bad.append(it)
    return ok, bad


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    mode = sys.argv[1]
    p = get_page()
    cdp = CDP(p["webSocketDebuggerUrl"])
    cdp.ensure_dom()

    if mode == "scan":
        c = modal_ctx(cdp)
        if not c:
            print("MODAL NOT OPEN")
            return
        m = scan_groups(cdp, c["id"])
        for k, v in m.items():
            print("[%s] -> %s" % (k, ", ".join(v)))
        print()
        print(json.dumps(m, ensure_ascii=False, indent=1))
        return

    if mode == "pick":
        group = sys.argv[2]
        names = sys.argv[3:]
        md = Modal(cdp)
        if md.cid is None:
            print("MODAL NOT OPEN")
            return
        print("switch:", switch_group(md, group))
        avail = list_names(md.cdp, md.cid)
        print("该分组商品:", avail)
        ok, bad = [], []
        for nm in names:
            md.refresh()
            if nm not in avail:
                print("  MISS(不在分组内) %s" % nm)
                bad.append(nm)
                continue
            r = check_item(md, nm)
            md.refresh()
            sel = selected_names(md.cdp, md.cid) if md.cid else []
            if nm in sel:
                ok.append(nm)
                print("  OK %s  ->%s" % (nm, r))
            else:
                bad.append(nm)
                print("  FAIL %s  (%s) 已选=%s" % (nm, r, sel))
        print("已选区:", selected_names(md.cdp, md.cid) if md.cid else [])
        print("OK=%d MISS=%d -> %s" % (len(ok), len(bad), bad))
        return

    if mode == "clear":
        md = Modal(cdp)
        if md.cid is None:
            print("MODAL NOT OPEN")
            return
        print(clear_selected(md))
        print("已选区:", selected_names(md.cdp, md.cid) if md.cid else [])
        return

    if mode == "selected":
        md = Modal(cdp)
        if md.cid is None:
            print("MODAL NOT OPEN")
            return
        print("已选区:", selected_names(md.cdp, md.cid))
        return

    print("unknown mode")


if __name__ == "__main__":
    main()
