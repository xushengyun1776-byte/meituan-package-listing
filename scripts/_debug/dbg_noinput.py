# -*- coding: utf-8 -*-
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
from clicktext import JSError
cdp = cdp_connect(); cdp.wake(); time.sleep(0.4)
form=[x for x in cdp.contexts() if "套餐名称" in x["text"]][0]
fid=form["id"]
for label, expr in [
  ("A querySelector", "(()=>{const e=document.querySelector('input.cropper-upload__upload__input'); return e? 'FOUND':'NULL';})()"),
  ("B querySelectorAll", "(()=>{return 'n='+document.querySelectorAll('input[type=file]').length;})()"),
  ("C files len", "(()=>{const l=document.querySelectorAll('input[type=file]'); return [...l].map(e=>e.className.slice(0,26)+':'+e.files.length).join(' | ');})()"),
  ("D 直接 dispatch", "(()=>{const l=document.querySelectorAll('input[type=file]'); const e=[...l].find(x=>x.className.includes('cropper-upload')); if(!e) return 'NO-CROP'; const n=e.files.length; e.dispatchEvent(new Event('change',{bubbles:true})); return 'files='+n+' dispatched';})()"),
]:
    try:
        v = cdp.evaluate(expr, fid, strict=True)
        print("%-20s -> %r" % (label, v))
    except JSError as e:
        print("%-20s -> JSError: %s" % (label, str(e)[:220]))
