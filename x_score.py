#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
x_score.py v3  ——  X 关注账号「是否值得留在信息流」评分引擎
==================================================================
评分框架（按重要性排序）：
  1. 内容质量（不能只看多久没发帖）—— 最高优先级
  2. 被有价值的人关注的程度（社会证明 / 声望）
  3. 是否涉及太多推广 / 营销 / 诈骗
  4. 是否 AI 化（机器人 / 自动号）
  5. 是否互关太多（关注数远多于粉丝数 = 互关党）
  6. 是否回关你 —— 最末位

本脚本用「取关优先级分」表达：分越高 = 越该删；负分 = 建议保留。

v3 相对 v2 的五项修正（都是会造成误删的真问题）：
  A. 营销词【分级】：HARD(黑产/诈骗) vs SOFT(商业化但未必垃圾)。
     "link in bio / linktr.ee / 推广 / 带货" 正经创作者也用，一刀切 +35 会误杀。
  B. 【可信身份豁免】：教授/记者/研究员/工程师/作者/开源维护者 命中营销词时
     自动降权。解决 "crypto researcher" 被当诈骗号删除这类最痛的误判。
  C. 蓝标【分级】：2026 年蓝标 = 付费订阅，任何人能买，已不是权威信号。
     legacy/business/government 才算社会证明(-25)；blue(付费) 只给 -5。
  D. 互关比【分档】：following/followers >=10 重度(+20)、>=3 中度(+10)，
     v2 只有一档，把「关注 3100 / 粉丝 900 的产品设计师」也伤害了。
  E. handle【随机串检测】：5 位以上数字结尾是批量号最廉价、最典型的指纹。

数据来源：
  基础字段(handle/name/bio/follows_you)  —— x_audit.js
  深度字段(verified_type/followers/following/tweets/account_age_days/
          avatar_default/last_post_date) —— x_deepscan.js，输出 deepscan.json
  本脚本自动合并同目录 deepscan.json；缺失字段不报错，仅该维度不计分。

用法：
    python3 x_score.py                    # 读 following_audit.json(+deepscan.json)
    python3 x_score.py 路径/audit.json    # 指定审计文件
    python3 x_score.py --selftest         # 用 testcases.json 跑准确率/误删率
    python3 x_score.py --selftest --dump  # 逐条打印评分明细
