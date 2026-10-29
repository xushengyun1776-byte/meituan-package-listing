#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""当前页面状态总览：contexts / 弹窗 / 售卖信息 / 规格组 / 图片数。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

JS_STATE = r"""(() => {
  const o = {};
  o.title = document.title;
  o.modalCount = document.querySelectorAll('div.roo-modal-dialog').length;
  o.modalVisible = [...document.querySelectorAll('div.roo-modal-dialog')].map(m => {
     const r = m.getBoundingClientRect();
     return {w: Math.round(r.width), h: Math.round(r.height),
             txt: (m.innerText||'').trim().replace(/\s+/g,' ').slice(0,120)};
  });
  o.inputs = [...document.querySelectorAll('input,textarea')].filter(e=>{
     const r=e.getBoundingClientRect(); return r.width>0 && r.height>0;
  }).map(e => {
     const r=e.getBoundingClientRect();
     return JSON.stringify({tag:e.tagName, type:e.type, v:(e.value||'').slice(0,28),
        ph:(e.placeholder||'').slice(0,22), ro:e.readOnly?'R':'', x:Math.round(r.x), y:Math.round(r.y),
        par:String(e.parentElement?e.parentElement.className:'').slice(0,30)});
  });
  o.thumbs = [...document.querySelectorAll('div[class*=thumbnailItem]')].map(e=>{
     const img=e.querySelector('img');
     return JSON.stringify({cls:String(e.className).slice(0,50), hasImg: !!img, src:(img?img.src:'').slice(0,60)});
  });
  o.bodyTail = (document.body.innerText||'').replace(/\s+/g,' ').slice(-700);
  return JSON.stringify(o);
})()"""


def main():
    cdp = cdp_connect()
    ctxs = cdp.contexts()
    print("=== CONTEXTS ===")
    for c in ctxs:
        print(f"  id={c['id']} frame={c['frameId'][:12]} text={c['text'][:90]!r}")
    for c in ctxs:
        try:
            v = cdp.evaluate(JS_STATE, c["id"])
        except Exception as e:
            continue
        if not v:
            continue
        try:
            d = json.loads(v)
        except Exception:
            continue
        if d.get("modalCount") or d.get("inputs") or "楚味" in (d.get("bodyTail") or ""):
            print(f"\n=== STATE in ctx {c['id']} (frame {c['frameId'][:12]}) ===")
            print("  title:", d.get("title"))
            print("  modalCount:", d.get("modalCount"))
            for m in d.get("modalVisible", []):
                print("   modal:", m)
            print("  -- inputs --")
            for i in d.get("inputs", []):
                print("   ", i)
            print("  -- thumbs --")
            for t in d.get("thumbs", []):
                print("   ", t)
            print("  -- bodyTail --")
            print("   ", d.get("bodyTail"))


if __name__ == "__main__":
    main()
