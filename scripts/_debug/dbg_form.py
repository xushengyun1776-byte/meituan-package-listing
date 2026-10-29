#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断：表单规格组区域的实际 DOM 结构 + 关掉残留的商品选择弹窗。"""
import sys, os, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, click_el, click_menu_item
from pick import modal_ctx

JS_DUMP = r"""(() => {
  const out=[];
  // 找所有含「规格」「分组」「添加商品分组」的元素
  const hits=[...document.querySelectorAll('*')].filter(e=>{
    const t=(e.innerText||'').trim();
    return t && t.length<40 && /添加商品分组|本组商品|规格/.test(t);
  });
  for(const h of hits.slice(0,6)){
    out.push('HIT '+h.tagName+'.'+String(h.className).slice(0,50)+' :: '+(h.innerText||'').trim().slice(0,40));
  }
  // 列出 class 名里含 group / sku / spec 的容器
  const cls=new Set();
  for(const e of document.querySelectorAll('div[class]')){
    const c=String(e.className);
    if(/group|sku|spec/i.test(c)) cls.add(c.split(' ')[0]);
  }
  out.push('CLASSES: '+[...cls].slice(0,40).join(' | '));
  // 统计可能的组容器
  for(const sel of ['div[class*=groupWrap]','div[class*=groupName]','div[class*=skuSum]','div[class*=skuCount]','input[class*=groupName]','div[class*=groupType]']){
    out.push(sel+' -> '+document.querySelectorAll(sel).length);
  }
  return out.join('\n');
})()"""

JS_BTN = r"""(() => {
  const o=[];
  for(const b of document.querySelectorAll('button')){
    const t=(b.innerText||'').replace(/\s+/g,'').trim();
    if(t && t.length<14) o.push(t+'@'+Math.round(b.getBoundingClientRect().x)+','+Math.round(b.getBoundingClientRect().y));
  }
  return o.join(' | ')||'none';
})()"""


def main():
    cdp = cdp_connect()
    # 1) 关掉残留弹窗
    m = modal_ctx(cdp)
    if m:
        expr = ("(() => { for(const e of document.querySelectorAll('button,span')){ "
                "const t=(e.innerText||'').trim(); if(t==='取消'&&e.children.length===0) return e; } return null; })()")
        print("close modal:", click_menu_item(cdp, m["id"], expr))
        time.sleep(2.0)
        print("modal still:", modal_ctx(cdp))

    # 2) 找表单 ctx
    fid = None
    for c in cdp.contexts():
        if "套餐名称" in c["text"]:
            fid = c["id"]
            break
    if fid is None:
        print("!! 表单未打开")
        for c in cdp.contexts():
            print("  ", c["id"], repr(c["text"][:60]))
        return
    print("\nform ctx", fid)
    print("\n-- buttons --")
    print(cdp.evaluate(JS_BTN, fid))
    print("\n-- 规格组结构 --")
    print(cdp.evaluate(JS_DUMP, fid))


if __name__ == "__main__":
    main()
