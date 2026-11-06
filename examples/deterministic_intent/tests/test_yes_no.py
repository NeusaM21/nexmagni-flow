"""Booking confirmation: "Shall I book Tuesday at 10:00?" (fictional)."""

import pytest

from deterministic_intent import Action, Context, Intent, Reason, decide, interpret

CTX = Context.BOOKING_CONFIRMATION


def run(message):
    result = interpret(message, CTX)
    return result, decide(result, CTX)


@pytest.mark.parametrize(
    "message",
    [
        "yes",
        "YES!!",
        "Yeah",
        "sure, go ahead",
        "Ok",
        "sounds good",
        "Yes please",
        "Perfect, book it",
        "Of course",
        "I don't mind",
    ],
)
def test_explicit_yes_confirms_booking(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.AFFIRM, Reason.EXPLICIT)
    assert decision.action is Action.CONFIRM_BOOKING


@pytest.mark.parametrize(
    "message",
    [
        "no",
        "Nope",
        "not now",
        "never mind",
        "No thanks",
        "I'd rather not",
        "absolutely not",
        "Cancel",  # in this context "cancel" means "do not book"
        "I can't make it",
        "no I don't",
    ],
)
def test_explicit_no_takes_no_action(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.DENY, Reason.EXPLICIT)
    assert decision.action is Action.NO_ACTION


@pytest.mark.parametrize(
    "message",
    ["this works?", "yesterday", "okra", "nothing", "maybe", "1"],
)
def test_lookalike_words_are_not_answers(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.NO_SIGNAL)
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize(
    "message",
    [
        "no, go ahead",
        "yes but I'd rather not",
        "yes no",
        "ok, but I can't make it",
    ],
)
def test_conflicting_answers_ask_for_clarification(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize(
    "message",
    ["yes but later", "ok, later", "yes, not yet", "sure, hold on", "yes. wait", "ok in a bit"],
)
def test_deferred_yes_asks_instead_of_booking(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize("message", ["no, later", "nope, not yet"])
def test_deferred_refusal_is_still_a_refusal(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.DENY, Reason.EXPLICIT)
    assert decision.action is Action.NO_ACTION


@pytest.mark.parametrize("message", ["later", "not yet"])
def test_deferral_alone_asks(message):
    result, decision = run(message)
    assert result.intent is Intent.UNCLEAR
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize("message", ["not sure", "I'm not sure"])
def test_negated_yes_is_not_a_yes(message):
    result, decision = run(message)
    assert result.intent is Intent.UNCLEAR
    assert result.reason is Reason.NEGATED
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize("message", ["sure, I guess not", "yes. I don't know", "ok, not really"])
def test_stray_negation_in_another_clause_blocks_the_yes(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize("message", ["no, I don't", "nope. not interested"])
def test_stray_negation_next_to_a_refusal_is_still_a_refusal(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.DENY, Reason.EXPLICIT)
    assert decision.action is Action.NO_ACTION
