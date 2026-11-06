import pytest

from deterministic_intent.normalize import fold, split_clauses, tokenize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("YES", "yes"),
        ("Café", "cafe"),
        ("I’ll", "i'll"),
        ("Don´t", "don't"),
    ],
)
def test_fold(raw, expected):
    assert fold(raw) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("can't", ("can", "not")),
        ("cant", ("can", "not")),
        ("cannot", ("can", "not")),
        ("won't", ("will", "not")),
        ("don't", ("do", "not")),
        ("i'll", ("i", "will")),
        ("i'm", ("i", "am")),
        ("i'd", ("i", "would")),
    ],
)
def test_contractions_are_expanded(text, expected):
    assert tokenize(text) == expected


def test_clauses_split_on_punctuation_and_but():
    assert split_clauses("No, go ahead") == (("no",), ("go", "ahead"))
    assert split_clauses("yes but later") == (("yes",), ("later",))


def test_yesterday_is_one_token():
    assert split_clauses("yesterday") == (("yesterday",),)


@pytest.mark.parametrize("text", ["", "   ", "!!!", "\U0001F44D", "\n\t"])
def test_contentless_text_has_no_clauses(text):
    assert split_clauses(text) == ()
