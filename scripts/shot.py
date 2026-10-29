#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""截取当前页面（可指定 iframe 内滚动位置）。用法: shot.py <out.png> [scrollExpr]"""
import sys, os, time, base64, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
    cdp = cdp_connect()
    if len(sys.argv) > 2:
        c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
        if c:
            cdp.evaluate(sys.argv[2], c["id"])
            time.sleep(1.2)
    r = cdp.send("Page.captureScreenshot", format="png")
    data = base64.b64decode(r["result"]["data"])
    with open(out, "wb") as f:
        f.write(data)
    print("saved", out, len(data))


if __name__ == "__main__":
    main()
