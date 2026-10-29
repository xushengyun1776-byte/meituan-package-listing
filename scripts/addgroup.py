#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在「新建套餐」表单中新增/填充规格组。
用法:
  python addgroup.py add "<组名>" "<可选商品|固定商品>" <选N|-> "<商品名1>" ...
  python addgroup.py fill <idx> "<组名>" "<商品名1>" ...  # 填充已有第 idx 组(0起)
  python addgroup.py type <idx> "<可选商品|固定商品>"   # 切换第 idx 组的组类型
  python addgroup.py pickn <idx> <N>                    # 设置第 idx 组的「选N」
  python addgroup.py show                               # 列出所有组的状态
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import (cdp_connect, type_into, click_button, click_el, click_menu_item,
                  find_ctx, select_popup, dismiss_stuck_backdrops, purge_modals)
from pick import modal_ctx, pick_auto, confirm_modal as pick_confirm, selected_names

GN = "input.groupName_RJkgVI"

# ★ 组容器不要用 `div.groupWrap_EMuN4h` 这种带哈希的类名 —— 美团前端每次发版
#   CSS Module 哈希都会变，类名一失效就读不到任何组（表现为「组都建好了但核对是空」）。
#   改为：从 `input.groupName_RJkgVI` 向上找包含 skuSum/skuCount 的祖先作为组容器，
#   并用 [class*=xxx] 前缀匹配（哈希在末尾，前缀稳定）。
JS_GROUP_STATE = r"""(() => {
  const gs=[...document.querySelectorAll('input.groupName_RJkgVI')];
  if(!gs.length) return '[]';
  const Y=e=>e.getBoundingClientRect().top + (window.scrollY||0);
  const rows=[...document.querySelectorAll('div[class*=rowWrap], tr')].map(r=>{
    const rr=r.getBoundingClientRect();
    return {t:(r.innerText||r.textContent||'').trim().split('\n')[0].trim(), top:rr.top+(window.scrollY||0)};
  }).filter(r=>r.t && r.t.indexOf('商品名称')!==0);
  const sums=[...document.querySelectorAll('div[class*=skuSum]')].map(e=>({t:e.innerText.trim(), top:Y(e)}));
  const cnts=[...document.querySelectorAll('div[class*=skuCount] input')].map(e=>({v:e.value, top:Y(e)}));
  const tys=[...document.querySelectorAll('input[readonly]')]
    .filter(e=>['可选商品','固定商品'].indexOf((e.value||'').trim())>=0)
    .map(e=>({v:e.value.trim(), top:Y(e)}));
  /* ★ 组类型必须从 **React fiber** 读，不能读 input.value：
       roo 的 readonly input 显示滞后 —— 明明已经把 groupType 改成 0（固定商品），
       input.value 仍然显示「可选商品」，导致「设置组类型」被误判为失败。
       fiber 里的 props 才是真值：{groupName, groupType, skuCount, maxSelectCount}
       groupType: 0=固定商品, 1=可选商品 */
  const ftypes=[];
  for(const el of document.querySelectorAll('div[class*=group-header], div[class*=group-wrap-item]')){
    const k=Object.keys(el).find(x=>x.startsWith('__reactFiber'));
    if(!k) continue;
    let f=el[k], d=0;
    while(f && d<12){
      const p=f.memoizedProps||{};
      if(p && p.groupName!==undefined && p.groupType!==undefined){
        ftypes.push({name:p.groupName, gtype:p.groupType, skuCount:p.skuCount}); break;
      }
      f=f.return; d++;
    }
  }
  return JSON.stringify(gs.map((nm,i)=>{
    const my=Y(nm);
    const nextTop = (i+1<gs.length) ? Y(gs[i+1]) : Infinity;
    const inRange = o => o.top>=my-6 && o.top<nextTop;
    const sm=sums.find(inRange);
    const pn=cnts.find(inRange);
    const ty=tys.find(inRange);
    const ft=ftypes.find(x=>x.name===nm.value);
    return {i, name:nm.value, type:ty?ty.v:null,
            gtype: ft ? (ft.gtype===0?'固定商品':'可选商品') : null,
            skuCount: ft ? ft.skuCount : null,
            sum:sm?sm.t:null, pickN:pn?pn.v:null,
            items:rows.filter(inRange).map(r=>r.t)};
  }));
})()"""


def group_names(cdp, fid):
    return json.loads(cdp.evaluate(
        "(()=>JSON.stringify([...document.querySelectorAll('%s')].map(e=>e.value)))()" % GN, fid) or "[]")


def group_state(cdp, fid):
    """返回每个组的 {name, type, sum, pickN, items[]}"""
    try:
        return json.loads(cdp.evaluate(JS_GROUP_STATE, fid) or "[]")
    except Exception:
        return []


