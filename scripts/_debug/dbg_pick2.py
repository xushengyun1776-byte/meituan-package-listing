# -*- coding: utf-8 -*-
"""验证：清空已选 -> 切分组 -> 勾选商品 的完整链路 + 两种勾选方式对比。"""
import sys, time, json
sys.path.insert(0, '.')
from form import cdp_connect
from pick import modal_ctx

# 主列表商品卡（x<600）；已选区卡片在右侧 x>=625
MAIN_CARD = r'''(()=>{const o=[];for(const e of document.querySelectorAll('div[class*=product-card]')){
 const r=e.getBoundingClientRect(); if(r.x>600) continue;
 const t=(e.innerText||'').trim().split('\n')[0]; if(t) o.push(t);} return o.join(' | ');})()'''
SEL_CARD = r'''(()=>{const o=[];for(const e of document.querySelectorAll('div[class*=product-card]')){
 const r=e.getBoundingClientRect(); if(r.x<600) continue;
 const t=(e.innerText||'').trim().split('\n')[0]; if(t) o.push(t);} return o.join(' | ');})()'''


def card_expr(name, in_sel=False):
    """定位商品卡内的勾选框"""
    cond = "r.x>=600" if in_sel else "r.x<600"
    return ("(()=>{for(const e of document.querySelectorAll('div[class*=product-card]')){"
            "const r=e.getBoundingClientRect(); if(!(%s)) continue;"
            "const t=(e.innerText||'').trim().split('\\n')[0].trim();"
            "if(t===%s){ const cb=e.querySelector('span.custom-checkbox');"
            "  if(cb) return cb; const lbl=e.querySelector('span.custom-checkbox-label');"
            "  if(lbl) return lbl; } } return null;})()" % (cond, json.dumps(name)))


def tree_click(cdp, cid, group):
    """点左侧分组树上的某个分组"""
    js = ("(()=>{const a=[...document.querySelectorAll('div[class*=tag-list-item]')];"
          "for(const e of a){const c=e.querySelector('div[class*=content]');"
          "if(c && (c.innerText||'').trim()===%s) return e;} return null;})()"
          % json.dumps(group))
    return cdp.js_click(cid, js)


def main():
    cdp = cdp_connect()
    m = modal_ctx(cdp)
    if not m:
        print("NO MODAL")
        return
    mid = m["id"]
    print("modal ctx", mid)
    print("已选(前):", cdp.evaluate(SEL_CARD, mid))
    print("主列表(前):", str(cdp.evaluate(MAIN_CARD, mid))[:120])

    # --- 1. 清空已选 ---
    r = cdp.js_click(mid, "(()=>{const b=[...document.querySelectorAll('button')].find(e=>(e.innerText||'').trim()==='清空');return b||null;})()")
    print("\n[清空] js_click ->", r)
    time.sleep(1.5)
    print("  已选(后):", repr(cdp.evaluate(SEL_CARD, mid)))

    # --- 2. 切分组 ---
    r = tree_click(cdp, mid, "湖乡下饭 —😍—")
    print("\n[切分组] ->", r)
    time.sleep(1.8)
    print("  主列表:", str(cdp.evaluate(MAIN_CARD, mid))[:200])

    # --- 3. 勾选 A: js_click ---
    target = "荆州小炒肉"
    print("\n[勾选A js_click]", target)
    r = cdp.js_click(mid, card_expr(target))
    print("  ->", r)
    time.sleep(1.2)
    print("  已选:", cdp.evaluate(SEL_CARD, mid))
    print("  主列表:", str(cdp.evaluate(MAIN_CARD, mid))[:200])

    # --- 4. 再勾一个：坐标点击 ---
    target2 = "爆炒猪肝"
    print("\n[勾选B 坐标]", target2)
    pos = cdp.page_coords(mid, card_expr(target2))
    print("  coords:", pos)
    if pos:
        cdp.click_xy(pos[0], pos[1])
        time.sleep(1.2)
    print("  已选:", cdp.evaluate(SEL_CARD, mid))


if __name__ == "__main__":
    main()
