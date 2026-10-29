#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到「商品管理 → 商品列表」页，并确保页面状态健康。

★ 关键经验：多次 navigate/history.back 之后，美团 SPA 会进入半死状态 ——
  表现是商品列表只渲染 1 条（实际 54 条）、「新建商品」下拉点了没反应。
  **硬刷新（Page.reload ignoreCache）可恢复**。所以这里带健康检查 + 自愈。

用法: nav_to_list.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el

URL = "https://waimaie.meituan.com/#/gw/static_resource/product#/listView"


def list_ctx(cdp):
    """返回承载商品列表的 context（含「新建商品」按钮）"""
    for c in cdp.contexts():
        if "商家首页" in c["text"]:
            continue
        try:
            if cdp.evaluate("(()=>document.body&&/新建商品/.test(document.body.innerText)?'YES':'')()", c["id"]) == "YES":
                return c
        except Exception:
            continue
    return None


def page_health(cdp, cid):
    """判断列表页是否真正加载完成。

    ★ 不要用「商品行数」判活：列表按分组筛选，当前分组可能只有 1 个商品，
    行数少是正常的（旧版健康检查因此误判成「渲染不全」而白白硬刷新）。
    可靠信号是分组导航上的「全部N」计数 —— 它来自后端总数，与筛选无关。
    """
    try:
        total = cdp.evaluate(
            "(()=>{const m=(document.body.innerText||'').match(/全部\\s*(\\d+)/);"
            "return m?m[1]:'';})()", cid)
    except Exception:
        total = ""
    try:
        has_btn = cdp.evaluate(
            "(()=>[...document.querySelectorAll('button')].some(e=>(e.innerText||'').trim()==='新建商品')?'Y':'')()",
            cid)
    except Exception:
        has_btn = ""
    if total and total != "0" and has_btn == "Y":
        return True, "全部%s" % total
    return False, ("全部%s btn=%s" % (total or "-", has_btn or "-"))


def biz_frame_ctx(cdp):
    """找业务 iframe（URL 含 /gw/static_resource/product）的 context。"""
    for c in cdp.contexts():
        try:
            u = cdp.evaluate("location.href", c["id"]) or ""
        except Exception:
            continue
        if "/gw/static_resource/product" in u:
            return c
    return None


def goto_list_route(cdp):
    """在业务 iframe 内把 hash 路由切回 #/listView（保留 query）。

    ★ 顶层 URL 一直是 https://waimaie.meituan.com/#/gw/static_resource/product#/listView，
      业务 iframe 才是真正带路由的那一层（.../gw/static_resource/product#/listView?region_id=...）。
      对顶层做 Page.navigate 因为 URL 没变 → 变成 same-document navigation → **页面不重载**，
      业务 iframe 还停在表单页。必须改业务 iframe 自己的 hash。
    """
    b = biz_frame_ctx(cdp)
    if not b:
        return False
    js = ("(()=>{ try{ const h=location.hash||'';"
          "const i=h.indexOf('?'); const q=i>=0? h.slice(i):'';"
          "const nh='#/listView'+q; if(h!==nh) location.hash=nh; return nh; }catch(e){ return 'err'; }})()")
    try:
        print("业务 iframe hash ->", cdp.evaluate(js, b["id"]))
    except Exception as e:
        print("  hash 切换失败:", str(e)[:80])
        return False
    time.sleep(5.0)
    return True


def top_url(cdp):
    try:
        return cdp.evaluate("location.href") or ""
    except Exception:
        return ""


PRODUCT_URL = "https://waimaie.meituan.com/#/gw/static_resource/product#/listView"