def resolve_idx(cdp, fid, key):
    """按组名或索引定位组序号。优先按组名（更稳）。"""
    st = group_state(cdp, fid)
    for g in st:
        if g["name"] == key:
            return g["i"]
    try:
        i = int(key)
        if 0 <= i < len(st):
            return i
    except ValueError:
        pass
    return None


def empty_group_idx(cdp, fid):
    """找出第一个「组名为空」的空组序号（表单自带 1~2 个），没有返回 None。"""
    for g in group_state(cdp, fid):
        if not (g["name"] or "").strip():
            return g["i"]
    return None


def _group_box_js(idx):
    """返回「从第 idx 个 groupName input 找到组容器」的 JS 片段。

    定位法：向上找**只包含这一个 groupName input、且含 button 的祖先**。
    ★ 不能靠 skuSum / skuCount / groupType —— 空组还没有商品，
      这几个节点都不存在，用它们定位会返回 null（表现为「+添加商品」点不到、
      「选N」框找不到）。
    ★ 也不能靠 groupType 的类名 —— 美团那部分是 roo-input，没有 groupType 字样。
    """
    return ("const gs=[...document.querySelectorAll('input.groupName_RJkgVI')]; const g=gs[%d];"
            "if(!g) return null; let p=g,box=null;"
            "for(let k=0;k<10&&p;k++){ p=p.parentElement; if(!p) break;"
            "const n=p.querySelectorAll('input.groupName_RJkgVI').length;"
            "if(n===1 && p.querySelector('button')){ box=p; break; } }" % idx)


def grp_type_expr(idx):
    """第 idx 组的「组类型」下拉触发器"""
    return ("(()=>{ %s return box? box.querySelector('div[class*=groupType] input[readonly]'): null; })()"
            % _group_box_js(idx))


def grp_pickn_expr(idx):
    """第 idx 组的「选N」输入框"""
    return ("(()=>{ %s return box? box.querySelector('div[class*=skuCount] input'): null; })()"
            % _group_box_js(idx))


def grp_name_expr(idx):
    return "document.querySelectorAll('%s')[%d]" % (GN, idx)


def grp_additem_expr(idx):
    """第 idx 组里的「+添加商品」按钮（按组容器定位，避免按钮索引漂移）"""
    return ("(()=>{ %s if(!box) return null;"
            "for(const b of box.querySelectorAll('button')){"
            "const t=(b.innerText||b.textContent||'').replace(/\\s+/g,'').trim();"
            "if(t==='+添加商品'||t==='添加商品') return b; } return null; })()"
            % _group_box_js(idx))


def show(cdp, fid):
    for g in group_state(cdp, fid):
        # 组类型以 React fiber 为准（input.value 显示滞后）
        t = g.get("gtype") or g.get("type")
        print("  [%d] 名称=%r 类型=%r %r 选N=%s 商品=%s" % (
            g["i"], g["name"], t, g["sum"], g["pickN"], g["items"]))


def pick_items(cdp, items):
    """在「选择商品」弹窗里勾选本组商品。

    ★ 走**分组树导航**，不用搜索框：
      弹窗左侧是菜单分组树，右侧只列当前分组的商品；
      而搜索框在弹窗里怎么输入都不触发检索（onChange/onKeyDown 都挂着，
      服务端检索就是不动）—— 实测三种输入方式（insertText / 真实按键 /
      逐字符 keydown）全部无效。直接点左侧分组 100% 可靠。
    """
    ok, bad = pick_auto(cdp, items)
    print(f"  picked {len(ok)}/{len(items)} miss={bad}")
    return ok, bad


def confirm_modal(cdp):
    """点商品选择弹窗的「确定」，并清理残留遮罩。"""
    c = modal_ctx(cdp)
    if not c:
        print("  confirm: no modal")
        return
    print("  confirm:", pick_confirm(cdp, c["id"]))
    time.sleep(1.5)
    # ★ 弹窗关闭后残留的 backdrop 会盖住表单，让**下一组的坐标点击全部失效**
    #   （表现为「+添加商品」点不到）。必须清掉。
    print("  cleanup:", purge_modals(cdp, c["id"]))


def form_ctx(cdp):
    return find_ctx(cdp, "套餐名称",
                    probe="(()=>document.querySelector('%s')?'YES':'')()" % GN)


