#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CDP 接管工具：连接 9222 的 Edge，支持新开标签 / 截图 / 执行JS / 点击 / 上传文件。
用法:
  python cdp_helper.py newtab <url> <out_png>          # 新建标签并导航，记录为当前目标
  python cdp_helper.py shot <out_png> [target_id]      # 对当前(或指定)标签截图
  python cdp_helper.py eval <js> [target_id]           # 执行 JS
  python cdp_helper.py click <selector> [target_id]    # JS 点击元素
  python cdp_helper.py fill <selector> <value> [target_id]  # 给 input/textarea 赋值并触发input事件
  python cdp_helper.py setfile <selector> <filepath> [target_id]  # 上传文件到 <input type=file>
  python cdp_helper.py navigate <url> <out_png> [target_id]      # 导航当前(或指定)标签
"""
import json, base64, sys, time, os, re, urllib.request, urllib.parse, websocket

TID_RE = re.compile(r"^[0-9A-F]{32}$")

PORT = 9222
CWD = os.path.dirname(os.path.abspath(__file__))
TARGET_FILE = os.path.join(CWD, ".cdp_target")


def list_pages():
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/list")
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def get_page(target_id=None):
    pages = list_pages()
    if target_id:
        for p in pages:
            if p.get("id") == target_id:
                return p
        raise SystemExit(f"target {target_id} not found")
    # 默认用记录的当前目标
    if os.path.exists(TARGET_FILE):
        tid = open(TARGET_FILE).read().strip()
        for p in pages:
            if p.get("id") == tid and p.get("type") == "page":
                return p
    for p in pages:
        if p.get("type") == "page" and not p["url"].startswith("edge://"):
            return p
    for p in pages:
        if p.get("type") == "page":
            return p
    raise SystemExit("no page found")


def new_tab(url):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?{urllib.parse.quote(url)}", method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
    open(TARGET_FILE, "w").write(resp["id"])
    return resp


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
                # 没有 id 的是事件，缓存起来
                self.events.append(r)

    def navigate(self, url):
        self.send("Page.enable")
        return self.send("Page.navigate", url=url)

    def wait(self, ms):
        time.sleep(ms / 1000.0)

    def screenshot(self, path, quality=90):
        r = self.send("Page.captureScreenshot", format="png")
        data = base64.b64decode(r["result"]["data"])
        open(path, "wb").write(data)
        return len(data)

    def evaluate(self, expr, context_id=None):
        self.send("Runtime.enable")
        params = dict(expression=expr, returnByValue=True, awaitPromise=True)
        if context_id is not None:
            params["contextId"] = int(context_id)
        return self.send("Runtime.evaluate", **params)

    def collect_contexts(self):
        """收集所有 execution contexts（含 iframe），返回 [{id, name, frameId, aux}]"""
        self.events = []
        self.send("Runtime.enable")
        time.sleep(2.5)
        ctxs = []
        for e in self.events:
            if e.get("method") == "Runtime.executionContextCreated":
                ctxs.append(e["params"]["context"])
        # 也补一次 getDraft？直接返回
        return ctxs

    def find_context(self, keyword):
        """遍历所有 context，返回 body 文本包含 keyword 的 contextId"""
        ctxs = self.collect_contexts()
        for c in ctxs:
            try:
                r = self.evaluate(
                    f"document.body?document.body.innerText.slice(0,300):''", c["id"])
                txt = r.get("result", {}).get("result", {}).get("value", "")
                if keyword in txt:
                    return c["id"]
            except Exception:
                continue
        return None

    def set_file(self, selector, filepath):
        # 用 DOM domain + pierce 穿透 iframe 拿到 nodeId 再 setFileInputFiles
        self.send("DOM.enable")
        doc = self.send("DOM.getDocument", depth=-1, pierce=True)
        root = doc["result"]["root"]["nodeId"]
        try:
            q = self.send("DOM.querySelector", nodeId=root, selector=selector)
        except Exception as e:
            return f"query error: {e}"
        node_id = q.get("result", {}).get("nodeId")
        if not node_id:
            return "element not found"
        return self.send("DOM.setFileInputFiles", nodeId=node_id, files=[filepath])

    def get_iframe_boxes(self):
        self.send("DOM.enable")
        doc = self.send("DOM.getDocument", depth=-1, pierce=True)
        root = doc["result"]["root"]["nodeId"]
        try:
            q = self.send("DOM.querySelectorAll", nodeId=root, selector="iframe")
        except Exception as e:
            return [f"query error: {e}"]
        nids = q.get("result", {}).get("nodeIds", [])
        res = []
        for nid in nids:
            try:
                bm = self.send("DOM.getBoxModel", nodeId=nid)
                res.append(bm["result"]["model"]["content"])
            except Exception as e:
                res.append(f"err:{e}")
        return res

    def click_xy(self, x, y):
        self.send("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y,
                  button="left", clickCount=1)
        self.send("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y,
                  button="left", clickCount=1)
        return f"clicked {x},{y}"

    def press_key(self, key):
        self.send("Input.dispatchKeyEvent", type="keyDown", key=key)
        self.send("Input.dispatchKeyEvent", type="keyUp", key=key)
        return f"pressed {key}"

    def fill(self, selector, value, context_id=None):
        expr = (
            f"""(() => {{
                const el = document.querySelector({selector!r});
                if (!el) return 'no element';
                const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
                            : el.tagName === 'SELECT' ? HTMLSelectElement.prototype
                            : HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                setter.call(el, {value!r});
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                return 'filled';
            }})()"""
        )
        return self.evaluate(expr, context_id)

    def click(self, selector, context_id=None):
        expr = (
            f"""(() => {{
                const el = document.querySelector({selector!r});
                if (!el) return 'no element';
                el.click();
                return 'clicked';
            }})()"""
        )
        return self.evaluate(expr, context_id)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if cmd == "newtab":
        url = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 else "shot.png"
        resp = new_tab(url)
        cdp = CDP(resp["webSocketDebuggerUrl"])
        cdp.wait(7000)
        size = cdp.screenshot(out)
        print(f"newtab -> {url}\ntarget_id={resp['id']}\nscreenshot: {out} ({size} bytes)")
        return
    # 其余命令都需要目标标签
    target_id = sys.argv[-1] if len(sys.argv) > 2 and TID_RE.match(sys.argv[-1]) else None
    p = get_page(target_id)
    cdp = CDP(p["webSocketDebuggerUrl"])
    # 当前 iframe 上下文（商品内容在 iframe 内）
    CTX_FILE = os.path.join(CWD, ".cdp_ctx")
    cur_ctx = open(CTX_FILE).read().strip() if os.path.exists(CTX_FILE) else None

    def parse_ctx():
        # 命令行若显式给了 contextId 则优先
        if len(sys.argv) > 2 and TID_RE.match(sys.argv[-1]):
            return sys.argv[-1]
        return cur_ctx

    if cmd == "shot":
        out = sys.argv[2] if len(sys.argv) > 2 else "shot.png"
        size = cdp.screenshot(out)
        print(f"screenshot: {out} ({size} bytes)")
    elif cmd == "ctxs":
        ctxs = cdp.collect_contexts()
        for c in ctxs:
            try:
                r = cdp.evaluate("document.body?document.body.innerText.slice(0,120):''", c["id"])
                snippet = r.get("result", {}).get("result", {}).get("value", "")
            except Exception:
                snippet = ""
            print(f"ctx={c['id']} name={c.get('name','')} frame={c.get('auxData',{}).get('frameId','')[:12]} | {snippet[:100]!r}")
    elif cmd == "usectx":
        cid = sys.argv[2]
        open(CTX_FILE, "w").write(cid)
        print(f"set current ctx -> {cid}")
    elif cmd == "navigate":
        url = sys.argv[2]
        out = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("target") else "shot.png"
        cdp.navigate(url)
        cdp.wait(7000)
        size = cdp.screenshot(out)
        print(f"navigated -> {url}\nscreenshot: {out} ({size} bytes)")
    elif cmd == "reload":
        cdp.send("Page.reload")
        cdp.wait(6000)
        print("reloaded")
    elif cmd == "iframebox":
        boxes = cdp.get_iframe_boxes()
        for i, b in enumerate(boxes):
            print(f"iframe[{i}]={b}")
    elif cmd == "clickxy":
        x = int(sys.argv[2]); y = int(sys.argv[3])
        print(cdp.click_xy(x, y))
    elif cmd == "presskey":
        print(cdp.press_key(sys.argv[2]))
    elif cmd == "eval":
        expr = sys.argv[2]
        r = cdp.evaluate(expr, parse_ctx())
        print(json.dumps(r.get("result", {}).get("result", {}), ensure_ascii=False))
    elif cmd == "click":
        sel = sys.argv[2]
        print(cdp.click(sel, parse_ctx()))
    elif cmd == "fill":
        sel = sys.argv[2]
        val = sys.argv[3]
        print(cdp.fill(sel, val, parse_ctx()))
    elif cmd == "setfile":
        sel = sys.argv[2]
        fp = sys.argv[3]
        print(cdp.set_file(sel, fp))
    else:
        print("unknown cmd")


if __name__ == "__main__":
    main()
