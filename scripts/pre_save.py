#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""关闭残留下拉，滚到页面底部并定位「保存并返回」按钮。"""
import sys, os, time, json, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx

JS_DD = r"""(() => {
  // 可见的 dropdown 选项数量
  let n=0;
  for(const e of document.querySelectorAll('li')){
    const r=e.getBoundingClientRect();
    if(r.width<=0||r.height<=0) continue;
    const t=(e.textContent||'').trim();
    if(/^\d+人份$/.test(t)) n++;
  }
  return n;
})()"""

JS_BTN = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('button')){
    const t=(e.innerText||'').trim();
    if(!t) continue;
    const r=e.getBoundingClientRect();
    if(r.width<=0) continue;
    o.push(JSON.stringify({t:t.slice(0,12), cls:String(e.className).slice(0,44),
        x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height),
        dis: e.disabled?1:0}));
  }
  return o.join(' ;; ') || 'no-buttons';
})()"""


def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    cid = c["id"]
    print("dropdown options visible:", cdp.evaluate(JS_DD, cid))

    # 按 ESC 关闭下拉
    for t in ("keyDown", "keyUp"):
        cdp.send("Input.dispatchKeyEvent", type=t, key="Escape", code="Escape",
                 windowsVirtualKeyCode=27, nativeVirtualKeyCode=27)
    time.sleep(0.8)
    print("after ESC, dropdown options visible:", cdp.evaluate(JS_DD, cid))

    # 滚到最底部
    cdp.evaluate("(()=>{window.scrollTo(0, document.body.scrollHeight); const s=document.querySelector('#packSellInfo'); if(s) s.scrollIntoView({block:'end'}); return 1;})()", cid)
    time.sleep(1.2)
    print("BUTTONS:", cdp.evaluate(JS_BTN, cid))

    r = cdp.send("Page.captureScreenshot", format="png")
    with open("S_bottom.png", "wb") as f:
        f.write(base64.b64decode(r["result"]["data"]))
    print("saved S_bottom.png")


if __name__ == "__main__":
    main()
