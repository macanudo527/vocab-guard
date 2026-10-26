"""Convert downloaded source files into the vocab-guard list format.

Called by fetch_lists.sh. Standard library only, so it runs before any
project dependencies are installed.

    python3 convert_lists.py jlpt  <raw_dir> <out_dir>
    python3 convert_lists.py cefrj <raw_dir> <out_dir>
"""

import csv
import json
import re
import sys
from pathlib import Path

JLPT_LEVELS = ["N5", "N4", "N3", "N2", "N1"]
CEFR_LEVELS = ["A1", "A2", "B1", "B2"]
# Kanji that the upstream lists leave out entirely; see lists/SOURCES.md.
JLPT_KANJI_OVERRIDES = Path(__file__).parent / "overrides" / "jlpt-kanji.csv"

VARIANT_SEP = re.compile(r"[;,、\s]+")
PAREN_NOTE = re.compile(r"[(（][^)）]*[)）]")
AFFIX_MARK = re.compile(r"[～〜~]")
KANA_TAIL = re.compile(r"[぀-ゟ]+$")
KANJI = re.compile(r"[一-鿿々]")
HIRAGANA_READING = re.compile(r"[ぁ-ゖー]+")


def to_hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def split_variants(text: str) -> list[str]:
    text = AFFIX_MARK.sub("", PAREN_NOTE.sub("", text))
    return [v for v in VARIANT_SEP.split(text) if v]


def expand_entry(expression: str, reading: str) -> list[tuple[str, str]]:
    """Turn one source row into (word, reading) pairs.

    Source rows pack spelling variants together ("高校; 高等学校"), add notes
    in parentheses ("(花を〜) 生ける"), mark affixes with ～ ("～派"),
    sometimes drop shared okurigana from all but the last variant
    ("堅; 硬; 固い"), and in one row swap the two columns ("いただく", "頂く").
    """
    if KANJI.search(reading) and not KANJI.search(expression):
        expression, reading = reading, expression
    words = split_variants(expression)
    readings = [to_hiragana(r) for r in split_variants(reading)]
    if not words:
        return []
    tail = KANA_TAIL.search(words[-1])
    if tail and len(readings) == 1:
        words = [w if KANA_TAIL.search(w) else w + tail.group() for w in words]
    if not readings:
        # Kana-only entries sometimes leave the reading blank.
        readings = [to_hiragana(w) for w in words if not KANJI.search(w)]
    if len(words) == len(readings):
        pairs = list(zip(words, readings, strict=True))
    elif len(readings) == 1:
        pairs = [(w, readings[0]) for w in words]
    elif len(words) == 1:
        pairs = [(words[0], r) for r in readings]
    else:
        raise ValueError(f"cannot pair {expression!r} with {reading!r}")
    for word, read in pairs:
        if not HIRAGANA_READING.fullmatch(read):
            raise ValueError(f"reading {read!r} for {word!r} is not hiragana")
    return pairs


def write_list(out_dir: Path, meta: dict, vocab: dict, kanji: dict | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    order = {level: i for i, level in enumerate(meta["levels"])}
    with open(out_dir / "vocab.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["word", "reading", "level"])
        for (word, read), level in sorted(vocab.items(), key=lambda x: (order[x[1]], x[0])):
            w.writerow([word, read, level])
    if kanji is not None:
        with open(out_dir / "kanji.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["kanji", "level"])
            for char, level in sorted(kanji.items(), key=lambda x: (order[x[1]], x[0])):
                w.writerow([char, level])


def keep_easiest(table: dict, key, level: str, levels: list[str]) -> None:
    if key not in table or levels.index(level) < levels.index(table[key]):
        table[key] = level


def convert_jlpt(raw: Path, out: Path) -> None:
    vocab: dict[tuple[str, str], str] = {}
    kanji: dict[str, str] = {}
    for level in JLPT_LEVELS:
        n = level[1]
        with open(raw / f"vocab-n{n}.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for pair in expand_entry(row["expression"], row["reading"]):
                    keep_easiest(vocab, pair, level, JLPT_LEVELS)
        with open(raw / f"kanji-n{n}.csv", encoding="utf-8") as f:
            rows = [line.strip() for line in f if line.strip()]
        if rows[0] != "Kanji":
            raise ValueError(f"unexpected header in kanji-n{n}.csv: {rows[0]!r}")
        for char in rows[1:]:
            if len(char) != 1 or not KANJI.fullmatch(char):
                raise ValueError(f"not a single kanji in kanji-n{n}.csv: {char!r}")
            keep_easiest(kanji, char, level, JLPT_LEVELS)
    with open(JLPT_KANJI_OVERRIDES, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Overrides only fill gaps, so an upstream fix shows up as an error here.
            if row["kanji"] in kanji:
                raise ValueError(f"override {row['kanji']!r} is already in the upstream list")
            kanji[row["kanji"]] = row["level"]
    meta = {"name": "jlpt", "lang": "ja", "levels": JLPT_LEVELS}
    write_list(out, meta, vocab, kanji)
    print(f"jlpt: {len(vocab)} words, {len(kanji)} kanji -> {out}")


def convert_cefrj(raw: Path, out: Path) -> None:
    vocab: dict[tuple[str, str], str] = {}
    with open(raw / "cefrj-vocabulary-profile-1.5.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            # Headwords pack variants: "a.m./A.M./am/AM".
            for word in (w.strip() for w in row["headword"].split("/")):
                if word:
                    keep_easiest(vocab, (word, ""), row["CEFR"].strip(), CEFR_LEVELS)
    meta = {"name": "cefrj", "lang": "en", "levels": CEFR_LEVELS}
    write_list(out, meta, vocab, None)
    print(f"cefrj: {len(vocab)} words -> {out}")


if __name__ == "__main__":
    name, raw_dir, out_dir = sys.argv[1:4]
    {"jlpt": convert_jlpt, "cefrj": convert_cefrj}[name](Path(raw_dir), Path(out_dir))
