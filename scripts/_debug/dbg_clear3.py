# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, purge_modals
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
ctxs=cdp.contexts()
form=[x for x in ctxs if "套餐名称" in x["text"]][0]
fid=form["id"]; ffid=form["frameId"]
purge_modals(cdp, fid); time.sleep(0.4)
CNT="""(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')].filter(t=>t.getBoundingClientRect().width>0);
 const t=l.map(e=>(e.innerText||'').replace(/\\s+/g,' ').trim()).join('|');const m=t.match(/(\\d+)\\s*\\/\\s*5/);return m?m[1]:'0';})()"""
print("before count:", cdp.evaluate(CNT, fid))
print("A) 合成事件点 closeIcon（不 hover）:", cdp.evaluate(r"""(()=>{
  const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')].filter(t=>!String(t.className).includes('upload'));
  if(!li.length) return 'NO LI';
  const c=li[0].querySelector('img[class*=closeIcon]');
  if(!c) return 'NO CLOSE';
  c.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
  return 'clicked closeIcon';})()""", fid))
time.sleep(2.0)
print("   count after:", cdp.evaluate(CNT, fid))
print("B) 若没删掉，试 operateBtnWrapper 内的元素:", cdp.evaluate(r"""(()=>{
  const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')].filter(t=>!String(t.className).includes('upload'));
  if(!li.length) return 'NO LI';
  const c=li[0].querySelector('img[class*=closeIcon]');
  const sib=c?c.parentElement.querySelector('div[class*=operateBtnWrapper]'):null;
  if(!sib) return 'NO WRAP';
  const k=Object.keys(sib).find(x=>x.startsWith('__reactFiber'));
  return 'wrap html='+sib.outerHTML.replace(/\s+/g,' ').slice(0,300);})()""", fid))
