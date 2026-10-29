#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实验：哪种合成事件模式能点开「新建商品」下拉触发器。

假设：roo 的 trigger 在 onMouseDown 里切换展开状态，若同时又绑定 onClick，
     down+click 都派发会「开→关」互相抵消。
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

TRIG = ("(()=>{const l=[...document.querySelectorAll('button')]"
        ".filter(e=>(e.innerText||'').trim()==='新建商品');"
        "return l.length? l[0]: null;})()")

ITEM_CHK = ("(()=>{const l=[...document.querySelectorAll('div[class*=create-button-text]')]"
            ".filter(e=>(e.textContent||'').trim()==='新建套餐');"
            "return l.length? 'FOUND':'';})()")

JS_CLICK_ONLY = """(()=>{
  const e=(%s); if(!e) return 'no-el';
  const r=e.getBoundingClientRect();
  const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
  e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window,
     clientX:cx,clientY:cy,button:0,detail:1}));
  return 'CLICKONLY@'+cx+','+cy;
})()"""

JS_DOWNUP = """(()=>{
  const e=(%s); if(!e) return 'no-el';
  const r=e.getBoundingClientRect();
  const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
  e.dispatchEvent(new MouseEvent('mousedown',{bubbles:true,cancelable:true,view:window,
     clientX:cx,clientY:cy,button:0,buttons:1,detail:1}));
  e.dispatchEvent(new MouseEvent('mouseup',{bubbles:true,cancelable:true,view:window,
     clientX:cx,clientY:cy,button:0,buttons:0,detail:1}));
  return 'DOWNUP@'+cx+','+cy;
})()"""

JS_CLICK_SCROLL = """(()=>{
  const e=(%s); if(!e) return 'no-el';
  try{ e.scrollIntoView({block:'center',inline:'nearest'}); }catch(err){}
  const r=e.getBoundingClientRect();
  const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
  e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window,
     clientX:cx,clientY:cy,button:0,detail:1}));
  return 'CLICKSCROLL@'+cx+','+cy;
})()"""


def biz_ctx(cdp):
    for c in cdp.contexts():
        try:
            if cdp.evaluate("(()=>document.body&&/新建商品/.test(document.body.innerText)?'Y':'')()", c["id"]) == "Y":
                return c
        except Exception:
            pass
    return None


def dd_open(cdp, cid):
    try:
        return cdp.evaluate(ITEM_CHK, cid) == "FOUND"
    except Exception:
        return False


def main():
    cdp = cdp_connect()
    # 先回到列表页
    import subprocess
    subprocess.run([sys.executable, "nav_to_list.py"], cwd=os.path.dirname(os.path.abspath(__file__)))
    c = biz_ctx(cdp)
    if not c:
        print("!! 无列表 ctx")
        return
    cid = c["id"]

    tests = [("click-only", JS_CLICK_ONLY), ("mousedown+up", JS_DOWNUP),
             ("click-only+scroll", JS_CLICK_SCROLL), ("full(默认js_click)", None)]

    for name, js in tests:
        if dd_open(cdp, cid):
            print("  (下拉已开，先关闭)")
            cdp.evaluate("(()=>{document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 1})()", cid)
            time.sleep(1.0)
        if js is None:
            r = cdp.js_click(cid, TRIG)
        else:
            r = cdp.evaluate(js % TRIG, cid)
        time.sleep(1.8)
        ok = dd_open(cdp, cid)
        print("%-22s -> %s | 下拉打开=%s" % (name, r, ok))
        if ok:
            print(">>> 命中模式:", name)
            break


if __name__ == "__main__":
    main()
