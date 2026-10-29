# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
cdp = cdp_connect(); cdp.wake(); time.sleep(0.5)
form=None
for x in cdp.contexts():
    if "套餐名称" in x["text"]: form=x; break
fid=form["id"]

print("=== A. 手动 dispatch change 到第一个 cropper input（files=1）===")
print(cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('input.cropper-upload__upload__input')];
  if(!l.length) return 'NO INPUT';
  const e=l[0];
  const before=e.files.length;
  e.dispatchEvent(new Event('change',{bubbles:true}));
  return 'files='+before+' dispatched';})()''', fid))
for i in range(8):
    time.sleep(1.0)
    st = cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('input.cropper-upload__upload__input')];
      const im=document.querySelector('div.cropper-container img, .cropper-canvas img');
      const btn=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
      const br=btn?btn.getBoundingClientRect():null;
      return 'files=['+l.map(e=>e.files.length).join(',')+'] img='+(im?im.naturalWidth+'x'+im.naturalHeight:'no')
        +' saveBtn='+(btn?Math.round(br.width)+'x'+Math.round(br.height):'no');})()''', fid)
    print("  t=%ds %s" % (i+1, st))

print("\n=== B. 点「保存图片」内部 span ===")
print("before count:", cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')];
  const t=l.map(e=>(e.innerText||'').replace(/\s+/g,' ').trim()).join('|');
  const m=t.match(/(\d+)\s*\/\s*5/); return m?m[1]:'0';})()''', fid))
print(cdp.evaluate(r'''(()=>{const b=[...document.querySelectorAll('button')].filter(e=>(e.innerText||'').trim()==='保存图片');
  if(!b.length) return 'NO BTN';
  const bt=b[b.length-1]; const s=bt.querySelector('span')||bt;
  s.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
  return 'clicked span';})()''', fid))
time.sleep(3.0)
print("after count:", cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')];
  const t=l.map(e=>(e.innerText||'').replace(/\s+/g,' ').trim()).join('|');
  const m=t.match(/(\d+)\s*\/\s*5/); return m?m[1]:'0';})()''', fid))
print("modal:", cdp.evaluate(r'''(()=>{const m=document.querySelector('div.roo-modal'); if(!m) return 'GONE';
  return 'op='+getComputedStyle(m).opacity+' cls='+String(m.className).slice(0,60);})()''', fid))
