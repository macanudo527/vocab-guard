#!/usr/bin/env bash
# Downloads word-list sources at pinned commits, verifies their checksums,
# and converts them. See lists/SOURCES.md.
#   jlpt  -> lists/jlpt/        (committed; CC BY allows redistribution)
#   cefrj -> lists/data/cefrj/  (gitignored; redistribution not granted)
#
#   scripts/fetch_lists.sh            # all lists
#   scripts/fetch_lists.sh jlpt       # one list (jlpt or cefrj)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$ROOT/lists/data"

JAM=https://raw.githubusercontent.com/jamsinclair/open-anki-jlpt-decks/1ad66734417aca9dbcca6b2d5ee440cb13ab3ba0/src
BLU=https://raw.githubusercontent.com/Bluskyo/JLPT_Vocabulary/4358f932937ad0232194a36e9f4f875094910c6b/data/kanji/parsedData
OLP=https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f

fetch() { # url dest sha256
  curl -sSfL --retry 3 -o "$2" "$1"
  echo "$3  $2" | sha256sum -c --quiet - || { echo "checksum mismatch: $1" >&2; exit 1; }
}

fetch_jlpt() {
  local raw="$DATA/.raw/jlpt"
  mkdir -p "$raw"
  fetch "$JAM/n5.csv" "$raw/vocab-n5.csv" f89abc86b391c4f2b551bbf8910b0de6cd600973b3a9f8d98347513921929ebe
  fetch "$JAM/n4.csv" "$raw/vocab-n4.csv" 0e835f40a8d2a1f191d7aa499076002756fa099b95634758376f43c73793e9f6
  fetch "$JAM/n3.csv" "$raw/vocab-n3.csv" ba071571d344e60b0e1fd11cd2e98a6aaa04515361653ca45147129460531297
  fetch "$JAM/n2.csv" "$raw/vocab-n2.csv" 2d0f1ddd6222881cd9fc2ca701db74300af99b3f1f84d5ac3c18411c20f0c055
  fetch "$JAM/n1.csv" "$raw/vocab-n1.csv" 120911636c019899552aa6d7bd64b036ecef4bedfe272a744f75735c46aae5cd
  fetch "$BLU/n5_kanji.csv" "$raw/kanji-n5.csv" eb0b1f3c077f62b325a096562461bae6c5d4fb21015637210a3a3ef91713e651
  fetch "$BLU/n4_kanji.csv" "$raw/kanji-n4.csv" 42a8993084e741d6885147f181a886a5e2d515e137a8433cbf2820f8c5086a1c
  fetch "$BLU/n3_kanji.csv" "$raw/kanji-n3.csv" f32b1ac7e02efcbf29c46e9dfb75bdac9526254ed448b245d4cc3915410754ef
  fetch "$BLU/n2_kanji.csv" "$raw/kanji-n2.csv" 3678f64b6bccaca53686f31e9c2e4825e85ef5173d2312c134008dfcfa824f95
  fetch "$BLU/n1_kanji.csv" "$raw/kanji-n1.csv" ae0e4f451f4eae702c5d99d112e6910250a59568101a2639b9e574536d8d98ee
  python3 "$ROOT/scripts/convert_lists.py" jlpt "$raw" "$ROOT/lists/jlpt"
}

fetch_cefrj() {
  local raw="$DATA/.raw/cefrj"
  mkdir -p "$raw"
  fetch "$OLP/cefrj-vocabulary-profile-1.5.csv" "$raw/cefrj-vocabulary-profile-1.5.csv" b0dd3c635f1c9a4fdf1490c7e5b7c48e8bbe55b652ad0c9860a95f98e10ae498
  python3 "$ROOT/scripts/convert_lists.py" cefrj "$raw" "$DATA/cefrj"
}

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=(jlpt cefrj)
for t in "${targets[@]}"; do
  case "$t" in
    jlpt) fetch_jlpt ;;
    cefrj) fetch_cefrj ;;
    *) echo "unknown list: $t (expected jlpt or cefrj)" >&2; exit 2 ;;
  esac
done
