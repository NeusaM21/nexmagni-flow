"""Cancellation confirmation and cancellation requests in open conversation."""

import pytest

from deterministic_intent import Action, Context, Intent, Reason, decide, interpret

CONFIRM = Context.CANCELLATION_CONFIRMATION
OPEN = Context.OPEN_CONVERSATION


def run(message, context):
    result = interpret(message, context)
    return result, decide(result, context)


@pytest.mark.parametrize(
    "message",
    [
        "yes",
        "yes, cancel it",
        "please cancel",
        "Cancel",
        "go ahead",
        "I confirm the cancellation",
        "I can't make it anyway",
        "call it off",
    ],
)
def test_explicit_yes_cancels_only_in_cancellation_confirmation(message):
    result, decision = run(message, CONFIRM)
    assert (result.intent, result.reason) == (Intent.AFFIRM, Reason.EXPLICIT)
    assert decision.action is Action.CANCEL_APPOINTMENT
    assert decision.destructive is True


@pytest.mark.parametrize(
    "message",
    [
        "no",
        "don't cancel",
        "Do not cancel it",
        "keep it",
        "No need to cancel",
        "Don't cancel, I'll be there",
        "never mind",
    ],
)
def test_keeping_the_appointment(message):
    result, decision = run(message, CONFIRM)
    assert (result.intent, result.reason) == (Intent.DENY, Reason.EXPLICIT)
    assert decision.action is Action.KEEP_APPOINTMENT
    assert decision.destructive is False


@pytest.mark.parametrize(
    "message",
    [
        "I don't not want to cancel",
        "yes, keep it",
        "cancel? no",
        "cancel and move it to another day",
    ],
)
def test_confusing_answers_never_cancel(message):
    result, decision = run(message, CONFIRM)
    assert result.intent is Intent.UNCLEAR
    assert result.reason is Reason.CONFLICTING
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize(
    "message",
    [
        "I need to cancel my appointment",
        "Can you cancel my booking?",
        "cancel",
        "Something came up, I won't make it",
        "I'm not coming tomorrow",
    ],
)
def test_open_conversation_request_starts_flow_without_cancelling(message):
    result, decision = run(message, OPEN)
    assert (result.intent, result.reason) == (Intent.REQUEST_CANCEL, Reason.EXPLICIT)
    assert decision.action is Action.START_CANCELLATION_FLOW
    assert decision.changes_state is False


@pytest.mark.parametrize(
    "message",
    [
        "Did you cancel it?",
        "did you cancel it",
        "Is it cancelled?",
        "Has it been cancelled?",
        "is my appointment cancelled",
        "has the appointment been cancelled",
        "is the booking cancelled",
        "Can you cancel it?",
        "Can you cancel my booking?",
        "cancel?",
    ],
)
def test_questions_never_cancel_in_cancellation_confirmation(message):
    result, decision = run(message, CONFIRM)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.QUESTION)
    assert decision.action is Action.ASK_CLARIFICATION
    assert decision.destructive is False


def test_question_next_to_an_explicit_yes_asks():
    result, decision = run("Did you cancel it? yes", CONFIRM)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize("message", ["Did you cancel it?", "has it been cancelled"])
def test_status_question_in_open_conversation_starts_nothing(message):
    result, decision = run(message, OPEN)
    assert (result.intent, result.reason) == (Intent.NO_INTENT, Reason.QUESTION)
    assert decision.action is Action.NO_ACTION


@pytest.mark.parametrize(
    "message",
    ["yes but later", "ok, cancel it later", "yes, not yet", "cancel it, but wait", "hold on, yes"],
)
def test_deferred_answers_never_cancel(message):
    result, decision = run(message, CONFIRM)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)
    assert decision.action is Action.ASK_CLARIFICATION
    assert decision.destructive is False


@pytest.mark.parametrize("message", ["no, later", "no, not yet"])
def test_deferred_refusal_keeps_the_appointment(message):
    result, decision = run(message, CONFIRM)
    assert (result.intent, result.reason) == (Intent.DENY, Reason.EXPLICIT)
    assert decision.action is Action.KEEP_APPOINTMENT


@pytest.mark.parametrize("context", list(Context))
@pytest.mark.parametrize("message", ["No problem", "No worries", "not a problem", "no prob!"])
def test_neutral_idioms_are_neither_yes_nor_no(message, context):
    result, decision = run(message, context)
    assert result.reason is Reason.NO_SIGNAL
    assert result.intent not in (Intent.AFFIRM, Intent.DENY)
    assert decision.changes_state is False


def test_neutral_idiom_does_not_hide_an_explicit_answer():
    result, decision = run("No problem, cancel it", CONFIRM)
    assert (result.intent, decision.action) == (Intent.AFFIRM, Action.CANCEL_APPOINTMENT)
    result, decision = run("No worries, keep it", CONFIRM)
    assert (result.intent, decision.action) == (Intent.DENY, Action.KEEP_APPOINTMENT)
    result, decision = run("No, no problem", CONFIRM)
    assert (result.intent, decision.action) == (Intent.DENY, Action.KEEP_APPOINTMENT)
