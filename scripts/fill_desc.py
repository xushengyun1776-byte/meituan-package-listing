#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""填写「套餐描述」。数据来自 `上架数据模板.json` 的 package.description 段。
用法: python fill_desc.py
"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect, find_ctx, type_into, dismiss_stuck_backdrops
import cfg

DEFAULT_DESC = ("楚味一人食·自选搭配：荤菜200ml二选一（鱼香肉丝/糖醋里脊/土家酸辣鸡杂/荆州小炒肉/爆炒猪肝/"
                "沔阳粉蒸肉/洪湖农家糍粑鱼/罗田板栗烧鸡任选其一），素菜300ml四选一（时令蔬菜/酸辣土豆丝/"
                "砂锅花菜/砂锅扁豆），加料二选一（荆楚农家水蒸蛋/江汉平原香米），另配江汉平原香米1份。"
                "荆楚风味，一人一餐，热食现做。")

SEL_TA = ("(()=>{const t=document.querySelector('textarea[placeholder*=\"套餐描述\"]'); return t||null;})()")
JS_V = "(()=>{const t=%s; return t? (t.value||'').length + ' :: ' + (t.value||'') : 'NONE';})()"


def load_desc():
    pkg, src = cfg.get_package()
    d = (pkg.get("description") or "").strip()
    return (d or DEFAULT_DESC), src


def main():
    desc, src = load_desc()
    if src:
        print("模板:", src)
    print("desc len =", len(desc))
    if len(desc) > 200:
        print("!! 超过 200 字上限，截断")
        desc = desc[:200]
    cdp = cdp_connect()
    c = find_ctx(cdp, "套餐名称", probe="(()=>document.querySelector('#packSellInfo')?'YES':'')()")
    if not c:
        print("未找到表单 context")
        return
    cid = c["id"]
    print("cleanup:", dismiss_stuck_backdrops(cdp, cid, timeout=2.0))
    print("BEFORE:", cdp.evaluate(JS_V % SEL_TA, cid))
    print("type:", type_into(cdp, cid, SEL_TA, desc, fx=0.2))
    time.sleep(0.6)
    print("AFTER :", cdp.evaluate(JS_V % SEL_TA, cid))


if __name__ == "__main__":
    main()
