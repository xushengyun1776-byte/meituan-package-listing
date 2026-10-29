#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配置加载：找 `上架数据模板.json` 并读取指定段。

模板可能在：
  1) 脚本同目录        （工作区扁平布局）
  2) 脚本的上一级目录  （归档 scripts/ 子目录布局）
  3) 上两级目录
找不到时返回内置默认值，不抛异常。
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.join(HERE, "上架数据模板.json"),
    os.path.join(os.path.dirname(HERE), "上架数据模板.json"),
    os.path.join(os.path.dirname(os.path.dirname(HERE)), "上架数据模板.json"),
]

DEFAULT_SELL = {
    "portion": "1人份", "price": "29.9",
    "stock_remain": "10000", "stock_max": "10000",
    "box_fee": "2", "box_fee_unit": "每1份", "sell_time": "全时段售卖",
}
DEFAULT_PACKAGE = {
    "name": "楚味一人食·自选搭配",
    "type": "分组可选套餐",
    "menu_group": "一人食套餐",
    "main_image": "",
    "description": "",
}


def template_path():
    for p in CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def load_template():
    """返回 (template_dict, path)。找不到返回 ({}, None)。"""
    p = template_path()
    if not p:
        return {}, None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f), p
    except Exception:
        return {}, p


def get_sell():
    tpl, src = load_template()
    s = dict(DEFAULT_SELL)
    for k, v in (tpl.get("sell") or {}).items():
        if v is not None:
            s[k] = str(v)
    return s, src


def get_package():
    tpl, src = load_template()
    p = dict(DEFAULT_PACKAGE)
    for k, v in (tpl.get("package") or {}).items():
        if v:
            p[k] = v
    return p, src


def get_groups():
    tpl, src = load_template()
    return (tpl.get("groups") or []), src
