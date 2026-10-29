#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打开「套餐份量」下拉并列出选项。用法: portion2.py [选项文本]"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el

SEL = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"weightUnit\"]');"
       "if(!lb) return null; return lb.closest('div.form-group').querySelector('input[readonly]');})()")

JS_LIST = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('li,ul[class*=dropdown] *,div[class*=dropdown-menu] *')){
    const r=e.getBoundingClientRect();
    if(r.width<=0||r.height<=0) continue;
    const t=(e.textContent||'').trim();
    if(!t || t.length>16) continue;
    const cx=r.x+r.width/2, cy=r.y+r.height/2;
    const hit=document.elementFromPoint(cx,cy);
    o.push(JSON.stringify({t, x:Math.round(cx), y:Math.round(cy),
        hit: hit? (hit.tagName+'|'+(hit.textContent||'').trim().slice(0,12)) : 'null',
        cls:String(e.className).slice(0,36), tag:e.tagName}));
  }
  return o.join(' ;; ') || 'no-options';
})()"""


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]
    print("open:", click_el(cdp, cid, SEL))
    time.sleep(1.5)
    print("OPTIONS:", cdp.evaluate(JS_LIST, cid))


if __name__ == "__main__":
    main()
