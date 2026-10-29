# -*- coding: utf-8 -*-
"""诊断裁剪弹窗：「保存图片」按钮为什么点不动。"""
import sys, time
sys.path.insert(0, '.')
from form import cdp_connect
from crop_upload import crop_ctx, confirm_expr

cdp = cdp_connect()
c = crop_ctx(cdp)
if not c:
    print("CROPPER NOT OPEN")
    raise SystemExit
fid = c['id']
print('crop ctx', fid)

print('--- 按钮状态 ---')
print(cdp.evaluate(r'''(()=>{const o=[];
 for(const e of document.querySelectorAll('button,a,span,div')){
   const t=(e.innerText||'').trim();
   if(!t||t.length>8) continue;
   if(!/保存图片|重新上传|上传图片|取消|完成|确定/.test(t)) continue;
   const r=e.getBoundingClientRect(); const st=getComputedStyle(e);
   o.push(e.tagName+'.'+String(e.className).slice(0,30)+' :: '+t+' @'+Math.round(r.x)+','+Math.round(r.y)
     +' '+Math.round(r.width)+'x'+Math.round(r.height)+' disabled='+(e.disabled!==undefined?e.disabled:'?')
     +' pe='+st.pointerEvents+' op='+st.opacity+' kids='+e.children.length);}
 return o.join('\n')||'NONE';})()''', fid))

print()
print('--- 裁剪区图片 ---')
print(cdp.evaluate(r'''(()=>{const c=document.querySelector('div.cropper-body'); if(!c) return 'no-body';
 const im=c.querySelector('img,canvas');
 if(!im) return 'NO-IMG';
 const r=im.getBoundingClientRect();
 return JSON.stringify({tag:im.tagName, src:(im.src||'').slice(0,60), complete:im.complete,
   nat:[im.naturalWidth, im.naturalHeight], rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)]});})()''', fid))

print()
print('--- 弹窗内是否有遮罩盖住按钮 ---')
print(cdp.evaluate(r'''(()=>{const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
 if(!b) return 'NO-BTN';
 const r=b.getBoundingClientRect(); const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
 const hit=document.elementFromPoint(cx,cy);
 let chain=[]; let n=hit; for(let i=0;i<4&&n;i++){chain.push(n.tagName+'.'+String(n.className).slice(0,34)+'::'+(n.innerText||'').replace(/\s+/g,' ').trim().slice(0,10)); n=n.parentElement;}
 return JSON.stringify({probe:[cx,cy], hit:hit?(hit.tagName+'.'+String(hit.className).slice(0,34)):'NULL', chain:chain});})()''', fid))

print()
print('--- 弹窗里的错误提示 ---')
print((cdp.evaluate("(()=>{const t=document.body?document.body.innerText:''; return t.replace(/\\s+/g,' ').slice(0,400);})()", fid) or ''))
