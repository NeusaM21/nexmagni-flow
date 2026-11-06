"""Deterministic message interpretation.

Pipeline: normalize -> split into clauses -> detect cues -> apply modifiers
-> map cues to intents for the current context -> resolve.

The interpreter only describes what the message most likely means. Whether
anything may happen as a result is decided separately by `policy.decide()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .lexicon import ACTION_CUES, PHRASE_INDEX, Cue
from .models import Context, Intent, Interpretation, Reason
from .normalize import Clause, fold, split_clauses

_MENU = re.compile(r"(?:option|number|#)?\s*([1-3])")
_MENU_TRAILING = re.compile(r"[\s.!)]+$")
_MENU_CHOICES = {
    "1": Intent.CONFIRM_ATTENDANCE,
    "2": Intent.REQUEST_RESCHEDULE,
    "3": Intent.REQUEST_CANCEL,
}


_REFUSAL_CUES = frozenset({Cue.DENY, Cue.CANNOT_ATTEND})


class _Mod(Enum):
    PLAIN = "plain"
    NEGATED = "negated"
    DOUBLE_NEGATED = "double_negated"
    HYPOTHETICAL = "hypothetical"
    POLICY = "policy"


@dataclass(frozen=True, slots=True)
class _Signal:
    cue: Cue
    phrase: str
    mod: _Mod


# How a plain (unmodified) action cue reads in each context. `None` = no meaning.
_CUE_MEANING: dict[Context, dict[Cue, Intent | None]] = {
    Context.BOOKING_CONFIRMATION: {
        Cue.AFFIRM: Intent.AFFIRM,
        Cue.DENY: Intent.DENY,
        Cue.CANCEL: Intent.DENY,  # "cancel" while confirming a booking means "no"
        Cue.CANNOT_ATTEND: Intent.DENY,
        Cue.KEEP: None,
        Cue.ATTEND: Intent.CONFIRM_ATTENDANCE,
        Cue.RESCHEDULE: Intent.REQUEST_RESCHEDULE,
    },
    Context.CANCELLATION_CONFIRMATION: {
        Cue.AFFIRM: Intent.AFFIRM,
        Cue.DENY: Intent.DENY,
        Cue.CANCEL: Intent.AFFIRM,  # "cancel" answers "yes" to "cancel it?"
        Cue.CANNOT_ATTEND: Intent.AFFIRM,
        Cue.KEEP: Intent.DENY,
        Cue.ATTEND: Intent.DENY,
        Cue.RESCHEDULE: Intent.REQUEST_RESCHEDULE,
    },
    Context.REMINDER_REPLY: {
        Cue.AFFIRM: Intent.AFFIRM,
        Cue.DENY: Intent.DENY,
        Cue.CANCEL: Intent.REQUEST_CANCEL,
        Cue.CANNOT_ATTEND: Intent.REQUEST_CANCEL,
        Cue.KEEP: Intent.CONFIRM_ATTENDANCE,
        Cue.ATTEND: Intent.CONFIRM_ATTENDANCE,
        Cue.RESCHEDULE: Intent.REQUEST_RESCHEDULE,
    },
    Context.OPEN_CONVERSATION: {
        Cue.AFFIRM: Intent.AFFIRM,
        Cue.DENY: Intent.DENY,
        Cue.CANCEL: Intent.REQUEST_CANCEL,
        Cue.CANNOT_ATTEND: Intent.REQUEST_CANCEL,
        Cue.KEEP: None,
        Cue.ATTEND: Intent.CONFIRM_ATTENDANCE,
        Cue.RESCHEDULE: Intent.REQUEST_RESCHEDULE,
    },
}

# When no intent survives, the strongest qualifier explains why.
_QUALIFIER_PRIORITY: tuple[tuple[_Mod, Reason], ...] = (
    (_Mod.DOUBLE_NEGATED, Reason.CONFLICTING),
    (_Mod.NEGATED, Reason.NEGATED),
    (_Mod.HYPOTHETICAL, Reason.HYPOTHETICAL),
    (_Mod.POLICY, Reason.POLICY_QUESTION),
)


def _match_at(clause: Clause, start: int) -> tuple[int, Cue] | None:
    for phrase, cue in PHRASE_INDEX.get(clause[start], ()):
        end = start + len(phrase)
        if clause[start:end] == phrase:
            return len(phrase), cue
    return None


def _scan_clause(clause: Clause) -> tuple[list[_Signal], bool]:
    """Find action cues in one clause and attach the modifiers that precede them.

    Also reports whether the clause holds a negator but no action cue
    ("sure, I guess not"), which casts doubt on the rest of the message.
    """
    found: list[tuple[Cue, str]] = []
    i = 0
    while i < len(clause):
        match = _match_at(clause, i)
        if match is None:
            i += 1
            continue
        length, cue = match
        found.append((cue, " ".join(clause[i : i + length])))
        i += length

    is_policy_clause = any(cue is Cue.POLICY for cue, _ in found)
    negators = 0
    hypothetical = False
    signals: list[_Signal] = []
    for cue, phrase in found:
        if cue is Cue.NEGATOR:
            negators += 1
        elif cue is Cue.HYPOTHETICAL:
            hypothetical = True
        elif cue in ACTION_CUES:
            if hypothetical:
                mod = _Mod.HYPOTHETICAL
            elif is_policy_clause and cue in (Cue.CANCEL, Cue.RESCHEDULE):
                mod = _Mod.POLICY
            elif negators >= 2:
                mod = _Mod.DOUBLE_NEGATED
            elif negators == 1:
                mod = _Mod.NEGATED
            else:
                mod = _Mod.PLAIN
            signals.append(_Signal(cue, phrase, mod))

    # A negator after the last action cue ("sure, I guess not") makes it doubtful,
    # unless that cue is already a refusal ("no I do not" stays a plain "no").
    last_action = max((n for n, (cue, _) in enumerate(found) if cue in ACTION_CUES), default=-1)
    if (
        last_action >= 0
        and signals[-1].cue not in _REFUSAL_CUES
        and any(cue is Cue.NEGATOR for cue, _ in found[last_action + 1 :])
    ):
        last = signals[-1]
        signals[-1] = _Signal(last.cue, last.phrase, _Mod.NEGATED)
    dangling_negation = not signals and any(cue is Cue.NEGATOR for cue, _ in found)
    return signals, dangling_negation


def _menu_choice(message: str) -> Intent | None:
    compact = _MENU_TRAILING.sub("", fold(message).strip())
    match = _MENU.fullmatch(compact)
    return _MENU_CHOICES[match.group(1)] if match else None


def _resolve(signals: list[_Signal], context: Context) -> Interpretation:
    meanings = _CUE_MEANING[context]
    intents: set[Intent] = set()
    qualifiers: set[_Mod] = set()
    evidence: list[str] = []

    for signal in signals:
        label = signal.phrase if signal.mod is _Mod.PLAIN else f"{signal.phrase} [{signal.mod.value}]"
        evidence.append(label)
        if signal.mod is _Mod.PLAIN:
            meaning = meanings[signal.cue]
            if meaning is not None:
                intents.add(meaning)
        elif (
            signal.mod is _Mod.NEGATED
            and context is Context.CANCELLATION_CONFIRMATION
            and signal.cue is Cue.CANCEL
        ):
            intents.add(Intent.DENY)  # "don't cancel" is a clear answer here
        else:
            qualifiers.add(signal.mod)

    found = tuple(evidence)
    doubtful = qualifiers - {_Mod.POLICY}

    if len(intents) == 1 and not doubtful:
        return Interpretation(intents.pop(), Reason.EXPLICIT, found)
    if intents:
        # Several intents, or a clear intent next to a negated/hypothetical cue.
        return Interpretation(Intent.UNCLEAR, Reason.CONFLICTING, found)

    no_answer = Intent.NO_INTENT if context is Context.OPEN_CONVERSATION else Intent.UNCLEAR
    for mod, reason in _QUALIFIER_PRIORITY:
        if mod in qualifiers:
            intent = Intent.UNCLEAR if reason is Reason.CONFLICTING else no_answer
            return Interpretation(intent, reason, found)
    return Interpretation(no_answer, Reason.NO_SIGNAL, found)


def interpret(message: str | None, context: Context) -> Interpretation:
    """Describe what `message` means in `context`. Pure; never raises for str/None."""
    if not isinstance(context, Context):
        raise TypeError(f"context must be a Context, got {type(context).__name__}")
    if message is not None and not isinstance(message, str):
        raise TypeError(f"message must be str or None, got {type(message).__name__}")

    clauses = split_clauses(message) if message else ()
    if not clauses:
        return Interpretation(Intent.UNCLEAR, Reason.EMPTY)

    if context is Context.REMINDER_REPLY:
        choice = _menu_choice(message)
        if choice is not None:
            return Interpretation(choice, Reason.MENU_OPTION, (message.strip(),))

    signals: list[_Signal] = []
    dangling_negation = False
    for clause in clauses:
        clause_signals, dangling = _scan_clause(clause)
        signals.extend(clause_signals)
        dangling_negation = dangling_negation or dangling

    # A stray "not" elsewhere doubts any non-refusal answer; a refusal stays a refusal.
    if dangling_negation and any(s.cue not in _REFUSAL_CUES for s in signals):
        signals.append(_Signal(Cue.NEGATOR, "not", _Mod.NEGATED))
    return _resolve(signals, context)
