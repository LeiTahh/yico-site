#!/usr/bin/env python3
"""站点自检：support 页的 App 卡片不许半填，首页写的「共 N 款」不许和卡片数对不上。

为什么要有：2026-11-03 用户问「为什么 support 没有新项目的介绍」。查下来是两个问题叠在一起——
support 页只有一张三行的表（没有介绍），而首页在 11-03 的 ccdc07c 里把 #apps 段整段删掉了，
A/B 连名字都不在站上了。页面能打开、链接也通，所以没有任何检查会报错。

这里查的是「内容与内容之间」的一致性，不是 HTTP 通不通（那个另有 curl/PAGES 轮询）。

用法：
    python tool/check_site.py            # 检查本仓
    python tool/check_site.py --selftest # 反向自测：每条规则都必须能精确报错
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
       7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n")


def cards(html: str) -> list[str]:
    """返回非 promo 的 App 卡片内容（promo 是「每月上新」那张说明卡，不占 App 计数）。"""
    out = []
    for m in re.finditer(r"<article\s+class=\"([^\"]*)\"[^>]*>(.*?)</article>", html, re.S):
        if "promo" in m.group(1).split():
            continue
        out.append(m.group(2))
    return out


def check(support: str, home: str) -> list[str]:
    bad: list[str] = []
    cs = cards(support)
    n = len(cs)

    # C1 / C2：三处数字必须一致 —— 卡片数、support 首句、首页 About 句
    m = re.search(r"in one place — (\w+) apps", support)
    if not m:
        bad.append("C2 support 页首句缺少「N apps」计数")
    elif m.group(1) != NUM.get(n):
        bad.append(f"C2 support 页写 {m.group(1)} apps，实际 {n} 张卡片")

    m = re.search(r"we now publish (\w+)", home)
    if not m:
        bad.append("C1 首页 About 段缺少「we now publish N」")
    elif m.group(1) != NUM.get(n):
        bad.append(f"C1 首页写 publish {m.group(1)}，实际 {n} 张卡片")

    # C3 / C4：每张卡必须三件齐（标题 / 一句功能 / 隐私链接），且功能说明不是占位
    for i, body in enumerate(cs, 1):
        h3 = re.search(r"<h3>(.*?)</h3>", body, re.S)
        what = re.search(r"<p class=\"what\">(.*?)</p>", body, re.S)
        pol = re.search(r"<p class=\"pol\">(.*?)</p>", body, re.S)
        name = h3.group(1).strip() if h3 else f"<第 {i} 张卡>"
        if not h3:
            bad.append(f"C3 第 {i} 张卡没有 <h3> 标题")
        if not what:
            bad.append(f"C3 {name} 没有功能说明 <p class=\"what\">")
        elif len(re.sub(r"<[^>]+>", "", what.group(1)).split()) < 6:
            bad.append(f"C4 {name} 的功能说明过短（少于 6 个词，像占位）")
        if not pol or "http" not in pol.group(1):
            bad.append(f"C3 {name} 没有隐私链接 <p class=\"pol\">")

    # C5 / C6：隐私链接不重复，且只指向 Pages 域名
    links = re.findall(r"href=\"(https://[^\"]+)\"", "".join(cs))
    seen: set[str] = set()
    for u in links:
        if u in seen:
            bad.append(f"C5 隐私链接重复：{u}")
        seen.add(u)
        if not u.startswith("https://leitahh.github.io/"):
            bad.append(f"C6 隐私链接不在 Pages 域名下：{u}")

    # C7：防回退 —— 表格版式不许回来（表头就是当年「没有介绍」的形态）
    if "<th>Privacy policy</th>" in support:
        bad.append("C7 support 页又变回表格版式（表头 Privacy policy），App 没有介绍")

    return bad


def selftest() -> int:
    support = read("support/index.html")
    home = read("index.html")
    # (规则号, 说明, 改坏后的 support, 改坏后的首页)
    cases = [
        ("C1", "首页计数改成 six", support, home.replace("we now publish five", "we now publish six")),
        ("C2", "support 首句改成 four", support.replace("— five apps", "— four apps"), home),
        ("C3", "删掉一张卡的功能说明",
         re.sub(r"<p class=\"what\">.*?</p>", "", support, count=1, flags=re.S), home),
        ("C4", "功能说明改成占位词",
         re.sub(r"<p class=\"what\">.*?</p>", "<p class=\"what\">TODO</p>", support, count=1, flags=re.S), home),
        ("C5", "两张卡用同一隐私链接",
         support.replace("a-photo-nd-privacy", "yico-privacy"), home),
        ("C6", "隐私链接换成别的域名",
         support.replace("https://leitahh.github.io/a-photo-nd", "https://example.com/a-photo-nd"), home),
        ("C7", "塞回表格表头",
         support.replace("<h2>Our apps</h2>",
                         "<h2>Our apps</h2>\n<table><tr><th>Privacy policy</th></tr></table>"), home),
    ]
    failed = 0
    for want, desc, sup, hom in cases:
        got = [e for e in check(sup, hom) if e.startswith(want)]
        if got:
            print(f"  ok   {want} 反向用例被抓住：{desc}  →  {got[0]}")
        else:
            print(f"  FAIL {want} 反向用例没被抓住：{desc}")
            failed += 1
    return failed


def main() -> int:
    if "--selftest" in sys.argv:
        n = selftest()
        print(f"自测：{'全部通过' if n == 0 else f'{n} 条没抓住'}")
        return 1 if n else 0

    bad = check(read("support/index.html"), read("index.html"))
    if bad:
        print("站点自检失败：")
        for b in bad:
            print("  -", b)
        return 1
    n = len(cards(read("support/index.html")))
    print(f"站点自检通过：{n} 张 App 卡片，三处计数一致，卡片无半填")
    return 0


if __name__ == "__main__":
    sys.exit(main())