def main():
    mode = sys.argv[1]
    cdp = cdp_connect()
    form = form_ctx(cdp)
    if not form:
        print("  [ERR] 未找到新建套餐表单 context（是否还在列表页？）")
        return
    fid = form["id"]
    ffid = form["frameId"]
    # ★ 清掉可能残留的弹窗遮罩（商品选择弹窗是独立 iframe，遮罩在别的 context，
    #   不清会让本组所有点击失效）
    print("  cleanup:", dismiss_stuck_backdrops(cdp, fid, timeout=2.0))

    if mode == "show":
        show(cdp, fid)
        return

    if mode == "type":
        idx = resolve_idx(cdp, fid, sys.argv[2])
        gtype = sys.argv[3]
        if idx is None:
            print("  未找到组:", sys.argv[2]); return
        print("  group-type:", select_popup(cdp, fid, ffid, grp_type_expr(idx), gtype))
        time.sleep(1.0)
        show(cdp, fid)
        return

    if mode == "pickn":
        idx = resolve_idx(cdp, fid, sys.argv[2])
        n = sys.argv[3]
        if idx is None:
            print("  未找到组:", sys.argv[2]); return
        print("  pickN:", type_into(cdp, fid, grp_pickn_expr(idx), n))
        time.sleep(0.8)
        show(cdp, fid)
        return

    if mode == "add":
        # 用法: add "<组名>" "<可选商品|固定商品>" <选N|-> "<商品名>" ...
        gname = sys.argv[2]
        gtype = sys.argv[3]
        pickn = sys.argv[4]
        items = sys.argv[5:]

        # 1) 找/建组
        # 优先复用表单自带的空组，避免留下空壳组、并保证「+添加商品」按钮索引对得上
        idx = empty_group_idx(cdp, fid)
        if idx is None:
            before = len(group_names(cdp, fid))
            print("  add-btn:", click_button(cdp, fid, "添加商品分组"))
            time.sleep(2.5)
            idx = before
            form = form_ctx(cdp)
            fid = form["id"]
            ffid = form["frameId"]
        else:
            print("  reuse empty group at idx", idx)

        # 2) 填组名
        print("  name:", type_into(cdp, fid, grp_name_expr(idx), gname))
        time.sleep(0.6)

        # 3) 设组类型（必须在加商品之前 —— 固定商品/可选商品的 UI 不同）
        #    默认就是「可选商品」，值已经对时**不要去点下拉**：
        #    select_popup 会开下拉、点选项、再回读校验，
        #    而下拉里同名项多，容易点到错的那一项把值改坏。
        if gtype and gtype != "-":
            try:
                cur = (cdp.evaluate("(()=>{const e=%s; return e?String(e.value||''):'';})()"
                                    % grp_type_expr(idx), fid) or "").strip()
            except Exception:
                cur = ""
            if cur == gtype:
                print("  group-type: 已是 %s，跳过" % gtype)
            else:
                print("  group-type:", select_popup(cdp, fid, ffid, grp_type_expr(idx), gtype))
            time.sleep(1.0)

        # 4) 打开该组的商品选择器（按组容器定位按钮，不依赖全局按钮顺序）
        #    ★ 用 JS 合成事件（mode="auto"）：js_click 会自动点按钮内部的
        #      span 子元素，直接在 <button> 上派发事件不会触发 React 的 onClick。
        #    ★ 坐标点击在这个表单 iframe 里会静默失效（命中正确但无响应），
        #      所以这里只走 JS 路径；verify 负责确认弹窗真的开了。
        add_expr = grp_additem_expr(idx)

        def _picker_opened(timeout=5.0):
            # 弹窗 iframe 要加载 + 渲染，verify 必须轮询等待，
            # 立刻判定会把「点中了但还没渲染出来」误判成失败。
            t0 = time.time()
            while time.time() - t0 < timeout:
                if modal_ctx(cdp, tries=1) is not None:
                    return True
                time.sleep(0.6)
            return False

        print("  open-picker:", click_el(cdp, fid, add_expr, mode="js", verify=_picker_opened))
        time.sleep(2.0)

        # 5) 选商品 + 确定
        pick_items(cdp, items)
        confirm_modal(cdp)

        form = form_ctx(cdp)
        fid = form["id"]
        ffid = form["frameId"]

        # 6) 设「选N」（必须在选完商品之后 —— N 不能大于商品数）
        if pickn and pickn != "-":
            print("  pickN:", type_into(cdp, fid, grp_pickn_expr(idx), pickn))
            time.sleep(0.8)

        print("  groups:", group_names(cdp, fid))
        show(cdp, fid)
        return

    # fill <idx> "<组名>" "<商品名>" ...：在已有第 idx 组里补商品
    idx = int(sys.argv[2])
    gname = sys.argv[3]
    items = sys.argv[4:]

    # 打开该组的商品选择器（按组容器定位按钮，不依赖全局按钮顺序）
    add_expr = grp_additem_expr(idx)
    print("  open-picker:", click_el(cdp, fid, add_expr))
    time.sleep(2.5)

    pick_items(cdp, items)
    confirm_modal(cdp)

    form = form_ctx(cdp)
    fid = form["id"]
    print("  name:", type_into(cdp, fid, grp_name_expr(idx), gname))
    time.sleep(0.8)
    print("  groups:", group_names(cdp, fid))
    show(cdp, fid)


if __name__ == "__main__":
    main()
