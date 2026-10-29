#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核对套餐规格组（名称/类型/已选商品/选N）。

★ 复用 addgroup.group_state —— 那套选择器不依赖 CSS Module 哈希类名，
  比这里原本写死的 groupWrap_EMuN4h / skuSum_M7Iow8 抗发版。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx
from addgroup import group_state, form_ctx


def main():
    cdp = cdp_connect()
    c = form_ctx(cdp)
    if not c:
        print("未找到新建套餐表单 context")
        return
    cid = c["id"]
    st = group_state(cdp, cid)
    if not st:
        print("未读到任何规格组（表单可能还没渲染完）")
        return
    print("共 %d 个规格组：" % len(st))
    for g in st:
        print("  [%d] 名称=%r 类型=%r %r 选N=%s" % (g["i"], g["name"], g["type"], g["sum"], g["pickN"]))
        for it in g["items"]:
            print("        - %s" % it)


if __name__ == "__main__":
    main()
