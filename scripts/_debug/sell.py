#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探查/填写「售卖信息」区域控件。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el, type_into, select_popup

NL = chr(10)


def form_ctx(cdp):
    return find_ctx(cdp, "套餐名称",
                    probe="(()=>document.querySelector('input.groupName_RJkgVI')?'YES':'')()")


def sel_info(cdp, fid):
    """列出所有 readonly 下拉框的当前值和位置"""
    js = """(() => {
      const o=[];
      for (const e of document.querySelectorAll('input[readonly]')) {
        const r = e.getBoundingClientRect();
        if (r.width<=0) continue;
        o.push(JSON.stringify({v:e.value, ph:e.placeholder, x:Math.round(r.x), y:Math.round(r.y),
                               par:String(e.parentElement.parentElement.className).slice(0,34)}));
      }
      return o.join(' ; ');
    })()"""
    return cdp.evaluate(js, fid)


def open_and_list(cdp, fid, ffid, trigger_expr):
    """打开下拉并列出所有可见 LI"""
    offs = cdp.offsets()
    ox, oy = offs.get(ffid, (0, 0))
    cdp.evaluate("(function(){try{const e=(%s); if(e) e.scrollIntoView({block:'center'});}catch(e){}})()"
                 % trigger_expr, fid)
    time.sleep(0.6)
    sel = cdp.evaluate(
        "(() => { const e=(%s); if(!e) return null; const r=e.getBoundingClientRect(); "
        "return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2}); })()" % trigger_expr, fid)
    if not sel:
        return "no-trigger"
    d = json.loads(sel)
    cdp.click_xy(d["x"] + ox, d["y"] + oy)
    time.sleep(1.5)
    js = """(() => {
      const o=[];
      for (const e of document.querySelectorAll('li')) {
        const r = e.getBoundingClientRect();
        if (r.width<=0||r.height<=0) continue;
        const cx=r.x+r.width/2, cy=r.y+r.height/2;
        const hit=document.elementFromPoint(cx,cy);
        o.push(JSON.stringify({t:e.textContent.trim(), x:Math.round(cx), y:Math.round(cy),
                               hit: hit? hit.tagName : 'null'}));
      }
      return o.join(' ; ');
    })()"""
    return cdp.evaluate(js, fid)


if __name__ == "__main__":
    cdp = cdp_connect()
    f = form_ctx(cdp)
    fid = f["id"]
    ffid = f["frameId"]
    mode = sys.argv[1] if len(sys.argv) > 1 else "info"
    if mode == "info":
        print("SELECTS:", sel_info(cdp, fid))
    elif mode == "portion":
        print("PORTION OPTIONS:", open_and_list(cdp, fid, ffid, sys.argv[2]))
    elif mode == "unit":
        print("UNIT OPTIONS:", open_and_list(cdp, fid, ffid, sys.argv[2]))
