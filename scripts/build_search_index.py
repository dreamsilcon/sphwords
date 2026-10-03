#!/usr/bin/env python3
"""Scan chapter HTML, attach entry anchors, and build assets/search-index.json."""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAPTER_DIR = ROOT / "chapter"
INDEX_PATH = ROOT / "assets" / "search-index.json"

ARTICLE_RE = re.compile(
    r'(<article\s+class="entry")([^>]*)(>)(.*?)(</article>)',
    re.S,
)
HEAD_RE = re.compile(r'<p class="head">(.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
# Lemma only: letters with optional internal / - ' . (no spaces, so IPA "/saɪt/" is not swallowed)
WORD_RE = re.compile(r"^([A-Za-z]+(?:[/'.-][A-Za-z]+)*)")


def strip_tags(html: str) -> str:
    return unescape(TAG_RE.sub("", html)).replace("\xa0", " ")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_word(head_text: str) -> str | None:
    text = normalize_space(head_text)
    if not text:
        return None
    # Drop leading bracket phonetics like [væn]
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    m = WORD_RE.match(text)
    if not m:
        return None
    word = m.group(1).strip(" ./")
    return word or None


def extract_gloss(head_text: str, word: str) -> str:
    rest = normalize_space(head_text)
    if rest.lower().startswith(word.lower()):
        rest = rest[len(word) :]
    rest = rest.strip(" ,;·")
    rest = re.sub(r"^(?:英|美)\s*", "", rest)
    # Skip one or two IPA blocks: /.../ or 英/.../ ，美/.../
    rest = re.sub(
        r"^(?:(?:英|美)\s*)?/[^/\n]{1,60}/(?:\s*[，,]\s*(?:英|美)?\s*/[^/\n]{1,60}/)?\s*",
        "",
        rest,
        count=1,
    )
    rest = rest.strip(" ,;·")
    # Compact long teacher notes
    rest = re.split(r"/{2,}|\s{2,}老师说", rest)[0].strip()
    if len(rest) > 48:
        rest = rest[:47].rstrip() + "…"
    return rest


def slugify(word: str) -> str:
    s = word.lower()
    s = s.replace("/", "-").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "entry"


def ensure_script(html: str, script_src: str) -> str:
    if "assets/search.js" in html:
        return html
    tag = f'  <script src="{script_src}" defer></script>\n'
    if "</body>" in html:
        return html.replace("</body>", tag + "</body>", 1)
    return html + "\n" + tag


def process_chapter(path: Path) -> list[dict]:
    html = path.read_text(encoding="utf-8")
    used: dict[str, int] = {}
    entries: list[dict] = []
    chapter_no = path.stem.lstrip("0") or path.stem

    def repl(match: re.Match[str]) -> str:
        open_tag, attrs, gt, body, close = match.groups()
        head_m = HEAD_RE.search(body)
        if not head_m:
            return match.group(0)
        head_text = normalize_space(strip_tags(head_m.group(1)))
        word = extract_word(head_text)
        if not word:
            return match.group(0)

        base = slugify(word)
        n = used.get(base, 0) + 1
        used[base] = n
        entry_id = f"w-{base}" if n == 1 else f"w-{base}-{n}"

        attrs_clean = re.sub(r'\s*id="[^"]*"', "", attrs)
        new_open = f'{open_tag}{attrs_clean} id="{entry_id}"{gt}'

        gloss = extract_gloss(head_text, word)
        url = f"chapter/{path.name}#{entry_id}"
        entries.append(
            {
                "word": word,
                "head": head_text[:120],
                "gloss": gloss,
                "chapter": chapter_no,
                "url": url,
                "id": entry_id,
            }
        )
        return new_open + body + close

    new_html = ARTICLE_RE.sub(repl, html)
    new_html = ensure_script(new_html, "../assets/search.js")
    if new_html != html:
        path.write_text(new_html, encoding="utf-8")
    return entries


def main() -> None:
    all_entries: list[dict] = []
    for path in sorted(CHAPTER_DIR.glob("*.html")):
        all_entries.extend(process_chapter(path))

    index_html = ROOT / "index.html"
    index_html.write_text(
        ensure_script(index_html.read_text(encoding="utf-8"), "assets/search.js"),
        encoding="utf-8",
    )

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(all_entries, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Indexed {len(all_entries)} entries -> {INDEX_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
