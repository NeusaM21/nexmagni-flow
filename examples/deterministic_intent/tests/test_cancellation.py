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
