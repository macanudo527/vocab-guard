def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_lists(client):
    lists = {lst["name"]: lst for lst in client.get("/lists").json()["lists"]}
    assert lists["sample-n4"] == {
        "name": "sample-n4",
        "lang": "ja",
        "level": "N4",
        "levels": ["N5", "N4"],
        "words": 54,
        "kanji": 44,
    }
    assert "jlpt-n3" in lists


def test_response_shape(client):
    r = client.post("/check", json={"text": "毎日勉強します。把握します。", "list": "sample-n5"})
    data = r.json()
    assert set(data) == {"pass", "pass_rate", "content_tokens", "sentences"}
    assert data["pass"] is False
    # 毎日 勉強 し 把握 し: 勉強 has above-level kanji and 把握 isn't in the list.
    assert data["content_tokens"] == 5
    assert data["pass_rate"] == 0.6
    first, second = data["sentences"]
    assert first["text"] == "毎日勉強します。"
    assert (first["start"], first["end"]) == (0, 8)
    assert second["violations"] == [
        {"surface": "把握", "lemma": "把握", "reading": "はあく", "reason": "not_in_list"}
    ]


def test_text_with_no_content_words_passes(client):
    data = client.post("/check", json={"text": "123。", "list": "sample-n5"}).json()
    assert data["pass"] is True
    assert data["pass_rate"] == 1.0
    assert data["content_tokens"] == 0


def test_list_is_required(client):
    r = client.post("/check", json={"text": "水。"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"
    assert "list" in r.json()["message"]


def test_unknown_list_names_the_available_ones(client):
    r = client.post("/check", json={"text": "水。", "list": "nope"})
    assert r.status_code == 400
    assert "sample-n5" in r.json()["message"]


def test_unsupported_lang(client):
    r = client.post("/check", json={"text": "water", "lang": "en", "list": "cefrj-a1"})
    assert r.status_code == 400
    assert r.json()["error"] == "unsupported_lang"


def test_oversized_body_is_rejected_before_parsing(client):
    r = client.post(
        "/check",
        content=b'{"text": "' + b"a" * 1_000_001 + b'", "list": "sample-n5"}',
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413
    assert r.json()["error"] == "request_too_large"


def test_long_sentence_without_breaks(client):
    # Sudachi rejects input over 49,149 bytes, so long sentences are chunked.
    r = client.post("/check", json={"text": "学校" * 10_000, "list": "sample-n5"})
    assert r.status_code == 200
    assert r.json()["pass"] is True
