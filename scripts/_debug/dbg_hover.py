# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
ctxs = cdp.contexts()
form=[x for x in ctxs if "套餐名称" in x["text"]][0]
fid=form["id"]; ffid=form["frameId"]
print("form ffid:", ffid)
offs = cdp.offsets(); print("offsets:", offs)

LOCAL = cdp.evaluate(r'''(()=>{const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')]
  .filter(t=>!String(t.className).includes('upload'))[0];
  if(!li) return ''; const r=li.getBoundingClientRect();
  return JSON.stringify({x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)});})()''', fid)
print("li local center:", LOCAL)
d=json.loads(LOCAL)

# 顶层 frame 滚动量
for x in ctxs:
    u = cdp.evaluate("location.href", x["id"]) or ""
    if "listView" in u:
        print("top ctx", x["id"], "scroll:", cdp.evaluate("JSON.stringify({x:window.scrollX,y:window.scrollY,vw:innerWidth,vh:innerHeight})", x["id"]))
    if x["id"]==fid:
        print("form scroll:", cdp.evaluate("JSON.stringify({x:window.scrollX,y:window.scrollY,vw:innerWidth,vh:innerHeight})", fid))

ox,oy = offs.get(ffid,(0,0))
for name,(dx,dy) in [("rect+off",(ox,oy)), ("rect only",(0,0)), ("rect+off-70",(ox,oy-70))]:
    px,py = d["x"]+dx, d["y"]+dy
    cdp.send("Input.dispatchMouseEvent", type="mouseMoved", x=px, y=py)
    time.sleep(0.8)
    hov = cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll(':hover')];
      return l.map(e=>e.tagName+'.'+String(e.className).slice(0,28)).join(' < ')||'NONE';})()''', fid)
    clo = cdp.evaluate(r'''(()=>{const c=document.querySelector('img[class*=closeIcon]');
      if(!c) return 'no-close'; const r=c.getBoundingClientRect();
      return 'rect='+Math.round(r.width)+'x'+Math.round(r.height)+' disp='+getComputedStyle(c).display;})()''', fid)
    print("  %-12s click(%.0f,%.0f) hover=%s close=%s" % (name,px,py,hov,clo))
