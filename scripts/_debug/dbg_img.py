# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
cdp = cdp_connect(); cdp.wake()
form=None
for x in cdp.contexts():
    if "套餐名称" in x["text"]: form=x; break
if form is None: print("NO FORM"); raise SystemExit
fid=form["id"]
print(cdp.evaluate(r'''(()=>{const o=[];
  const l=[...document.querySelectorAll('div[class*=thumbnailItem],div[class*=thumbnail-item]')];
  o.push('thumb count='+l.length);
  for(const t of l){ const r=t.getBoundingClientRect();
    o.push(' cls='+String(t.className).slice(0,40)+' rect='+Math.round(r.width)+'x'+Math.round(r.height)
      +' @'+Math.round(r.x)+','+Math.round(r.y)+' txt="'+String(t.innerText||'').replace(/\s+/g,' ').trim().slice(0,16)+'"'
      +' html='+t.outerHTML.replace(/\s+/g,' ').slice(0,220));
  }
  return o.join('\n');})()''', fid))
print("\n=== 弹窗当前 tab ===")
print(cdp.evaluate(r'''(()=>{const t=[...document.querySelectorAll('[class*=tab],[class*=Tab]')].filter(e=>e.children.length===0&&(e.innerText||'').trim());
  return t.map(e=>e.innerText.trim()+'@'+Math.round(e.getBoundingClientRect().x)+','+Math.round(e.getBoundingClientRect().y)).join(' | ')||'NO TABS';})()''', fid))
print("\n=== file inputs ===")
print(cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('input[type=file]')];
  return l.map((e,i)=>i+' cls='+String(e.className).slice(0,40)+' disp='+getComputedStyle(e).display+' files='+e.files.length).join('\n')||'NONE';})()''', fid))
