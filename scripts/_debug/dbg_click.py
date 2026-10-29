#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实测：在目标 frame 内用 JS 合成鼠标事件点击「新建套餐」，验证是否绕开坐标问题。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_button

SEL_ITEM_EL = ("(()=>{const l=[...document.querySelectorAll('div[class*=create-button-text]')]"
               ".filter(e=>(e.textContent||'').trim()==='新建套餐');"
               "return l.length? l[l.length-1]: null;})()")

JS_SYNTH = """(()=>{
  const e=(%s); if(!e) return 'no-el';
  const r=e.getBoundingClientRect();
  const cx=Math.round(r.x+r.width/2), cy=Math.round(r.y+r.height/2);
  const mk=(t)=>new MouseEvent(t,{bubbles:true,cancelable:true,view:window,
      clientX:cx,clientY:cy,button:0,buttons:(t==='mousedown'||t==='pointerdown')?1:0});
  for(const t of ['pointerdown','mousedown','pointerup','mouseup','click']){
    try{ e.dispatchEvent(mk(t)); }catch(err){}
  }
  return 'SYNTH '+cx+','+cy;
})()"""

JS_SYNTH_CLICK = """(()=>{
  const e=(%s); if(!e) return 'no-el';
  try{ e.click(); }catch(err){ return 'err:'+err; }
  return 'ELCLICK';
})()"""

JS_ITEM_RECT = """(()=>{
  const l=[...document.querySelectorAll('div[class*=create-button-text]')]
    .filter(e=>(e.textContent||'').trim()==='新建套餐');
  if(!l.length) return 'none';
  const e=l[l.length-1]; const r=e.getBoundingClientRect();
  // 元素在 DOM 里的挂载点（判断是否 portal 到 body）
  let p=e, chain=[];
  for(let i=0;i<6&&p;i++){ chain.push(p.tagName+'#'+(p.id||'')+'.'+String(p.className||'').slice(0,24)); p=p.parentElement; }
  return JSON.stringify({rect:[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
    chain:chain.join(' < '), rootChild:(e.getRootNode()===document?'DOC':'SHADOW'),
    parentIsBody: e.parentElement===document.body});
})()"""

JS_HIT = """(()=>{
  const pts=%s; const out=[];
  for(const p of pts){
    const h=document.elementFromPoint(p[0],p[1]);
    out.push(p.join(',')+' => '+(h?(h.tagName+'.'+String(h.className).slice(0,30)+'|'+(h.textContent||'').trim().slice(0,10)):'null'));
  }
  return out.join(' ;; ');
})()"""


def form_open(cdp):
    return any("套餐名称" in x["text"] for x in cdp.contexts())


def biz_ctx(cdp):
    for c in cdp.contexts():
        try:
            if cdp.evaluate("(()=>document.body&&/新建商品/.test(document.body.innerText)?'Y':'')()", c["id"]) == "Y":
                return c
        except Exception:
            pass
    return None


def main():
    cdp = cdp_connect()
    c = biz_ctx(cdp)
    if not c:
        print("!! 找不到业务 iframe")
        for x in cdp.contexts():
            print("  ", x["id"], repr(x["text"][:60]))
        return
    cid = c["id"]
    offs = cdp.offsets()
    off = offs.get(c["frameId"], (0, 0))
    print("ctx", cid, "off", off)

    # 1) 展开下拉
    print("open dd:", click_button(cdp, cid, "新建商品"))
    time.sleep(2.2)
    info = cdp.evaluate(JS_ITEM_RECT, cid)
    print("item rect:", info)

    # 2) 命中检测：局部 vs 绝对
    try:
        d = json.loads(info)
        lx, ly = d["rect"][0] + d["rect"][2] / 2, d["rect"][1] + d["rect"][3] / 2
        print("local hit :", cdp.evaluate(JS_HIT % json.dumps([[lx, ly]]), cid))
        print("abs  hit :", cdp.evaluate(JS_HIT % json.dumps([[lx + off[0], ly + off[1]]])))
    except Exception as e:
        print("hit err", e)

    # 3) 尝试 JS 合成事件点击
    print("\nsynth:", cdp.evaluate(JS_SYNTH % SEL_ITEM_EL, cid))
    time.sleep(3.0)
    if form_open(cdp):
        print(">>> 合成事件点击成功！表单已打开")
        return
    print(">>> 合成事件未生效，试 el.click()")
    print("elclick:", cdp.evaluate(JS_SYNTH_CLICK % SEL_ITEM_EL, cid))
    time.sleep(3.0)
    if form_open(cdp):
        print(">>> el.click() 成功！")
        return
    print(">>> 都不行，回到坐标派发")
    for c2 in cdp.page_coords_all(cid, SEL_ITEM_EL, scroll=False):
        print("  click @", (round(c2[0]), round(c2[1])))
        cdp.click_xy(c2[0], c2[1])
        time.sleep(3.0)
        if form_open(cdp):
            print("  -> 命中")
            return
    print("!! 全部失败")


if __name__ == "__main__":
    main()
