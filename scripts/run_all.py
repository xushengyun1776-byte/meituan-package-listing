#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键跑完整条「新建分组可选套餐」流水线。数据全部来自 `上架数据模板.json`。

用法:
  python run_all.py                 # 跑到「保存并返回」为止（会真的上架！）
  python run_all.py --no-save       # 只填表不提交（用于演练/验收）
  python run_all.py --skip-groups   # 跳过规格组构建（组已存在时）

⚠️ 默认模式会真的保存并上架。演练请加 --no-save。
"""
import sys, os, time, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable

import cfg


def run(script, *args, label=None):
    cmd = [PY, os.path.join(HERE, script)] + [str(a) for a in args]
    print("\n>>> %s" % (label or script))
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print("  [ERR rc=%s] %s" % (r.returncode, (r.stderr or "")[-600:]))
    return r.returncode == 0


def main():
    no_save = "--no-save" in sys.argv
    skip_groups = "--skip-groups" in sys.argv
    skip_image = "--skip-image" in sys.argv

    groups, src = cfg.get_groups()
    pkg, _ = cfg.get_package()
    if not src:
        print("[warn] 找不到 上架数据模板.json，用内置默认值")
    print("模板:", src or "(内置默认值)")

    # 0) 确保在商品列表页 -> 打开「新建套餐」表单
    run("nav_to_list.py", label="步骤0a 回到商品列表页")
    run("nav_new.py", label="步骤0b 打开新建套餐表单")
    time.sleep(2.0)

    # 1) 名称 + 套餐类型 + 菜单分组
    run("fill_package.py", label="步骤1 名称/类型/菜单分组")

    # 2) 规格组
    if not skip_groups:
        for i, g in enumerate(groups):
            gtype = g.get("type") or "可选商品"
            pickn = str(g.get("pick_n") if g.get("pick_n") else "-")
            # addgroup add 会一次性完成：建组 -> 填名 -> 设组类型 -> 选商品 -> 设选N
            run("addgroup.py", "add", g["name"], gtype, pickn, *g["items"],
                label="步骤2.%d 建组[%s] 类型=%s 选N=%s" % (i, g["name"], gtype, pickn))

    # 3) 核对规格组
    run("addgroup.py", "show", label="步骤3 规格组核对")

    # 4) 主图
    img = pkg.get("main_image")
    if skip_image:
        print("\n[skip] --skip-image：跳过主图上传")
    elif img and os.path.isfile(img):
        # crop_upload.py 自包含：清旧图 -> 打开裁剪弹窗 -> 本地上传 -> 保存 -> 校验计数
        run("crop_upload.py", img, label="步骤4 上传主图")
        run("img.py", "status", label="步骤4b 图片计数")
    else:
        print("\n[skip] 主图不存在：%s" % img)

    # 5) 售卖信息
    run("fill_sell.py", label="步骤5 售卖信息")
    # 6) 套餐描述
    run("fill_desc.py", label="步骤6 套餐描述")
    # 7) 截图存档
    run("shot.py", "run_all_售卖信息.png", "(()=>{const s=document.querySelector('#packSellInfo'); if(s) s.scrollIntoView({block:'start'}); window.scrollBy(0,-90); return 1;})()",
        label="步骤7 截图存档")

    if no_save:
        print("\n=== --no-save：已填完，未提交。可用 cancel_draft.py 或 history.back() 放弃 ===")
        return

    # 8) 保存
    run("pre_save.py", label="步骤8a 定位保存按钮")
    run("save.py", label="步骤8b 保存并返回")
    print("\n=== 完成，请用 open_group.py 核验列表 ===")


if __name__ == "__main__":
    main()
