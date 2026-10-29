"""Word-list loading. Format: lists/README.md.

Each list directory holds meta.json, vocab.csv and an optional kanji.csv.
Levels are cumulative: list "jlpt" with levels N5..N1 becomes "jlpt-n5",
"jlpt-n4", ... where "jlpt-n4" allows every N5 and N4 row.
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path


class ListError(ValueError):
    pass


@dataclass(frozen=True)
class LevelList:
    name: str  # e.g. "jlpt-n4"
    base: str  # e.g. "jlpt"
    lang: str
    level: str
    levels: tuple[str, ...]  # every level this list allows, easiest first
    words: frozenset[str]
    readings: frozenset[str]
    word_readings: dict[str, tuple[str, ...]]
    word_levels: dict[str, str]  # easiest level each word or reading appears at
    reading_levels: dict[str, str]
    kanji: frozenset[str] | None  # None when the list has no kanji.csv


def discover(root: Path) -> list[Path]:
    """List directories under root (one or two levels deep) that contain meta.json."""
    found = []
    for meta in sorted([*root.glob("*/meta.json"), *root.glob("*/*/meta.json")]):
        rel = meta.parent.relative_to(root)
        if not any(part.startswith(".") for part in rel.parts):
            found.append(meta.parent)
    return found


def _read_csv(path: Path, header: list[str]) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != header:
            raise ListError(f"{path}: header must be {','.join(header)}, got {reader.fieldnames}")
        return list(reader)


def _check_level(path: Path, row: dict[str, str], levels: list[str]) -> str:
    level = row["level"]
    if level not in levels:
        raise ListError(f"{path}: level {level!r} is not in meta.json levels {levels}")
    return level


def load_dir(directory: Path) -> list[LevelList]:
    try:
        meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        base, lang, levels = meta["name"], meta["lang"], list(meta["levels"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ListError(f"{directory}/meta.json: needs name, lang and levels ({e})") from e
    if not levels or len(set(levels)) != len(levels):
        raise ListError(f"{directory}/meta.json: levels must be non-empty and unique")

    vocab_path = directory / "vocab.csv"
    vocab = [
        (row["word"], row["reading"], _check_level(vocab_path, row, levels))
        for row in _read_csv(vocab_path, ["word", "reading", "level"])
    ]
    kanji_path = directory / "kanji.csv"
    kanji = None
    if kanji_path.exists():
        kanji = [
            (row["kanji"], _check_level(kanji_path, row, levels))
            for row in _read_csv(kanji_path, ["kanji", "level"])
        ]

    result = []
    for i, level in enumerate(levels):
        allowed = set(levels[: i + 1])
        rows = [(w, r) for w, r, lv in vocab if lv in allowed]
        word_readings: dict[str, list[str]] = {}
        word_levels: dict[str, str] = {}
        reading_levels: dict[str, str] = {}
        # Easiest level first, so setdefault keeps the easiest one.
        for word, reading, lv in sorted(vocab, key=lambda row: levels.index(row[2])):
            if lv not in allowed:
                continue
            word_levels.setdefault(word, lv)
            if reading:
                reading_levels.setdefault(reading, lv)
        for word, reading in rows:
            if reading:
                word_readings.setdefault(word, []).append(reading)
        result.append(
            LevelList(
                name=f"{base}-{level.lower()}",
                base=base,
                lang=lang,
                level=level,
                levels=tuple(levels[: i + 1]),
                words=frozenset(w for w, _ in rows),
                readings=frozenset(r for _, r in rows if r),
                word_readings={w: tuple(rs) for w, rs in word_readings.items()},
                word_levels=word_levels,
                reading_levels=reading_levels,
                kanji=None if kanji is None else frozenset(k for k, lv in kanji if lv in allowed),
            )
        )
    return result


def load_lists(root: Path) -> dict[str, LevelList]:
    lists: dict[str, LevelList] = {}
    for directory in discover(root):
        for level_list in load_dir(directory):
            if level_list.name in lists:
                raise ListError(f"duplicate list name {level_list.name!r} in {directory}")
            lists[level_list.name] = level_list
    return lists
