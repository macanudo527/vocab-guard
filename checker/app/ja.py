"""Japanese analysis: sentence splitting, Sudachi tokenization, list matching.

Rules are listed in docs/BUILD_PLAN.md (Phase 2, "Japanese analysis rules").
Two additions:
- Neighbour join: a token that fails on its own passes together with up to
  three neighbouring tokens when they form a list word, since Sudachi splits
  some list entries (お + 茶 -> お茶, すぐ + に -> すぐに, 二 + つ -> 二つ) and
  kana compounds (にち + ようび -> にちようび).
- Kana suggestions use the list's readings when the word is in dictionary form
  (明日 -> あした rather than Sudachi's あす), and name every reading the list
  allows when there is more than one (私 -> わたくし or わたし).
"""

import re
import threading
from dataclasses import dataclass

from sudachipy import Dictionary, Morpheme, SplitMode

from .lists import LevelList
from .models import CheckOptions, SentenceResult, Violation, Word

TERMINATORS = "。！？!?"
CLOSING_QUOTES = "」』"
SKIP_POS = {"助詞", "助動詞", "補助記号", "記号", "空白"}
KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
KATAKANA_ONLY = re.compile(r"[ァ-ヺー・]+")
# Sudachi rejects input over 49,149 bytes; 12,000 characters stays under that
# even if every character takes 4 bytes in UTF-8.
MAX_CHUNK_CHARS = 12_000
CHUNK_BREAKS = "、，, 　\t"
MAX_JOIN = 4


def to_hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Split on 。！？!? and line breaks, keeping closing 」』 with their sentence.

    Returns (start, end) offsets with surrounding whitespace trimmed; empty
    sentences are dropped.
    """
    spans: list[tuple[int, int]] = []

    def add(start: int, end: int) -> None:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))

    start = i = 0
    while i < len(text):
        if text[i] in "\r\n":
            add(start, i)
            start = i = i + 1
        elif text[i] in TERMINATORS:
            i += 1
            while i < len(text) and text[i] in TERMINATORS + CLOSING_QUOTES:
                i += 1
            add(start, i)
            start = i
        else:
            i += 1
    add(start, len(text))
    return spans


@dataclass
class CheckResult:
    sentences: list[SentenceResult]
    content_tokens: int
    matched_tokens: int


def _skippable(m: Morpheme) -> bool:
    pos = m.part_of_speech()
    return pos[0] in SKIP_POS or pos[1] == "数詞" or not m.surface().strip()


def _matches(m: Morpheme, lst: LevelList) -> bool:
    return (
        m.dictionary_form() in lst.words
        or m.normalized_form() in lst.words
        or to_hiragana(m.reading_form()) in lst.readings
        or to_hiragana(m.dictionary_form()) in lst.readings
    )


def _compound_matches(m: Morpheme, lst: LevelList) -> bool:
    parts = m.split(SplitMode.A)
    return len(parts) > 1 and all(_skippable(p) or _matches(p, lst) for p in parts)


def _span_match(parts: list[Morpheme], lst: LevelList) -> str | None:
    """The list word (or reading) a run of tokens forms, if any."""
    surface = "".join(m.surface() for m in parts)
    forms = [
        surface,
        "".join(m.surface() for m in parts[:-1]) + parts[-1].dictionary_form(),
        "".join(m.normalized_form() for m in parts),
    ]
    readings = [
        to_hiragana(surface),
        to_hiragana("".join(m.reading_form() for m in parts)),
    ]
    return next((f for f in forms if f in lst.words), None) or next(
        (r for r in readings if r in lst.readings), None
    )


def _joins(morphemes: list[Morpheme], lst: LevelList) -> list[range]:
    """Runs of tokens where one fails alone but they form a list word together."""
    spans: list[range] = []
    joined: set[int] = set()
    for i, m in enumerate(morphemes):
        if i in joined or _skippable(m) or _matches(m, lst) or _compound_matches(m, lst):
            continue
        # Try the longest span first.
        for size in range(min(MAX_JOIN, len(morphemes)), 1, -1):
            first = max(0, i - size + 1)
            last = min(i, len(morphemes) - size)
            span = next(
                (
                    range(a, a + size)
                    for a in range(first, last + 1)
                    if _span_match(morphemes[a : a + size], lst)
                ),
                None,
            )
            if span:
                spans.append(span)
                joined.update(span)
                break
    return spans


def _level(m: Morpheme, lst: LevelList) -> str | None:
    """The easiest level the token matches at; the hardest part's level for compounds."""
    for form in (m.dictionary_form(), m.normalized_form()):
        if form in lst.word_levels:
            return lst.word_levels[form]
    for reading in (to_hiragana(m.reading_form()), to_hiragana(m.dictionary_form())):
        if reading in lst.reading_levels:
            return lst.reading_levels[reading]
    parts = [_level(p, lst) for p in m.split(SplitMode.A) if not _skippable(p)]
    if len(parts) > 1 and all(parts):
        return max(parts, key=lst.levels.index)
    return None


def _lemma_reading(lemma: str, fallback: str | None, lst: LevelList) -> str | None:
    listed = lst.word_readings.get(lemma)
    if listed:
        return listed[0]
    if to_hiragana(lemma) in lst.reading_levels:
        return to_hiragana(lemma)
    return fallback


