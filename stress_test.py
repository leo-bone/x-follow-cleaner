#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stress_test.py  ——  规模压力测试（模拟 2000 个关注账号）
==================================================================
32 个人工样本能过，不代表 3000 个真实关注也能过。本脚本按 X 关注列表的
经验分布随机生成 2000 个账号（每类生成时就带标准答案 label），用来验证：
  1. 引擎在大规模下的准确率 / 误删率是否稳定（不靠 32 个样本过拟合）
  2. 分数分布是否合理 —— 最怕的是「一刀切把大半关注都判成该删」
  3. 各类账号的识别能力（分类召回矩阵）

⚠️ 诚实说明：这是**模拟器**，不是真实数据。价值在于规模稳定性和分布合理性，
   真实效果仍须以你导出的 following_audit.json 为准。

用法：
    python3 stress_test.py            # 默认 2000 个
    python3 stress_test.py 3000       # 指定规模
"""

import json
import random
import sys

import x_score as V3

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
TH = V3.SCORE_THRESHOLD

REAL_BIOS = [
    "Photographer. Coffee. Mountains.", "Writer and dad. Essays on ordinary life.",
    "Building things on the internet.", "Product designer at a startup.",
    "跑步、读书、写代码", "前端工程师，喜欢做小工具", "Two kids, one dog, zero sleep.",
    "Indie hacker, shipping small tools.", "喜欢旅行和摄影的普通人",
    "Data scientist. Cycling. Bad jokes.", "教师。记录日常。",
    "SRE. On-call survivor.", "读书笔记 / 生活碎片", "Trying to grow tomatoes.",
]
SPAM_BIOS = [
    "crypto airdrop 加微信 返利 telegram", "代购 引流 加微信 返利 全自动",
    "follow back follow back get followers free follow", "casino bet slot 博彩 彩票 日入过万",
    "被动收入 月入十万 拉人头 多级 加盟", "link in bio linktr.ee dm me promo code",
    "forex signals, fully automated, 24/7, dm me", "otc 跑分 代投 收币 出金",
    "🔥🔥🔥", "buy followers cheap, click here",
]
AI_BIOS = [
    "fully automated AI news 24/7 auto-post", "AI 每日快讯：自动抓取 AI 新闻，定时推送",
    "ai-powered content, auto-tweet every hour 🤖", "机器人号，全网自动推送",
    "AI agent that posts market summaries", "每日 slot 推荐，自动更新赔率",
]
PRO_BIOS = [
    "Crypto researcher, ex-JP Morgan. Writing on market structure.",
    "Smart contract auditor. 智能合约审计. 兼职接单",
    "独立开发者，做开源项目，偶尔推广自己的产品",
    "Growth marketer, ex-Uber. I write about 增长 and 推广 策略.",
    "Journalist covering blockchain policy. Tips: signal.",
    "AI researcher. Working on multimodal LLM alignment.",
    "Equity analyst covering OTC markets and small caps. CFA.",
    "Open source maintainer. Building dev tools. linktr.ee/ken",
]
OLD_MUTATED_BIOS = [
    "crypto 荐股 稳赚 保本 资金盘", "NFT 代投 保本 日化 复利",
    "外汇喊单 拉人头 返利网", "私募 荐股 加微信 稳赚不赔",
]


def rnd_name():
    a = ["Alex", "Sam", "Jordan", "Wei", "Lin", "Mia", "Ken", "Ana", "Leo", "Yuki",
         "阿泽", "小明", "老王", "Chen", "Bob", "Nina"]
    b = ["Chen", "Li", "Wang", "Zhang", "Dev", "Writer", "Daily", "Tech", "Studio", ""]
    return f"{random.choice(a)} {random.choice(b)}".strip()


def rnd_handle(i, bot_style=False):
    if bot_style:
        return f"user{random.randint(100000, 999999)}"
    return f"person_{i}_{random.choice(['a','b','x','z','mj','kt'])}"


def gen(n):
    """按经验分布生成账号。每类自带 label 标准答案。"""
    out = []
    # 经验分布（合计 1.0）
    kinds = [
        ("content_real", 0.30, "keep"),   # 内容型真人
        ("ordinary",     0.17, "keep"),   # 普通用户（低活跃）
        ("pro_mid",      0.08, "keep"),   # 腰部正经从业者（含营销词）
        ("big_v",        0.05, "keep"),   # 大V / 机构
        ("mutual_pal",   0.10, "keep"),   # 互关好友
        ("follow_back",  0.13, "cut"),    # 互关党
        ("spam",         0.09, "cut"),    # 营销/诈骗
        ("ai_bot",       0.05, "cut"),    # AI 机器人
        ("ghost",        0.03, "cut"),    # 幽灵/空号
    ]
    for i in range(n):
        k = random.choices([x[0] for x in kinds], weights=[x[1] for x in kinds])[0]
        label = dict((x[0], x[2]) for x in kinds)[k]
        rec = {"handle": rnd_handle(i), "name": rnd_name(), "bio": "",
               "follows_you": False, "label": label, "kind": k}

        if k == "content_real":
            rec["bio"] = random.choice(REAL_BIOS)
            rec["followers"] = random.randint(300, 45000)
            rec["following"] = random.randint(150, 900)
            rec["account_age_days"] = random.randint(400, 4000)
            if random.random() < 0.06:
                rec["verified_type"] = "legacy"
        elif k == "ordinary":
            rec["bio"] = random.choice(REAL_BIOS)
            rec["followers"] = random.randint(20, 800)
            rec["following"] = random.randint(200, 1800)
            rec["account_age_days"] = random.randint(200, 3000)
        elif k == "pro_mid":
            rec["bio"] = random.choice(PRO_BIOS)
            rec["followers"] = random.randint(1200, 28000)
            rec["following"] = random.randint(250, 900)
            rec["account_age_days"] = random.randint(900, 4000)
            if random.random() < 0.25:
                rec["verified_type"] = "legacy"
        elif k == "big_v":
            rec["bio"] = random.choice(REAL_BIOS)
            rec["followers"] = random.randint(120000, 20000000)
            rec["following"] = random.randint(50, 900)
            rec["account_age_days"] = random.randint(2500, 6000)
            rec["verified_type"] = random.choice(["legacy", "business"])
        elif k == "mutual_pal":
            rec["bio"] = random.choice(REAL_BIOS) if random.random() > 0.18 else ""
            rec["follows_you"] = True
            rec["followers"] = random.randint(50, 6000)
            rec["following"] = random.randint(150, 2500)
            rec["account_age_days"] = random.randint(400, 4000)
        elif k == "follow_back":
            rec["bio"] = random.choice(REAL_BIOS) if random.random() > 0.4 else "follow back 🔥"
            rec["followers"] = random.randint(80, 1200)
            rec["following"] = random.randint(3000, 9900)
            rec["account_age_days"] = random.randint(200, 2500)
        elif k == "spam":
            rec["bio"] = random.choice(SPAM_BIOS)
            rec["followers"] = random.randint(10, 6000)
            rec["following"] = random.randint(400, 9000)
            rec["account_age_days"] = random.choice([
                random.randint(60, 900), random.randint(1500, 4000)])  # 含老号变质
            if random.random() < 0.15:
                rec["verified_type"] = "blue"
        elif k == "ai_bot":
            rec["bio"] = random.choice(AI_BIOS)
            rec["handle"] = rnd_handle(i, bot_style=random.random() < 0.45)
            rec["followers"] = random.randint(20, 2500)
            rec["following"] = random.randint(1500, 11000)
            rec["account_age_days"] = random.randint(100, 2200)
        elif k == "ghost":
            rec["bio"] = "" if random.random() < 0.7 else "🔥"
            rec["handle"] = rnd_handle(i, bot_style=True)
            rec["followers"] = random.randint(0, 95)
            rec["following"] = random.randint(2100, 9500)
            rec["account_age_days"] = random.randint(30, 800)
            rec["avatar_default"] = True

        out.append(rec)
    return out


def main():
    random.seed(42)
    cases = gen(N)
    tp = fp = tn = miss = 0
    by_kind = {}
    fp_samples = []
    scores = []

    for c in cases:
        s, reasons = V3.score(c)
        scores.append(s)
        pred = "cut" if s >= TH else "keep"
        truth = c["label"]
        k = c["kind"]
        st = by_kind.setdefault(k, {"n": 0, "cut": 0, "truth_cut": 0})
        st["n"] += 1
        st["truth_cut"] += 1 if truth == "cut" else 0
        st["cut"] += 1 if pred == "cut" else 0

        if truth == "cut" and pred == "cut":
            tp += 1
        elif truth == "keep" and pred == "cut":
            fp += 1
            if len(fp_samples) < 8:
                fp_samples.append((c, s, reasons))
        elif truth == "keep":
            tn += 1
        else:
            miss += 1

    n = len(cases)
    print(f"=== 规模压力测试：{n} 个模拟账号（随机种子 42，阈值 {TH}）===\n")
    print(f"  正确删 {tp} ｜ 正确留 {tn} ｜ 误删 {fp} ｜ 漏删 {miss}")
    print(f"  准确率 {(tp+tn)/n*100:.1f}% ｜ 误删率 {fp/(fp+tn)*100:.2f}% ｜ 召回率 {tp/(tp+miss)*100:.1f}%")
    print(f"  实际判定该删 {tp+fp} / {n} = {(tp+fp)/n*100:.1f}%\n")

    print(f"{'类型':<14}{'数量':>6}{'应删':>6}{'判删':>6}{'召回':>8}")
    print("-" * 42)
    for k, st in sorted(by_kind.items(), key=lambda x: -x[1]["n"]):
        rc = st["cut"] / st["truth_cut"] * 100 if st["truth_cut"] else 0.0
        print(f"{k:<14}{st['n']:>6}{st['truth_cut']:>6}{st['cut']:>6}{rc:>7.0f}%")

    buckets = [("≥50", lambda s: s >= 50), ("30-49", lambda s: 30 <= s < 50),
               ("20-29", lambda s: 20 <= s < 30), ("0-19", lambda s: 0 <= s < 20),
               ("-19~0", lambda s: -20 < s < 0), ("≤-20", lambda s: s <= -20)]
    print(f"\n分数分布：")
    for lb, f in buckets:
        c = sum(1 for s in scores if f(s))
        print(f"  {lb:<8}{c:>6}  {'█' * int(c / n * 60):<40}{c/n*100:>5.1f}%")

    if fp_samples:
        print(f"\n误删样例（最多 8 条）：")
        for c, s, rs in fp_samples:
            print(f"  @{c['handle']:<20}{s:>4}分  [{c['kind']}]  {c['bio'][:38]}")
            print(f"      {'、'.join(rs)}")

    print(f"\n{'='*52}")
    print(f"结论：误删率 {fp/(fp+tn)*100:.2f}%（取关不可撤销，此项最关键），"
          f"垃圾号召回 {tp/(tp+miss)*100:.1f}%")


if __name__ == "__main__":
    main()
