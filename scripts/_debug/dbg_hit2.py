#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断：坐标点击为什么失效 —— 逐层命中检测（frame 内局部坐标 / 页面绝对坐标）。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

SEL_RADIO = ("(()=>{const l=[...document.querySelectorAll('span.custom-radio-label')]"
              ".filter(e=>(e.textContent||'').replace(/\\s+/g,'').trim()==='分组可选套餐');"
              "return l.length?l[l.length-1]:null;})()")

JS_LOCAL_HIT = r"""(()=>{
  const e=(%s); if(!e) return 'NO-EL';
  const r=e.getBoundingClientRect();
  const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
  const h=document.elementFromPoint(cx,cy);
  const chain=[]; let p=h;
  for(let i=0;i<4&&p;i++){ chain.push(p.tagName+'.'+String(p.className||'').slice(0,30)); p=p.parentElement; }
  return JSON.stringify({rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
    cx:cx, cy:cy,
    hit: h? (h.tagName+'.'+String(h.className||'').slice(0,34)+'|'+(h.textContent||'').trim().slice(0,12)) : 'null',
    hitChain: chain.join(' < '),
    elemAtPointIsTarget: h===e || (e.contains&&e.contains(h))});
})()"""

JS_TOP_HIT = r"""(()=>{
  const pts=%s; const o=[];
  for(const p of pts){
    const h=document.elementFromPoint(p[0],p[1]);
    o.push(JSON.stringify({p:p, hit:h?(h.tagName+'.'+String(h.className||'').slice(0,36)):'null'}));
  }
  return o.join(' ;; ');
})()"""

JS_OVERLAY = r"""(()=>{
  const o=[];
  const H=window.innerHeight, W=window.innerWidth;
  for(const e of document.querySelectorAll('div,span,section')){
    const st=getComputedStyle(e); const r=e.getBoundingClientRect();
    if(st.display==='none'||st.visibility==='hidden'||parseFloat(st.opacity)===0) continue;
    if(st.pointerEvents==='none') continue;
    if(r.width<W*0.8||r.height<H*0.8) continue;
    o.push(e.tagName+'.'+String(e.className||'').slice(0,44)+' pos='+st.position+' z='+st.zIndex+
           ' rect='+[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)].join(','));
  }
  return o.slice(0,10).join('\n')||'none';
})()"""


def main():
    cdp = cdp_connect()
    cid = None
    for c in cdp.contexts():
        if "套餐名称" in c["text"]:
            cid = c["id"]
            break
    if cid is None:
        print("!! 无表单")
        return
    print("form ctx", cid)

    local = cdp.evaluate(JS_LOCAL_HIT % SEL_RADIO, cid)
    print("\n-- frame 内局部命中 --")
    print(local)
    d = json.loads(local) if local and local != "NO-EL" else {}

    off = cdp._abs_correction(cid, SEL_RADIO)
    print("\nabs_correction:", off)
    abs_pt = [d["cx"] + off[0], d["cy"] + off[1]]
    print("\n-- 顶层绝对坐标命中 --")
    print(cdp.evaluate(JS_TOP_HIT % json.dumps([abs_pt])))
    print("page_coords_all:", cdp.page_coords_all(cid, SEL_RADIO, scroll=False))

    print("\n-- 全屏覆盖层 --")
    print(cdp.evaluate(JS_OVERLAY, cid))


if __name__ == "__main__":
    main()
