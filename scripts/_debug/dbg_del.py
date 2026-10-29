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
  const lis=[...document.querySelectorAll('ul[class*=thumbnailList] > li')];
  o.push('li count='+lis.length);
  for(const li of lis){ const r=li.getBoundingClientRect();
    const extra=li.querySelector('div[class*=thumbnailExtra]');
    o.push('--- li @'+Math.round(r.x)+','+Math.round(r.y)+' '+Math.round(r.width)+'x'+Math.round(r.height));
    if(extra){ for(const c of extra.children){ const cr=c.getBoundingClientRect(); const cs=getComputedStyle(c);
      o.push('    child '+c.tagName+'.'+String(c.className).slice(0,30)+' src='+String(c.src||'').slice(0,30)
        +' rect='+Math.round(cr.width)+'x'+Math.round(cr.height)+' @'+Math.round(cr.x)+','+Math.round(cr.y)
        +' disp='+cs.display+' op='+cs.opacity+' vis='+cs.visibility+' pe='+cs.pointerEvents); } }
  }
  return o.join('\n');})()''', fid))
