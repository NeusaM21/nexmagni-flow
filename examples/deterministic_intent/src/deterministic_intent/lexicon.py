"""Cue phrases, kept as plain data so the rules stay reviewable.

Phrases are written in their normalized form: lowercase, no accents, and
contractions already expanded ("can't" is listed as "can not"). Matching is
done on whole tokens with longest-match-first, so "not now" is read as one
refusal rather than as "not" + "now", and "yesterday" never matches "yes".
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping


class Cue(Enum):
    # Action cues: they carry meaning on their own.
    AFFIRM = "affirm"
    DENY = "deny"
    CANCEL = "cancel"
    KEEP = "keep"
    ATTEND = "attend"
    CANNOT_ATTEND = "cannot_attend"
    RESCHEDULE = "reschedule"
    # Modifier cues: they change how later action cues in the clause are read.
    NEGATOR = "negator"
    HYPOTHETICAL = "hypothetical"
    POLICY = "policy"
    QUESTION = "question"
    # Message-level cues: "later" makes any non-refusal answer doubtful.
    DEFERRAL = "deferral"
    # Neutral filler: consumes idioms such as "no problem" so that their "no"
    # is not read as a refusal. Carries no meaning of its own.
    NEUTRAL = "neutral"


ACTION_CUES: frozenset[Cue] = frozenset(
    {Cue.AFFIRM, Cue.DENY, Cue.CANCEL, Cue.KEEP, Cue.ATTEND, Cue.CANNOT_ATTEND, Cue.RESCHEDULE}
)

_PHRASES: dict[Cue, tuple[str, ...]] = {
    Cue.AFFIRM: (
        "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay", "alright", "all right",
        "sounds good", "go ahead", "please do", "do it", "book it", "yes please",
        "confirm", "confirmed", "i confirm", "that works", "works for me",
        "absolutely", "of course", "correct", "perfect", "great", "deal",
        "i do not mind", "do not mind",
    ),
    Cue.DENY: (
        "no", "n", "nope", "nah", "not now", "not today", "never mind", "nevermind",
        "no thanks", "no thank you", "rather not", "not interested", "forget it",
        "skip it", "decline", "no way", "not at all", "absolutely not",
        "of course not", "definitely not", "certainly not",
    ),
    Cue.CANCEL: (
        "cancel", "cancelled", "canceled", "cancelling", "canceling", "cancellation",
        "call it off", "call off",
    ),
    Cue.KEEP: (
        "keep", "keep it", "leave it", "leave it as is",
    ),
    Cue.ATTEND: (
        "i will be there", "will be there", "see you", "see you then", "see you there",
        "i am coming", "i will come", "count me in", "will make it", "can make it",
        "on my way", "i will attend", "see you later",
    ),
    Cue.CANNOT_ATTEND: (
        "can not make it", "will not make it", "not going to make it",
        "not be able to make it", "not be able to come", "can not come",
        "can not attend", "unable to attend", "unable to make it", "unable to come",
        "will not be there", "can not be there", "something came up",
        "not coming", "will not come", "not able to come", "not able to make it",
    ),
    Cue.RESCHEDULE: (
        "reschedule", "rebook", "postpone", "move it", "move my appointment",
        "move the appointment", "push it back", "another time", "another day",
        "different time", "different day", "change the time", "change the date",
        "new time", "later date",
    ),
    Cue.NEGATOR: (
        "not", "never", "no need to",
    ),
    Cue.HYPOTHETICAL: (
        "if", "in case", "what if", "suppose", "supposing", "should i", "should we",
        "in the event", "whether",
    ),
    Cue.POLICY: (
        "policy", "fee", "fees", "charge", "charged", "penalty", "deadline", "rule",
        "rules", "refund", "how far in advance", "how late", "free",
    ),
    Cue.QUESTION: (
        "did you", "did it", "did i", "have you", "has it", "has my", "was it", "was my",
        "is it", "is my", "is the", "has the",
    ),
    Cue.DEFERRAL: (
        "later", "not yet", "wait", "hold on", "in a bit",
    ),
    Cue.NEUTRAL: (
        "no problem", "no worries", "not a problem", "no prob",
    ),
}


def _build_index() -> Mapping[str, tuple[tuple[tuple[str, ...], Cue], ...]]:
    """Index phrases by first token, longest phrase first."""
    index: dict[str, list[tuple[tuple[str, ...], Cue]]] = {}
    seen: dict[tuple[str, ...], Cue] = {}
    for cue, phrases in _PHRASES.items():
        for phrase in phrases:
            tokens = tuple(phrase.split())
            if tokens in seen:
                raise ValueError(f"phrase {phrase!r} assigned to {seen[tokens]} and {cue}")
            seen[tokens] = cue
            index.setdefault(tokens[0], []).append((tokens, cue))
    return MappingProxyType(
        {
            first: tuple(sorted(entries, key=lambda entry: len(entry[0]), reverse=True))
            for first, entries in index.items()
        }
    )


PHRASE_INDEX = _build_index()
