#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打印售卖信息区每个 form-group.row 的 outerHTML（截断），用于找准控件选择器。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx

JS = r"""(() => {
  const sec = document.querySelector('#packSellInfo');
  if(!sec) return 'no-section';
  const rows = [...sec.querySelectorAll('div.form-group.row')];
  return rows.map((g,i)=>{
     const lb=g.querySelector('label');
     const html=g.outerHTML.replace(/\s+/g,' ').slice(0,2200);
     return '### ROW '+i+' for='+(lb?lb.getAttribute('for'):'?')+' lbl='+(lb?(lb.innerText||'').trim():'')+'\n'+html;
  }).join('\n\n');
})()"""


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]
    print(cdp.evaluate(JS, cid))


if __name__ == "__main__":
    main()
