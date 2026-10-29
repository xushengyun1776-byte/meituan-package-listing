# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
form=None
for x in cdp.contexts():
    if "套餐名称" in x["text"]: form=x; break
fid=form["id"]
print(cdp.evaluate(r'''(()=>{const o=[];
  const l=[...document.querySelectorAll('[class*=thumbnail]')];
  o.push('nodes='+l.length);
  for(const t of l){ const r=t.getBoundingClientRect();
    o.push('--- '+t.tagName+'.'+String(t.className).slice(0,44)+' rect='+Math.round(r.width)+'x'+Math.round(r.height)
      +' @'+Math.round(r.x)+','+Math.round(r.y)+' txt="'+String(t.innerText||'').replace(/\s+/g,' ').trim().slice(0,14)+'"');
    if(r.width>0) o.push('    html='+t.outerHTML.replace(/\s+/g,' ').slice(0,400));
  }
  return o.join('\n');})()''', fid))
