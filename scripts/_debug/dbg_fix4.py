# -*- coding: utf-8 -*-
"""测试三种方式点「保存图片」：合成事件点 span / 合成事件点 button / 坐标点击。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

BTN_SPAN = r"""(()=>{const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
 if(!b) return null; return b.querySelector('span')||b;})()"""

def modal_state(cdp, fid):
    return cdp.evaluate(r'''(()=>{const m=document.querySelector('div.roo-modal');
      if(!m) return 'GONE';
      const st=getComputedStyle(m);
      return 'op='+st.opacity+' cls='+String(m.className).slice(0,50);})()''', fid)

def main():
    cdp = cdp_connect()
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x; break
    if form is None: print("NO FORM"); return
    fid = form["id"]

    print("before:", modal_state(cdp, fid))
    print("--- 1) 合成事件点 span ---")
    print(cdp.evaluate("(()=>{const e=(%s); if(!e) return 'no-el';"
                        "e.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));"
                        "return 'dispatched';})()" % BTN_SPAN, fid))
    time.sleep(2.5)
    print("after:", modal_state(cdp, fid))
    print("thumbs:", cdp.evaluate("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')]"
                                  ".filter(t=>t.getBoundingClientRect().width>0);"
                                  "return l.map(t=>JSON.stringify({cls:String(t.className).slice(0,30),"
                                  "img:!!t.querySelector('img'),t:(t.innerText||'').replace(/\\s+/g,' ').slice(0,20)})).join(' ;; ');})()", fid))
    if 'GONE' in modal_state(cdp, fid):
        print(">>> 合成事件成功")
    else:
        print(">>> 合成事件未生效，改试坐标点击")
        off = cdp.offsets()
        print("offsets:", off)
        ffid = form["frameId"]
        ox, oy = off.get(ffid, (0,0))
        c = cdp.evaluate(r"""(()=>{const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='保存图片');
          if(!b) return ''; const s=b.querySelector('span')||b; const r=s.getBoundingClientRect();
          return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()""", fid)
        print("span local coord:", c, "offset:", (ox,oy))
        d = json.loads(c)
        cdp.click_xy(d["x"]+ox, d["y"]+oy)
        time.sleep(2.5)
        print("after xy:", modal_state(cdp, fid))

main()
