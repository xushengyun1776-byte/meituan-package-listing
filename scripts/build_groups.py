#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 `上架数据模板.json` 的 groups 段批量建规格组。
用法:
  python build_groups.py            # 建所有组（固定商品组会自动改组类型）
  python build_groups.py --dry      # 只打印将要执行的命令
  python build_groups.py --index 1  # 只建第 1 个组
"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cfg

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def load_groups():
    groups, _ = cfg.get_groups()
    return groups


def main():
    dry = "--dry" in sys.argv
    only = None
    if "--index" in sys.argv:
        only = int(sys.argv[sys.argv.index("--index") + 1])
    groups = load_groups()
    for i, g in enumerate(groups):
        if only is not None and i != only:
            continue
        gtype = g.get("type") or "可选商品"
        pickn = str(g.get("pick_n") if g.get("pick_n") else "-")
        cmd = ([PY, os.path.join(HERE, "addgroup.py"), "add", g["name"], gtype, pickn]
               + list(g["items"]))
        print("# 组%d [%s] pickN=%s" % (i, gtype, pickn))
        print("  " + " ".join(cmd))
        if dry:
            continue
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip())
        if r.returncode != 0:
            print("  [ERR]", (r.stderr or "")[-400:])


if __name__ == "__main__":
    main()
