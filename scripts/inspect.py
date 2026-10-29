#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""连接 9222 的饿了么/美团标签，按 contextId 打印页面结构。
用法: python inspect.py <ctx_id> [keyword_filter]
"""
import sys, json, time, os, re, urllib.request, websocket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp_helper import list_pages, CDP

TID_RE = re.compile(r"^[0-9A-F]{32}$")

def get_target(target_id=None):
    pages = list_pages()
    if target_id:
        for p in pages:
            if p.get("id") == target_id:
                return p
    for p in pages:
        if p.get("type") == "page" and not p["url"].startswith("edge://"):
            return p
    raise SystemExit("no page")

def main():
    ctx = sys.argv[1]
    kw = sys.argv[2] if len(sys.argv) > 2 else ""
    tid = None
    if len(sys.argv) > 3 and TID_RE.match(sys.argv[3]):
        tid = sys.argv[3]
    p = get_target(tid)
    cdp = CDP(p["webSocketDebuggerUrl"])
    cdp.send("Runtime.enable")
    time.sleep(1.5)
    js = r"""
    (() => {
      const out = {inputs:[], buttons:[], links:[], clickable:[], tree:[]};
      const all = document.querySelectorAll('*');
      const seen = new Set();
      for (const e of all) {
        const tag = e.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
          out.inputs.push({tag, type:e.type, id:e.id, name:e.name, ph:e.placeholder, val:e.value, cls:String(e.className).slice(0,50)});
        }
        if (tag === 'BUTTON') {
          const t = (e.innerText||'').trim().slice(0,30);
          if (t) out.buttons.push({t, cls:String(e.className).slice(0,50), id:e.id});
        }
        if (tag === 'A' && (e.innerText||'').trim()) {
          out.links.push((e.innerText||'').trim().slice(0,40));
        }
      }
      // 收集含关键字的可见可点击文本元素
      const kw = %s;
      const walk = (node, depth) => {
        if (depth > 6) return;
        const t = (node.innerText||'').replace(/\s+/g,' ').trim();
        if (t && t.length<=40 && node.children.length===0) {
          if (!kw || t.includes(kw)) {
            out.tree.push(t);
          }
        }
        for (const c of node.children) walk(c, depth+1);
      };
      walk(document.body, 0);
      return JSON.stringify(out);
    })()
    """ % json.dumps(kw)
    r = cdp.evaluate(js, ctx)
    res = r.get("result", {}).get("result", {})
    if "value" in res:
        data = json.loads(res["value"])
        print(f"=== ctx {ctx} (frame {p.get('id','')[:8]}) kw={kw!r} ===")
        print("--- INPUTS/TEXTAREA/SELECT ---")
        for i in data["inputs"]:
            print(f"  [{i['tag']}] type={i['type']!r} id={i['id']!r} name={i['name']!r} ph={i['ph']!r} val={i['val']!r} cls={i['cls']!r}")
        print("--- BUTTONS ---")
        for b in data["buttons"]:
            print(f"  {b['t']!r} id={b['id']!r} cls={b['cls']!r}")
        print("--- KEYWORD NODES ---")
        for t in data["tree"][:40]:
            print(f"  {t!r}")
    else:
        print("NO VALUE:", json.dumps(res, ensure_ascii=False)[:500])

if __name__ == "__main__":
    main()
