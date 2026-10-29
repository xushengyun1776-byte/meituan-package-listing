# -*- coding: utf-8 -*-
"""实验：把裁剪弹窗提到 body 顶层 + 找真正可点的元素。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

def main():
    cdp = cdp_connect()
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x; break
    if form is None: print("NO FORM"); return
    fid = form["id"]

    print("1) 提到 body 顶层")
    print(cdp.evaluate(r'''(()=>{
      const m=document.querySelector('div.roo-modal'); if(!m) return 'NO MODAL';
      const oldParent=String(m.parentElement.className).slice(0,40);
      m.style.position='fixed'; m.style.zIndex='2147483647';
      m.style.pointerEvents='auto';
      document.body.appendChild(m);
      return 'moved from '+oldParent+' -> body';})()''', fid))
    time.sleep(0.8)

    print("\n2) 提层后状态")
    print(cdp.evaluate(r'''(()=>{const o=[];
      const m=document.querySelector('div.roo-modal');
      const d=m.querySelector('.roo-modal-dialog');
      const dr=d.getBoundingClientRect();
      o.push('dialog rect='+Math.round(dr.width)+'x'+Math.round(dr.height)+' @'+Math.round(dr.x)+','+Math.round(dr.y));
      const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
      const br=b.getBoundingClientRect();
      o.push('BTN @'+Math.round(br.x)+','+Math.round(br.y)+' '+Math.round(br.width)+'x'+Math.round(br.height)+' pe='+getComputedStyle(b).pointerEvents);
      const sp=b.querySelector('span'); const sr=sp?sp.getBoundingClientRect():null;
      o.push('SPAN '+(sr?('@'+Math.round(sr.x)+','+Math.round(sr.y)+' '+Math.round(sr.width)+'x'+Math.round(sr.height)+' pe='+getComputedStyle(sp).pointerEvents):'NONE'));
      const cx=Math.round(br.x+br.width/2), cy=Math.round(br.y+br.height/2);
      const hit=document.elementFromPoint(cx,cy);
      o.push('elementFromPoint('+cx+','+cy+') -> '+(hit?hit.tagName+'.'+String(hit.className).slice(0,44):'NULL'));
      // 逐层解释 hit
      let n=hit; for(let i=0;i<5&&n;i++){ o.push('   hit chain '+i+' '+n.tagName+'.'+String(n.className).slice(0,44)); n=n.parentElement; }
      // 裁剪画布
      const im=document.querySelector('div.cropper-container img, .cropper-canvas img');
      if(im){ const ir=im.getBoundingClientRect(); o.push('canvas img rect='+Math.round(ir.width)+'x'+Math.round(ir.height)+' nat='+im.naturalWidth+'x'+im.naturalHeight+' src='+(im.src||'').slice(0,40)); }
      else o.push('canvas img NONE');
      return o.join('\n');})()''', fid))

    print("\n3) 尝试点 span 坐标 (trusted)")
    sp = cdp.evaluate(r'''(()=>{const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
      if(!b) return ''; const s=b.querySelector('span')||b; const r=s.getBoundingClientRect();
      return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()''', fid)
    print("span coord:", sp)
    if sp:
        d=json.loads(sp)
        cdp.click_xy(d["x"], d["y"])
        time.sleep(2.5)
        print("after click ->", cdp.evaluate(r'''(()=>{const m=document.querySelector('div.roo-modal');
          if(!m) return 'MODAL GONE';
          const st=getComputedStyle(m); const d=m.querySelector('.roo-modal-dialog');
          const dr=d.getBoundingClientRect();
          return 'modal op='+st.opacity+' cls='+String(m.className)+' dialogRect='+Math.round(dr.width)+'x'+Math.round(dr.height);})()''', fid))

main()
