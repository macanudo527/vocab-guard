import json
from pathlib import Path

import pytest

from app.lists import ListError, load_dir, load_lists

LISTS = Path(__file__).resolve().parents[2] / "lists"


@pytest.fixture(scope="module")
def sample():
    return {lst.name: lst for lst in load_dir(LISTS / "sample")}


def test_levels_are_cumulative(sample):
    n5, n4 = sample["sample-n5"], sample["sample-n4"]
    assert n5.levels == ("N5",)
    assert n4.levels == ("N5", "N4")
    assert "食べる" in n5.words and "食べる" in n4.words
    assert "料理" not in n5.words and "料理" in n4.words
    assert "強" not in n5.kanji and "強" in n4.kanji
    assert n5.words < n4.words
    assert n5.kanji < n4.kanji


def test_readings(sample):
    n5 = sample["sample-n5"]
    assert "べんきょう" in n5.readings
    assert n5.word_readings["明日"] == ("あした",)


def test_load_lists_finds_every_list():
    lists = load_lists(LISTS)
    assert {"sample-n5", "sample-n4", "jlpt-n5", "jlpt-n1"} <= set(lists)
    assert lists["jlpt-n4"].levels == ("N5", "N4")


def write_list(path: Path, meta: dict, vocab: str, kanji: str | None = None) -> Path:
    path.mkdir(parents=True)
    (path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (path / "vocab.csv").write_text(vocab, encoding="utf-8")
    if kanji is not None:
        (path / "kanji.csv").write_text(kanji, encoding="utf-8")
    return path


def test_kanji_file_is_optional(tmp_path):
    d = write_list(
        tmp_path / "en",
        {"name": "en", "lang": "en", "levels": ["A1"]},
        "word,reading,level\ngo,,A1\n",
    )
    (lst,) = load_dir(d)
    assert lst.name == "en-a1"
    assert lst.kanji is None
    assert lst.words == {"go"}
    assert lst.readings == set()


def test_unknown_level_is_rejected(tmp_path):
    d = write_list(
        tmp_path / "x",
        {"name": "x", "lang": "ja", "levels": ["N5"]},
        "word,reading,level\n水,みず,N9\n",
    )
    with pytest.raises(ListError, match="N9"):
        load_dir(d)


def test_bad_header_is_rejected(tmp_path):
    d = write_list(
        tmp_path / "x",
        {"name": "x", "lang": "ja", "levels": ["N5"]},
        "expression,reading,level\n水,みず,N5\n",
    )
    with pytest.raises(ListError, match="header"):
        load_dir(d)


def test_duplicate_names_are_rejected(tmp_path):
    meta = {"name": "x", "lang": "ja", "levels": ["N5"]}
    write_list(tmp_path / "a", meta, "word,reading,level\n")
    write_list(tmp_path / "b", meta, "word,reading,level\n")
    with pytest.raises(ListError, match="duplicate"):
        load_lists(tmp_path)


def test_hidden_directories_are_skipped(tmp_path):
    meta = {"name": "x", "lang": "ja", "levels": ["N5"]}
    write_list(tmp_path / "data" / ".raw", meta, "word,reading,level\n")
    write_list(tmp_path / "data" / "x", meta, "word,reading,level\n")
    assert set(load_lists(tmp_path)) == {"x-n5"}
