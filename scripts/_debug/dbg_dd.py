#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断：下拉项「新建套餐」的坐标口径 + 是否存在直达 hash 路由。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

JS_TOP_IFRAMES = r"""(() => {
  const o=[];
  for(const f of document.querySelectorAll('iframe')){
    const r=f.getBoundingClientRect();
    o.push(JSON.stringify({rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
      src:(f.src||'').slice(0,120), name:f.name||'', id:f.id||''}));
  }
  return o.join(' ;; ') || 'none';
})()"""

JS_HASH_LINKS = r"""(() => {
  const s=new Set();
  for(const a of document.querySelectorAll('a[href]')){
    const h=a.getAttribute('href')||'';
    if(h.includes('#')) s.add(h.slice(0,160));
  }
  return [...s].slice(0,40).join(' ;; ') || 'none';
})()"""

JS_ITEM_ALL = r"""(() => {
  const out=[];
  const all=[...document.querySelectorAll('*')].filter(e=>(e.textContent||'').trim()==='新建套餐');
  for(const e of all){
    const r=e.getBoundingClientRect();
    let chain=[]; let p=e;
    for(let i=0;i<4 && p;i++){ chain.push(String(p.className||p.tagName).slice(0,26)); p=p.parentElement; }
    out.push(JSON.stringify({rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
      cx:Math.round(r.x+r.width/2), cy:Math.round(r.y+r.height/2),
      tag:e.tagName, cls:String(e.className).slice(0,40), chain:chain.join('<'),
      ol:e.offsetLeft, ot:e.offsetTop, inDoc: e.ownerDocument===document}));
  }
  return out.join(' ;; ') || 'none';
})()"""

JS_HIT_LOCAL = r"""(() => {
  const pts=JSON.parse(arguments[0]);
  const out=[];
  for(const p of pts){
    const h=document.elementFromPoint(p[0],p[1]);
    out.push(JSON.stringify({p:p, hit: h? (h.tagName+'.'+String(h.className).slice(0,34)+'|'+(h.textContent||'').trim().slice(0,12)) : 'null'}));
  }
  return out.join(' ;; ');
})()"""


def main():
    cdp = cdp_connect()
    print("TOP URL:", cdp.evaluate("location.href"))
    print("\n-- top iframes --")
    print(cdp.evaluate(JS_TOP_IFRAMES))
    print("\n-- hash links --")
    print(cdp.evaluate(JS_HASH_LINKS))

    # 找到业务 iframe 上下文
    ctxs = cdp.contexts()
    biz = None
    for c in ctxs:
        try:
            if cdp.evaluate("(()=>document.body&&/新建商品/.test(document.body.innerText)?'Y':'')()", c["id"]) == "Y":
                biz = c
                break
        except Exception:
            pass
    if not biz:
        print("\n!! 业务 iframe 未找到，ctxs:")
        for c in ctxs:
            print("  ", c["id"], repr(c["text"][:70]))
        return
    cid = biz["id"]
    print("\nBIZ ctx:", cid, "frame:", biz["frameId"][:14])
    print("BIZ URL:", cdp.evaluate("location.href", cid))
    print("BIZ hash links:", (cdp.evaluate(JS_HASH_LINKS, cid) or "")[:600])

    # iframe 偏移
    offs = cdp.offsets()
    print("\n-- offsets (frameId -> xy) --")
    for k, v in offs.items():
        print("  ", k[:14], v)
    print("biz frameId:", biz["frameId"], "-> off", offs.get(biz["frameId"]))

    # 展开下拉
    print("\n-- 点开下拉 --")
    from form import click_button
    print(click_button(cdp, cid, "新建商品"))
    time.sleep(2.0)

    print("\n-- 新建套餐 全部匹配元素 --")
    print(cdp.evaluate(JS_ITEM_ALL, cid))

    # 收集候选局部坐标，做命中检测
    pts = []
    raw = cdp.evaluate(JS_ITEM_ALL, cid) or "none"
    for chunk in raw.split(" ;; "):
        try:
            d = json.loads(chunk)
        except Exception:
            continue
        pts.append((d["cx"], d["cy"]))
        pts.append((d["rect"][0] + 3, d["rect"][1] + d["rect"][3] / 2))
    if pts:
        print("\n-- frame 内命中检测 --")
        print(cdp.evaluate(JS_HIT_LOCAL.replace("arguments[0]", json.dumps(pts)), cid))

    # 顶层命中检测（绝对坐标）
    off = offs.get(biz["frameId"], (0, 0))
    abs_pts = [[p[0] + off[0], p[1] + off[1]] for p in pts]
    print("\n-- 顶层命中检测 (abs) --")
    print(cdp.evaluate(JS_HIT_LOCAL.replace("arguments[0]", json.dumps(abs_pts))))


if __name__ == "__main__":
    main()
