#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查价格输入框位置上的实际命中元素（顶层 + iframe 内）。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx

SEL_PRICE = ("(()=>{const lb=document.querySelector('#packSellInfo label[for=\"price\"]');"
             "if(!lb) return null; return lb.closest('div.form-group').querySelector('input[placeholder=\"请输入价格\"]');})()")


def main():
    cdp = cdp_connect()
    ctxs = cdp.contexts()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]
    ffid = c["frameId"]
    offs = cdp.offsets()
    ox, oy = offs.get(ffid, (0, 0))
    print("iframe offset:", ox, oy)

    # iframe 内坐标
    v = cdp.evaluate(
        "(()=>{const e=(%s); if(!e) return null; const r=e.getBoundingClientRect();"
        "const cx=r.x+r.width/2, cy=r.y+r.height/2; const hit=document.elementFromPoint(cx,cy);"
        "return JSON.stringify({x:cx,y:cy,w:r.width,h:r.height, top:r.top, left:r.left,"
        "hit: hit? (hit.tagName+'|'+(hit.className||'').toString().slice(0,40)+'|'+(hit.textContent||'').trim().slice(0,15)) : 'null'});})()"
        % SEL_PRICE, cid)
    print("IN-IFRAME:", v)
    d = json.loads(v)
    px, py = d["x"] + ox, d["y"] + oy
    print("PAGE coords:", px, py)

    # 顶层 frame 该点的命中元素
    for cc in ctxs:
        if cc["id"] == cid:
            continue
        try:
            r = cdp.evaluate(
                "(()=>{const el=document.elementFromPoint(%f,%f); return el? (el.tagName+'|'+(el.className||'').toString().slice(0,50)+'|'+(el.textContent||'').trim().slice(0,25)) : 'null';})()"
                % (px, py), cc["id"])
        except Exception as e:
            continue
        if r and r != "null":
            print(f"TOP ctx{cc['id']} frame={cc['frameId'][:10]}: {r}")

    # 顶层可能挡住 iframe 的 overlay
    print("--- top-level iframes ---")
    for cc in ctxs:
        try:
            r = cdp.evaluate(
                "(()=>{const o=[]; for(const e of document.querySelectorAll('*')){const s=getComputedStyle(e);"
                "if((s.position==='fixed'||s.position==='absolute') && s.zIndex && s.zIndex!=='auto'){"
                "const b=e.getBoundingClientRect(); if(b.width>200&&b.height>200&&b.top<900&&b.left<1900)"
                "o.push(e.tagName+'|'+String(e.className).slice(0,36)+'|z='+s.zIndex+'|'+Math.round(b.x)+','+Math.round(b.y)+','+Math.round(b.width)+'x'+Math.round(b.height)+'|'+(e.innerText||'').trim().slice(0,20));}}"
                "return o.join(' ;; ')||'none';})()", cc["id"])
        except Exception:
            continue
        if r and r != "none":
            print(f"ctx{cc['id']}: {r}")


if __name__ == "__main__":
    main()
