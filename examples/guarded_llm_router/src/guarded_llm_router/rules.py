"""Deterministic pre-routing. Runs before any model call.

Rules are checked in a fixed order and match whole tokens only. A request
for a human always wins, even in the middle of a booking flow.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import Intent

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> tuple[str, ...]:
    decomposed = unicodedata.normalize("NFKD", text.replace("’", "'"))
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()
    return tuple(_TOKEN.findall(plain.replace("'", "")))


def _phrases(*items: str) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(item.split()) for item in items)


HUMAN_PHRASES = _phrases(
    "human", "a person", "real person", "talk to someone", "speak to someone",
    "speak with someone", "talk with someone", "representative", "operator",
    "staff member", "the owner", "manager", "supervisor", "someone in charge",
    "person in charge", "staff", "receptionist", "live agent", "real agent",
)
GREETINGS = frozenset(
    _phrases(
        "hi", "hello", "hey", "hi there", "hello there", "good morning",
        "good afternoon", "good evening", "thanks", "thank you", "thank you so much",
    )
)
SERVICE_PHRASES = _phrases(
    "price", "prices", "pricing", "cost", "costs", "how much", "services",
    "opening hours", "open on", "address", "location", "where are you", "how long",
)
BOOKING_PHRASES = _phrases(
    "book", "book an appointment", "make an appointment", "schedule an appointment",
    "reserve", "reservation",
)


@dataclass(frozen=True, slots=True)
class RuleMatch:
    name: str
    intent: Intent


def _contains(tokens: tuple[str, ...], phrases: tuple[tuple[str, ...], ...]) -> bool:
    for phrase in phrases:
        size = len(phrase)
        if any(tokens[i : i + size] == phrase for i in range(len(tokens) - size + 1)):
            return True
    return False


def match_rule(message: str, in_booking_flow: bool = False) -> RuleMatch | None:
    """Return the first matching rule, or None if the model should decide."""
    tokens = tokenize(message)
    if _contains(tokens, HUMAN_PHRASES):
        return RuleMatch("human_request", Intent.HUMAN_HANDOFF)
    if in_booking_flow:
        return RuleMatch("active_booking_flow", Intent.BOOKING)
    if tokens in GREETINGS:
        return RuleMatch("greeting_only", Intent.SMALL_TALK)
    if _contains(tokens, SERVICE_PHRASES):
        return RuleMatch("service_question", Intent.SERVICE_INFO)
    if _contains(tokens, BOOKING_PHRASES):
        return RuleMatch("explicit_booking", Intent.BOOKING)
    return None
