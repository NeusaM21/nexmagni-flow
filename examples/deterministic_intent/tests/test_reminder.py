"""Reminder reply: "Reply 1 to confirm, 2 to reschedule, 3 to cancel." (fictional)."""

import pytest

from deterministic_intent import Action, Context, Intent, Reason, decide, interpret

CTX = Context.REMINDER_REPLY


def run(message):
    result = interpret(message, CTX)
    return result, decide(result, CTX)


@pytest.mark.parametrize(
    ("message", "intent", "action"),
    [
        ("1", Intent.CONFIRM_ATTENDANCE, Action.RECORD_ATTENDANCE_CONFIRMATION),
        (" 2 ", Intent.REQUEST_RESCHEDULE, Action.START_RESCHEDULE_FLOW),
        ("3", Intent.REQUEST_CANCEL, Action.START_CANCELLATION_FLOW),
        ("option 3", Intent.REQUEST_CANCEL, Action.START_CANCELLATION_FLOW),
        ("#2", Intent.REQUEST_RESCHEDULE, Action.START_RESCHEDULE_FLOW),
        ("1.", Intent.CONFIRM_ATTENDANCE, Action.RECORD_ATTENDANCE_CONFIRMATION),
    ],
)
def test_menu_digits_count_only_as_the_whole_message(message, intent, action):
    result, decision = run(message)
    assert (result.intent, result.reason) == (intent, Reason.MENU_OPTION)
    assert decision.action is action


@pytest.mark.parametrize("message", ["4", "13", "0", "option 9"])
def test_out_of_range_digits_are_not_options(message):
    result, decision = run(message)
    assert result.reason is not Reason.MENU_OPTION
    assert decision.action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize(
    ("message", "intent", "action"),
    [
        ("I'll be there at 3", Intent.CONFIRM_ATTENDANCE, Action.RECORD_ATTENDANCE_CONFIRMATION),
        ("yes, see you then", None, Action.ASK_CLARIFICATION),
        ("confirmed", Intent.AFFIRM, Action.RECORD_ATTENDANCE_CONFIRMATION),
        ("see you later", Intent.CONFIRM_ATTENDANCE, Action.RECORD_ATTENDANCE_CONFIRMATION),
        ("yes, but later", None, Action.ASK_CLARIFICATION),
        ("did you get my reply?", None, Action.ASK_CLARIFICATION),
        ("I can't make it", Intent.REQUEST_CANCEL, Action.START_CANCELLATION_FLOW),
        ("cant make it, sorry", Intent.REQUEST_CANCEL, Action.START_CANCELLATION_FLOW),
        ("I won't be there", Intent.REQUEST_CANCEL, Action.START_CANCELLATION_FLOW),
        ("please cancel", Intent.REQUEST_CANCEL, Action.START_CANCELLATION_FLOW),
        ("can we reschedule?", Intent.REQUEST_RESCHEDULE, Action.START_RESCHEDULE_FLOW),
        ("another day would be better", Intent.REQUEST_RESCHEDULE, Action.START_RESCHEDULE_FLOW),
    ],
)
def test_written_reminder_replies(message, intent, action):
    result, decision = run(message)
    if intent is not None:
        assert (result.intent, result.reason) == (intent, Reason.EXPLICIT)
    assert decision.action is action


def test_yes_and_see_you_are_two_intents_so_clarify():
    result, _ = run("yes, see you then")
    assert result.reason is Reason.CONFLICTING


@pytest.mark.parametrize(
    "message",
    ["3", "cancel", "I can't make it", "cancel it now please", "option 3"],
)
def test_reminder_never_cancels_directly(message):
    _, decision = run(message)
    assert decision.action is not Action.CANCEL_APPOINTMENT
    assert decision.destructive is False


@pytest.mark.parametrize(
    "message",
    ["confirm, or maybe reschedule", "ok, but I can't make it", "keep it, actually cancel"],
)
def test_two_reminder_intents_are_ambiguous(message):
    result, decision = run(message)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)
    assert decision.action is Action.ASK_CLARIFICATION


def test_plain_no_to_a_reminder_asks_what_they_mean():
    result, decision = run("no")
    assert result.intent is Intent.DENY
    assert decision.action is Action.ASK_CLARIFICATION