def goto_top_route(cdp):
    """把**顶层** hash 归位到商品模块路由（多策略）。

    ★ 坑 1：Page.navigate 到「含 # 的完整 URL」会被 Chrome 当成相对路径解析，
      顶层 URL 变成 https://waimaie.meituan.com/#https://... 这种鬼样子。
      正确姿势：location.replace(完整URL) —— fragment 里的第二个 # 会原样保留。
    ★ 坑 2：顶层可能被污染成「igate」工作台路由
      （https://waimaie.meituan.com/#https://waimaieapp.meituan.com/igate/wmactpc/my），
      这时 replace 后 SPA 要 10~15 秒才重建业务 iframe，8 秒不够。
    ★ 坑 3：replace 到一个**不同的顶层路由形态**时，SPA 会把它规范化成
      ?time=...&region_id=...#/new_fe/business#/index（商家首页），
      所以必须先「清干净」再 replace。
    """
    strategies = [
        ("replace(带query)", "(()=>{try{const u=new URL(location.href);"
                             "location.replace(u.origin+u.pathname+u.search+'#/gw/static_resource/product#/listView');"
                             "return 'SET';}catch(e){return 'err';}})()"),
    ]
    for name, js in strategies:
        try:
            r = cdp.evaluate(js)
        except Exception as e:
            print("  %s 失败: %s" % (name, str(e)[:60]))
            continue
        print("  %s -> %s" % (name, r))
        time.sleep(10.0)
        if list_ctx(cdp):
            print("  ✓ %s 成功" % name)
            return True
        print("  %s 未就绪（顶层被污染时 replace 常常无效，交给 UI 兜底）" % name)
    return False


def goto_by_ui(cdp):
    """UI 兜底：点顶部标签「商品管理」→ 再点「商品列表」。

    ★ 必须取**最靠上**的同名元素：左侧主导航里也有「商品管理」，
      点错会跳到 igate 工作台页面（实测顶层被带到
      https://waimaie.meituan.com/#https://waimaieapp.meituan.com/igate/wmactpc/my）。
    """
    top = None
    for c in cdp.contexts():
        if "商品管理" in c["text"] and "商家首页" in c["text"]:
            top = c
            break
    if not top:
        return False
    tid = top["id"]

    def by_text(t):
        return ("(()=>{const l=[...document.querySelectorAll('a,span,div,li')].filter(e=>{"
                "const s=(e.innerText||e.textContent||'').replace(/\\s+/g,'').trim();"
                "return s===%s&&e.children.length===0;});"
                "l.sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);"
                "return l.length?l[0]:null;})()" % json.dumps(t))

    print("UI 点「商品管理」:", click_el(cdp, tid, by_text("商品管理")))
    time.sleep(3.0)
    print("UI 点「商品列表」:", click_el(cdp, tid, by_text("商品列表")))
    time.sleep(8.0)
    return bool(list_ctx(cdp))


def main():
    cdp = cdp_connect()
    c = list_ctx(cdp)
    if c:
        ok, info = page_health(cdp, c["id"])
        print("已在商品列表页，ctx %s，健康=%s（%s）" % (c["id"], ok, info))
        if ok:
            return
        print("  页面状态异常，硬刷新")
        cdp.send("Page.reload", ignoreCache=True)
        time.sleep(10.0)
    else:
        # 不在列表页 —— 顶层模块不对就先归位
        u = top_url(cdp)
        if "static_resource/product" not in u:
            print("顶层不在商品模块（%s）" % u[:90])
            goto_top_route(cdp)
        # 再切业务 iframe 的 hash 路由
        if not goto_list_route(cdp):
            print("  业务 iframe 路由切换后仍未就绪 -> UI 点击兜底")
            goto_by_ui(cdp)
    c = list_ctx(cdp)
    if not c:
        print("  -> 硬刷新")
        cdp.send("Page.reload", ignoreCache=True)
        time.sleep(12.0)
        c = list_ctx(cdp)
    if not c:
        print("!! 仍找不到商品列表页")
        return
    ok, info = page_health(cdp, c["id"])
    print("list ctx %s，健康=%s（%s）" % (c["id"], ok, info))
    if not ok:
        print("!! 列表页未就绪，建议手动刷新一次再继续")


if __name__ == "__main__":
    main()
