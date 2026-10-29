#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核验上架结果：在左侧菜单分组里点「一人食套餐」并查找新套餐。"""
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el

JS_FIND = r"""(() => {
  const out=[];
  for(const e of document.querySelectorAll('*')){
    const t=(e.textContent||'').trim();
    if(t.includes('楚味一人食') && t.length<80) out.push(e.tagName+'|'+String(e.className).slice(0,30)+'|'+t.slice(0,60));
  }
  return out.join(' ;; ') || 'NOT-FOUND-in-page';
})()"""

JS_SIDE = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('*')){
    const t=(e.textContent||'').trim();
    if(/^一人食套餐/.test(t) && t.length<30) o.push(e.tagName+'|'+String(e.className).slice(0,40)+'|'+t);
  }
  return o.join(' ;; ') || 'NO-GROUP';
})()"""

JS_LIST = r"""(() => {
  const rows=[...document.querySelectorAll('tr,[class*=tableRow],[class*=goodsItem],[class*=productItem]')];
  const o=[];
  rows.forEach(r=>{
    const t=(r.innerText||'').trim().replace(/\s+/g,' ');
    if(t && t.length<200) o.push(t.slice(0,90));
  });
  return o.slice(0,40).join(' ;; ') || 'no-rows';
})()"""


def shot(cdp, name):
    r = cdp.send("Page.captureScreenshot", format="png")
    with open(name, "wb") as f:
        f.write(base64.b64decode(r["result"]["data"]))
    print("saved", name)


def main():
    cdp = cdp_connect()
    ctxs = cdp.contexts()
    for c in ctxs:
        try:
            v = cdp.evaluate(JS_FIND, c["id"])
        except Exception:
            continue
        if v and v != "NOT-FOUND-in-page":
            print(f"ctx{c['id']}: {v[:300]}")
    # 找业务 iframe（含商品列表）
    target = None
    for c in ctxs:
        try:
            if cdp.evaluate("(()=>document.body&&/商品管理/.test(document.body.innerText)?'YES':'')()", c["id"]) == "YES":
                target = c
                break
        except Exception:
            continue
    if not target:
        print("no list ctx"); return
    cid = target["id"]
    print("\nSIDEBAR 一人食套餐:", cdp.evaluate(JS_SIDE, cid))
    # 点击该分组
    sel = ("(()=>{const l=[...document.querySelectorAll('*')].filter(e=>/^一人食套餐/.test((e.textContent||'').trim())&&e.children.length===0);"
           "if(!l.length) return null; return l[l.length-1];})()")
    print("click group:", click_el(cdp, cid, sel))
    time.sleep(2.5)
    print("LIST:", cdp.evaluate(JS_LIST, cid))
    shot(cdp, "S_group.png")


if __name__ == "__main__":
    main()
