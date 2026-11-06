import pytest

from guarded_llm_router import Intent, parse_label


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BOOKING", Intent.BOOKING),
        (" booking\n", Intent.BOOKING),
        ("Booking.", Intent.BOOKING),
        ("SERVICE_INFO", Intent.SERVICE_INFO),
        ("human_handoff", Intent.HUMAN_HANDOFF),
        ("Small_Talk.", Intent.SMALL_TALK),
    ],
)
def test_valid_labels(raw, expected):
    assert parse_label(raw) is expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        ".",
        "Booking..",
        "BOOKING SERVICE_INFO",
        "BOOKING, SERVICE_INFO",
        "The answer is BOOKING",
        "NOT_BOOKING",
        "BOOK",
        "BOOKINGS",
        '{"intent": "BOOKING"}',
        "`BOOKING`",
        '"BOOKING"',
        "BOOK​ING",
        "BOOKING\u0000",
        "CANCEL_EVERYTHING",
        "B" * 10_000,
        "BOOKING" + " " * 40,
    ],
)
def test_invalid_labels_are_rejected(raw):
    assert parse_label(raw) is None


@pytest.mark.parametrize("raw", [None, 42, b"BOOKING", ["BOOKING"], Intent.BOOKING])
def test_non_string_output_is_rejected(raw):
    assert parse_label(raw) is None
