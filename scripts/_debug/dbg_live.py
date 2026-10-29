# -*- coding: utf-8 -*-
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect
from clicktext import CDP

def main():
    cdp = cdp_connect()
    ctxs = cdp.contexts()
    print("=== CONTEXTS ===")
    for c in ctxs:
        u = cdp.evaluate("location.href", c["id"]) or ""
        t = cdp.evaluate("document.title", c["id"]) or ""
        print("  id=%s url=%s title=%s" % (c["id"], u[:110], t[:40]))
    print("=== PAGE TEXT (top-level) ===")
    for c in ctxs:
        u = cdp.evaluate("location.href", c["id"]) or ""
        if "editPack" in u or "product" in u:
            body = cdp.evaluate("(()=>{return (document.body.innerText||'').slice(0,600);})()", c["id"]) or ""
            print("  --- ctx %s ---" % c["id"])
            print("  " + body.replace("\n", "\n  ")[:800])

main()