def _word(m: Morpheme, start: int, lst: LevelList, in_list: bool) -> Word:
    reading = _readings(m, lst)[0] if in_list else to_hiragana(m.reading_form())
    lemma = m.dictionary_form()
    same = m.surface() == lemma
    return Word(
        surface=m.surface(),
        lemma=lemma,
        reading=reading,
        lemma_reading=(
            _lemma_reading(lemma, reading if same else None, lst)
            or _lemma_reading(m.normalized_form(), None, lst)
            if in_list
            else (reading if same else None)
        ),
        level=_level(m, lst) if in_list else None,
        start=start + m.begin(),
        end=start + m.end(),
    )


def _span_word(parts: list[tuple[int, Morpheme]], start: int, lst: LevelList) -> Word:
    morphemes = [m for _, m in parts]
    match = _span_match(morphemes, lst) or ""
    reading = to_hiragana("".join(m.reading_form() for m in morphemes))
    level = lst.word_levels.get(match) or lst.reading_levels.get(match)
    return Word(
        surface="".join(m.surface() for m in morphemes),
        lemma=match,
        reading=reading,
        lemma_reading=_lemma_reading(match, reading, lst),
        level=level,
        start=start + parts[0][0] + morphemes[0].begin(),
        end=start + parts[-1][0] + morphemes[-1].end(),
    )


def _readings(m: Morpheme, lst: LevelList) -> list[str]:
    """Kana spellings for a token, Sudachi's reading first when the list allows it."""
    reading = to_hiragana(m.reading_form())
    if m.surface() == m.dictionary_form():
        for form in (m.dictionary_form(), m.normalized_form()):
            listed = lst.word_readings.get(form)
            if listed:
                if reading not in listed:
                    return list(listed)
                return [reading, *(r for r in listed if r != reading)]
    return [reading]


def _kanji_above(surface: str, lst: LevelList) -> list[str]:
    if lst.kanji is None:
        return []
    return list(dict.fromkeys(c for c in surface if KANJI.match(c) and c not in lst.kanji))


def _find_spans(text: str, terms: list[str]) -> list[tuple[int, int]]:
    spans = []
    for term in terms:
        start = text.find(term) if term else -1
        while start != -1:
            spans.append((start, start + len(term)))
            start = text.find(term, start + 1)
    return spans


class Analyzer:
    def __init__(self) -> None:
        self._dictionary = Dictionary(dict="core")
        self._local = threading.local()

    def _tokenize(self, text: str) -> list[tuple[int, Morpheme]]:
        """Tokenize in mode C, returning (offset of the morpheme's chunk, morpheme)."""
        # Sudachi tokenizers aren't thread-safe; FastAPI runs requests in a pool.
        tokenizer = getattr(self._local, "tokenizer", None)
        if tokenizer is None:
            tokenizer = self._local.tokenizer = self._dictionary.create(SplitMode.C)
        result = []
        start = 0
        while start < len(text):
            end = min(start + MAX_CHUNK_CHARS, len(text))
            if end < len(text):
                # Cut after the last comma or space in the chunk, if there is one.
                cut = max(text.rfind(c, start, end) for c in CHUNK_BREAKS)
                end = cut + 1 if cut > start else end
            result.extend((start, m) for m in tokenizer.tokenize(text[start:end]))
            start = end
        return result

    def check(
        self, text: str, lst: LevelList, allow: list[str], options: CheckOptions
    ) -> CheckResult:
        allow_set = set(allow)
        sentences = []
        content = matched = 0
        for index, (start, end) in enumerate(split_sentences(text)):
            sentence = text[start:end]
            tokens = self._tokenize(sentence)
            morphemes = [m for _, m in tokens]
            spans = _joins(morphemes, lst)
            joined = {i for span in spans for i in span}
            allow_spans = _find_spans(sentence, allow)
            violations = []
            words: list[Word] = []
            failed: set[int] = set()
            for i, (offset, m) in enumerate(tokens):
                if _skippable(m):
                    continue
                tok_begin, tok_end = offset + m.begin(), offset + m.end()
                if (
                    {m.surface(), m.dictionary_form(), m.normalized_form()} & allow_set
                    or any(s <= tok_begin and tok_end <= e for s, e in allow_spans)
                    or (options.allow_proper_nouns and m.part_of_speech()[1] == "固有名詞")
                ):
                    if i not in joined:
                        words.append(_word(m, start + offset, lst, in_list=False))
                    continue
                surface = m.surface()
                in_list = i in joined or _matches(m, lst) or _compound_matches(m, lst)
                if not in_list and options.allow_katakana and KATAKANA_ONLY.fullmatch(surface):
                    words.append(_word(m, start + offset, lst, in_list=False))
                    continue
                content += 1
                readings = _readings(m, lst)
                reading = readings[0]
                if not in_list:
                    failed.add(i)
                    violations.append(
                        Violation(
                            surface=surface,
                            lemma=m.dictionary_form(),
                            reading=reading,
                            reason="not_in_list",
                        )
                    )
                elif above := _kanji_above(surface, lst):
                    failed.add(i)
                    violations.append(
                        Violation(
                            surface=surface,
                            lemma=m.dictionary_form(),
                            reading=reading,
                            reason="kanji_above_level",
                            kanji=above,
                            suggestion=f"write in kana: {' or '.join(readings)}",
                        )
                    )
                else:
                    matched += 1
                    if i not in joined:
                        words.append(_word(m, start + offset, lst, in_list=True))
            for span in spans:
                if not failed & set(span):
                    words.append(_span_word([tokens[i] for i in span], start, lst))
            words.sort(key=lambda w: w.start)
            sentences.append(
                SentenceResult(
                    index=index,
                    text=sentence,
                    start=start,
                    end=end,
                    ok=not violations,
                    violations=violations,
                    words=words if options.include_words else None,
                )
            )
        return CheckResult(sentences=sentences, content_tokens=content, matched_tokens=matched)
