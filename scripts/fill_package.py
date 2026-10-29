#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""设置套餐名称 + 套餐类型 + 菜单分组。数据来自 `上架数据模板.json`。
用法: python fill_package.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import (cdp_connect, find_ctx, click_el, type_into, dismiss_stuck_backdrops,
                  select_popup, wait_for_el)
import cfg

# ★ 不要用带哈希的完整类名（correctNameTooltip_j9rW4a）—— 美团发版会改哈希，
#   改用 placeholder + 类名前缀双保险。
SEL_NAME = ("(()=>{const l=[...document.querySelectorAll('input')]"
            ".filter(e=>((e.placeholder||'').indexOf('30字')>=0 || String(e.className).indexOf('correctNameTooltip')>=0));"
            "return l.length?l[0]:null;})()")
SEL_TYPE_RADIO = ("(()=>{const l=[...document.querySelectorAll('span.custom-radio-label')]"
                  ".filter(e=>(e.textContent||'').replace(/\\s+/g,'').trim()===%s);return l.length?l[l.length-1]:null;})()")
SEL_MENU = ("(()=>{const l=[...document.querySelectorAll('input[placeholder=\"请选择\"]')].filter(e=>{"
            "const p=e.closest('div.form-group'); const lab=p&&p.querySelector('label');"
            "return lab && (lab.innerText||'').replace(/\\s+/g,'').trim()==='菜单分组';});"
            "return l.length?l[l.length-1]:null;})()")

# 套餐类型是否真的生效：分组可选套餐才会出现「组名 + N选 + 选N」这套规格组 UI
JS_GROUP_UI = ("(()=>{const n=document.querySelectorAll('input.groupName_RJkgVI').length;"
               "const s=document.querySelectorAll('div[class*=skuSum]').length;"
               "return 'groups='+n+' skuSum='+s;})()")


load_pkg = cfg.get_package


def radio_state(cdp, cid):
    return cdp.evaluate(
        "(()=>JSON.stringify([...document.querySelectorAll('input.roo-radio-input')].map(r=>"
        "({v:r.value,checked:r.checked,t:(r.parentElement.innerText||'').trim().slice(0,12)}))))()", cid)


def main():
    pkg, src = load_pkg()
    if src:
        print("模板:", src)
    print("目标:", json.dumps(pkg, ensure_ascii=False)[:200])

    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('input.groupName_RJkgVI')?'YES':'')()")
    if not c:
        print("未找到表单 context")
        return
    cid = c["id"]
    ffid = c["frameId"]
    print("cleanup:", dismiss_stuck_backdrops(cdp, cid, timeout=2.0))

    # ---- 1. 套餐名称 ----
    cur = cdp.evaluate("(()=>{const e=%s; return e?e.value:'';})()" % SEL_NAME, cid)
    if cur != pkg["name"]:
        print("name:", type_into(cdp, cid, SEL_NAME, pkg["name"], fx=0.2))
    print("名称 =", cdp.evaluate("(()=>{const e=%s; return e?e.value:'';})()" % SEL_NAME, cid))

    # ---- 2. 套餐类型 radio ----
    # ★ roo 的 radio 是自绘控件：input.roo-radio-input 的 checked 属性不可信
    #   （组件自己管选中态，DOM property 也可能不同步）。
    #   可靠判据是「分组可选套餐」独有的规格组 UI 是否出现。
    print("radio before:", radio_state(cdp, cid), "|", cdp.evaluate(JS_GROUP_UI, cid))
    want_type = pkg["type"]
    expr = SEL_TYPE_RADIO % json.dumps(want_type)
    # ★ radio 用 JS 合成事件点击（实测：CDP 坐标点击在表单里可能完全失效，
    #   而合成事件 100% 可靠 —— 合成事件不走 hit-test，直接派发到目标元素）
    from form import click_menu_item
    print("click 类型[%s]:" % want_type, click_menu_item(cdp, cid, expr))
    time.sleep(1.5)
    print("radio after :", radio_state(cdp, cid), "|", cdp.evaluate(JS_GROUP_UI, cid))

    # ---- 3. 菜单分组下拉 ----
    # ★ 表单是分块异步渲染的：刚打开时「菜单分组」那一块可能还没渲染出来，
    #   直接 select 会返回 FAILED（当前值=''）。先等它出现。
    wait_for_el(cdp, cid, SEL_MENU, timeout=20.0, label="菜单分组下拉")
    cur_mg = cdp.evaluate("(()=>{const e=%s; return e?e.value:'';})()" % SEL_MENU, cid)
    if cur_mg != pkg["menu_group"]:
        print("menu group:", select_popup(cdp, cid, ffid, SEL_MENU, pkg["menu_group"]))
        time.sleep(1.0)
    print("菜单分组 =", cdp.evaluate("(()=>{const e=%s; return e?e.value:'';})()" % SEL_MENU, cid))


if __name__ == "__main__":
    main()
