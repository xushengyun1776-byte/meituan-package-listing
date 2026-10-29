# -*- coding: utf-8 -*-
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, purge_modals
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
ctxs=cdp.contexts()
form=[x for x in ctxs if "套餐名称" in x["text"]][0]
fid=form["id"]; ffid=form["frameId"]
purge_modals(cdp, fid); time.sleep(0.4)
offs=cdp.offsets(); ox,oy=offs.get(ffid,(0,0))
JS_CLOSE="""(()=>{const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')].filter(t=>!String(t.className).includes('upload'));
  if(!li.length) return ''; const c=li[0].querySelector('img[class*=closeIcon]'); if(!c) return '';
  const r=c.getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2,w:Math.round(r.width),h:Math.round(r.height)});})()"""
d=json.loads(cdp.evaluate("""(()=>{const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')].filter(t=>!String(t.className).includes('upload'));
  const r=li[0].getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()""", fid))
cdp.send("Input.dispatchMouseEvent", type="mouseMoved", x=d["x"]+ox, y=d["y"]+oy); time.sleep(0.8)
c=json.loads(cdp.evaluate(JS_CLOSE, fid))
print("close local:", c)
# 1) 检查 iframe 内 elementFromPoint 命中谁
print("local elementFromPoint:", cdp.evaluate("""(()=>{const e=document.elementFromPoint(%f,%f);
  return e? e.tagName+'.'+String(e.className).slice(0,40)+' src='+String(e.src||'').slice(0,24):'NULL';})()""" % (c["x"], c["y"]), fid))
# 2) 顶层 elementFromPoint
print("top elementFromPoint:", cdp.evaluate("""(()=>{const e=document.elementFromPoint(%f,%f);
  return e? e.tagName+'.'+String(e.className).slice(0,40):'NULL';})()""" % (c["x"]+ox, c["y"]+oy), ctxs[0]["id"]))
# 3) 点击
cdp.click_xy(c["x"]+ox, c["y"]+oy); time.sleep(1.5)
print("after click, body text tail:", (cdp.evaluate("(()=>document.body.innerText.replace(/\\s+/g,' ').slice(0,300))()", fid) or ''))
print("modals:", cdp.evaluate("(()=>[...document.querySelectorAll('div.roo-modal')].map(m=>{const s=getComputedStyle(m);return 'op='+s.opacity+' cls='+String(m.className).slice(0,40)+' txt='+String(m.innerText||'').replace(/\\s+/g,' ').slice(0,40);}).join(' | ')||'NONE')()", fid))
# 4) 截图
r=cdp.send("Page.captureScreenshot", format="png")
open("_dbg_after_click.png","wb").write(base64.b64decode(r["result"]["data"]))
print("shot saved")
