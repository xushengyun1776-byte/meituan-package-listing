# -*- coding: utf-8 -*-
"""遍历「选择商品」弹窗左侧分组树，输出每个分组下的商品列表。"""
import sys, time, json
sys.path.insert(0, '.')
from form import cdp_connect
from pick import modal_ctx

CARDS = r'''(()=>{const o=[];for(const e of document.querySelectorAll('div[class*=product-card]')){
 const t=(e.innerText||'').trim().split('\n')[0]; if(t) o.push(t);} return o.join(' | ');})()'''

TREE_ITEM = "document.querySelectorAll('div[class*=tag-list-item]')"


def tree_names(cdp, cid):
    js = ("(()=>{const a=[...document.querySelectorAll('div[class*=tag-list-item]')]"
          ".map(e=>{const c=e.querySelector('div[class*=content]');return c?(c.innerText||'').trim():'';})"
          ".filter(Boolean); return JSON.stringify(a);})()")
    return json.loads(cdp.evaluate(js, cid, strict=True) or "[]")


def main():
    cdp = cdp_connect()
    m = modal_ctx(cdp)
    if not m:
        print("NO MODAL")
        return
    mid = m["id"]
    names = tree_names(cdp, mid)
    print("分组数:", len(names))
    mapping = {}
    for i, nm in enumerate(names):
        expr = "(document.querySelectorAll('div[class*=tag-list-item]')[%d])" % i
        r = cdp.js_click(mid, expr)
        time.sleep(1.6)
        cards = cdp.evaluate(CARDS, mid) or ""
        items = [x.strip() for x in cards.split("|") if x.strip()]
        # 去重保序
        uniq = []
        for x in items:
            if x not in uniq:
                uniq.append(x)
        mapping[nm] = uniq
        print("[%d] %-18s (%s) -> %s" % (i, nm, r, ", ".join(uniq) if uniq else "(空)"))
    print()
    print("=== JSON ===")
    print(json.dumps(mapping, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