"""

import json
import re
import sys
import os
import html as _html
from datetime import datetime

INPUT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "following_audit.json"
DEEPSCAN = os.path.join(os.path.dirname(INPUT) or ".", "deepscan.json")
OUT_HTML = "following_report.html"
OUT_LIST = "unfollow_targets.txt"
SCORE_THRESHOLD = 20          # 达到此分进入取关名单（可调）

# ---------- 关键词 ----------
# 框架3-A：明确的黑产 / 诈骗 / 博彩（重罚）
MARKETING_HARD = re.compile(
    r"(airdrop|telegram|onlyfans|cashapp|forex|"
    r" casino|\bbet\b|\bslot\b|viagra|"
    r" make money|passive income|money online|earn \$|"
    r"兼职|返利|刷单|代购|引流|加微信|加微|带货|招商|加盟|"
    r"被动收入|赚[钱￥]|日入|月入|彩票|博彩|荐股|割韭菜|资金盘|拉人头|"
    r"金字塔|多级|返利网|跑分|代投|稳赚|保本|复利|互助盘|"
    r"buy followers|get followers|free follow)",
    re.I,
)
# 框架3-B：商业化但未必是垃圾（轻罚；正经创作者也用）
MARKETING_SOFT = re.compile(
    r"(link in bio|linktr\.ee|dm me|dm us|click here|promo code|推广|私聊|"
    r"follow\s?back|f4f|follow4follow|互关|互粉|求关注|"
    r"\botc\b|crypto|nft|web3)",
    re.I,
)
# 框架4：AI 化
AI_RE = re.compile(
    r"(🤖|fully automated|24/7|auto-?post|auto-?tweet|auto-?reply|"
    r"ai agent\b|ai-powered|ai generated|gpt-?[0-9]|llm bot|"
    r"全网自动|自动推送|机器人号|全自动|自动发文|"
    r"自动抓取|自动更新|自动发布|自动采集|自动同步|无人值守|定时推送)",
    re.I,
)
# 框架B：可信身份 —— 命中则营销词降权，避免误杀正经从业者
TRUSTED = re.compile(
    r"(professor|\bprof\b|\bphd\b|researcher|research|scientist|journalist|"
    r"reporter|correspondent|author|founder|co-?founder|engineer|developer|"
    r"maintainer|open source|open-source|architect|physician|doctor|attorney|"
    r"\bcfa\b|\bcpa\b|analyst|economist|professor|"
    r"\bwrit(e|er|ers|ing)\b|essay|newsletter|columnist|blogger|curator|auditor|"
    r"教授|研究员|记者|主编|作者|工程师|开发|开源|律师|医生|分析师|学者|博士|"
    r"审计|安全|写作|写作人|独立开发)",
    re.I,
)
# bot handle 指纹：5 位以上数字结尾，或 字母+4位以上数字结尾
BOT_HANDLE_RE = re.compile(r"(\d{5,})$|([a-z]{2,}\d{4,})$", re.I)

# ---------- 权重（与 x_smart_unfollow.js 的 WEIGHTS 保持一致，用 verify_engines.js 校验） ----------
WEIGHTS = {
    # —— 该删信号 +
    "marketing_hard":      35,   # 黑产/诈骗/博彩（框架3 核心）
    "marketing_soft":      12,   # 商业化但未必垃圾（框架3 次要）
    "ai":                  20,   # AI 化（框架4）
    "thin_bio":            15,   # 简介空洞（框架1 代理）
    "ratio_heavy":         25,   # 重度互关党 关注/粉丝>=5 且关注>3000（框架5）
    "ratio_mid":            8,   # 中度 关注/粉丝>=2.5 且关注>1500
    "following_extreme":   12,   # 关注数 >5000（正常人极少关注这么多人）
    "ghost":                8,   # 幽灵号：粉丝<100 且 关注>2000
    "bot_handle":          15,   # handle 随机数字串（批量号指纹）
    "mutated":             10,   # ★老号变质：老号 + 当前营销 = 最该删
    "default_avatar":       5,   # 默认头像（蛋号）
    "not_following_back":   5,   # 未回关你（框架6 最末）
    "overactive":           0,   # 过度活跃霸屏（默认关闭；介意刷屏设 10~20）
    # —— 保留信号 -
    "mutual":             -10,   # 互关（不参与排序，只做误删保护垫）
    "solid_bio":          -10,   # 简介有实质（框架1 代理）
    "old_account":        -10,   # 老账号（>3年）且未变质
    "trusted":           -20,   # ★可信身份（教授/记者/工程师/开源…）
    "big_followers":      -15,   # 粉丝 > 1万（框架2 代理）
    "huge_followers":     -25,   # 粉丝 > 10万
    "verified_legacy":    -25,   # 旧版认证（名人/机构，真社会证明）
    "verified_business":  -25,   # 机构/政府认证
    "verified_blue":       -5,   # 付费蓝标（谁都能买，弱信号）
}
# 可信身份命中时，营销词权重的折减系数（0=不折减，1=完全取消）
TRUST_DISCOUNT = 0.7

# ---------- 自定义关键词（可选 keywords.json） ----------
CUSTOM_SPAM, CUSTOM_KEEP = [], []
try:
    with open("keywords.json", encoding="utf-8") as _f:
        _k = json.load(_f)
        CUSTOM_SPAM = _k.get("spam") or []
        CUSTOM_KEEP = _k.get("keep") or []
    print(f"已载入自定义关键词：spam {len(CUSTOM_SPAM)} 条 / keep {len(CUSTOM_KEEP)} 条")
except FileNotFoundError:
    pass
_spam_re = re.compile("|".join(map(re.escape, CUSTOM_SPAM)), re.I) if CUSTOM_SPAM else None
_keep_re = re.compile("|".join(map(re.escape, CUSTOM_KEEP)), re.I) if CUSTOM_KEEP else None

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\u2700-\u27bf]"
)


def to_num(s):
    """把 '12.3K' / '1.2M' / '845' 解析为整数。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).strip().replace(",", "")
    m = re.match(r"([\d.]+)\s*([kKmM]?)", s)
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "k":
        v *= 1_000
    elif unit == "m":
        v *= 1_000_000
    return int(v)


def is_thin(bio):
    """简介是否空洞（框架1 的反面 / 可疑信号）。"""
    b = (bio or "").strip()
    if len(b) < 4:
        return True
    if EMOJI_RE.sub("", b).strip() == "":
        return True
    if re.fullmatch(r"(https?://\S+\s*)+", b):
        return True
    if re.fullmatch(r"([#@]\S+\s*)+", b):
        return True
    if b.lower().startswith("http") and len(EMOJI_RE.sub("", re.sub(r"https?://\S+", "", b)).strip()) < 6:
        return True
    return False


