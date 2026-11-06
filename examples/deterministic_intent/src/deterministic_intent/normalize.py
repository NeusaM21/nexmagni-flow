"""Text normalization: accents, apostrophes, contractions, and clause splitting.

A clause is the unit in which negation and hypothetical markers apply.
"no, go ahead" therefore contains two clauses, and the "no" cannot negate
"go ahead".
"""

from __future__ import annotations

import re
import unicodedata

Clause = tuple[str, ...]

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})

# Punctuation, dashes, and contrastive conjunctions start a new clause.
_CLAUSE_BREAK = re.compile(
    r"[.,;:!?()\[\]\"\n\r\t–—]+|\s-\s|\b(?:but|however|though|although)\b"
)
_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)*")

# Contractions commonly typed without an apostrophe.
_BARE_CONTRACTIONS: dict[str, Clause] = {
    "cant": ("can", "not"),
    "cannot": ("can", "not"),
    "wont": ("will", "not"),
    "dont": ("do", "not"),
    "doesnt": ("does", "not"),
    "didnt": ("did", "not"),
    "isnt": ("is", "not"),
    "arent": ("are", "not"),
    "wasnt": ("was", "not"),
    "couldnt": ("could", "not"),
    "wouldnt": ("would", "not"),
    "shouldnt": ("should", "not"),
    "havent": ("have", "not"),
    "hasnt": ("has", "not"),
    "im": ("i", "am"),
    "ive": ("i", "have"),
}

_IRREGULAR_NOT_STEMS = {"ca": "can", "wo": "will", "sha": "shall"}

_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("'ll", "will"),
    ("'re", "are"),
    ("'ve", "have"),
    ("'d", "would"),
    ("'m", "am"),
    ("'s", "is"),
)


def _expand(token: str) -> Clause:
    if token in _BARE_CONTRACTIONS:
        return _BARE_CONTRACTIONS[token]
    if token.endswith("n't"):
        stem = token[:-3]
        return (_IRREGULAR_NOT_STEMS.get(stem, stem), "not")
    for suffix, word in _SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix):
            return (token[: -len(suffix)], word)
    return (token.replace("'", ""),)


def fold(text: str) -> str:
    """Lowercase, unify apostrophes, and strip accents ("Sí" -> "si")."""
    text = text.translate(_APOSTROPHES)
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def tokenize(text: str) -> Clause:
    """Split already-folded text into expanded word tokens."""
    tokens: list[str] = []
    for raw in _TOKEN.findall(text):
        tokens.extend(part for part in _expand(raw) if part)
    return tuple(tokens)


def split_marked_clauses(text: str) -> tuple[tuple[Clause, bool], ...]:
    """Like `split_clauses`, also reporting whether each clause ends with "?"."""
    folded = fold(text)
    marked: list[tuple[Clause, bool]] = []
    start = 0
    for match in _CLAUSE_BREAK.finditer(folded):
        clause = tokenize(folded[start : match.start()])
        if clause:
            marked.append((clause, "?" in match.group()))
        start = match.end()
    clause = tokenize(folded[start:])
    if clause:
        marked.append((clause, False))
    return tuple(marked)


def split_clauses(text: str) -> tuple[Clause, ...]:
    """Fold, split into clauses, and tokenize. Empty clauses are dropped."""
    return tuple(clause for clause, _ in split_marked_clauses(text))
