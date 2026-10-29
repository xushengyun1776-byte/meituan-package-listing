# -*- coding: utf-8 -*-
"""打开商品选择弹窗 —— 多路径点击对比实验。"""
import sys, time
sys.path.insert(0, '.')
from form import cdp_connect, purge_modals
from pick import modal_ctx
from addgroup import grp_additem_expr

JS_CENTER = r'''(()=>{const e=%s; if(!e) return "NULL";
 const r=e.getBoundingClientRect();
 return JSON.stringify([Math.round(r.x+r.width/2), Math.round(r.y+r.height/2)]);})()'''

cdp = cdp_connect()
cid = None
for x in cdp.contexts():
    if '套餐名称' in x['text']:
        cid = x['id']
        break
print('form ctx', cid)
expr = grp_additem_expr(0)

print('purge:', purge_modals(cdp, cid))
cdp.evaluate('(function(){try{const e=%s; e.scrollIntoView({block:"center"});}catch(e){}})()' % expr, cid)
time.sleep(1.0)


def modal_now():
    m = modal_ctx(cdp, tries=2)
    return m['id'] if m else None


def report(tag):
    print('  %-22s -> modal=%s' % (tag, modal_now()))


# --- 路径 1: 坐标点击 ---
pos = cdp.page_coords(cid, expr)
print('path1 coords:', pos)
if pos:
    cdp.click_xy(pos[0], pos[1])
    time.sleep(3.0)
    report('xy click')
    if modal_now():
        print('PATH1 OK'); raise SystemExit

# --- 路径 2: 点子元素（文本 span） ---
child = ("(()=>{const e=%s; if(!e) return null; return e.querySelector('span')||e;})()" % expr)
print('path2 js_click child:', cdp.js_click(cid, child))
time.sleep(2.5)
report('js child')
if modal_now():
    print('PATH2 OK'); raise SystemExit

# --- 路径 3: 原生 e.click() ---
print('path3 native click:', cdp.evaluate(
    "(()=>{const e=%s; if(!e) return 'NO'; e.click(); return 'clicked';})()" % expr, cid))
time.sleep(2.5)
report('native click')
if modal_now():
    print('PATH3 OK'); raise SystemExit

# --- 路径 4: 找到真正绑 onClick 的祖先再点 ---
print('path4 onclick ancestor:', cdp.evaluate(
    "(()=>{const e=%s; if(!e) return 'NO';"
    "let n=e; for(let i=0;i<5&&n;i++){"
    "  const k=Object.keys(n).find(x=>x.startsWith('__reactProps'));"
    "  if(k && n[k] && n[k].onClick) { n.click(); return 'clicked-on:'+n.tagName+'.'+String(n.className).slice(0,26); }"
    "  n=n.parentElement;} return 'NO-ONCLICK';})()" % expr, cid))
time.sleep(2.5)
report('onClick ancestor')
