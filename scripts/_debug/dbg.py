#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试：定位 #weightUnit 的坐标获取失败原因。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx

def main():
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    if not c:
        print("no ctx"); return
    cid = c["id"]
    print("ctx id:", cid, "frame:", c["frameId"])
    print("has weightUnit:", cdp.evaluate("(()=>{const e=document.querySelector('#weightUnit'); return e? e.outerHTML.slice(0,120):'NONE';})()", cid))
    # 1) evaluate 不带 returnByValue
    try:
        r = cdp.send("Runtime.evaluate", expression="document.querySelector('#weightUnit')",
                     contextId=int(cid), returnByValue=False)
        print("EVAL raw:", json.dumps(r)[:400])
    except Exception as e:
        print("EVAL err:", e); return
    oid = r.get("result", {}).get("result", {}).get("objectId")
    print("objectId:", oid)
    if not oid: return
    # 2) DOM.requestNode
    try:
        rr = cdp.send("DOM.requestNode", objectId=oid)
        print("REQNODE:", json.dumps(rr)[:300])
        nid = rr.get("result", {}).get("nodeId")
    except Exception as e:
        print("REQNODE err:", e); return
    if not nid: return
    # 3) getBoxModel
    try:
        bm = cdp.send("DOM.getBoxModel", nodeId=nid)
        print("BOX:", json.dumps(bm)[:400])
    except Exception as e:
        print("BOX err:", e); return
    # 4) 不带 contextId 的 evaluate
    try:
        r2 = cdp.send("Runtime.evaluate", expression="document.querySelector('#weightUnit')", returnByValue=False)
        oid2 = r2.get("result", {}).get("result", {}).get("objectId")
        print("oid2 (no ctxId):", oid2)
        if oid2:
            nid2 = cdp.send("DOM.requestNode", objectId=oid2).get("result", {}).get("nodeId")
            print("nid2:", nid2)
            if nid2:
                bm2 = cdp.send("DOM.getBoxModel", nodeId=nid2)
                print("BOX2:", json.dumps(bm2)[:400])
    except Exception as e:
        print("no-ctxId err:", e)

if __name__ == "__main__":
    main()
