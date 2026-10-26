from pathlib import Path

import pytest
import yaml

CASES = yaml.safe_load((Path(__file__).parent / "golden.yaml").read_text(encoding="utf-8"))


def test_enough_cases():
    assert len(CASES) >= 15


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden(client, case):
    body = {
        "text": case["text"] * case.get("text_repeat", 1),
        "lang": "ja",
        "list": case["list"],
        "allow": case.get("allow", []),
        "options": case.get("options", {}),
    }
    expect = case["expect"]
    r = client.post("/check", json=body)
    data = r.json()

    if "status" in expect:
        assert r.status_code == expect["status"], data
        assert data["error"] == expect["error"]
        assert data["message"]
        return

    assert r.status_code == 200, data
    got = [{"sentence": s["index"], **v} for s in data["sentences"] for v in s["violations"]]
    want = expect["violations"]
    assert [(v["sentence"], v["surface"], v["reason"]) for v in got] == [
        (v["sentence"], v["surface"], v["reason"]) for v in want
    ], got
    for g, w in zip(got, want, strict=True):
        for key in ("kanji", "suggestion"):
            if key in w:
                assert g.get(key) == w[key], g
    assert data["pass"] == (not want)
    for key in ("pass", "content_tokens"):
        if key in expect:
            assert data[key] == expect[key], data
    if "sentences" in expect:
        assert len(data["sentences"]) == expect["sentences"]
