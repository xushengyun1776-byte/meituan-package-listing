#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""点击「一人食套餐」分组并列出其中的商品。"""
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el

SEL_GROUP = ("(()=>{const l=[...document.querySelectorAll('span[class*=name_],div[class*=tag-item]')]"
             ".filter(e=>(e.textContent||'').trim()==='一人食套餐');"
             "if(!l.length) return null; return l[l.length-1];})()")

JS_ROWS = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('div[class*=goodsItem],div[class*=item-content],tr,div[class*=card]')){
    const t=(e.textContent||'').trim().replace(/\s+/g,' ');
    if(t && t.length<260 && /￥|¥/.test(t)) o.push(t.slice(0,120));
  }
  return o.slice(0,25).join(' ||| ') || 'no-rows';
})()"""

JS_ALL = r"""(() => (document.body?document.body.innerText:'').replace(/\s+/g,' ').slice(300,2200))()"""


def main():
    cdp = cdp_connect()
    cid = 175
    # 保险起见重新找 list ctx
    for c in cdp.contexts():
        try:
            if cdp.evaluate("(()=>document.body&&document.body.innerText.includes('一人食套餐')?'YES':'')()", c["id"]) == "YES":
                cid = c["id"]; break
        except Exception:
            continue
    print("list ctx:", cid)
    print("click group:", click_el(cdp, cid, SEL_GROUP))
    time.sleep(3.0)
    print("ROWS:", cdp.evaluate(JS_ROWS, cid))
    print("---")
    print("PAGE:", cdp.evaluate(JS_ALL, cid))
    r = cdp.send("Page.captureScreenshot", format="png")
    with open("S_final.png", "wb") as f:
        f.write(base64.b64decode(r["result"]["data"]))
    print("saved S_final.png")


if __name__ == "__main__":
    main()
