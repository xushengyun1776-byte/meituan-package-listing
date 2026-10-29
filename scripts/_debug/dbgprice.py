#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试价格输入框：逐步输入并观察 value / activeElement / React 受控行为。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, type_into

SEL_PRICE = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"price\"]');"
             "if(!lb) return null; return lb.closest('div.form-group').querySelector('input[placeholder=\"请输入价格\"]');})()")

JS_INFO = r"""(() => {
  const p = %s;
  if(!p) return 'NONE';
  const a = document.activeElement;
  return JSON.stringify({
    val: p.value, disabled: p.disabled, readOnly: p.readOnly,
    maxLength: p.maxLength, type: p.type,
    cls: String(p.className).slice(0,60),
    outer: p.outerHTML.slice(0,200),
    active: a ? (a.tagName + '|' + (a.className||'').toString().slice(0,30) + '|' + (a.value||'').slice(0,20)) : 'none'
  });
})()""" % SEL_PRICE


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]
    print("0:", cdp.evaluate(JS_INFO, cid))

    # 直接点一下，看 focus 落在哪
    pos = cdp.page_coords(cid, SEL_PRICE)
    print("coords:", pos)
    cdp.click_xy(pos[0], pos[1])
    time.sleep(0.6)
    print("1 after click:", cdp.evaluate(JS_INFO, cid))

    # 逐字 insertText
    for ch in "29.9":
        cdp.send("Input.insertText", text=ch)
        time.sleep(0.5)
        print("  typed %r ->" % ch, cdp.evaluate(JS_INFO, cid))

    print("2 after all:", cdp.evaluate(JS_INFO, cid))


if __name__ == "__main__":
    main()
