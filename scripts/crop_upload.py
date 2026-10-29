#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在「上传图片」裁剪弹窗中：切到「本地上传」-> 选择本地文件 -> 点「保存图片」。

用法:
  python crop_upload.py <文件路径>            # 上传（幂等：先清掉已有主图）
  python crop_upload.py <文件路径> --keep     # 已有主图则跳过
  python crop_upload.py --status              # 只看当前主图计数

★ 本脚本是整个项目里最反直觉的一段，根因链条（详见 references/踩坑记录.md）：
  1) Edge 标签页在后台时 document.visibilityState === 'hidden'，
     Chrome **冻结 CSS 动画时钟** → 弹窗停在入场动画第 0 帧：
        遮罩 opacity=0、dialog transform=scale(0)、按钮 pointer-events:none、
        所有 getBoundingClientRect() 都是 0x0。
     ⇒ 每次操作弹窗前必须 cdp.wake() + finish_animations()。
  2) 判定弹窗是否打开**不能**用 getBoundingClientRect().width>0
     （transform 缩放后恒为 0），要用 offsetWidth（布局尺寸，不受 transform 影响）。
  3) roo 的 <button> 自己 pointer-events:none，真正可点的是它内部的 <span>；
     对 <span> 派发合成 click 会冒泡到 button，React onClick 正常触发。
  4) CDP 的 DOM.setFileInputFiles **不会**派发 change 事件，必须手动 dispatch，
     否则组件不知道文件来了，裁剪画布永远空白。
  5) 页面里有 4 个 cropper file input（4 个 tab 各一个），
     只有**第一个**（本地上传 tab，rect=0x0）是有效目标。
  6) 弹窗离场后遮罩节点**不消失**（opacity=0 但仍铺满全屏），
     不清掉它会吃掉所有 hover / 坐标点击。
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el, dismiss_stuck_backdrops, purge_modals
import img as img_mod

# 确认按钮候选文案，按优先级
CONFIRM_TEXTS = ["保存图片", "确定使用", "确定", "完成"]

# 「本地上传」tab（叶子节点）
SEL_TAB_LOCAL = ("(()=>{const l=[...document.querySelectorAll('span,div,a')]"
                 ".filter(e=>e.children.length===0 && (e.textContent||'').trim()==='本地上传');"
                 "return l.length? l[l.length-1] : null;})()")

# 主图上传槽位
SEL_SLOT = ("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')]"
            ".filter(e=>String(e.className).includes('upload'));"
            "if(!l.length) return null; return l[l.length-1];})()")

# 主图缩略图计数：'上传图片 1/5' -> '1'
COUNT_JS = ("(()=>{const l=[...document.querySelectorAll('div[class*=thumbnailItem]')]"
            ".filter(t=>t.getBoundingClientRect().width>0);"
            "const t=l.map(e=>(e.innerText||'').replace(/\\s+/g,' ').trim()).join('|');"
            "const m=t.match(/(\\d+)\\s*\\/\\s*5/); return m?m[1]:'0';})()")

# 裁剪画布里是否已有图
IMG_JS = ("(()=>{const im=document.querySelector('div.cropper-container img, .cropper-canvas img');"
          "if(!im) return 'no-img';"
          "return (im.naturalWidth>0)? ('OK '+im.naturalWidth+'x'+im.naturalHeight) : 'empty';})()")


def form_ctx(cdp):
    for x in cdp.contexts():
        if "套餐名称" in x["text"]:
            return x
    return None


def crop_ctx(cdp):
    """定位「上传图片」裁剪弹窗所在的 context。

    ★ 用 offsetWidth 而不是 getBoundingClientRect().width：
      入场动画被冻结时 dialog 是 transform:scale(0)，
      rect 恒为 0x0（会误判成「弹窗没开」），但 offsetWidth 仍是真实布局尺寸 792。
    """
    probe = ("(() => { const d=document.querySelector('div.cropper-body');"
             " if(d && d.offsetWidth>0) return 'YES'; return ''; })()")
    for x in cdp.contexts():
        try:
            if cdp.evaluate(probe, x["id"]) == "YES":
                return x
        except Exception:
            continue
    return find_ctx(cdp, "上传图片", probe=probe)


def count_imgs(cdp, fid):
    v = cdp.evaluate(COUNT_JS, fid)
    return int(v) if v and str(v).isdigit() else 0


def wait_img_loaded(cdp, fid, timeout=25.0):
    """等裁剪画布里真的出现图片（naturalWidth>0）。"""
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout:
        r = cdp.evaluate(IMG_JS, fid)
        last = r or ""
        if last.startswith("OK"):
            return last
        time.sleep(0.8)
    return last or "timeout"


