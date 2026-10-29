#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打开「新建套餐」表单并点开主图上传槽位（拉起「上传图片」裁剪弹窗）。
用法: open_form_and_upload.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el

SEL_NEW = ("(()=>{const l=[...document.querySelectorAll('div[class*=create-button-text],span,div')]"
           ".filter(e=>(e.textContent||'').trim()==='新建套餐');"
           "if(!l.length) return null; return l[l.length-1];})()")
SEL_SLOT = ("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')]"
            ".filter(e=>String(e.className).includes('upload'));"
            "if(!l.length) return null; return l[l.length-1];})()")

# ★ 裁剪弹窗是否打开：用 offsetWidth（布局尺寸）判定，
#   不用 getBoundingClientRect().width —— 入场动画被冻结时 dialog 是
#   transform:scale(0)，rect 恒为 0x0，会误判成「弹窗没开」。
PROBE_CROPPER = ("(()=>{const d=document.querySelector('div.cropper-body');"
                  "return d&&d.offsetWidth>0?'YES':'';})()")


def main():
    cdp = cdp_connect()
    # ★ 叫醒页面：后台标签页会冻结 CSS 动画，弹窗会卡在入场第 0 帧
    cdp.wake()
    time.sleep(0.4)

    # 若表单已打开，直接点上传槽位；否则先导航进「新建套餐」
    form = None
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            form = x
            break
    if form is None:
        lid = None
        for x in cdp.contexts():
            if "商家首页" in x["text"]:
                continue
            try:
                if cdp.evaluate("(()=>document.body&&/新建商品/.test(document.body.innerText)?'YES':'')()", x["id"]) == "YES":
                    lid = x["id"]
                    break
            except Exception:
                continue
        if lid is None:
            print("no list ctx")
            return
        print("click 新建套餐:", click_el(cdp, lid, SEL_NEW))
        time.sleep(4.0)
        for x in cdp.contexts():
            if "套餐名称" in x["text"]:
                form = x
                print("form ctx", x["id"], x["frameId"][:12])
                break
    if form is None:
        print("NO FORM CTX")
        return
    fid = form["id"]

    # 点主图上传槽位
    print("click 主图上传槽位:", click_el(cdp, fid, SEL_SLOT))
    time.sleep(2.5)

    # ★ 把弹窗的入场动画推到终态（解冻 scale(0) / pointer-events:none）
    for x in cdp.contexts():
        try:
            cdp.finish_animations(x["id"])
        except Exception:
            pass
    time.sleep(0.6)

    # 裁剪弹窗是否打开
    for x in cdp.contexts():
        try:
            if cdp.evaluate(PROBE_CROPPER, x["id"]) == "YES":
                print("CROPPER OPEN in ctx", x["id"], x["frameId"][:12])
                return
        except Exception:
            continue
    print("cropper not detected")


if __name__ == "__main__":
    main()
