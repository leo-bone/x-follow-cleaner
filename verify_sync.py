#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_sync.py  ——  校验 Python 引擎与浏览器引擎行为是否一致
==================================================================
两个引擎各存一份（x_score.py / x_smart_unfollow.js）是有意为之：浏览器脚本
需要能整段粘贴进控制台，不能依赖外部文件。代价是可能漂移 —— 本脚本就是防漂移的闸门。

用法：python3 verify_sync.py
"""

import json
import os
import shutil
import subprocess
import sys

import x_score as V3

NODE_CANDIDATES = [
    os.environ.get("NODE_BIN", ""),
    shutil.which("node") or "",
    "/Users/leo/.workbuddy/binaries/node/versions/22.22.2-3/bin/node",
]


def find_node():
    for c in NODE_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def main():
    node = find_node()
    if not node:
        print("未找到可用的 node，跳过双引擎校验")
        sys.exit(0)

    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([node, os.path.join(here, "engines_check.js")],
                       capture_output=True, text=True, cwd=here)
    if r.returncode != 0:
        print(f"浏览器引擎执行失败：\n{r.stderr}")
        sys.exit(1)

    js_scores = json.loads(r.stdout.strip().splitlines()[-1])

    cases = json.load(open(os.path.join(here, "testcases.json"), encoding="utf-8"))["cases"]
    diffs = []
    print(f"=== 双引擎一致性校验：{len(cases)} 个用例 ===\n")
    print(f"{'handle':<24}{'Python':>8}{'浏览器':>8}{'判定':>8}")
    print("-" * 50)
    for c in cases:
        py_s, _ = V3.score(c)
        js_s = js_scores.get(c["handle"])
        same = py_s == js_s
        if not same:
            diffs.append((c["handle"], py_s, js_s))
        print(f"{c['handle']:<24}{py_s:>8}{str(js_s):>8}{'一致' if same else '✗ 不一致':>8}")

    print("-" * 50)
    if diffs:
        print(f"\n❌ {len(diffs)} 个用例不一致，两个引擎已漂移，请同步：")
        for h, p, j in diffs:
            print(f"  @{h}: Python={p} 浏览器={j}")
        sys.exit(1)
    print(f"\n✅ 全部 {len(cases)} 个用例分数完全一致（阈值 {V3.SCORE_THRESHOLD} 下判定相同）")


if __name__ == "__main__":
    main()
