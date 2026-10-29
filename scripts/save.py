#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""关闭份量下拉 -> 点击「保存并返回」 -> 截图核验结果。"""
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el

SEL_TRIGGER = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"weightUnit\"]');"
               "if(!lb) return null; return lb.closest('div.form-group').querySelector('input[readonly]');})()")
SEL_SAVE = ("(()=>{const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存并返回');"
            "return b||null;})()")

JS_DD = r"""(() => { let n=0;
  for(const e of document.querySelectorAll('li')){
    const r=e.getBoundingClientRect();
    if(r.width<=0||r.height<=0) continue;
    if(/^\d+人份$/.test((e.textContent||'').trim())) n++;
  } return n; })()"""


def shot(cdp, name):
    r = cdp.send("Page.captureScreenshot", format="png")
    with open(name, "wb") as f:
        f.write(base64.b64decode(r["result"]["data"]))
    print("saved", name)


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]

    # 1) 再次点击触发器，toggle 关闭下拉
    print("dropdown before:", cdp.evaluate(JS_DD, cid))
    print("toggle:", click_el(cdp, cid, SEL_TRIGGER))
    time.sleep(1.2)
    print("dropdown after toggle:", cdp.evaluate(JS_DD, cid))

    if int(cdp.evaluate(JS_DD, cid) or 0) > 0:
        # 再点一次 chevron
        chev = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"weightUnit\"]');"
                "if(!lb) return null; const g=lb.closest('div.form-group');"
                "const i=g.querySelector('i.roo-icon-chevron-down'); return i||null;})()")
        print("chevron:", click_el(cdp, cid, chev))
        time.sleep(1.2)
        print("dropdown after chevron:", cdp.evaluate(JS_DD, cid))

    shot(cdp, "S_before_save.png")

    # 2) 点击保存并返回
    pos = cdp.page_coords(cid, SEL_SAVE)
    print("save button page coords:", pos)
    if pos:
        cdp.click_xy(pos[0], pos[1])
        time.sleep(3.0)
    shot(cdp, "S_after_save.png")
    print("ctx text now:", cdp.evaluate("document.body?document.body.innerText.slice(0,300):''", cid))


if __name__ == "__main__":
    main()
