# Sources

Only `lists/sample/` is committed to this repo. Every other list is downloaded
and converted locally by `scripts/fetch_lists.sh`, at the pinned commits below.

| List | Committed? | Why |
| --- | --- | --- |
| `sample` | yes | Hand-made for this project, MIT. |
| `jlpt` | no, fetched | The upstream license is attested only second-hand (see below). |
| `cefrj` | no, fetched | The terms allow use but don't address redistribution. |

## `jlpt` vocabulary

- **Source:** [jamsinclair/open-anki-jlpt-decks](https://github.com/jamsinclair/open-anki-jlpt-decks),
  files `src/n5.csv` … `src/n1.csv`, commit `1ad66734417aca9dbcca6b2d5ee440cb13ab3ba0` (2025-08-11).
- **License:** MIT, Copyright (c) 2020 Jamie Sinclair.
- **Upstream data:** built from Jonathan Waller's JLPT Resources,
  <http://www.tanos.co.uk/jlpt/>, described as Creative Commons "BY" (see the notes below).
- **Fetched:** 2026-10-26.
- **Changes made by `convert_lists.py`:** spelling variants split into separate rows,
  notes in parentheses and the ～ affix marks removed, shared okurigana restored
  (`堅; 硬; 固い` → `堅い`, `硬い`, `固い`), katakana readings converted to hiragana,
  one row with swapped columns fixed (`頂く`), and duplicates kept at the easiest level.
- **Attribution text:**
  > JLPT vocabulary from open-anki-jlpt-decks by Jamie Sinclair (MIT), based on
  > Jonathan Waller's JLPT Resources (tanos.co.uk/jlpt), licensed CC BY.

## `jlpt` kanji

- **Source:** [Bluskyo/JLPT_Vocabulary](https://github.com/Bluskyo/JLPT_Vocabulary),
  files `data/kanji/parsedData/n5_kanji.csv` … `n1_kanji.csv`,
  commit `4358f932937ad0232194a36e9f4f875094910c6b` (2026-07-15).
- **License:** MIT for the repository. Its README states: "Data from:
  https://www.tanos.co.uk/jlpt/ are licenced under Creative Commons "BY" by Jonathan Waller".
- **Upstream data:** Jonathan Waller's N5–N1 kanji lists, the same source as the vocabulary.
- **Fetched:** 2026-10-26.
- **Counts:** N5 79, N4 166, N3 367, N2 367, N1 1,232 (2,211 total, no kanji at two levels).
- **Changes made by `convert_lists.py`:** none beyond reformatting to `kanji,level`.
- **Attribution text:**
  > JLPT kanji levels from Jonathan Waller's JLPT Resources (tanos.co.uk/jlpt),
  > licensed CC BY, as converted by Bluskyo/JLPT_Vocabulary (MIT).

### Why this kanji source

JLPT has published no official word or kanji lists since the 2010 switch to N5–N1,
so every N-level list is a community list. Candidates considered:

- **KANJIDIC2 (EDRDG, CC BY-SA 4.0):** its `jlpt` field uses the old 4-level test,
  which doesn't map cleanly onto N5–N1. Rejected.
- **[davidluzgouveia/kanji-data](https://github.com/davidluzgouveia/kanji-data) (MIT):**
  its `jlpt_new` field is scraped from Waller's pages. It's a 5.5 MB file that also
  bundles KANJIDIC (CC BY-SA) and WaniKani data we don't need. We used it only as a
  cross-check: all 2,211 kanji and their levels match Bluskyo exactly (2026-10-26).
- **[OpenJLPT](https://pypi.org/project/openjlpt/) (CC BY-SA 4.0):** derived from
  Waller's lists as well, but newer (0.1.0, July 2026) and share-alike. Not needed.
- **Bluskyo/JLPT_Vocabulary:** small per-level files parsed straight from Waller's
  PDFs, from the same upstream as our vocabulary. **Chosen.**

### Notes on the tanos.co.uk license

tanos.co.uk was unreachable on 2026-10-26 (the domain has name servers but no
address record), so its own terms could not be read. Several independent projects
that reuse the lists describe them as Creative Commons "BY" by Jonathan Waller,
none with a version number: Bluskyo/JLPT_Vocabulary,
[oysteikt/tanos-japanese-word-books](https://git.pvv.ntnu.no/oysteikt/tanos-japanese-word-books),
[hanabira.org](https://hanabira.org/about) and
[Tanoshii Japanese](https://www.tanoshiijapanese.com/home/acknowledgements.cfm).
CC BY would allow redistribution with attribution. Until the terms can be read
first-hand, this repo doesn't commit the converted JLPT lists.

## `cefrj` vocabulary (English, for later)

- **Source:** [openlanguageprofiles/olp-en-cefrj](https://github.com/openlanguageprofiles/olp-en-cefrj),
  file `cefrj-vocabulary-profile-1.5.csv`, commit `d4e45b75b38f27b30dfc5c44d8c571aec7e7092f` (2020-03-25).
- **Terms (from its README):** "CEFR-J vocabulary and grammar profile datasets can be
  used for research and commercial purposes with no charge, provided that you cite the
  dataset properly. The copyright belongs to Tono Laboratory at TUFS (Tokyo University
  of Foreign Studies)." Redistribution isn't addressed, so it is **fetched only, never
  committed**.
- **Fetched:** 2026-10-26.
- **Changes made by `convert_lists.py`:** headword variants split (`a.m./A.M./am/AM`),
  part of speech dropped, duplicates kept at the easiest level.
- **Required citation:**
  > The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies.

## `sample`

- Hand-made for this project's tests: 50 words (N5, N4) and 43 kanji.
- Levels roughly follow the JLPT lists but are simplified, so don't use it for real content.
- **License:** MIT, same as this repo.
