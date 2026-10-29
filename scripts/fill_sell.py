#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""填写售卖信息：份量 / 价格 / 打包费 / 单位。
数据来源：同目录上一层的 `上架数据模板.json` 的 sell 段（找不到则用内置默认值）。
用法: python fill_sell.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import (cdp_connect, find_ctx, click_el, type_into, dismiss_stuck_backdrops,
                  select_popup, wait_for_el)
import cfg

load_sell = cfg.get_sell


SEL_PORTION = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"weightUnit\"]');"
                "if(!lb) return null; const g=lb.closest('div.form-group'); if(!g) return null;"
                "return g.querySelector('input[readonly]')||g.querySelector('input[placeholder=\"请选择\"]');})()")
SEL_PRICE = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"price\"]');"
             "if(!lb) return null; return lb.closest('div.form-group').querySelector('input[placeholder=\"请输入价格\"]');})()")
SEL_BOX = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"stockAndBoxPriceSkus\"]');"
           "if(!lb) return null; const b=lb.closest('div.form-group').querySelector('div[class*=box-price-input]');"
           "if(!b) return null; return b.querySelector('input:not([readonly])');})()")
SEL_UNIT = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"stockAndBoxPriceSkus\"]');"
            "if(!lb) return null; const b=lb.closest('div.form-group').querySelector('div[class*=box-price-input]');"
            "if(!b) return null; return b.querySelector('div.dropdown input[readonly]');})()")

JS_VAL = ("(()=>{const p=%s; return p? (p.value||'') : 'NONE';})()")


def val(cdp, cid, sel):
    return cdp.evaluate(JS_VAL % sel, cid)


def main():
    sell, src = load_sell()
    if src:
        print("模板:", src)
    print("目标值:", json.dumps(sell, ensure_ascii=False))

    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    if not c:
        print("未找到表单 context")
        return
    cid = c["id"]
    ffid = c["frameId"]
    print("cleanup:", dismiss_stuck_backdrops(cdp, cid, timeout=2.0))
    # 表单分块异步渲染：售卖信息区可能还没出现，先等
    wait_for_el(cdp, cid, SEL_PORTION, timeout=20.0, label="售卖信息区")
    wait_for_el(cdp, cid, SEL_PRICE, timeout=20.0, label="价格输入框")
    print("BEFORE 份量=%r 价格=%r 打包费=%r 单位=%r" % (
        val(cdp, cid, SEL_PORTION), val(cdp, cid, SEL_PRICE),
        val(cdp, cid, SEL_BOX), val(cdp, cid, SEL_UNIT)))

    # ---- 1. 套餐份量 ----
    # 用 select_popup：它会**校验下拉框的值真的变成目标值**，
    # 避免「点了但选错同名项」的假成功（老逻辑曾把份量留在空值）。
    want = sell["portion"]
    if val(cdp, cid, SEL_PORTION) != want:
        print("select 份量:", select_popup(cdp, cid, ffid, SEL_PORTION, want))
    print("AFTER 份量 =", val(cdp, cid, SEL_PORTION))

    # ---- 2. 套餐价格（fx=0.08：中心被 addon-icon 遮住）----
    if val(cdp, cid, SEL_PRICE) != sell["price"]:
        print("type price:", type_into(cdp, cid, SEL_PRICE, sell["price"], fx=0.08))
    print("AFTER 价格 =", val(cdp, cid, SEL_PRICE))

    # ---- 3. 打包费 ----
    if val(cdp, cid, SEL_BOX) != sell["box_fee"]:
        print("type box fee:", type_into(cdp, cid, SEL_BOX, sell["box_fee"]))
    print("AFTER 打包费 =", val(cdp, cid, SEL_BOX))

    # ---- 4. 打包费单位 ----
    want_unit = sell.get("box_fee_unit")
    if want_unit and val(cdp, cid, SEL_UNIT) != want_unit:
        print("select 单位:", select_popup(cdp, cid, ffid, SEL_UNIT, want_unit))
    print("单位 =", val(cdp, cid, SEL_UNIT))


if __name__ == "__main__":
    main()
