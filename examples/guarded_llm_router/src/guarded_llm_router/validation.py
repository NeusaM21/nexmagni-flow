"""Strict validation of model output.

Accepted: exactly one label, any letter case, optional surrounding
whitespace, and at most one trailing period ("Booking."). Everything else
is rejected; there is no substring search, so "NOT_BOOKING" or
"The answer is BOOKING" never count as BOOKING.
"""

from __future__ import annotations

import re

from .models import Intent

MAX_RAW_LENGTH = 32
_LABEL = re.compile(r"[A-Za-z_]+")


def parse_label(raw: object) -> Intent | None:
    if not isinstance(raw, str) or len(raw) > MAX_RAW_LENGTH:
        return None
    text = raw.strip()
    if text.endswith("."):
        text = text[:-1]
    if not _LABEL.fullmatch(text):
        return None
    try:
        return Intent[text.upper()]
    except KeyError:
        return None
