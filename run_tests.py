#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_tests.py  ——  一键跑全部验证
==================================================================
  1. 自检      x_score.py --selftest   标注样本上的准确率 / 误删率
  2. 对照      benchmark.py            与朴素规则（通用工具做法）的差距
  3. 规模      stress_test.py          2000 个模拟账号的分布与稳定性
  4. 同步      verify_sync.py          Python 引擎 vs 浏览器引擎是否漂移

用法：python3 run_tests.py
"""

import subprocess
import sys

PY = sys.executable


def step(title, cmd):
    print(f"\n{'#'*60}\n# {title}\n{'#'*60}")
    r = subprocess.run(cmd, cwd=__file__.rsplit("/", 1)[0] or ".")
    if r.returncode != 0:
        print(f"\n❌ 步骤失败：{title}")
        return False
    return True


def main():
    ok = True
    ok &= step("1/4 自检：标注样本的准确率与误删率", [PY, "x_score.py", "--selftest"])
    ok &= step("2/4 对照：与朴素规则（通用工具做法）的差距", [PY, "benchmark.py", "--detail"])
    ok &= step("3/4 规模：2000 个模拟账号的分布与稳定性", [PY, "stress_test.py", "2000"])
    ok &= step("4/4 同步：Python 引擎 vs 浏览器引擎", [PY, "verify_sync.py"])

    print(f"\n{'='*60}")
    print("✅ 全部验证通过" if ok else "❌ 存在失败项，见上方输出")
    print(f"{'='*60}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
