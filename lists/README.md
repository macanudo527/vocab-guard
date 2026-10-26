# Word lists

Each list is a directory with up to three files:

```
lists/data/jlpt/        # fetched by scripts/fetch_lists.sh (gitignored)
  meta.json
  vocab.csv
  kanji.csv             # Japanese lists only
lists/sample/           # tiny hand-made list used by the tests (committed, MIT)
```

## `meta.json`

```json
{ "name": "jlpt", "lang": "ja", "levels": ["N5", "N4", "N3", "N2", "N1"] }
```

`levels` runs from easiest to hardest. Levels are **cumulative**: the checker
exposes one list name per level, `<name>-<level>` in lowercase, and each one
allows that level plus every easier one. `jlpt-n4` allows N5 and N4;
`sample-n5` allows only the N5 rows of the sample list.

## `vocab.csv`

```csv
word,reading,level
食べる,たべる,N5
コンピューター,こんぴゅーたー,N4
```

- `word`: the dictionary form as usually written, in kanji or kana.
- `reading`: the reading in hiragana (katakana loanwords are converted, `ー` stays).
  Leave it empty for languages without readings.
- `level`: one of the levels in `meta.json`.

A word may appear on several rows when it has more than one reading or spelling
(`毎年,まいねん` and `毎年,まいとし`). If the same word and reading appear at two
levels, the easier level wins.

## `kanji.csv`

```csv
kanji,level
日,N5
```

One kanji per row. The checker flags any kanji in a word that isn't allowed at
the requested level, even when the word itself is in `vocab.csv`.

## Getting the lists

```sh
scripts/fetch_lists.sh          # jlpt and cefrj
scripts/fetch_lists.sh jlpt     # just one
```

The script downloads each source at a pinned commit, checks its SHA-256, and
converts it with `scripts/convert_lists.py`. Raw downloads are kept in
`lists/data/.raw/`. Sources and licenses are in [SOURCES.md](SOURCES.md).

## Bring your own list

Create `lists/data/<name>/` with the three files above. Any list that follows
the format works, such as a textbook's glossary or a company's approved terms.
