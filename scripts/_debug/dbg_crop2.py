# -*- coding: utf-8 -*-
"""深挖裁剪弹窗 DOM：结构、层级、pointer-events 来源。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el

SEL_SLOT = ("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')]"
            ".filter(e=>String(e.className).includes('upload'));"
            "if(!l.length) return null; return l[l.length-1];})()")

def main():
    cdp = cdp_connect()
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x; break
    if form is None:
        print("NO FORM"); return
    fid = form["id"]
    print("form ctx", fid)
    print("click slot:", click_el(cdp, fid, SEL_SLOT))
    time.sleep(4.0)

    print("\n--- cropper 相关元素全量 ---")
    print(cdp.evaluate(r'''(()=>{const o=[];
      for(const e of document.querySelectorAll('[class*=cropper], [class*=Cropper]')){
        const r=e.getBoundingClientRect(); const st=getComputedStyle(e);
        o.push(e.tagName+'.'+String(e.className).slice(0,46)+' @'+Math.round(r.x)+','+Math.round(r.y)
          +' '+Math.round(r.width)+'x'+Math.round(r.height)
          +' pe='+st.pointerEvents+' op='+st.opacity+' vis='+st.visibility+' disp='+st.display+' z='+st.zIndex);
      }
      return o.join('\n')||'NONE';})()''', fid))

    print("\n--- 所有 modal 容器 ---")
    print(cdp.evaluate(r'''(()=>{const o=[];
      for(const e of document.querySelectorAll('div[class*=modal], div[class*=Modal], div[class*=mask], div[class*=Mask]')){
        const r=e.getBoundingClientRect(); const st=getComputedStyle(e);
        o.push(e.tagName+'.'+String(e.className).slice(0,50)+' @'+Math.round(r.x)+','+Math.round(r.y)
          +' '+Math.round(r.width)+'x'+Math.round(r.height)
          +' pe='+st.pointerEvents+' op='+st.opacity+' pos='+st.position+' z='+st.zIndex
          +' txt="'+String(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,28)+'"');
      }
      return o.join('\n')||'NONE';})()''', fid))

    print("\n--- 保存图片 按钮祖先链（含 pe/op/vis/display） ---")
    print(cdp.evaluate(r'''(()=>{
      const bs=[...document.querySelectorAll('button')].filter(e=>(e.innerText||'').trim()==='保存图片');
      if(!bs.length) return 'NO SAVE BTN; all buttons: '+[...document.querySelectorAll('button')].map(e=>(e.innerText||'').trim()).filter(Boolean).join(' | ');
      const b=bs[bs.length-1]; const o=[]; let n=b;
      for(let i=0;i<12&&n;i++){ const st=getComputedStyle(n); const r=n.getBoundingClientRect();
        o.push(i+' '+n.tagName+'.'+String(n.className).slice(0,44)+' pe='+st.pointerEvents+' op='+st.opacity+' vis='+st.visibility+' disp='+st.display+' rect='+Math.round(r.width)+'x'+Math.round(r.height)+' txt="'+String(n.innerText||'').replace(/\s+/g,' ').trim().slice(0,20)+'"');
        n=n.parentElement; }
      return o.join('\n');})()''', fid))

main()
