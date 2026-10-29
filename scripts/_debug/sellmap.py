#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""定位「售卖信息」区各控件：份量 / 价格 / 打包费 / 单位。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx

JS = r"""(() => {
  // 找到含"售卖信息"标题的表单区块，向上找到最近的 form/容器
  const all = [...document.querySelectorAll('*')];
  const hdr = all.find(e => e.children.length===0 && (e.textContent||'').trim()==='售卖信息');
  if(!hdr) return 'no-header';
  let sec = hdr;
  for(let i=0;i<6 && sec.parentElement;i++){
    sec = sec.parentElement;
    if (sec.querySelectorAll('input').length >= 4) break;
  }
  const out = [];
  // 遍历区块内每个 .form-group / form-item
  const groups = sec.querySelectorAll('div[class*=form-group], div[class*=form-item], div[class*=formControl], div[class*=control]');
  groups.forEach((g,i)=>{
    const r=g.getBoundingClientRect();
    if(r.width<=0) return;
    const lbl=(g.querySelector('label,div[class*=label],span[class*=label]')||{}).innerText||'';
    const inp=g.querySelector('input,textarea');
    let v='', ph='', ro='';
    if(inp){ v=inp.value||''; ph=inp.placeholder||''; ro=inp.readOnly?'R':''; }
    out.push(JSON.stringify({i, lbl:lbl.trim().replace(/\s+/g,' ').slice(0,20), v:v.slice(0,20), ph:ph.slice(0,14), ro,
      cls:String(g.className).slice(0,46), y:Math.round(r.y), h:Math.round(r.height)}));
  });
  return out.join(' ;; ') || 'no-groups';
})()"""


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称",
                 probe="(()=>document.querySelector('input.groupName_RJkgVI')?'YES':'')()")
    if not c:
        print("no form ctx")
        return
    cid = c["id"]
    # 先滚到售卖信息
    cdp.evaluate("(()=>{const h=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&(e.textContent||'').trim()==='售卖信息'); if(h) h.scrollIntoView({block:'start'}); window.scrollBy(0,-120); return 1;})()", cid)
    time.sleep(1.0)
    print("GROUPS:")
    print(cdp.evaluate(JS, cid))


if __name__ == "__main__":
    main()
