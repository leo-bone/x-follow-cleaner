#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_bookmarklet.py —— 把 x_smart_unfollow.js 打包成浏览器书签（bookmarklet）

为什么需要它：
  每次清理都要「打开 js 文件 → 全选 → 复制 → 粘贴进控制台」，
  而 Chrome 首次粘贴会拦一道 "allow pasting"，还要手动输入一遍。
  做成书签后：打开关注页 → 点一下书签 → 直接开跑，零复制。

用法：
  python3 make_bookmarklet.py
  → 生成 bookmarklet.html，打开它，把页面上的两个按钮拖到书签栏即可。

改配置的方式：
  直接改 x_smart_unfollow.js 里的 DRY_RUN / MIN_SCORE / WHITELIST，
  然后重新跑本脚本，书签内容会自动同步。不用手工改书签。

为什么自带 minify：
  浏览器书签 URL 上限约 32KB，源码未经压缩编码后会超过这个数被静默截断。
  压缩器是状态机实现，能正确区分 正则字面量 / 字符串 / 模板串，
  不会把 /(airdrop|加微信|...)/i 这类词表压坏。
"""
import os
import re
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "x_smart_unfollow.js")
OUT_HTML = os.path.join(HERE, "bookmarklet.html")

SAFE_LIMIT = 26000  # 留足余量，超过就告警

# 预置两种模式：变量覆盖写死进书签（书签里没法再手改，所以出两颗）
MODES = [
    {
        "key": "preview",
        "label": "预览（不删人）",
        "DRY_RUN": "true",
        "MIN_SCORE": "40",
        "color": "#1D9E75",
        "desc": "只列出它认为该删的账号，一个都不动。第一次一定用这颗。",
    },
    {
        "key": "execute",
        "label": "执行（真删）",
        "DRY_RUN": "false",
        "MIN_SCORE": "40",
        "color": "#E24B4A",
        "desc": "真正取关。脚本跑满 50 个自动停，自带 15–40 秒随机延迟。",
    },
]

# 「/」是正则还是除法，取决于它前面那个 token
KW_BEFORE_REGEX = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "case", "do", "else", "yield", "await",
}
PUNCT_BEFORE_REGEX = set("(=:[!&|?{};+-*%~^<>,")
IDENT = re.compile(r"[A-Za-z0-9_$]")


def minify(src):
    """去掉注释与多余空白，保留正则/字符串/模板串原样。"""
    out = []
    i, n = 0, len(src)
    prev = ""          # 上一个非空白字符
    last_ident = ""    # 上一个标识符（用于 return /typeof 等关键字判定）

    def emit(ch):
        nonlocal prev
        out.append(ch)
        prev = ch

    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""

        # —— 行注释 ——
        if c == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        # —— 块注释 ——
        if c == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
            prev = " "
            continue
        # —— 字符串 ——
        if c in "\"'":
            q = c
            emit(c)
            i += 1
            while i < n:
                if src[i] == "\\":
                    emit(src[i])
                    i += 1
                    if i < n:
                        emit(src[i])
                        i += 1
                    continue
                if src[i] == q:
                    emit(src[i])
                    i += 1
                    break
                if src[i] == "\n":          # 源码里不应出现，保险起见转成转义
                    emit("\\")
                    emit("n")
                    i += 1
                    continue
                emit(src[i])
                i += 1
            last_ident = ""
            continue
        # —— 模板串（整体保留，含 ${} 内部）——
        if c == "`":
            emit(c)
            i += 1
            while i < n:
                if src[i] == "\\":
                    emit(src[i])
                    i += 1
                    if i < n:
                        emit(src[i])
                        i += 1
                    continue
                if src[i] == "`":
                    emit(src[i])
                    i += 1
                    break
                emit(src[i])
                i += 1
            last_ident = ""
            continue
        # —— 正则字面量 ——
        if c == "/":
            starts_regex = (
                prev == ""
                or prev in PUNCT_BEFORE_REGEX
                or last_ident in KW_BEFORE_REGEX
            )
            if starts_regex:
                emit(c)
                i += 1
                in_class = False
                while i < n:
                    ch = src[i]
                    if ch == "\\":
                        emit(ch)
                        i += 1
                        if i < n:
                            emit(src[i])
                            i += 1
                        continue
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        emit(ch)
                        i += 1
                        break
                    emit(ch)
                    i += 1
                while i < n and IDENT.match(src[i]):   # 标志位 gimsuyd
                    emit(src[i])
                    i += 1
                last_ident = ""
                continue
            emit(c)
            i += 1
            last_ident = ""
            continue
        # —— 空白 ——
        if c in " \t\r\n":
            while i < n and src[i] in " \t\r\n":
                i += 1
            if prev not in ("", " "):
                out.append(" ")
                prev = " "
            continue
        # —— 普通字符 ——
        emit(c)
        i += 1
        if IDENT.match(c):
            last_ident += c
        else:
            last_ident = ""

    return "".join(out).strip()


def read_source():
    with open(SRC, "r", encoding="utf-8") as f:
        return f.read()


def patch(src, mode):
    """把配置区的 DRY_RUN / MIN_SCORE 替换成该模式的取值。"""
    out = src
    for var in ("DRY_RUN", "MIN_SCORE"):
        pat = re.compile(r"(const\s+%s\s*=\s*)[^;\n]+(;)" % var, re.M)
        out, cnt = pat.subn(r"\g<1>%s\g<2>" % mode[var], out, count=1)
        assert cnt == 1, "未能在源码中定位 const %s，文件结构可能已变" % var
    return out


def to_bookmarklet(src):
    """整段做 URI 编码：中文与特殊字符都能安全通过书签 URL。"""
    return "javascript:" + urllib.parse.quote(src, safe="")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def build_html(items):
    cards = []
    for it in items:
        cards.append(f"""
  <div class="card">
    <div class="row">
      <span class="dot" style="background:{it['color']}"></span>
      <span class="name">{esc(it['label'])}</span>
      <span class="tag">DRY_RUN = {it['DRY_RUN']} ｜ MIN_SCORE = {it['MIN_SCORE']}</span>
    </div>
    <p class="desc">{esc(it['desc'])}</p>
    <a class="bm" href="{esc(it['href'])}" onclick="return false;">{esc(it['label'])}</a>
    <p class="hint">↑ 按住这个按钮，拖到浏览器书签栏松手</p>
  </div>""")

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>X 关注清理 · 书签安装</title>
<style>
body{font-family:-apple-system,"PingFang SC",sans-serif;max-width:760px;margin:40px auto;padding:0 24px;color:#1a1a1a;line-height:1.7;background:#fff}
h1{font-size:20px;font-weight:600;margin:0 0 6px}
.sub{color:#666;font-size:13px;margin:0 0 28px}
.card{border:1px solid #e3e3e3;border-radius:12px;padding:18px 20px;margin-bottom:16px}
.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.name{font-size:15px;font-weight:600}
.tag{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:#666;background:#f2f2f2;padding:2px 8px;border-radius:5px}
.desc{font-size:13px;color:#444;margin:8px 0 14px}
.bm{display:inline-block;background:#1a1a1a;color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;font-size:14px;cursor:grab}
.hint{font-size:12px;color:#888;margin:8px 0 0}
ol{font-size:14px;padding-left:22px}
li{margin-bottom:10px}
code{background:#f2f2f2;padding:1px 6px;border-radius:4px;font-size:13px}
.warn{border:1px solid #f0c36d;background:#fffaf0;border-radius:10px;padding:14px 18px;font-size:13px;color:#7a5200;margin-top:28px}
</style></head><body>
<h1>X 关注清理 · 一键书签</h1>
<p class="sub">安装后不用再复制粘贴代码，打开关注页点一下就跑。</p>

<h3 style="font-size:15px;margin:0 0 12px">安装（做一次就行）</h3>
<ol>
  <li>显示书签栏：<code>Cmd + Shift + B</code>（Chrome / Edge / Brave 通用）</li>
  <li>把下面两颗按钮<b>拖到书签栏</b>松手</li>
  <li>打开 <code>x.com/你的用户名/following</code></li>
  <li>先点「<b>预览</b>」看它圈得准不准，认可了再点「<b>执行</b>」</li>
</ol>

<h3 style="font-size:15px;margin:28px 0 12px">两颗书签</h3>
__CARDS__

<div class="warn">
<b>注意</b><br>
· 滚动期间<b>不要切走标签页</b>，浏览器会暂停后台滚动，脚本会卡住（看着像死了，其实只是被冻住）。<br>
· 每日取关不超过 100 个，脚本自带随机延迟，别改小。<br>
· 跑完会自动下载 <code>cleanup_log.json</code>，误删了照着名单加回来。<br>
· 想改判定标准：编辑 <code>x_smart_unfollow.js</code> 的 <code>WEIGHTS</code>，再跑一次 <code>python3 make_bookmarklet.py</code>，书签自动同步。
</div>
</body></html>"""
    return html.replace("__CARDS__", "".join(cards))


def main():
    src = read_source()
    assert "const calcScore" in src or "function calcScore" in src, "源码结构异常：找不到 calcScore"

    items = []
    for m in MODES:
        packed = minify(patch(src, m))
        items.append({
            "label": m["label"],
            "color": m["color"],
            "DRY_RUN": m["DRY_RUN"],
            "MIN_SCORE": m["MIN_SCORE"],
            "desc": m["desc"],
            "href": to_bookmarklet(packed),
        })

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(build_html(items))

    print("已生成 bookmarklet.html")
    for it, m in zip(items, MODES):
        size = len(it["href"])
        flag = "" if size <= SAFE_LIMIT else "  [警告] 超过安全长度，书签可能被截断"
        print("  %-14s %6d 字符%s" % (it["label"], size, flag))

    raw = len(to_bookmarklet(src))
    print("  未压缩对照：%d 字符（压缩省下 %.0f%%）"
          % (raw, (1 - len(items[0]["href"]) / raw) * 100))


if __name__ == "__main__":
    main()
