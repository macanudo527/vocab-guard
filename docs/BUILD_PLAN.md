# vocab-guard — Build Plan

Hand this file to Claude Code. Work through it one phase at a time and stop at every **Checkpoint** for approval before moving on.

## What we're building

An automation that writes articles which stay inside a required word list, and proves it.

1. An LLM writes a draft at a target level, for example JLPT N4.
2. A checker service splits the text into words with a real morphological analyzer and compares every word, and every kanji, against the level's lists.
3. Only the failing sentences go back to the LLM with the exact words to replace. This repeats up to 5 times.
4. The result lands as a **WordPress draft** (never auto-published), with a report: pass rate, what was caught, repair rounds, cost.

The approach follows SRS-Stories (EMNLP 2025 industry track, arXiv 2512.18362): a non-LLM verifier plus a rewrite loop. That paper covered English, Chinese and Polish, not Japanese. This project is **Japanese-first**, adds a **kanji-level check**, and ships as a reusable **checker API + n8n template**.

Audience: people who make materials (teachers, schools, publishers, site owners), not learners. This is also a portfolio piece, so README quality and real results matter as much as the code.

## Ground rules for Claude Code

- Stop at each Checkpoint, summarize what changed and what you verified, and wait for approval.
- Commit at the end of each phase with a clear message, then push.
- Never commit secrets. Keys go in `.env` (gitignored); `.env.example` lists the variable names only.
- Never commit word-list data unless `lists/SOURCES.md` records a license that allows redistribution. Otherwise download it with `scripts/fetch_lists.sh`.
- Don't change scope. If something in this plan turns out to be wrong (a library version, a node name), stop and explain instead of working around it silently.
- Pin dependency versions. Use the latest stable release at build time unless this plan pins one.

## Prerequisites (check before Phase 0)

- `gh auth status` shows a logged-in GitHub account.
- Docker and Docker Compose work (`docker compose version`).
- `uv` is installed (install it if missing).
- An OpenAI API key is available for Phase 4. It goes into the n8n credential, not into the repo.

---

## Phase 0 — Create the repo

1. Confirm with the user: repo name (default `vocab-guard`), GitHub account, and visibility (default **public**). Check the name is free: `gh repo view <account>/<name>` should fail, and the name should be unused on PyPI.
2. `gh repo create <name> --public --license mit --gitignore Python --clone`
3. Add this plan as `docs/BUILD_PLAN.md`.
4. Create the skeleton:

```
vocab-guard/
  checker/
    app/__init__.py
    app/main.py          # FastAPI app
    app/ja.py            # Japanese analysis
    app/lists.py         # list loading
    app/models.py        # request/response models
    tests/
    Dockerfile
    pyproject.toml
  lists/
    README.md            # file format
    SOURCES.md           # where each list comes from + license
    sample/              # tiny hand-made lists for tests (ours, MIT)
  scripts/
    fetch_lists.sh
    benchmark.py         # Phase 5
  n8n/
    workflow.json        # Phase 4
    README.md
  examples/              # real run outputs (Phase 5)
  docs/
    BUILD_PLAN.md
    RESULTS.md           # Phase 5
  docker-compose.yml
  .env.example
  .github/workflows/ci.yml
  README.md
```

5. `.gitignore` must also cover `.env`, `lists/data/`, `snapshots/`, and Python caches.

**Checkpoint 0:** repo exists on GitHub with the skeleton pushed.

---

## Phase 1 — Word lists

### File format (`lists/README.md`)

- Vocabulary: CSV with header `word,reading,level`. `word` is the dictionary form as usually written (kanji or kana), `reading` in hiragana, `level` such as `N5`.
- Kanji: CSV with header `kanji,level`.
- Lists live in `lists/data/<name>/` (gitignored if fetched) or `lists/sample/` (committed).
- Levels are **cumulative**: `jlpt-n4` allows N5 plus N4.

### Sources (record each in `lists/SOURCES.md` with URL, license, attribution text, date fetched)