def score(rec):
    """按 WEIGHTS 打分：分越高越该删，负分=保留。返回 (分数, 原因列表)。"""
    s = 0
    reasons = []
    bio = rec.get("bio") or ""
    name = rec.get("name") or ""
    handle = rec.get("handle") or ""
    text = f"{bio} {name}"

    # 框架6（最末）：是否回关你
    if rec.get("follows_you"):
        s += WEIGHTS["mutual"]
        reasons.append("互关")
    else:
        s += WEIGHTS["not_following_back"]
        reasons.append("未回关")

    # 框架B：可信身份（先算，后面用于营销词折减）
    is_trusted = bool(TRUSTED.search(text))
    if is_trusted:
        s += WEIGHTS["trusted"]
        reasons.append("可信身份")

    # 框架3：营销 / 诈骗 —— 分级 + 可信折减
    hard = bool(MARKETING_HARD.search(text) or (_spam_re and _spam_re.search(text)))
    soft = bool(MARKETING_SOFT.search(text))
    if hard:
        w = WEIGHTS["marketing_hard"]
        if is_trusted:
            w = round(w * (1 - TRUST_DISCOUNT))
            reasons.append(f"营销词(可信身份折减→{w})")
        else:
            reasons.append("营销/诈骗")
        s += w
    elif soft:
        w = WEIGHTS["marketing_soft"]
        if is_trusted:
            w = 0
            reasons.append("商业化词(可信身份豁免)")
        else:
            reasons.append("商业化推广")
        s += w

    # 框架4：AI 化
    if AI_RE.search(text):
        s += WEIGHTS["ai"]
        reasons.append("AI化")

    # 框架1（代理）：简介真实度
    if is_thin(bio):
        s += WEIGHTS["thin_bio"]
        reasons.append("简介空洞")
    else:
        s += WEIGHTS["solid_bio"]
        reasons.append("简介有实质")

    # 框架2（代理）：蓝标分级 —— 付费蓝标不是权威信号
    vt = (rec.get("verified_type") or "").lower()
    if vt in ("legacy", "government"):
        s += WEIGHTS["verified_legacy"]
        reasons.append("权威认证(legacy)")
    elif vt == "business":
        s += WEIGHTS["verified_business"]
        reasons.append("机构认证")
    elif vt == "blue":
        s += WEIGHTS["verified_blue"]
        reasons.append("付费蓝标(弱)")

    followers = to_num(rec.get("followers"))
    following = to_num(rec.get("following"))
    if followers:
        if followers >= 100_000:
            s += WEIGHTS["huge_followers"]
            reasons.append("粉丝>10万")
        elif followers >= 10_000:
            s += WEIGHTS["big_followers"]
            reasons.append("粉丝>1万")

    # 框架5：互关比分档（同时看比值与绝对关注数，避免误伤「关注多但正常」的人）
    if followers and following:
        ratio = following / max(followers, 1)
        if ratio >= 5 and following > 3000:
            s += WEIGHTS["ratio_heavy"]
            reasons.append(f"重度互关党(比{ratio:.0f}:1)")
        elif ratio >= 2.5 and following > 1500:
            s += WEIGHTS["ratio_mid"]
            reasons.append(f"中度互关(比{ratio:.0f}:1)")
    # 绝对关注数：正常人极少关注 5000 人以上（与比值无关，独立信号）
    if following and following > 5000:
        s += WEIGHTS["following_extreme"]
        reasons.append(f"关注数异常({following})")
    # 幽灵号：几乎没粉丝却关注几千
    if followers is not None and following is not None:
        if followers < 100 and following > 2000:
            s += WEIGHTS["ghost"]
            reasons.append("幽灵号(粉丝<100/关注>2千)")

    # 批量号指纹：handle 随机数字串
    if handle and BOT_HANDLE_RE.search(handle):
        s += WEIGHTS["bot_handle"]
        reasons.append("handle疑似批量号")

    # ★ 变质号：老号 + 当前营销 → 取消老号加分，反追加惩罚
    age = rec.get("account_age_days")
    if age and age > 365 * 3:
        if hard and not is_trusted:
            s += WEIGHTS["mutated"]
            reasons.append("★老号变质")
        else:
            s += WEIGHTS["old_account"]
            reasons.append("老账号")

    if rec.get("avatar_default"):
        s += WEIGHTS["default_avatar"]
        reasons.append("默认头像")

    if WEIGHTS["overactive"]:
        tw = to_num(rec.get("tweets"))
        if tw and tw > 50000 and following and following > 1000:
            s += WEIGHTS["overactive"]
            reasons.append("过度活跃霸屏")

    if _keep_re and _keep_re.search(text):
        s += -1000
        reasons.append("★自定义保留")

    return s, reasons


