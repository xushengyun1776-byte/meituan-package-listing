#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""探测：商品选择弹窗里到底有哪些商品（用于定位搜不到的名字）。"""
import sys, os, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el
from pick import modal_ctx, type_search, list_names

HERE = os.path.dirname(os.path.abspath(__file__))

JS_MODAL_TEXT = r"""(() => {
  const t = document.body.innerText || '';
  return t.slice(0, 2500);
})()"""

JS_INPUTS = r"""(() => {
  const o=[];
  for(const i of document.querySelectorAll('input')){
    o.push(JSON.stringify({ph:i.placeholder||'', val:i.value||'', type:i.type||''}));
  }
  return o.join(' ;; ') || 'none';
})()"""

JS_FILTERS = r"""(() => {
  const o=[];
  for(const e of document.querySelectorAll('div[class*=tab],span[class*=tab],div[class*=filter],div[class*=menu]')){
    const t=(e.innerText||'').trim();
    if(t && t.length<20) o.push(t);
  }
  return [...new Set(o)].slice(0,40).join(' | ') || 'none';
})()"""


def main():
    subprocess.run([sys.executable, "nav_to_list.py"], cwd=HERE)
    subprocess.run([sys.executable, "nav_new.py"], cwd=HERE)
    cdp = cdp_connect()

    # 找表单
    fid = None
    for c in cdp.contexts():
        if "套餐名称" in c["text"]:
            fid = c["id"]
            break
    if fid is None:
        print("!! 表单未打开")
        return
    print("form ctx", fid)

    # 点第 0 组的「+添加商品」
    add_expr = ("(() => { const list=[]; for(const e of document.querySelectorAll('button')){ "
                "const t=(e.innerText||'').replace(/\\s+/g,''); if(t==='+添加商品'||t==='添加商品') list.push(e); } "
                "return list[0] || null; })()")
    print("open picker:", click_el(cdp, fid, add_expr))
    time.sleep(3.0)

    mc = modal_ctx(cdp)
    if not mc:
        print("!! 弹窗未打开")
        return
    mid = mc["id"]
    print("modal ctx", mid)
    print("\n-- inputs --")
    print(cdp.evaluate(JS_INPUTS, mid))
    print("\n-- filters/tabs --")
    print(cdp.evaluate(JS_FILTERS, mid))
    print("\n-- modal text (前 1800 字) --")
    print((cdp.evaluate(JS_MODAL_TEXT, mid) or "")[:1800])

    for term in ["水蒸蛋", "香米", "荆楚", "江汉平原"]:
        type_search(cdp, mid, term)
        time.sleep(2.0)
        print("\n搜索 %-8s -> %s" % (term, list_names(cdp, mid)[:12]))

    # 清空搜索看默认列表
    type_search(cdp, mid, "")
    time.sleep(2.0)
    print("\n默认列表 -> %s" % list_names(cdp, mid)[:30])


if __name__ == "__main__":
    main()
