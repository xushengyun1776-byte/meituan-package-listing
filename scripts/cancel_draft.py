#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""取消当前新建套餐草稿（含可能的二次确认弹窗）。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el, click_button

SEL_CANCEL = ("(()=>{const l=[...document.querySelectorAll('button')].filter(e=>(e.innerText||'').trim()==='取消');"
              "return l.length? l[l.length-1]:null;})()")
SEL_CONFIRM = ("(()=>{const l=[]; for(const e of document.querySelectorAll('button,span,div')){"
               "const t=(e.innerText||'').trim(); if((t==='确定'||t==='确认'||t==='是的')&&e.children.length===0){ "
               "const r=e.getBoundingClientRect(); if(r.width>0) l.push(e);} } return l[l.length-1]||null;})()")


def main():
    cdp = cdp_connect()
    fid = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            fid = x["id"]; break
    if fid is None:
        print("no form -> already cancelled?")
    else:
        print("cancel:", click_el(cdp, fid, SEL_CANCEL))
        time.sleep(2.0)
        # 二次确认
        for x in cdp.contexts():
            try:
                has = cdp.evaluate("(()=>{const b=document.body; return b&&/确定|确认/.test(b.innerText)?'Y':'';})()", x["id"])
            except Exception:
                continue
            if has == "Y":
                print("confirm dialog in ctx", x["id"], ":", click_el(cdp, x["id"], SEL_CONFIRM))
                time.sleep(2.0)
                break
    time.sleep(2.0)
    # 回到列表验证
    for x in cdp.contexts():
        try:
            v = cdp.evaluate("(()=>{const b=document.body; if(!b) return ''; const t=b.innerText||''; "
                             "const m=t.match(/一人食套餐\\((\\d+)\\)/); return m? m[0] : '';})()", x["id"])
        except Exception:
            continue
        if v:
            print("列表侧栏分组:", v)
            break
    else:
        print("列表未在当前 context")


if __name__ == "__main__":
    main()
