# -*- coding: utf-8 -*-
"""诊断「第 N 组」的组类型下拉有哪些选项。"""
import sys, time, json
sys.path.insert(0, '.')
from form import cdp_connect, purge_modals
from addgroup import form_ctx, grp_type_expr, group_state

cdp = cdp_connect()
form = form_ctx(cdp)
fid = form['id']
print('form ctx', fid)
print('groups:', [(g['i'], g['name'], g['type']) for g in group_state(cdp, fid)])

idx = int(sys.argv[1]) if len(sys.argv) > 1 else 3
expr = grp_type_expr(idx)
print('trigger:', cdp.evaluate("(()=>{const e=%s; return e?String(e.value||''):'NULL';})()" % expr, fid))
print('rect:', cdp.evaluate("(()=>{const e=%s; if(!e) return 'NULL'; const r=e.getBoundingClientRect(); return JSON.stringify([Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)]);})()" % expr, fid))

# 打开下拉
purge_modals(cdp, fid)
print('open:', cdp.js_click(fid, expr))
time.sleep(1.5)

print()
print('--- 可见候选（文本完全等于「固定商品」或「可选商品」）---')
print(cdp.evaluate(r'''(()=>{const o=[];for(const e of document.querySelectorAll('li,a,span,div')){
 const t=(e.innerText||e.textContent||'').replace(/\s+/g,'').trim();
 if(t!=='固定商品'&&t!=='可选商品') continue;
 const st=getComputedStyle(e); const r=e.getBoundingClientRect();
 if(st.display==='none'||st.visibility==='hidden'||parseFloat(st.opacity)===0) continue;
 if(r.width<=0||r.height<=0) continue;
 o.push(e.tagName+'.'+String(e.className).slice(0,34)+' :: '+t+' @'+Math.round(r.x)+','+Math.round(r.y)+' kids='+e.children.length+' inDD='+!!(e.closest('ul[class*=dropdown]')||e.closest('[class*=popup]')));}
return o.join('\n')||'NONE';})()''', fid))

print()
print('--- 下拉浮层整体 ---')
print(cdp.evaluate(r'''(()=>{const o=[];for(const e of document.querySelectorAll('ul[class*=dropdown], div[class*=popup], div[class*=bottom-start]')){
 const st=getComputedStyle(e); const r=e.getBoundingClientRect();
 o.push(String(e.className).slice(0,44)+' @'+Math.round(r.x)+','+Math.round(r.y)+' '+Math.round(r.width)+'x'+Math.round(r.height)+' disp='+st.display+' op='+st.opacity+' :: '+((e.innerText||'').replace(/\s+/g,' ').trim().slice(0,60)));}
return o.join('\n')||'NONE';})()''', fid))