def set_file(cdp, fid, path):
    """把本地文件塞进 cropper 的 file input。

    ★ 两个关键点（都实测过）：
      1) 必须选**第一个** ``input.cropper-upload__upload__input``。
         页面里同时存在 4 个 cropper input（4 个 tab 各一个），
         其中属于「本地上传」tab 的那个 rect=0x0（藏在「上传本地图片」按钮后面），
         但**只有它**是有效目标 —— 设成别的，裁剪画布不会出现图。
      2) CDP 的 ``DOM.setFileInputFiles`` **不会**派发 change 事件，
         必须手动 dispatch 一次，否则组件根本不知道文件来了，
         裁剪画布永远空白、「保存图片」按钮也不会出现。
    """
    r = cdp.send("Runtime.evaluate",
                 expression="document.querySelector('input.cropper-upload__upload__input')",
                 contextId=fid, returnByValue=False)
    oid = r.get("result", {}).get("result", {}).get("objectId")
    if not oid:
        r = cdp.send("Runtime.evaluate", expression="document.querySelector('input[type=file]')",
                     contextId=fid, returnByValue=False)
        oid = r.get("result", {}).get("result", {}).get("objectId")
        print("fallback to input[type=file]")
    if not oid:
        return None
    nid = cdp.send("DOM.requestNode", objectId=oid).get("result", {}).get("nodeId")
    print("setFileInputFiles node", nid)
    cdp.send("DOM.setFileInputFiles", nodeId=nid, files=[path])

    # ★ setFileInputFiles 之后 cropper 组件立刻读到文件并重渲染，
    #   input 可能已经被移除 —— 所以这里 querySelector 常常返回 null，
    #   **这是正常现象，不是错误**（说明组件已经处理完文件了）。
    #   实测：CDP 的 setFileInputFiles 会触发组件的 onChange，
    #   手动再 dispatch 一次反而会让组件处理两遍（第二次 files 已空）。
    #   这里只是「万一没触发」的兜底。
    for attempt in range(2):
        r2 = cdp.evaluate(
            "(()=>{const e=document.querySelector('input.cropper-upload__upload__input');"
            "if(!e) return 'gone(组件已消费文件)';"
            "e.dispatchEvent(new Event('change',{bubbles:true}));"
            "return 'change dispatched';})()", fid)
        if r2 and "dispatched" in str(r2):
            print("dispatch change:", r2)
            break
        print("dispatch change:", r2)
        time.sleep(0.5)
    return nid


def open_cropper(cdp, fid):
    """点主图上传槽位，拉起「上传图片」裁剪弹窗。"""
    print("click 主图上传槽位:", click_el(cdp, fid, SEL_SLOT))
    time.sleep(2.5)
    # ★ 把入场动画推到终态（解冻 scale(0) / pointer-events:none）
    for x in cdp.contexts():
        try:
            cdp.finish_animations(x["id"])
        except Exception:
            pass
    time.sleep(0.6)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep = "--keep" in sys.argv

    cdp = cdp_connect()
    # ★ 先叫醒页面，否则弹窗会卡在入场动画第 0 帧
    cdp.wake()
    time.sleep(0.4)

    form = form_ctx(cdp)
    if form is None:
        print("NO FORM CTX")
        return
    ffid = form["frameId"]

    if args and args[0] == "--status":
        print("THUMBS:", count_imgs(cdp, form["id"]), "/5")
        return

    if not args:
        print("usage: crop_upload.py <文件路径> [--keep]")
        return
    path = args[0]
    if not os.path.isfile(path):
        print("FILE NOT FOUND:", path)
        return

    # ---- 1) 清掉已有主图（幂等）----
    before = count_imgs(cdp, form["id"])
    print("before count:", before, "/5")
    if before > 0:
        if keep:
            print("已有主图，--keep 跳过")
            return
        print("clear:", img_mod.clear_all(cdp, form["id"], ffid))
        before = count_imgs(cdp, form["id"])
        print("after clear:", before, "/5")
        if before > 0:
            print("!! 旧图没清干净，继续上传可能变成多张")

    # ---- 2) 打开裁剪弹窗 ----
    c = crop_ctx(cdp)
    if not c:
        open_cropper(cdp, form["id"])
        c = crop_ctx(cdp)
    if not c:
        print("CROPPER NOT OPEN")
        return
    fid = c["id"]
    print("crop ctx", fid)

    # ★ 推进所有动画到终态：解冻 dialog 的 scale(0) / 按钮 pointer-events:none
    cdp.finish_animations(fid)
    time.sleep(0.5)

    # ---- 3) 切到「本地上传」----
    print("tab:", cdp.js_click(fid, SEL_TAB_LOCAL))
    time.sleep(1.2)
    cdp.finish_animations(fid)
    time.sleep(0.3)

    # ---- 4) 设置本地文件 ----
    if not set_file(cdp, fid, path):
        print("NO FILE INPUT")
        return
    time.sleep(2.5)
    cdp.finish_animations(fid)
    time.sleep(0.4)

    # ---- 5) 确认裁剪框内已有图 ----
    print("cropper content:", wait_img_loaded(cdp, fid))
    cdp.finish_animations(fid)
    time.sleep(0.3)

    # ---- 6) 点确认按钮（「保存图片」优先）----
    #    ★ 合成事件点**内部 span**（button 自身 pointer-events:none），
    #      React onClick 挂在 button 上，事件冒泡即可触发。
    for t in CONFIRM_TEXTS:
        expr = ("(()=>{const b=[...document.querySelectorAll('button')]"
                ".filter(e=>(e.innerText||'').trim()===%s);"
                "if(!b.length) return null; const bt=b[b.length-1];"
                "return bt.querySelector('span')||bt;})()" % json.dumps(t))
        if cdp.evaluate("(()=>{const e=(%s); return e?'YES':'NO';})()" % expr, fid) != "YES":
            print("  no button %s" % t)
            continue
        print("  click %s (span)" % t)
        print("  ->", cdp.js_click(fid, expr))
        time.sleep(3.0)
        # 弹窗离场后遮罩节点不消失（opacity=0 但仍拦截点击）
        print("  cleanup:", purge_modals(cdp, fid))
        after = count_imgs(cdp, form["id"])
        print("  count: %d -> %d /5" % (before, after))
        if after > before:
            print(">>> UPLOAD OK")
            return
        print("  !! count 未增加")

    print("NO CONFIRM BUTTON FOUND")


if __name__ == "__main__":
    main()
