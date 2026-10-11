#!/usr/bin/env python3
"""Build assets/drill-index.json for the mobile self-test page.

Cards include core headwords plus related words found in:
  - compare-table columns
  - 易混 / 联合记忆 lines
  - short glossary lines / table cells with POS + Chinese sense

Each card has its own short sense for daily drill without opening details.
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
LINE_RE = re.compile(r'<p class="line">(.*?)</p>', re.S)
TABLE_RE = re.compile(
    r'<div class="compare-table-wrap">\s*<table class="compare-table">(.*?)</table>',
    re.S,
)
CELL_RE = re.compile(r"<t[dh]>(.*?)</t[dh]>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"^([A-Za-z][A-Za-z]{1,}(?:[/'.-][A-Za-z]+)*)")
EXTRA_RE = re.compile(r"(辨析|易混：|易混记忆：|联合记忆：|Recall：|词源：|词根词缀：|词族)")
IPA_BLOCK = (
    r"(?:(?:英|美)\s*)?/[^/\n]{1,80}/"
    r"(?:\s*(?:[，,]\s*)?(?:(?:英|美)\s*)?/[^/\n]{1,80}/)?"
)
POS = r"(?:n|v|vt|vi|adj|adv|prep|conj|num|pron|n/v|v/n)"
CN = re.compile(r"[\u4e00-\u9fff]")
PREFIX_RE = re.compile(r"^(?:易混：|易混记忆：|联合记忆：|补全：|词族：)\s*")

# whole / segment glossary chunk — POS must be its own token (space before it)
CHUNK_RE = re.compile(
    rf"^(?P<word>[A-Za-z]{{3,}}(?:[/'.-][A-Za-z]+)*)"
    rf"(?:\s*/\s*[A-Za-z]{{3,}}(?:[/'.-][A-Za-z]+)*)*"
    rf"(?:\s*{IPA_BLOCK})?"
    rf"\s+(?P<sense>{POS}\.?\s*.+)$",
    re.I,
)
# word + optional IPA + Chinese gloss (no POS), e.g. intensity /ipa/ 强度
CHUNK_CN_RE = re.compile(
    rf"^(?P<word>[A-Za-z]{{3,}}(?:[/'.-][A-Za-z]+)*)"
    rf"(?:\s*/\s*[A-Za-z]{{3,}}(?:[/'.-][A-Za-z]+)*)*"
    rf"(?:\s*{IPA_BLOCK})?"
    rf"\s+(?P<sense>[\u4e00-\u9fff（(].+)$",
)


def strip_tags(html: str) -> str:
    return unescape(TAG_RE.sub("", html)).replace("\xa0", " ")


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_word(text: str) -> str | None:
    text = re.sub(r"^\[[^\]]+\]\s*", "", normalize_space(text))
    m = WORD_RE.match(text)
    if not m:
        return None
    return m.group(1).strip(" ./") or None


def extract_ipa(text: str, word: str) -> str:
    rest = normalize_space(text)
    if rest.lower().startswith(word.lower()):
        rest = rest[len(word) :].lstrip(" ,;·：")
    # drop alternate spelling tokens before IPA: / fertilize
    rest = re.sub(rf"^/\s*[A-Za-z]{{3,}}(?:[/'.-][A-Za-z]+)*\s*", "", rest).lstrip(" ,;·")
    m = re.match(rf"^{IPA_BLOCK}", rest)
    return normalize_space(m.group(0)) if m else ""


def extract_sense(text: str, word: str) -> str:
    rest = normalize_space(text)
    if rest.lower().startswith(word.lower()):
        rest = rest[len(word) :]
    rest = rest.lstrip(" ,;·：")
    rest = re.sub(rf"^/\s*[A-Za-z]{{3,}}(?:[/'.-][A-Za-z]+)*\s*", "", rest).lstrip(" ,;·")
    for _ in range(3):
        new = re.sub(r"^(?:英|美)\s*", "", rest)
        new2 = re.sub(rf"^{IPA_BLOCK}\s*", "", new, count=1)
        if new2 == rest:
            break
        rest = new2.lstrip(" ,;·：")
    # If IPA residue remains, cut to POS
    mpos = re.search(rf"(?:^|\s)({POS})\.?\s*", rest, re.I)
    if mpos and (
        rest.startswith("/")
        or rest[:1] in "ːˈˌ"
        or not re.match(rf"^{POS}\.?", rest, re.I)
    ):
        rest = rest[mpos.start() :].lstrip()
    rest = re.split(
        r"/{2,}|\s*老师说|,?\s*这个单词|\s*这个词|\s*注意|\s*med=|\s*以前读|\s*（见第|\s*\(见第|\s*详见|\s*完整对比|\s*另见",
        rest,
        maxsplit=1,
    )[0].strip(" ,;·：")
    if len(rest) > 64:
        rest = rest[:63].rstrip(" ，,;、") + "…"
    rest = rest.rstrip(" ，,;、")
    if not sense_ok(rest):
        return ""
    return rest


def slugify(word: str) -> str:
    s = word.lower().replace("/", "-").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "entry"


def sense_ok(sense: str) -> bool:
    if not sense or not CN.search(sense):
        return False
    if sense.startswith("/") or sense[:1] in "ːˈˌ":
        return False
    if re.match(
        r"^(is|are|was|were|the|a|an|on|of|to|my|your|his|her|their|this|that|behind|into|from)\b",
        sense,
        re.I,
    ):
        return False
    return True


def parse_chunk(text: str) -> tuple[str, str, str] | None:
    t = normalize_space(text)
    t = PREFIX_RE.sub("", t)
    if len(t) > 110 and t.count(" ") > 14:
        return None
    m = CHUNK_RE.match(t) or CHUNK_CN_RE.match(t)
    if not m:
        return None
    word = m.group("word")
    if CHUNK_RE.match(t):
        sense = extract_sense(t, word)
    else:
        sense = m.group("sense").strip()
        sense = re.split(r"\s{2,}|。", sense)[0].strip()
        if len(sense) > 64:
            sense = sense[:63].rstrip(" ，,;、") + "…"
    if not sense_ok(sense):
        return None
    return word, extract_ipa(t, word), sense


def parse_prefixed_or_multi(text: str) -> list[tuple[str, str, str]]:
    t = normalize_space(text)
    prefixed = bool(PREFIX_RE.match(t))
    t2 = PREFIX_RE.sub("", t)
    parts = re.split(r"[；;]", t2) if prefixed else [t2]
    out: list[tuple[str, str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # also split "word1 v.x  word2 n.y" on 2+ spaces before a lemma+POS
        bits = re.split(rf"\s{{2,}}(?=[A-Za-z]{{3,}}\s+(?:{IPA_BLOCK}\s+)?{POS}\.?)", part)
        if len(bits) == 1:
            bits = re.split(rf"(?<=[\u4e00-\u9fff])\s+(?=[A-Za-z]{{3,}}\s+(?:{IPA_BLOCK}\s+)?{POS}\.?)", part)
        for bit in bits:
            hit = parse_chunk(bit.strip(" ，,、"))
            if hit:
                out.append(hit)
    return out


def parse_compare_table(table_html: str) -> list[tuple[str, str, str]]:
    thead = re.search(r"<thead>(.*?)</thead>", table_html, re.S)
    if not thead:
        return []
    headers = [
        normalize_space(strip_tags(h))
        for h in re.findall(r"<th>(.*?)</th>", thead.group(1), re.S)
    ]
    words: list[tuple[str, str]] = []
    for h in headers[1:]:
        if not h or h in {"对比点"}:
            continue
        # family header: "intense / intensive 族"
        if "族" in h:
            for part in re.split(r"\s*/\s*", re.sub(r"\s*族$", "", h)):
                w = extract_word(part)
                if w and len(w) >= 3:
                    words.append((w, extract_ipa(part, w)))
            continue
        w = extract_word(h)
        if not w or len(h) > 56:
            continue
        words.append((w, extract_ipa(h, w)))
    if not words:
        return []

    def row_cells(label: str) -> list[str]:
        for row in re.findall(r"<tr>(.*?)</tr>", table_html, re.S):
            th = re.search(r"<th>(.*?)</th>", row, re.S)
            if not th:
                continue
            if normalize_space(strip_tags(th.group(1))) != label:
                continue
            return [normalize_space(strip_tags(td)) for td in re.findall(r"<td>(.*?)</td>", row, re.S)]
        return []

    senses = row_cells("释义") or row_cells("一句话") or row_cells("核心感觉")
    out: list[tuple[str, str, str]] = []
    for i, (word, ipa) in enumerate(words):
        sense = senses[i].strip() if i < len(senses) else ""
        if not sense or not CN.search(sense):
            continue
        if len(sense) > 64:
            sense = sense[:63].rstrip(" ，,;、") + "…"
        out.append((word, ipa, sense))
    return out


def parse_table_cells(table_html: str) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    labels = {
        "对比点",
        "释义",
        "语气",
        "侧重点",
        "常见搭配",
        "例句",
        "一句话",
        "词性",
        "形容词",
        "名词",
        "副词",
        "动词",
        "核心画面",
        "核心感觉",
        "出处",
    }
    for cell in CELL_RE.findall(table_html):
        text = normalize_space(strip_tags(cell))
        if not text or text in labels or len(text) > 140 or not CN.search(text):
            continue
        raw_parts = re.split(r"<br\s*/?>", cell, flags=re.I)
        chunks = [normalize_space(strip_tags(p)) for p in raw_parts]
        if len(chunks) == 1:
            # also split dense inventory cells on Chinese semicolon / period boundaries before a lemma
            chunks = re.split(
                rf"(?<=[\u4e00-\u9fff；;])\s*(?=[A-Za-z]{{3,}}\s)",
                text,
            )
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or chunk in labels or not CN.search(chunk):
                continue
            hit = parse_chunk(chunk)
            if hit:
                out.append(hit)
    return out


def upsert(by_key: dict[str, dict], card: dict) -> None:
    key = card["word"].lower()
    prev = by_key.get(key)
    if not prev:
        by_key[key] = card
        return
    if prev["kind"] == "head" and card["kind"] != "head":
        if card.get("extra"):
            prev["extra"] = True
        return
    if card["kind"] == "head" and prev["kind"] != "head":
        by_key[key] = card
        return
    # same kind: keep richer sense / ipa
    if len(card["sense"]) > len(prev["sense"]):
        prev["sense"] = card["sense"]
    if card.get("ipa") and not prev.get("ipa"):
        prev["ipa"] = card["ipa"]
    if card.get("extra"):
        prev["extra"] = True


def main() -> None:
    by_key: dict[str, dict] = {}

    for path in sorted(CHAPTER_DIR.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        chapter_no = path.stem.lstrip("0") or path.stem
        for m in ARTICLE_RE.finditer(html):
            eid, body = m.group(1), m.group(2)
            url = f"chapter/{path.name}#{eid}"
            extra = bool(EXTRA_RE.search(body))

            head_m = HEAD_RE.search(body)
            if head_m:
                head_text = normalize_space(strip_tags(head_m.group(1)))
                word = extract_word(head_text)
                if word:
                    sense = extract_sense(head_text, word)
                    if sense:
                        upsert(
                            by_key,
                            {
                                "word": word,
                                "ipa": extract_ipa(head_text, word),
                                "sense": sense,
                                "chapter": chapter_no,
                                "url": url,
                                "id": eid,
                                "kind": "head",
                                "extra": extra,
                            },
                        )

            for tm in TABLE_RE.finditer(body):
                table_html = tm.group(1)
                related_hits = parse_compare_table(table_html) + parse_table_cells(table_html)
                for word, ipa, sense in related_hits:
                    upsert(
                        by_key,
                        {
                            "word": word,
                            "ipa": ipa,
                            "sense": sense,
                            "chapter": chapter_no,
                            "url": url,
                            "id": f"{eid}__{slugify(word)}",
                            "kind": "related",
                            "extra": True,
                        },
                    )

            for lm in LINE_RE.finditer(body):
                line = normalize_space(strip_tags(lm.group(1)))
                if not line or not CN.search(line):
                    continue
                prefixed = bool(PREFIX_RE.match(line))
                if prefixed:
                    hits = parse_prefixed_or_multi(line)
                else:
                    # only tight whole-line glossary glosses
                    if len(line) > 90:
                        continue
                    if re.match(
                        r"^(辨析|词源|词根|Recall|中文|记忆|The|He|She|It|They|We|You|I|This|That)\b",
                        line,
                    ):
                        continue
                    hit = parse_chunk(line)
                    hits = [hit] if hit else []
                for word, ipa, sense in hits:
                    upsert(
                        by_key,
                        {
                            "word": word,
                            "ipa": ipa,
                            "sense": sense,
                            "chapter": chapter_no,
                            "url": url,
                            "id": f"{eid}__{slugify(word)}",
                            "kind": "related",
                            "extra": True,
                        },
                    )

    cards = sorted(
        by_key.values(),
        key=lambda c: (
            int(c["chapter"]) if str(c["chapter"]).isdigit() else 999,
            c["word"].lower(),
        ),
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(cards, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    related_n = sum(1 for c in cards if c["kind"] == "related")
    head_n = sum(1 for c in cards if c["kind"] == "head")
    print(
        f"Wrote {OUT.relative_to(ROOT)} · {len(cards)} cards "
        f"(head {head_n}, related {related_n})"
    )


if __name__ == "__main__":
    main()