- **JLPT vocabulary:** `jamsinclair/open-anki-jlpt-decks` (MIT; built from tanos.co.uk data). Check tanos.co.uk's own terms too. If redistribution is clear, a converted CSV may be committed; if not, fetch it.
- **JLPT kanji by level:** find a source with clear licensing and record it. Candidates to evaluate: community N-level kanji lists, and KANJIDIC2 (EDRDG; its JLPT field uses the old 4-level system, so it doesn't map cleanly to N5–N1). Explain the choice at the checkpoint.
- **English (CEFR-J), for later:** `openlanguageprofiles/olp-en-cefrj`. Free for commercial use with citation ("The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies"). Redistribution isn't addressed, so **fetch only, never commit**.

### Tasks

1. `scripts/fetch_lists.sh` downloads and converts sources into the CSV format under `lists/data/`.
2. `lists/sample/` gets a tiny hand-made N5/N4 vocab and kanji list (about 50 words, 40 kanji) used by the tests, so tests never depend on downloads.

**Checkpoint 1:** fetch script works; `SOURCES.md` lists every source with its license; explain the kanji-list choice.

---

## Phase 2 — Japanese checker service

Stack: Python 3.12, uv, FastAPI, uvicorn, **SudachiPy 0.6.x** with `sudachidict_core`, ruff, pytest. Do **not** use SudachiPy 0.7.x: it's marked unstable and its dictionary format doesn't match the packaged dictionaries yet.

### API

`GET /health` → `{"ok": true}`

`GET /lists` → available list names and levels.

`POST /check`

```json
{
  "text": "…",
  "lang": "ja",
  "list": "jlpt-n4",
  "allow": ["東京", "田中"],
  "options": { "allow_proper_nouns": true, "allow_katakana": false }
}
```

Response:

```json
{
  "pass": false,
  "pass_rate": 0.94,
  "content_tokens": 118,
  "sentences": [
    { "index": 0, "text": "…", "ok": true, "violations": [] },
    { "index": 3, "text": "…", "ok": false, "violations": [
      { "surface": "把握", "lemma": "把握", "reading": "はあく", "reason": "not_in_list" },
      { "surface": "勉強", "lemma": "勉強", "reading": "べんきょう", "reason": "kanji_above_level",
        "kanji": ["強"], "suggestion": "write in kana: べんきょう" }
    ]}
  ]
}
```

Limit request size (for example 20,000 characters) and reject unknown `list` names with a clear error.

### Japanese analysis rules (`app/ja.py`)

1. **Sentences:** split on 。！？!? and line breaks; keep closing quotes 」』 with their sentence.
2. **Tokens:** Sudachi split mode **C**.
3. **Skip:** particles (助詞), auxiliary verbs (助動詞), punctuation and symbols (補助記号, 記号), whitespace, numbers (数詞). Skip proper nouns (固有名詞) when `allow_proper_nouns` is true. Skip anything in `allow`.
4. **Match a token** if any of these is in the cumulative vocab list: `dictionary_form()`, `normalized_form()`, or the hiragana reading (convert `reading_form()` from katakana).
5. **Compound fallback:** if a mode-C token doesn't match, re-split it in mode **A**. If every part matches, it passes.
6. **Kanji check:** every kanji character in the token's surface must be in the cumulative kanji list. A word that's in the vocab list but uses a kanji above the level gets `kanji_above_level`, the offending kanji, and a kana suggestion.
7. **Katakana-only words** not in the list: violation unless `allow_katakana` is true.
8. `pass_rate` = matched content tokens ÷ content tokens (skipped tokens excluded). `pass` = no violations.

### Tests (`checker/tests/golden.yaml` + pytest)

At least 15 cases using `lists/sample/`, each with text, list, and expected violations:

- Conjugations match their dictionary form (食べました → 食べる; 行かなかった → 行く).
- An in-list word written with an above-level kanji → `kanji_above_level`.
- The same word written in kana → passes.
- A compound that's only valid through the mode-A fallback.
- An out-of-list word → `not_in_list`.
- Particles, punctuation and numbers are ignored.
- Allowlisted names pass; proper-noun option on and off.
- Katakana option on and off.
- Multi-sentence text returns correct sentence indexes.
- Empty text and oversized text return clean errors.

Also unit tests for sentence splitting and cumulative level loading.

**Checkpoint 2:** `uv run pytest` passes; show 3 example `/check` responses from real-looking N4 text.

---

## Phase 3 — Docker, Compose, CI

1. `checker/Dockerfile`: slim Python image, non-root user, dictionary installed at build time, healthcheck on `/health`.
2. `docker-compose.yml`:
   - `checker` on port 8000.
   - `n8n` (official `n8nio/n8n` image, pinned tag), with a volume for its data, able to reach `http://checker:8000`.
   - Profile `demo`: `wordpress` + `mariadb`, so the whole demo runs locally with no live site. WordPress on `localhost:8080`.
3. `.env.example`: `CHECKER_API_KEY` (optional), `N8N_ENCRYPTION_KEY`, WordPress DB variables. If `CHECKER_API_KEY` is set, `/check` requires an `X-API-Key` header.
4. `.github/workflows/ci.yml`: on push and PR run `ruff check` and `pytest`; on tags `v*`, build the checker image and push it to GHCR (`ghcr.io/<account>/vocab-guard-checker`).
5. CI also fails if `n8n/workflow.json` contains anything that looks like a secret (API keys, tokens).

**Checkpoint 3:** `docker compose up` brings up checker and n8n; `docker compose --profile demo up` adds WordPress; CI is green on GitHub.

---

## Phase 4 — n8n workflow (the template)

Build in the local n8n, then export to `n8n/workflow.json`. Stick to built-in nodes so it also works on n8n Cloud when the checker is hosted publicly: **no external npm modules**. Code nodes may only use plain JavaScript.

### Flow

1. **Trigger:** n8n Form Trigger (topic, level, target length, article type), plus a Webhook trigger with the same fields for batch runs.
2. **Draft:** LLM via n8n's OpenAI Chat Model node for testing, with the model name set in one place so a cheaper model can be used for repairs. Keep the LLM steps provider-neutral: plain prompts and JSON output only, no OpenAI-only features, so Anthropic or Gemini nodes can be swapped in. The prompt states the JLPT level, asks for short sentences, plain grammar for the level, and returns JSON `{ "title": "...", "body": "..." }`.
3. **Check:** HTTP Request → `POST /check`.
4. **Pass?** IF `pass` is true, or round count reached 5 → go to Output.
5. **Repair:** send only the failing sentences, each with its violations and the sentences before and after it for context. The prompt: keep the meaning, keep one sentence per input sentence, use simpler words, write above-level kanji in kana, no new names; return JSON `{ "<index>": "<new sentence>" }`.
6. **Merge:** Code node replaces those sentences by index, increments the round counter, loops back to Check.
7. **Output:**
   - WordPress node: create post with **status draft** (never publish), title and body as HTML.
   - Report object: final pass rate, violations left, rounds used, first-draft pass rate, unique words caught, token usage and estimated cost.
   - Webhook trigger responds with the report JSON.
8. **Sticky notes** in the workflow explaining setup: credentials to create (OpenAI or another LLM provider, WordPress application password), checker URL, how to change level or list.

### `n8n/README.md`

What it does, setup in 5 steps, the credentials needed, how to run the checker (`docker run ghcr.io/...`), how to swap word lists, how to swap the LLM provider, limits.

**Checkpoint 4:** a form submission produces a WordPress draft in the demo WordPress plus a report; `workflow.json` imports cleanly into a fresh n8n; no secrets in the export.

---

## Phase 4.5 — Article package and live-site drafts

The articles also serve as reading practice on jlptbootcamp, to bring in search traffic. Each post becomes a full study page, and drafts can go to the live site over the WordPress REST API. Posts are still **always drafts**: a human reviews and publishes each one.

### Rule: extras never change the article

Everything below is made from the article **after** it passes, so the checker's guarantee for the article is unaffected.

### Checker

1. `/check` also returns the words that passed (surface, lemma, reading, level) for each sentence. This is additive and backward compatible; the existing golden tests still pass, and new tests cover the new field.

### Article page sections

| Section | How it's made |
| --- | --- |
| Article (Japanese) | Existing draft → check → repair loop |
| Furigana | `<ruby>` markup from the checker's readings, with a show/hide toggle |
| Vocabulary list | From the checker's matched words: word, reading, level, plus a short English gloss from the LLM |
| Comprehension questions | 3–5 questions in Japanese with answers, made from the final article, then run through the **same check → repair loop** so they stay at level |
| Vocab exercises | Fill-in-the-blank built from the article's own words with plain code, no LLM; the answer key is the original text |
| English translation | Made last, from the final text; hidden behind a `<details>` toggle so readers try the Japanese first |

The HTML must survive WordPress's content filtering for a user **without** `unfiltered_html` (no `<script>`). Toggles use `<details>`/`<summary>` or CSS. Verify this in the demo WordPress with a user of the same role the live site will use.

### WordPress

1. Each draft gets a level category (N5, N4, …), topic tags, an SEO title such as "JLPT N4 Reading Practice: Going to the Supermarket", and an excerpt.
2. **Target site:** the WordPress credential decides where drafts go. The demo WordPress is used for development; the live site uses a second n8n WordPress credential. Nothing site-specific goes in `workflow.json`.
3. **Live-site credential:** a dedicated WordPress user with the lowest role that can create drafts with categories and tags (expected: Author; confirm on the site), plus an **application password** that can be revoked on its own. The site must serve HTTPS, and the REST API must not be blocked by a security plugin. Stored only in n8n.
4. Categories are created on the site beforehand and mapped by ID in Config, so the API user doesn't need permission to create categories.

### Traffic note

Google penalizes scaled, low-value AI content. Review and edit each draft before publishing, and publish gradually rather than in bulk.

**Checkpoint 4.5:** a form submission produces a full article page as a draft in the demo WordPress, with every section rendering correctly for the restricted role, and the questions passing the checker; then one test draft created on the live site via the API and deleted after review.

---

## Phase 5 — Benchmark and results (the portfolio evidence)

1. `scripts/benchmark.py`: reads `scripts/topics.yaml` (20 everyday topics), calls the n8n webhook for each topic at N5, N4 and N3, and saves each report to `examples/<level>/<slug>.json` plus the final article as `.md`. The workflow runs with the **live-site** WordPress credential, so all 60 articles land on jlptbootcamp as drafts for review (never published by the script). Before the full run, do one N4 article end to end and wait for the user's approval.
2. Aggregate into `docs/RESULTS.md`:

| Level | Articles | First-draft pass rate | Final pass rate | Avg repair rounds | Kanji caught above level | Avg cost per article |
| --- | --- | --- | --- | --- | --- | --- |

3. Pick 3 before-and-after sentence examples (original, violation, repaired) for the README.
4. Report out-of-vocabulary rate the same way SRS-Stories does, so results are comparable, and cite the paper.

**Checkpoint 5:** results table filled with real numbers; any surprising failures explained.

---

## Phase 6 — README and release

README sections, in order:

1. One-line pitch: AI-written content that provably stays inside a required word list.
2. Demo GIF or video (the user records this; leave a placeholder).
3. The problem: LLMs drift above level, and prompting alone doesn't fix it.
4. How it works: diagram of draft → check → repair → draft post.
5. Results: the table from `docs/RESULTS.md` and the before-and-after examples.
6. Quick start: `docker compose --profile demo up`, import the workflow, add credentials.
7. Checker API reference.
8. Word lists: format, sources, licenses, bring your own.
9. Credits: SRS-Stories, SudachiPy, list sources.
10. Roadmap.

Then tag `v0.1.0`, confirm the GHCR image is published, and draft a GitHub release.

**Checkpoint 6:** README reviewed by the user; `v0.1.0` released.

---

## Later (not in v0.1)

- **English:** spaCy lemmatizer + CEFR-J lists (fetched, never committed); tests for irregular forms (went → go).
- **Provider comparison:** rerun the benchmark with Anthropic and Gemini nodes and add the numbers to `docs/RESULTS.md`.
- **Custom glossaries:** "approved terms only" mode for company style guides, same API.
- **Exercises:** generate cloze questions with answer keys from the final article.
- **Hosted checker:** deploy with API keys so n8n Cloud users don't need Docker; possible paid tier.
- **Template listing:** submit to the n8n template library via the Creator hub.

## Definition of done for v0.1

- Checker passes all golden tests in CI and ships as a public GHCR image.
- `docker compose --profile demo up` plus importing the workflow produces a WordPress draft and a report with no other setup beyond credentials.
- `docs/RESULTS.md` has real numbers from 60 generated articles.
- No secrets and no unlicensed list data in the repo.
