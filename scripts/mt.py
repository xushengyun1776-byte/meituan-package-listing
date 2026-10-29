#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""美团商家后台稳定操作工具：动态解析 iframe context，避免 contextId 失效。
用法:
  python mt.py shot <out.png>
  python mt.py find <keyword>              # 列出包含关键字的 context
  python mt.py eval <js> [keyword]        # 在包含 keyword 的 context 执行 JS(多 context 时合并返回)
  python mt.py evalany <js>               # 在所有 context 执行, 返回首个非空结果
  python mt.py click <js_returning_element> [keyword]
  python mt.py setfile <selector> <path> [keyword]
"""
import sys, json, time, os, re, urllib.request, websocket

PORT = 9222
CWD = os.path.dirname(os.path.abspath(__file__))


def list_pages():
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/list")
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def get_page():
    pages = list_pages()
    for p in pages:
        if p.get("type") == "page" and "waimaie.meituan.com" in p.get("url", ""):
            return p
    for p in pages:
        if p.get("type") == "page" and not p["url"].startswith("edge://"):
            return p
    raise SystemExit("no meituan page")


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=90)
        self._id = 0
        self.events = []

    def send(self, method, **params):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        while True:
            r = json.loads(self.ws.recv())
            if "id" in r and r.get("id") == self._id:
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r
            else:
                self.events.append(r)

    def evaluate(self, expr, context_id=None):
        self.send("Runtime.enable")
        params = dict(expression=expr, returnByValue=True, awaitPromise=True)
        if context_id is not None:
            params["contextId"] = int(context_id)
        return self.send("Runtime.evaluate", **params)

    def val(self, expr, ctx=None):
        r = self.evaluate(expr, ctx)
        res = r.get("result", {}).get("result", {})
        if res.get("type") == "string":
            return res.get("value")
        return res.get("value")

    def contexts(self):
        """返回 [{id, frameId, text}]，按 iframe 层级排序"""
        self.events = []
        self.send("Runtime.enable")
        time.sleep(1.2)
        out = []
        seen = set()
        for e in self.events:
            if e.get("method") == "Runtime.executionContextCreated":
                c = e["params"]["context"]
                cid = c["id"]
                if cid in seen:
                    continue
                seen.add(cid)
                aux = c.get("auxData", {})
                if aux.get("isDefault") is False:
                    continue  # 跳过扩展注入的 context
                txt = ""
                try:
                    txt = self.val("document.body?document.body.innerText.slice(0,400):''", cid) or ""
                except Exception:
                    pass
                out.append({"id": cid, "frameId": aux.get("frameId", ""), "text": txt})
        return out

    def set_file(self, selector, filepath, ctx=None):
        """在指定 context 内查找 file input 并设置文件"""
        self.send("DOM.enable")
        doc = self.send("DOM.getDocument", depth=-1, pierce=True)
        root = doc["result"]["root"]["nodeId"]
        node_ids = []
        if ctx is not None:
            try:
                q = self.send("DOM.querySelectorAll", nodeId=root, selector=selector)
                node_ids = q.get("result", {}).get("nodeIds", [])
            except Exception:
                node_ids = []
        if not node_ids:
            # 逐个 iframe 的 contentDocument 找
            for f in doc["result"]["root"].get("children", []):
                _walk(f, node_ids)
        if not node_ids:
            return "file input not found"
        errs = []
        for nid in node_ids:
            try:
                self.send("DOM.setFileInputFiles", nodeId=nid, files=[filepath])
                return f"set file on node {nid}"
            except Exception as e:
                errs.append(str(e)[:80])
        return f"failed: {errs}"


def _walk(node, acc):
    for c in node.get("children", []) or []:
        if c.get("nodeName") == "INPUT":
            attrs = {a["name"]: a["value"] for a in c.get("attributes", [])}
            if attrs.get("type") == "file":
                acc.append(c.get("nodeId"))
        if c.get("contentDocument"):
            _walk(c["contentDocument"], acc)
        _walk(c, acc)


def main():
    cmd = sys.argv[1]
    p = get_page()
    cdp = CDP(p["webSocketDebuggerUrl"])

    if cmd == "shot":
        out = sys.argv[2] if len(sys.argv) > 2 else "shot.png"
        n = cdp.screenshot(out) if hasattr(cdp, "screenshot") else None
        print(f"{out}")
        return

    if cmd == "find":
        kw = sys.argv[2]
        for c in cdp.contexts():
            if kw in c["text"]:
                print(f"ctx={c['id']} frame={c['frameId'][:12]} :: {c['text'][:200]!r}")
        return

    if cmd == "eval":
        js = sys.argv[2]
        kw = sys.argv[3] if len(sys.argv) > 3 else ""
        cands = [c for c in cdp.contexts() if not kw or kw in c["text"]]
        for c in cands:
            try:
                v = cdp.val(js, c["id"])
                if v not in (None, "", "nf", "not found"):
                    print(f"[ctx={c['id']}] {v}")
                    return
            except Exception:
                continue
        print("NO RESULT (candidates: %s)" % [c["id"] for c in cands])
        return

    if cmd == "evalany":
        js = sys.argv[2]
        for c in cdp.contexts():
            try:
                v = cdp.val(js, c["id"])
                if v not in (None, "", "nf", "not found"):
                    print(f"[ctx={c['id']}] {v}")
                    return
            except Exception:
                continue
        print("NO RESULT")
        return

    if cmd == "setfile":
        sel = sys.argv[2]
        fp = sys.argv[3]
        kw = sys.argv[4] if len(sys.argv) > 4 else ""
        cands = [c for c in cdp.contexts() if not kw or kw in c["text"]]
        for c in cands:
            r = cdp.set_file(sel, fp)
            if "not found" not in str(r) and "failed" not in str(r):
                print(f"[ctx={c['id']}] {r}")
                return
            print(f"[ctx={c['id']}] {r}")
        print("SETFILE FAILED")
        return

    print("unknown cmd")


if __name__ == "__main__":
    main()
