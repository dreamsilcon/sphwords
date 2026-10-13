#!/usr/bin/env python3
"""Build compare.html: hub page of 辨析 / 易混 / 词源 notes extracted from chapter/*.html."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAPTER_DIR = ROOT / "chapter"
OUT = ROOT / "compare.html"

ARTICLE_RE = re.compile(
    r'<article class="entry" id="([^"]+)">(.*?)</article>', re.S
)
HEAD_RE = re.compile(r'<p class="head">(.*?)</p>', re.S)
# Keep block-level pieces in document order.
CHUNK_RE = re.compile(
    r'(<p class="line">.*?</p>|<div class="compare-table-wrap">.*?</div>)',
    re.S,
)
MARKER_RE = re.compile(
    r"(辨析\s|易混：|易混记忆：|联合记忆：|Recall：|词族对照：|词族与易混：|词族：|词源：|词根词缀：)"
)
STUB_RE = re.compile(r"见第\d+章")
TAG_RE = re.compile(r"<[^>]+>")


def plain(html: str) -> str:
    text = TAG_RE.sub("", html)
    text = (
        text.replace("&amp;", "&")
        .replace("&#x27;", "'")
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return re.sub(r"\s+", " ", text).strip()


def chapter_num(stem: str) -> str:
    return str(int(stem))


def classify(flags: set[str], has_table: bool) -> str:
    if has_table:
        return "compare"
    if flags & {"易混", "联合记忆", "Recall", "词族", "辨析"}:
        return "confusable"
    return "etymology"


def extract_entries() -> list[dict]:
    entries: list[dict] = []
    for path in sorted(CHAPTER_DIR.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        stem = path.stem
        for m in ARTICLE_RE.finditer(text):
            eid, body = m.group(1), m.group(2)
            head_m = HEAD_RE.search(body)
            if not head_m:
                continue
            head_html = head_m.group(1)
            head_plain = plain(head_html)

            chunks = CHUNK_RE.findall(body)
            start = None
            for i, chunk in enumerate(chunks):
                if MARKER_RE.search(chunk):
                    start = i
                    break
            if start is None:
                continue

            block_chunks = chunks[start:]
            block_html = "\n".join(block_chunks)
            has_table = "compare-table" in block_html
            block_plain = plain(block_html)

            flags: set[str] = set()
            if re.search(r"辨析\s", block_plain):
                flags.add("辨析")
            if "易混：" in block_plain or "易混记忆：" in block_plain:
                flags.add("易混")
            if "联合记忆：" in block_plain:
                flags.add("联合记忆")
            if "Recall：" in block_plain:
                flags.add("Recall")
            if "词族" in block_plain:
                flags.add("词族")
            if "词源：" in block_plain:
                flags.add("词源")
            if "词根词缀：" in block_plain:
                flags.add("词根词缀")

            meaningful = flags & {
                "辨析",
                "易混",
                "联合记忆",
                "Recall",
                "词族",
                "词源",
                "词根词缀",
            }
            if not meaningful:
                continue

            first_plain = plain(block_chunks[0])
            if not MARKER_RE.search(first_plain) and not has_table:
                continue

            # Skip pointer-only 辨析 that just say “见第X章” (full table lives elsewhere).
            if (
                not has_table
                and "辨析" in flags
                and STUB_RE.search(block_plain)
                and not (flags & {"易混", "联合记忆", "Recall", "词族", "词源", "词根词缀"})
            ):
                continue

            title = first_plain
            if len(title) > 72:
                title = title[:72] + "…"

            entries.append(
                {
                    "stem": stem,
                    "chapter": chapter_num(stem),
                    "id": eid,
                    "head": head_plain,
                    "title": title,
                    "block_html": block_html,
                    "has_table": has_table,
                    "flags": flags,
                    "section": classify(flags, has_table),
                    "href": f"chapter/{path.name}#{eid}",
                    "anchor": f"{stem}-{eid}",
                }
            )
    return entries


SECTION_META = [
    (
        "compare",
        "标准对比表",
        "咱们做过的表格辨析（释义 / 语气 / 侧重点 / 搭配 / 例句 / 一句话）。",
    ),
    (
        "confusable",
        "易混 · 联合记忆 · Recall",
        "拼写相近、中文易混、或需要串起来记的词。",
    ),
    (
        "etymology",
        "词源 · 词根词缀",
        "用词根词缀串起来的记忆笔记（也常用来分清易混词）。",
    ),
]


def render(entries: list[dict]) -> str:
    by_sec: dict[str, list[dict]] = {k: [] for k, *_ in SECTION_META}
    for e in entries:
        by_sec.setdefault(e["section"], []).append(e)

    toc_parts = []
    body_parts = []
    for key, label, blurb in SECTION_META:
        group = by_sec.get(key, [])
        if not group:
            continue
        toc_parts.append(f'<li><a href="#{key}">{label}</a>（{len(group)}）</li>')
        body_parts.append(f'<section class="compare-section" id="{key}">')
        body_parts.append(f"<h2>{label}</h2>")
        body_parts.append(f'<p class="section-blurb">{blurb}</p>')
        body_parts.append('<ul class="compare-toc-local">')
        for e in group:
            body_parts.append(
                f'<li><a href="#{e["anchor"]}">第{e["chapter"]}章 · {plain(e["title"])}</a></li>'
            )
        body_parts.append("</ul>")
        for e in group:
            tags = " · ".join(sorted(e["flags"]))
            body_parts.append(
                f'<article class="entry compare-card" id="{e["anchor"]}">'
            )
            body_parts.append(
                f'<p class="head"><span class="compare-ch">第{e["chapter"]}章</span> '
                f'{e["head"]}</p>'
            )
            body_parts.append(
                f'<p class="compare-meta"><span>{tags}</span>'
                f'<a href="{e["href"]}">查看原词条 →</a></p>'
            )
            body_parts.append(e["block_html"])
            body_parts.append("</article>")
        body_parts.append("</section>")

    total = len(entries)
    toc_html = "\n".join(toc_parts)
    body_html = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>辨析 · 易混词汇总 · 宋鹏昊单词笔记</title>
  <link rel="stylesheet" href="assets/style.css" />
</head>
<body>
  <header class="site-header">
    <div class="inner">
      <a class="brand" href="index.html">SPH<span>Words</span></a>
      <nav class="site-nav" data-site-nav data-active="compare" aria-label="主导航"></nav>
    </div>
  </header>
  <section class="hero wrap compare-hero">
    <h1>辨析 · 易混词汇总</h1>
    <p>把各章里咱们补过的对比表、易混词和词源记忆集中到一页，方便下一阶段专项复习。点「查看原词条」可回到章节上下文。</p>
    <p class="note">共 {total} 组 · 本页由 <code>scripts/build_compare_hub.py</code> 从各章自动抽取生成；新增辨析后重新运行该脚本即可更新。</p>
  </section>
  <nav class="wrap compare-toc">
    <h2>目录</h2>
    <ul>
{toc_html}
    </ul>
  </nav>
  <main class="wrap entries compare-hub">
{body_html}
  </main>
  <footer class="site-footer"><div class="wrap">宋鹏昊单词课原始笔记 · 辨析汇总</div></footer>
  <script src="assets/search.js" defer></script>
  <script src="assets/site-base.js"></script>
  <script src="assets/site-nav.js"></script>
  <script src="assets/compare-pager.js" defer></script>
</body>
</html>
"""


def main() -> None:
    entries = extract_entries()
    OUT.write_text(render(entries), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} with {len(entries)} groups")
    for key, label, _ in SECTION_META:
        n = sum(1 for e in entries if e["section"] == key)
        print(f"  {label}: {n}")


if __name__ == "__main__":
    main()
