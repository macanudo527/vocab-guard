"""Request/response models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckOptions(BaseModel):
    allow_proper_nouns: bool = True
    allow_katakana: bool = False
    include_words: bool = False  # also return the words that passed, per sentence


class CheckRequest(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    text: str
    lang: str = "ja"
    list_name: str = Field(alias="list")
    allow: list[str] = Field(default_factory=list, max_length=1000)
    options: CheckOptions = Field(default_factory=CheckOptions)


class Violation(BaseModel):
    surface: str
    lemma: str
    reading: str
    reason: Literal["not_in_list", "kanji_above_level"]
    kanji: list[str] | None = None
    suggestion: str | None = None


class Word(BaseModel):
    """A content word that passed. Offsets are in the request text."""

    surface: str
    lemma: str
    reading: str  # reading of the surface, for furigana
    lemma_reading: str | None = None  # reading of the dictionary form, when known
    level: str | None = None  # None for words allowed outside the list
    start: int
    end: int


class SentenceResult(BaseModel):
    index: int
    text: str
    start: int  # character offsets of the sentence in the request text
    end: int
    ok: bool
    violations: list[Violation]
    words: list[Word] | None = None  # only with options.include_words


class CheckResponse(BaseModel):
    passed: bool = Field(serialization_alias="pass")
    pass_rate: float
    content_tokens: int
    sentences: list[SentenceResult]


class ListInfo(BaseModel):
    name: str
    lang: str
    level: str
    levels: list[str]
    words: int
    kanji: int | None


class ListsResponse(BaseModel):
    lists: list[ListInfo]


class ErrorResponse(BaseModel):
    error: str
    message: str
