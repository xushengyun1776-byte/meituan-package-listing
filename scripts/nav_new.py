#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导航到「新建商品」下拉并点第 4 项「新建套餐」。

要点：
- 下拉是异步弹出的，点击后必须**轮询等待**「新建套餐」出现，不能 sleep 固定时长就开干。
- 点选项时不能用 scroll=True —— click_el 内部的 scrollIntoView 会把弹层关掉。
用法: nav_new.py [--open]   --open 只展开下拉不点击
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el, click_button

SEL_NEW_BTN = ("(()=>{const l=[...document.querySelectorAll('button')]"
               ".filter(e=>(e.innerText||'').trim()==='新建商品');"
               "if(!l.length) return null; return l[0];})()")
# 注意：必须返回字符串/布尔，不能返回 DOM 元素
# —— cdp.evaluate 用 returnByValue=True，元素结果序列化不出来，永远判空
SEL_NEW_ITEM = ("(()=>{const l=[...document.querySelectorAll('div[class*=create-button-text]')]"
                ".filter(e=>(e.textContent||'').trim()==='新建套餐');"
                "return l.length? 'FOUND' : '';})()")
# 取元素本身（给 page_coords 用），必须与上面的检测式分开
SEL_NEW_ITEM_EL = ("(()=>{const l=[...document.querySelectorAll('div[class*=create-button-text]')]"
                    ".filter(e=>(e.textContent||'').trim()==='新建套餐');"
                    "return l.length? l[l.length-1]: null;})()")

JS_DD = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('li,div,span,a')){
    const t=(e.textContent||'').trim();
    if(!t||t.length>14) continue;
    const r=e.getBoundingClientRect();
    if(r.width<=0||r.height<=0) continue;
    o.push(JSON.stringify({t, x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
       cls:String(e.className).slice(0,34)}));
  }
  return o.join(' ;; ') || 'none';
})()"""


def list_ctx(cdp):
    for x in cdp.contexts():
        if "商家首页" in x["text"]:
            continue
        try:
            if cdp.evaluate("(()=>document.body&&/新建商品/.test(document.body.innerText)?'YES':'')()", x["id"]) == "YES":
                return x
        except Exception:
            continue
    return None


def main():
    cdp = cdp_connect()
    c = list_ctx(cdp)
    if not c:
        print("no list ctx")
        for x in cdp.contexts():
            print("  ctx", x["id"], repr(x["text"][:60]))
        return
    cid = c["id"]

    # 表单已经开着就直接返回，避免重复点击触发器（表单页没有「新建商品」按钮）
    if any("套餐名称" in x["text"] for x in cdp.contexts()):
        print("表单已打开，跳过")
        for x in cdp.contexts():
            if "套餐名称" in x["text"]:
                print("FORM CTX:", x["id"], x["frameId"][:12])
        return

    if "--open" in sys.argv:
        print("click 新建商品:", click_el(cdp, cid, SEL_NEW_BTN))
        time.sleep(1.8)
        print("DROPDOWN:", cdp.evaluate(JS_DD, cid))
        return

    # 点触发器，并轮询等待下拉项出现
    # ★ roo 下拉触发器**只认 trusted 事件**（Input.dispatchMouseEvent）——
    #   JS 合成事件（click / mousedown+up / 完整序列）全部无效，实测过；
    #   而「新建套餐」菜单项是普通 DOM，合成事件反而 100% 命中。
    #   所以这里：坐标点击 + 多口径候选 + 点后验证。
    def dd_open():
        try:
            return cdp.evaluate(SEL_NEW_ITEM, cid) == "FOUND"
        except Exception:
            return False

    def dd_open_wait():
        for _ in range(6):
            if dd_open():
                return True
            time.sleep(0.4)
        return False

    item = None
    attempt = 0
    while attempt < 6:
        # 注意：页面上有两个 text==="新建商品" 的元素（x 差 8px），
        # 点内层那个不会弹出下拉；click_button 取的是外层，实测可弹出。
        # 「新建商品」是 roo Dropdown trigger —— 实测合成事件点不开它，
        # 必须用 trusted 的 CDP 坐标点击
        print("click 新建商品:", click_el(cdp, cid, SEL_NEW_BTN, scroll=False,
                                          verify=dd_open_wait, mode="xy"))
        if dd_open():
            item = SEL_NEW_ITEM
            break
        attempt += 1
        print("  dropdown not open, retry", attempt)
        if attempt == 2:
            # ★ 关键恢复手段：多次 navigate/back 之后 SPA 会进入半死状态
            #   （列表只渲染 1 条、下拉点了没反应），硬刷新可恢复
            print("  -> hard reload page")
            cdp.send("Page.reload", ignoreCache=True)
            time.sleep(10.0)
            c = list_ctx(cdp)
            if not c:
                print("  !! reload 后仍找不到列表页")
                return
            cid = c["id"]
            continue
        time.sleep(1.0)

    if not item:
        print("!! 下拉始终未打开")
        print("DROPDOWN:", cdp.evaluate(JS_DD, cid))
        return

    # 点击菜单项：JS 合成事件优先（免坐标，实测 100% 命中），失败再退到多口径坐标
    form_open = lambda: any("套餐名称" in x["text"] for x in cdp.contexts())
    if form_open():
        print("表单已打开")
    else:
        from form import click_menu_item
        r = click_menu_item(cdp, cid, SEL_NEW_ITEM_EL, verify=form_open, wait=2.5)
        print("click 新建套餐 ->", r)
        if not form_open():
            print("!! 菜单项没点中")
            return

    time.sleep(2.0)
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            print("FORM CTX:", x["id"], x["frameId"][:12])
            # 等表单渲染完成：套餐名称 input + 套餐类型 radio 就位
            js = ("(()=>{const n=document.querySelectorAll('input[placeholder*=\"30字\"]').length;"
                  "const r=document.querySelectorAll('input.roo-radio-input').length;"
                  "return 'name='+n+' radio='+r;})()")
            for i in range(20):
                try:
                    s = cdp.evaluate(js, x["id"])
                except Exception:
                    s = ""
                if "name=1" in s and "radio=2" in s:
                    print("  表单就绪:", s)
                    # ★ 清掉上一次遗留的弹窗（含打开中的）——
                    #   它们的 backdrop 会盖在表单上，让**所有坐标点击失效**
                    #   （radio 点不动、下拉打不开），而 JS 合成事件却一切正常。
                    from form import dismiss_stuck_backdrops
                    print("  cleanup:", dismiss_stuck_backdrops(cdp, x["id"], timeout=2.0,
                                                                close_open=True))
                    break
                time.sleep(0.8)
            return
    print("no form ctx yet; ctxs:", [(x["id"], x["text"][:40]) for x in cdp.contexts()])


if __name__ == "__main__":
    main()
