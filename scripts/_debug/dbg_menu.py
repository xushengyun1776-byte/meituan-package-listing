#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断：菜单分组下拉的选项结构（为什么点不中「一人食套餐」）。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el

SEL_MENU = ("(()=>{const l=[...document.querySelectorAll('input[placeholder=\"请选择\"]')].filter(e=>{"
            "const p=e.closest('div.form-group'); const lab=p&&p.querySelector('label');"
            "return lab && (lab.innerText||'').replace(/\\s+/g,'').trim()==='菜单分组';});"
            "return l.length?l[l.length-1]:null;})()")

JS_CAND = r"""(()=>{
  const o=[];
  for(const e of document.querySelectorAll('*')){
    const t=(e.innerText||e.textContent||'').replace(/\s+/g,'').trim();
    if(t!=='一人食套餐') continue;
    const st=getComputedStyle(e); const r=e.getBoundingClientRect();
    if(st.display==='none'||st.visibility==='hidden') continue;
    let chain=[],p=e;
    for(let i=0;i<5&&p;i++){ chain.push(p.tagName+'.'+String(p.className||'').slice(0,40)); p=p.parentElement; }
    o.push(JSON.stringify({tag:e.tagName, cls:String(e.className).slice(0,50),
      txt:(e.innerText||'').trim().slice(0,20), kids:e.children.length,
      rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
      chain:chain.join(' < ')}));
  }
  return o.join('\n')||'NONE';
})()"""

JS_POPUPS = r"""(()=>{
  const o=[];
  for(const e of document.querySelectorAll('body > div, body > ul, body > li')){
    const st=getComputedStyle(e); const r=e.getBoundingClientRect();
    if(r.width<50||r.height<20) continue;
    if(st.display==='none'||st.visibility==='hidden'||st.opacity==='0') continue;
    o.push(JSON.stringify({cls:String(e.className).slice(0,60),
      rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
      txt:(e.innerText||'').replace(/\s+/g,' ').trim().slice(0,90)}));
  }
  return o.join('\n')||'NONE';
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
    print("菜单分组 input:", cdp.evaluate(
        "(()=>{const e=%s; if(!e) return 'NULL'; return JSON.stringify({v:e.value,ph:e.placeholder,ro:e.readOnly});})()"
        % SEL_MENU, cid))

    print("\n-- 打开下拉 --")
    print(click_el(cdp, cid, SEL_MENU, scroll=False))
    time.sleep(2.0)

    print("\n-- 候选「一人食套餐」 --")
    print(cdp.evaluate(JS_CAND, cid))
    print("\n-- body 下的浮层 --")
    print(cdp.evaluate(JS_POPUPS, cid))


if __name__ == "__main__":
    main()
