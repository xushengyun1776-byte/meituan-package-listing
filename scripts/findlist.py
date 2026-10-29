#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""找出承载商品列表的 context，并列出左侧分组。"""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form import cdp_connect

JS = r"""(() => {
  const b = document.body;
  if(!b) return 'nobody';
  const t = b.innerText || '';
  return JSON.stringify({
    len: t.length,
    hasSteamedEgg: t.includes('荆楚农家水蒸蛋'),
    hasYirenshi: t.includes('一人食套餐'),
    hasChuwei: t.includes('楚味一人食'),
    head: t.replace(/\s+/g,' ').slice(0,200),
    side: (()=>{ const o=[]; for(const e of document.querySelectorAll('*')){
        const s=(e.textContent||'').trim(); if(/^一人食套餐/.test(s)&&s.length<30) o.push(e.tagName+'|'+String(e.className).slice(0,40)+'|'+s); }
        return o.join(' ;; ')||'none'; })()
  });
})()"""


def main():
    cdp = cdp_connect()
    for c in cdp.contexts():
        try:
            v = cdp.evaluate(JS, c["id"])
        except Exception:
            continue
        if not v:
            continue
        d = json.loads(v)
        if d.get("len", 0) > 50:
            print(f"ctx {c['id']} frame={c['frameId'][:12]} len={d['len']} "
                  f"egg={d['hasSteamedEgg']} yrs={d['hasYirenshi']} chuwei={d['hasChuwei']}")
            print("   head:", d["head"][:160])
            print("   side:", d["side"][:200])


if __name__ == "__main__":
    main()