def esc(x):
    return _html.escape(str(x if x is not None else ""))


def badge_for(s):
    if s >= SCORE_THRESHOLD:
        return '<span class="b high">该删</span>'
    if s >= 0:
        return '<span class="b mid">待定</span>'
    return '<span class="b low">保留</span>'


# ============ 自检：用标准答案测试集量化效果 ============
def selftest(dump=False):
    with open("testcases.json", encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    tp = fp = tn = fn = 0
    fp_list, fn_list = [], []
    print(f"=== 自检：{len(cases)} 个标注样本（阈值 {SCORE_THRESHOLD}）===\n")
    for c in cases:
        s, reasons = score(c)
        pred = "cut" if s >= SCORE_THRESHOLD else "keep"
        truth = c["label"]
        ok = pred == truth
        if dump:
            print(f"{'OK ' if ok else 'XX '}@{c['handle']:<22} {s:>5}分  "
                  f"预测={pred:<4} 答案={truth:<4} | {c.get('note','')}")
            print(f"      {'、'.join(reasons)}")
        if truth == "cut" and pred == "cut":
            tp += 1
        elif truth == "keep" and pred == "cut":
            fp += 1
            fp_list.append(c)
        elif truth == "keep" and pred == "keep":
            tn += 1
        else:
            fn += 1
            fn_list.append(c)

    total = len(cases)
    acc = (tp + tn) / total * 100
    prec = tp / (tp + fp) * 100 if (tp + fp) else 0.0
    rec = tp / (tp + fn) * 100 if (tp + fn) else 0.0
    fp_rate = fp / (fp + tn) * 100 if (fp + tn) else 0.0
    print(f"\n{'='*58}")
    print(f"样本 {total}：应删 {tp+fn} 个 / 应留 {tn+fp} 个")
    print(f"  正确识别该删 (TP) : {tp}")
    print(f"  正确保留     (TN) : {tn}")
    print(f"  ❌ 误删       (FP) : {fp}   ← 最致命：删掉了本该留的人")
    print(f"  ⚠️  漏删       (FN) : {fn}   ← 垃圾号没抓出来")
    print(f"{'-'*58}")
    print(f"  准确率   : {acc:.1f}%")
    print(f"  精确率   : {prec:.1f}%  （判为『该删』的里面真该删的比例）")
    print(f"  召回率   : {rec:.1f}%  （真正该删的被抓出来的比例）")
    print(f"  误删率   : {fp_rate:.1f}%  （★★ 必须趋近 0，取关不可撤销）")
    print(f"{'='*58}")
    if fp_list:
        print("\n误删明细（需要修规则）：")
        for c in fp_list:
            s, reasons = score(c)
            print(f"  @{c['handle']:<22} {s:>4}分  {c.get('note','')}")
            print(f"      {'、'.join(reasons)}")
    if fn_list:
        print("\n漏删明细（可以接受，保守优先）：")
        for c in fn_list:
            s, reasons = score(c)
            print(f"  @{c['handle']:<22} {s:>4}分  {c.get('note','')}")
            print(f"      {'、'.join(reasons)}")
    return acc, fp_rate, rec


def main():
    if "--selftest" in sys.argv:
        selftest(dump="--dump" in sys.argv)
        return

    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    deep = {}
    try:
        with open(DEEPSCAN, encoding="utf-8") as f:
            for d in json.load(f):
                deep[d.get("handle", "").lower()] = d
        print(f"已合并深度数据 deepscan.json：{len(deep)} 个账号")
    except FileNotFoundError:
        print("（未找到 deepscan.json，按基础字段评分；框架1/2/5 的部分维度将不计入）")

    scored = []
    for r in data:
        h = r.get("handle", "").lower()
        if h in deep:
            r = {**r, **{k: v for k, v in deep[h].items() if k != "handle"}}
        s, reasons = score(r)
        scored.append((s, reasons, r))
    scored.sort(key=lambda x: x[0], reverse=True)

    total = len(scored)
    high = [x for x in scored if x[0] >= SCORE_THRESHOLD]
    mid = [x for x in scored if 0 <= x[0] < SCORE_THRESHOLD]
    low = [x for x in scored if x[0] < 0]
    targets = [x[2]["handle"] for x in high]

    with open(OUT_LIST, "w", encoding="utf-8") as f:
        f.write("\n".join(targets))

    # 数据完整度
    has_deep = sum(1 for _, _, r in scored if r.get("followers") is not None)
    coverage = (has_deep / total * 100) if total else 0

    # 分数分布（用于条形图）
    buckets = [("≥50", lambda s: s >= 50), ("30-49", lambda s: 30 <= s < 50),
               ("20-29", lambda s: 20 <= s < 30), ("0-19", lambda s: 0 <= s < 20),
               ("-19~0", lambda s: -20 < s < 0), ("≤-20", lambda s: s <= -20)]
    maxn = max([sum(1 for s, _, _ in scored if f(s)) for _, f in buckets] or [1])
    bars = []
    for label, f in buckets:
        n = sum(1 for s, _, _ in scored if f(s))
        pct = (n / total * 100) if total else 0
        w = (n / maxn * 100) if maxn else 0
        color = "#dc2626" if label in ("≥50", "30-49", "20-29") else ("#d97706" if label == "0-19" else "#059669")
        bars.append(
            f"<div class='brow'><span class='bl'>{label}</span>"
            f"<span class='bbar'><i style='width:{w:.1f}%;background:{color}'></i></span>"
            f"<span class='bn'>{n} ({pct:.0f}%)</span></div>"
        )
    bars_html = "\n".join(bars)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for s, reasons, r in scored:
        chk = "checked" if s >= SCORE_THRESHOLD else ""
        vt = {"legacy": "权威", "business": "机构", "government": "政府", "blue": "付费蓝标"}.get(
            (r.get("verified_type") or "").lower(), "—")
        rows.append(
            f"<tr class='{'rowhi' if s >= SCORE_THRESHOLD else ''}'>"
            f"<td><input type='checkbox' class='pick' data-h='{esc(r['handle'])}' {chk}></td>"
            f"<td><a href='https://x.com/{esc(r['handle'])}' target='_blank' rel='noopener'>{esc(r['handle'])}</a></td>"
            f"<td>{esc(r.get('name'))}</td>"
            f"<td>{'是' if r.get('follows_you') else '否'}</td>"
            f"<td>{esc(r.get('followers'))}</td><td>{esc(r.get('following'))}</td>"
            f"<td>{vt}</td>"
            f"<td><b>{s}</b></td>"
            f"<td>{badge_for(s)} {esc('、'.join(reasons))}</td>"
            f"</tr>"
        )
    rows_html = "\n".join(rows)

    html_doc = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>X 关注清理评分报告 v3</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
   background:#f5f7fa;color:#1f2937;margin:0;padding:24px}}
 .wrap{{max-width:1120px;margin:0 auto;background:#fff;border-radius:12px;
   box-shadow:0 2px 12px rgba(0,0,0,.08);padding:24px}}
 h1{{font-size:22px;margin:0 0 4px}}
 .sub{{color:#6b7280;font-size:13px;margin-bottom:18px}}
 .cards{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}}
 .card{{flex:1;min-width:140px;background:#f9fafb;border:1px solid #e5e7eb;
   border-radius:10px;padding:14px}}
 .card .n{{font-size:26px;font-weight:700}}
 .card .l{{font-size:13px;color:#6b7280}}
 .hi .n{{color:#dc2626}} .mid .n{{color:#d97706}} .lo .n{{color:#059669}}
 .dist{{background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin-bottom:18px}}
 .dist h3{{margin:0 0 10px;font-size:14px}}
 .brow{{display:flex;align-items:center;gap:10px;margin:5px 0;font-size:12px}}
 .bl{{width:56px;color:#6b7280}} .bbar{{flex:1;background:#eef0f3;border-radius:4px;height:14px;overflow:hidden}}
 .bbar i{{display:block;height:100%}} .bn{{width:80px;text-align:right;color:#374151}}
 .bar{{display:flex;gap:8px;margin:10px 0 18px}}
 .bar button{{flex:1;padding:10px;border:none;border-radius:8px;cursor:pointer;
   font-size:14px;font-weight:600;background:#2563eb;color:#fff}}
 .bar button.sec{{background:#e5e7eb;color:#374151}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{padding:8px 10px;border-bottom:1px solid #eef0f3;text-align:left}}
 th{{background:#f3f4f6;font-weight:600;position:sticky;top:0}}
 .rowhi{{background:#fff7f7}}
 .b{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;color:#fff}}
 .b.high{{background:#dc2626}} .b.mid{{background:#d97706}} .b.low{{background:#9ca3af}}
 #out{{width:100%;height:120px;margin-top:10px;font-family:monospace;font-size:12px}}
 .tip{{background:#fffbeb;border:1px solid #fde68a;color:#92400e;border-radius:8px;
   padding:10px 12px;font-size:13px;margin-top:16px}}
 .cov{{background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af;border-radius:8px;
   padding:10px 12px;font-size:13px;margin-bottom:16px}}
 .legend{{font-size:12px;color:#6b7280;margin:6px 0 0}}
</style></head><body><div class="wrap">
<h1>X（推特）关注清理 · 评分报告 v3</h1>
<div class="sub">生成时间 {now} ｜ 数据源 {esc(INPUT)} ｜ 取关阈值 ≥{SCORE_THRESHOLD} 分（分越高越该删，负分=建议保留）</div>
<div class="cov">数据完整度：<b>{coverage:.0f}%</b>（{has_deep}/{total} 个账号有 profile 深度数据）。
低于 60% 时，框架1/2/5 只能靠简介与是否回关间接判断 —— 建议先跑 <code>x_deepscan.js</code> 补齐。</div>
<div class="cards">
 <div class="card"><div class="n">{total}</div><div class="l">关注总数</div></div>
 <div class="card hi"><div class="n">{len(high)}</div><div class="l">该删(≥{SCORE_THRESHOLD})</div></div>
 <div class="card mid"><div class="n">{len(mid)}</div><div class="l">待定(0-{SCORE_THRESHOLD-1})</div></div>
 <div class="card lo"><div class="n">{len(low)}</div><div class="l">保留(&lt;0)</div></div>
</div>
<div class="dist"><h3>分数分布</h3>{bars_html}</div>
<div class="bar">
 <button onclick="genList()">① 生成取关名单</button>
 <button class="sec" onclick="selAll(true)">全选该删</button>
 <button class="sec" onclick="selAll(false)">清空选择</button>
</div>
<table><thead><tr>
 <th>选</th><th>handle</th><th>显示名</th><th>回关?</th><th>粉丝</th><th>关注</th><th>认证</th><th>分</th><th>判定</th>
</tr></thead><tbody>
{rows_html}
</tbody></table>
<div class="legend">该删信号：黑产/诈骗+35 ｜ AI化+20 ｜ 重度互关党+20 ｜ 简介空洞+15 ｜ handle批量号+15 ｜ 商业化+12 ｜
 中度互关+10 ｜ 幽灵号+8 ｜ 默认头像+5 ｜ 未回关+5<br>
保留信号：可信身份-20 ｜ 权威/机构认证-25 ｜ 粉丝&gt;10万-25 ｜ 粉丝&gt;1万-15 ｜ 简介有实质-10 ｜ 老账号-10 ｜ 互关-5 ｜ 付费蓝标-5</div>
<div class="tip">用法：勾选要删的账号 → 点「生成取关名单」复制 → 粘贴进 x_unfollow.js 的 TARGET_HANDLES →
 先 DRY_RUN=true 预览，再执行。或用 x_smart_unfollow.js 一步式（边滚边打分边删，更省事）。
 <b>建议先跑 <code>python3 x_score.py --selftest</code> 看引擎在你自己标准下的表现。</b></div>
<textarea id="out" placeholder="点「生成取关名单」后这里出现 handle 列表"></textarea>
<script>
function genList(){{
  const hs=[...document.querySelectorAll('.pick:checked')].map(c=>c.dataset.h);
  document.getElementById('out').value=hs.join('\\n');
  document.getElementById('out').select();
}}
function selAll(v){{
  document.querySelectorAll('.pick').forEach(c=>{{ if(v) c.checked=(+c.closest('tr').querySelector('b').textContent)>={SCORE_THRESHOLD}; else c.checked=false; }});
}}
</script>
</div></body></html>"""

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_doc)

    print(f"总计 {total} 个关注")
    print(f"  该删(≥{SCORE_THRESHOLD}分): {len(high)}")
    print(f"  待定(0-{SCORE_THRESHOLD-1}):  {len(mid)}")
    print(f"  保留(<0分):  {len(low)}")
    print(f"建议取关名单 {len(targets)} 个 → {OUT_LIST}")
    print(f"可视化报告 → {OUT_HTML}（浏览器打开，可勾选后导出名单）")


if __name__ == "__main__":
    main()
