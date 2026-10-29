# -*- coding: utf-8 -*-
"""找「固定商品」这个选项到底在哪、怎么才能点开组类型下拉。"""
import sys, time
sys.path.insert(0, '.')
from form import cdp_connect, purge_modals
from addgroup import form_ctx, grp_type_expr

FIND = r'''(()=>{const o=[];for(const e of document.querySelectorAll('*')){
  const t=(e.innerText||e.textContent||'').replace(/\s+/g,'').trim();
  if(t!=='固定商品') continue;
  const st=getComputedStyle(e); const rr=e.getBoundingClientRect();
  o.push(e.tagName+'.'+String(e.className).slice(0,34)+' @'+Math.round(rr.x)+','+Math.round(rr.y)
        +' '+Math.round(rr.width)+'x'+Math.round(rr.height)+' disp='+st.display+' op='+st.opacity
        +' kids='+e.children.length+' inDD='+!!(e.closest('[class*=dropdown]')));
  }
  return o.join('\n')||'NONE';})()'''

cdp = cdp_connect()
form = form_ctx(cdp)
fid = form['id']
expr = grp_type_expr(3)
purge_modals(cdp, fid)

cdp.evaluate("(()=>{const e=%s; if(e) e.focus(); return 1;})()" % expr, fid)
for k, vk, txt in (('Enter', 13, ''), ('Space', 32, ' ')):
    params = dict(type='rawKeyDown', key=k, code=k,
                  windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
    if txt:
        params['text'] = txt
    cdp.send('Input.dispatchKeyEvent', **params)
    cdp.send('Input.dispatchKeyEvent', type='keyUp', key=k, code=k,
             windowsVirtualKeyCode=vk, nativeVirtualKeyCode=vk)
    time.sleep(1.2)
    print('after %s ->' % k, cdp.evaluate(FIND, fid))
    if cdp.evaluate(FIND, fid) != 'NONE':
        break

print()
print('--- 所有 ctx 里搜「固定商品」 ---')
for x in cdp.contexts():
    try:
        r = cdp.evaluate(FIND, x['id'])
    except Exception:
        continue
    if r and r != 'NONE':
        print('ctx', x['id'], ':', r[:500])

print()
print('--- 顶层 body 里含「固定」吗 ---')
try:
    print(cdp.evaluate("(()=>{const t=document.body?document.body.innerText:'';const i=t.indexOf('固定');return i>=0? t.slice(Math.max(0,i-120), i+120) : 'NOT-FOUND';})()"))
except Exception as e:
    print('err', e)
