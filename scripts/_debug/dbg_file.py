# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
cdp = cdp_connect(); cdp.wake(); time.sleep(0.5)
form=None
for x in cdp.contexts():
    if "套餐名称" in x["text"]: form=x; break
fid=form["id"]
print("vis:", cdp.evaluate("document.visibilityState", fid))
print("\n=== 所有 file input 详情 ===")
print(cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('input[type=file]')];
  return l.map((e,i)=>{const r=e.getBoundingClientRect();
    let pn=[]; let n=e; for(let k=0;k<6&&n;k++){pn.push(n.tagName+'.'+String(n.className).slice(0,26)); n=n.parentElement;}
    return i+' cls='+String(e.className).slice(0,34)+' files='+e.files.length
      +' visible='+(e.offsetParent!==null)+' rect='+Math.round(r.width)+'x'+Math.round(r.height)
      +'\n     chain: '+pn.join(' < ');}).join('\n');})()''', fid))
print("\n=== setFileInputFiles 到可见的 cropper input ===")
r = cdp.send("Runtime.evaluate",
    expression="""(()=>{const l=[...document.querySelectorAll('input[type=file]')].filter(e=>e.offsetParent!==null);
      return l.length? l[l.length-1] : null;})()""", contextId=fid, returnByValue=False)
oid = r.get("result",{}).get("result",{}).get("objectId")
print("oid:", bool(oid))
if oid:
    nid = cdp.send("DOM.requestNode", objectId=oid).get("result",{}).get("nodeId")
    print("nodeId:", nid)
    cdp.send("DOM.setFileInputFiles", nodeId=nid,
             files=["D:/工作/千湖边湖北菜/经开店套餐/微信图片_20261028155906_48_522.jpg"])
    print("set ok")
    for i in range(12):
        time.sleep(1.0)
        st = cdp.evaluate(r'''(()=>{const l=[...document.querySelectorAll('input[type=file]')].filter(e=>e.offsetParent!==null);
          const f=l.length?l[l.length-1].files.length:-1;
          const im=document.querySelector('div.cropper-container img, .cropper-canvas img');
          const btn=[...document.querySelectorAll('button')].some(e=>(e.innerText||'').trim()==='保存图片');
          return 'visFiles='+f+' img='+(im?im.naturalWidth+'x'+im.naturalHeight:'no')+' saveBtn='+btn;})()''', fid)
        print("  t=%ds %s" % (i+1, st))
