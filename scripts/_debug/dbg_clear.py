# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, purge_modals
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
ctxs=cdp.contexts()
form=[x for x in ctxs if "套餐名称" in x["text"]][0]
fid=form["id"]; ffid=form["frameId"]
print("purge:", purge_modals(cdp, fid))
time.sleep(0.5)
offs=cdp.offsets(); print("offsets:", offs, "form ffid:", ffid)
JS_FIRST="""(()=>{const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')].filter(t=>!String(t.className).includes('upload'));
  if(!li.length) return ''; const r=li[0].getBoundingClientRect();
  return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,w:Math.round(r.width),h:Math.round(r.height)});})()"""
JS_CLOSE="""(()=>{const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')].filter(t=>!String(t.className).includes('upload'));
  if(!li.length) return ''; const c=li[0].querySelector('img[class*=closeIcon]'); if(!c) return '';
  const r=c.getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,w:Math.round(r.width),h:Math.round(r.height)});})()"""
print("li:", cdp.evaluate(JS_FIRST, fid))
d=json.loads(cdp.evaluate(JS_FIRST, fid))
ox,oy=offs.get(ffid,(0,0))
cdp.send("Input.dispatchMouseEvent", type="mouseMoved", x=d["x"]+ox, y=d["y"]+oy)
time.sleep(0.8)
print("hover chain:", cdp.evaluate("(()=>[...document.querySelectorAll(':hover')].map(e=>e.tagName+'.'+String(e.className).slice(0,26)).join(' < ')||'NONE')()", fid))
cv=cdp.evaluate(JS_CLOSE, fid)
print("close:", cv)
if cv:
    c=json.loads(cv)
    print("click at", c["x"]+ox, c["y"]+oy)
    cdp.click_xy(c["x"]+ox, c["y"]+oy)
    time.sleep(2.0)
print("li after:", cdp.evaluate(JS_FIRST, fid))
print("count:", cdp.evaluate("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')].filter(t=>t.getBoundingClientRect().width>0);const t=l.map(e=>(e.innerText||'').replace(/\\s+/g,' ').trim()).join('|');const m=t.match(/(\\d+)\\s*\\/\\s*5/);return m?m[1]:'0';})()", fid))
