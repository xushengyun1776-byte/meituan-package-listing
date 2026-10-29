#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""管理「商品图片」上传区：查看当前缩略图 / 删除 / 上传新图。
用法:
  python img.py status
  python img.py clear            # 删除全部已上传图片
  python img.py upload <文件路径>
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, click_el, purge_modals

NL = chr(10)


def form_ctx(cdp):
    return find_ctx(cdp, "套餐名称",
                    probe="(()=>document.querySelector('input.groupName_RJkgVI')?'YES':'')()")


def thumbs(cdp, fid):
    js = """(() => {
      const out=[];
      const list=document.querySelectorAll('div[class*=thumbnailItem], div[class*=thumbnail-item]');
      for (const t of list) {
        const r=t.getBoundingClientRect();
        if (r.width<=0) continue;
        const img=t.querySelector('img');
        const del=t.querySelector('i,span,button');
        out.push(JSON.stringify({
          cls:String(t.className).slice(0,40),
          hasImg:!!img,
          src: img? (img.src||'').slice(0,90) : '',
          inner: (t.innerText||'').replace(/\\s+/g,' ').slice(0,30),
          delCls: del? (del.tagName+'.'+String(del.className).slice(0,30)) : ''
        }));
      }
      return out.join(' ;; ');
    })()"""
    return cdp.evaluate(js, fid)


def upload(cdp, fid, path, click_target=None):
    """先点击目标上传位（让 file input 绑定该槽位），再设置文件并派发 change。"""
    if click_target:
        print("  click slot:", click_el(cdp, fid, click_target))
        time.sleep(1.2)
    r = cdp.send("Runtime.evaluate", expression="document.querySelector('input[type=file]')", contextId=fid)
    oid = r.get("result", {}).get("result", {}).get("objectId")
    if not oid:
        return "no file input"
    nid = cdp.send("DOM.requestNode", objectId=oid).get("result", {}).get("nodeId")
    cdp.send("DOM.setFileInputFiles", nodeId=nid, files=[path])
    time.sleep(0.8)
    cdp.evaluate("(function(){const i=document.querySelector('input[type=file]');"
                 "if(i) i.dispatchEvent(new Event('change',{bubbles:true}));})()", fid)
    time.sleep(4.5)
    return f"uploaded {path}"


def clear_all(cdp, fid, ffid):
    """删除每张已上传的主图。

    ★ 删除按钮是 ``IMG.closeIcon_tHGthP``，常态 ``display:none``（hover 才显现）。
    ★ ★ **必须用 JS 合成事件，不能用坐标点击**：
        - 坐标点击要先 hover 缩略图让按钮显现；
        - 但 hover 会同时弹出 ``DIV.roo-tooltip``，**tooltip 正好盖在删除按钮上**
          （实测 iframe 内 elementFromPoint 命中的是 tooltip 而不是 closeIcon）
          → 坐标点击全部落空，极难定位。
      合成事件不走 hit-test，直接派发给 closeIcon 即可，
      React onClick 正常触发（冒泡到 li 的处理器）。
    ★ 派发前先 purge_modals()：弹窗离场后 ``div.roo-modal`` 遮罩节点不会被移除
      （opacity=0 但仍铺满全屏），会吃掉所有 hover / 坐标点击。
    ★ 只删 ``ul[class*=thumbnailList] > li``（已上传的），
      不碰 class 含 ``upload`` 的那个（那是「+」上传槽位）。
    ★ 顺便：每张图的 ``div[class*=operateBtnWrapper]`` 里还有一个「替换」按钮，
      需要换图（而不是新增一张）时可以用它。
    """
    JS_CLICK_CLOSE = """(() => {
      const li=[...document.querySelectorAll('ul[class*=thumbnailList] > li')]
        .filter(t=>!String(t.className).includes('upload'));
      if(!li.length) return 'NO-LI';
      const c=li[0].querySelector('img[class*=closeIcon], i[class*=closeIcon]');
      if(!c) return 'NO-CLOSE';
      c.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window}));
      return 'clicked';
    })()"""
    JS_COUNT = """(() => {
      const l=[...document.querySelectorAll('ul[class*=thumbnailList] > li')]
        .filter(t=>!String(t.className).includes('upload'));
      return l.length;
    })()"""
    n0 = cdp.evaluate(JS_COUNT, fid)
    try:
        n0 = int(n0)
    except Exception:
        n0 = 0
    n = n0
    for _ in range(8):
        try:
            purge_modals(cdp, fid)
        except Exception:
            pass
        if n <= 0:
            break
        r = cdp.evaluate(JS_CLICK_CLOSE, fid)
        if not r or str(r).startswith("NO"):
            print("  [clear] %s" % r)
            break
        time.sleep(1.8)
        # 可能有二次确认
        cdp.evaluate(r"""(()=>{const b=[...document.querySelectorAll('button')]
            .filter(e=>/^(确\s*定|确定)$/.test((e.innerText||'').trim()));
            if(b.length){ const s=b[b.length-1].querySelector('span')||b[b.length-1];
              s.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,view:window})); return 'confirmed'; }
            return '';})()""", fid)
        time.sleep(1.2)
        n -= 1
    left = cdp.evaluate(JS_COUNT, fid)
    try:
        left = int(left)
    except Exception:
        left = 0
    return f"deleted {n0 - left} (left {left})"


if __name__ == "__main__":
    cdp = cdp_connect()
    f = form_ctx(cdp)
    if not f:
        print("FORM NOT FOUND")
        raise SystemExit(1)
    fid, ffid = f["id"], f["frameId"]
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode == "status":
        print("THUMBS:", thumbs(cdp, fid))
    elif mode == "clear":
        print("CLEAR:", clear_all(cdp, fid, ffid))
        print("THUMBS:", thumbs(cdp, fid))
    elif mode == "upload":
        print("UPLOAD:", upload(cdp, fid, sys.argv[2]))
        print("THUMBS:", thumbs(cdp, fid))
