# -*- coding: utf-8 -*-
"""验证 scrollIntoView 之后坐标与命中是否一致。"""
import sys, time
sys.path.insert(0, '.')
from form import cdp_connect
from addgroup import grp_additem_expr

JS = r'''(()=>{const e=%s; if(!e) return "NULL";
 const rr=e.getBoundingClientRect();
 const cx=Math.round(rr.x+rr.width/2), cy=Math.round(rr.y+rr.height/2);
 const hit=document.elementFromPoint(cx,cy);
 return JSON.stringify({rect:[Math.round(rr.x),Math.round(rr.y),Math.round(rr.width),Math.round(rr.height)],
   cx:cx, cy:cy,
   hit: hit ? (hit.tagName+'.'+String(hit.className).slice(0,26)+'::'+(hit.innerText||'').replace(/\s+/g,' ').trim().slice(0,12)) : 'NULL',
   scrollTop: document.scrollingElement.scrollTop});})()'''

SCROLL = r'''(function(){try{const e=%s; e.scrollIntoView({block:"center",inline:"center"});}catch(e){}})()'''

cdp = cdp_connect()
cid = None
for x in cdp.contexts():
    if '套餐名称' in x['text']:
        cid = x['id']
        break
print('form ctx', cid)
expr = grp_additem_expr(0)
print('scrollTop before:', cdp.evaluate('document.scrollingElement.scrollTop', cid))
cdp.evaluate(SCROLL % expr, cid)
for t in (0.2, 0.6, 0.6, 1.0, 1.0):
    time.sleep(t)
    print('->', cdp.evaluate(JS % expr, cid))
