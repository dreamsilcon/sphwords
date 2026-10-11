#!/usr/bin/env python3
"""Build assets/drill-index.json for the mobile self-test page.

Card face uses lemma only; reveal uses a short core sense parsed from the
head line. Extensions / 辨析 / 易混 stay in the chapter entry (linked via url).
"""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAPTER_DIR = ROOT / "chapter"
OUT = ROOT / "assets" / "drill-index.json"

ARTICLE_RE = re.compile(
    r'<article\s+class="entry"[^>]*\bid="([^"]+)"[^>]*>(.*?)</article>',
    re.S,
)
HEAD_RE = re.compile(r'<p class="head">(.*?)</p>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"^([A-Za-z]+(?:[/'.-][A-Za-z]+)*)")
EXTRA_RE = re.compile(r"(辨析|易混：|易混记忆：|联合记忆：|Recall：|词源：|词根词缀：|词族)")
IPA_BLOCK = (
    r"(?:(?:英|美)\s*)?/[^/\n]{1,80}/"
    r"(?:\s*(?:[，,]\s*)?(?:(?:英|美)\s*)?/[^/\n]{1,80}/)?"
)


def strip_tags(html: str) -> str:
    return unescape(TAG_RE.sub("", html)).replace("\xa0", " ")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_word(head_text: str) -> str | None:
    text = re.sub(r"^\[[^\]]+\]\s*", "", normalize_space(head_text))
    m = WORD_RE.match(text)
    if not m:
        return None
    return m.group(1).strip(" ./") or None


def extract_ipa(head_text: str, word: str) -> str:
    rest = normalize_space(head_text)
    if rest.lower().startswith(word.lower()):
        rest = rest[len(word) :].strip()
    m = re.match(rf"^{IPA_BLOCK}", rest)
    if not m:
        return ""
    return normalize_space(m.group(0))


def extract_sense(head_text: str, word: str) -> str:
    rest = normalize_space(head_text)
    if rest.lower().startswith(word.lower()):
        rest = rest[len(word) :]
    rest = rest.strip(" ,;·")
    # Drop all leading IPA / 英美音标 blocks
    while True:
        new = re.sub(rf"^(?:英|美)\s*", "", rest)
        new2 = re.sub(rf"^{IPA_BLOCK}\s*", "", new, count=1)
        if new2 == rest:
            break
        rest = new2.strip(" ,;·")
    # Cut teacher asides / mnemonic tails
    rest = re.split(
        r"/{2,}|\s*老师说|,?\s*这个单词|\s*这个词|\s*注意|\s*med=|\s*以前读",
        rest,
        maxsplit=1,
    )[0].strip(" ,;·")
    # Keep POS + core gloss; trim very long tails
    if len(rest) > 64:
        rest = rest[:63].rstrip(" ，,;、") + "…"
    return rest.rstrip(" ，,;、")


def main() -> None:
    cards: list[dict] = []
    for path in sorted(CHAPTER_DIR.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        chapter_no = path.stem.lstrip("0") or path.stem
        for m in ARTICLE_RE.finditer(html):
            eid, body = m.group(1), m.group(2)
            head_m = HEAD_RE.search(body)
            if not head_m:
                continue
            head_text = normalize_space(strip_tags(head_m.group(1)))
            word = extract_word(head_text)
            if not word:
                continue
            sense = extract_sense(head_text, word)
            if not sense:
                continue
            cards.append(
                {
                    "word": word,
                    "ipa": extract_ipa(head_text, word),
                    "sense": sense,
                    "chapter": chapter_no,
                    "url": f"chapter/{path.name}#{eid}",
                    "id": eid,
                    "extra": bool(EXTRA_RE.search(body)),
                }
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(cards, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    extras = sum(1 for c in cards if c["extra"])
    print(
        f"Wrote {OUT.relative_to(ROOT)} · {len(cards)} cards · {extras} with extension notes"
    )


if __name__ == "__main__":
    main()
