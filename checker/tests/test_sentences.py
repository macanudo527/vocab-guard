import pytest

from app.ja import split_sentences


def split(text):
    return [text[s:e] for s, e in split_sentences(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("学校に行きます。先生が来ます。", ["学校に行きます。", "先生が来ます。"]),
        ("本当！？うそ?いいね!", ["本当！？", "うそ?", "いいね!"]),
        ("「行きます。」と言った。", ["「行きます。」", "と言った。"]),
        ("『はい！』", ["『はい！』"]),
        ("一行目\n二行目\r\n三行目", ["一行目", "二行目", "三行目"]),
        ("  前後の空白。 　\n\n次。", ["前後の空白。", "次。"]),
        ("終わりがない", ["終わりがない"]),
        ("", []),
        (" \n　", []),
    ],
)
def test_split(text, expected):
    assert split(text) == expected


def test_offsets_point_into_the_text():
    text = "毎日。\n  水を飲む！"
    assert split_sentences(text) == [(0, 3), (6, 11)]
