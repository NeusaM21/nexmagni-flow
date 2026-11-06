import pytest

from deterministic_intent.normalize import fold, split_clauses, split_marked_clauses, tokenize


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


def test_marked_clauses_report_question_marks():
    assert split_marked_clauses("Did you cancel it? yes") == (
        (("did", "you", "cancel", "it"), True),
        (("yes",), False),
    )
    assert split_marked_clauses("cancel?! no.") == ((("cancel",), True), (("no",), False))
    assert split_marked_clauses("yes but later?") == ((("yes",), False), (("later",), True))


@pytest.mark.parametrize("text", ["No, go ahead", "yes but later", "a - b. c", "?!", ""])
def test_marked_clauses_match_plain_clauses(text):
    assert tuple(clause for clause, _ in split_marked_clauses(text)) == split_clauses(text)


def test_yesterday_is_one_token():
    assert split_clauses("yesterday") == (("yesterday",),)


@pytest.mark.parametrize("text", ["", "   ", "!!!", "\U0001F44D", "\n\t"])
def test_contentless_text_has_no_clauses(text):
    assert split_clauses(text) == ()
