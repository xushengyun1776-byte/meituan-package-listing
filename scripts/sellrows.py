#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""导出 #packSellInfo 区块 HTML + 核对套餐类型 radio 的真实 checked 状态。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx

JS = r"""(() => {
  const sec = document.querySelector('#packSellInfo');
  if(!sec) return 'no-section';
  const radios = [...document.querySelectorAll('input.roo-radio-input')].map(r=>
     JSON.stringify({v:r.value, checked:r.checked, lbl:(r.parentElement.innerText||'').trim().slice(0,14)}));
  const rows = [...sec.querySelectorAll('div.form-group.row')].map(g=>{
     const lb=g.querySelector('label');
     const inp=g.querySelector('input,textarea');
     const r=g.getBoundingClientRect();
     return JSON.stringify({
        for: lb? lb.getAttribute('for') : null,
        lbl: lb? (lb.innerText||'').trim().replace(/\s+/g,' ').slice(0,14):'',
        inp: inp? {tag:inp.tagName, type:inp.type, ph:inp.placeholder, ro:inp.readOnly, v:inp.value} : null,
        y: Math.round(r.y), x: Math.round(r.x), w: Math.round(r.width), h: Math.round(r.height)
     });
  });
  return 'RADIOS:: ' + radios.join(' ;; ') + ' ||ROWS|| ' + rows.join(' ;; ');
})()"""


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称",
                 probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]
    v = cdp.evaluate(JS, cid)
    if v and "||ROWS||" in v:
        rad, rows = v.split("||ROWS||", 1)
        print(rad.strip())
        print("=" * 60)
        for r in rows.split(" ;; "):
            print("  ", r)
    else:
        print(v)


if __name__ == "__main__":
    main()
