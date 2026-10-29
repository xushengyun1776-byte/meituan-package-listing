#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打开「套餐份量」下拉并列出所有选项。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el

TRIGGER = "document.querySelector('#weightUnit')"
JS_LIST = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('li')){
    const r=e.getBoundingClientRect();
    if(r.width<=0||r.height<=0) continue;
    const cx=r.x+r.width/2, cy=r.y+r.height/2;
    const hit=document.elementFromPoint(cx,cy);
    o.push(JSON.stringify({t:e.textContent.trim().slice(0,20), x:Math.round(cx), y:Math.round(cy),
                           hit: hit? (hit.tagName+'|'+(hit.textContent||'').trim().slice(0,12)) : 'null',
                           cls:String(e.className).slice(0,40)}));
  }
  return o.join(' ;; ') || 'no-li';
})()"""


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#weightUnit')?'YES':'')()")
    cid = c["id"]
    print("open:", click_el(cdp, cid, TRIGGER))
    time.sleep(1.5)
    print("OPTIONS:", cdp.evaluate(JS_LIST, cid))


if __name__ == "__main__":
    main()
