#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark.py  ——  用 testcases.json 对比「朴素规则 v2」与「当前引擎 v3」
==================================================================
为什么需要这个：自己出题自己打分会过拟合。所以脚本内置一份**朴素基线规则**
（= 市面通用取关工具的典型做法：营销词一刀切 +35、蓝标一律 -25、关注/粉丝
单档判定、老号永远加分），让两套规则在同一套标注样本上跑，用差值证明 v3 的
改进是真实的，而不是测试集太简单。

用法：
    python3 benchmark.py            # 对比总表
    python3 benchmark.py --detail   # 逐条列出基线误删的账号
"""

import json
import re
import sys

import x_score as V3

THRESHOLD = 20


# ============ 基线：朴素规则（≈ v2 / 通用工具的典型做法）============
def naive_score(rec):
    """朴素基线：营销一刀切、蓝标不分真假、比率单档、老号永远加分、无可信豁免。"""
    s = 0
    rs = []
    bio = rec.get("bio") or ""
    name = rec.get("name") or ""
    text = f"{bio} {name}"

    if rec.get("follows_you"):
        s -= 5; rs.append("互关")
    else:
        s += 5; rs.append("未回关")

    if (V3.MARKETING_HARD.search(text) or V3.MARKETING_SOFT.search(text)
            or re.search(r"otc|crypto|nft|web3", text, re.I)):
        s += 35; rs.append("营销/诈骗")

    if V3.AI_RE.search(text):
        s += 20; rs.append("AI化")

    if V3.is_thin(bio):
        s += 15; rs.append("简介空洞")
    else:
        s -= 10; rs.append("简介有实质")

    if rec.get("verified_type"):
        s -= 25; rs.append("蓝标")

    fo = V3.to_num(rec.get("followers"))
    fg = V3.to_num(rec.get("following"))
    if fo and fo >= 10000:
        s -= 15; rs.append("粉丝>1万")
    if fo and fg and fg > fo * 3 and fg > 500:
        s += 15; rs.append("互关党")

    if rec.get("account_age_days") and rec["account_age_days"] > 365 * 3:
        s -= 10; rs.append("老账号")          # ← 基线漏洞：变质号也吃这个加分

    if rec.get("avatar_default"):
        s += 5; rs.append("默认头像")

    return s, rs


def evaluate(fn, cases):
    tp = fp = tn = miss = 0
    fp_detail = []
    for c in cases:
        s, rs = fn(c)
        pred = "cut" if s >= THRESHOLD else "keep"
        truth = c["label"]
        if truth == "cut" and pred == "cut":
            tp += 1
        elif truth == "keep" and pred == "cut":
            fp += 1
            fp_detail.append((c["handle"], s, c.get("note", ""), "、".join(rs)))
        elif truth == "keep":
            tn += 1
        else:
            miss += 1
    n = len(cases)
    return {
        "tp": tp, "tn": tn, "fp": fp, "miss": miss,
        "acc": (tp + tn) / n * 100,
        "fp_rate": fp / (fp + tn) * 100 if (fp + tn) else 0.0,
        "recall": tp / (tp + miss) * 100 if (tp + miss) else 0.0,
        "fp_detail": fp_detail,
    }


def main():
    with open("testcases.json", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    base = evaluate(naive_score, cases)
    cur = evaluate(V3.score, cases)

    print(f"=== 对照评测：{len(cases)} 个标注样本（阈值 {THRESHOLD}）===\n")
    print(f"{'':12}{'朴素基线(通用工具做法)':>22}{'当前引擎 v3':>16}")
    print(f"{'正确删':10}{base['tp']:>22}{cur['tp']:>16}")
    print(f"{'正确留':10}{base['tn']:>22}{cur['tn']:>16}")
    print(f"{'❌ 误删':10}{base['fp']:>22}{cur['fp']:>16}   ← 取关不可撤销，这项最重要")
    print(f"{'⚠️ 漏删':10}{base['miss']:>22}{cur['miss']:>16}")
    print(f"{'-'*52}")
    print(f"{'准确率':10}{base['acc']:>21.1f}%{cur['acc']:>15.1f}%")
    print(f"{'误删率':10}{base['fp_rate']:>21.1f}%{cur['fp_rate']:>15.1f}%")
    print(f"{'召回率':10}{base['recall']:>21.1f}%{cur['recall']:>15.1f}%")
    print(f"{'='*52}")
    print(f"v3 相对基线：减少误删 {base['fp'] - cur['fp']} 例，"
          f"减少漏删 {base['miss'] - cur['miss']} 例")

    if base["fp_detail"] and "--detail" in sys.argv:
        print("\n基线误删明细（v3 已修掉的部分）：")
        for h, s, note, rs in base["fp_detail"]:
            print(f"  @{h:<22}{s:>4}分  {note}")
            print(f"      {rs}")


if __name__ == "__main__":
    main()
