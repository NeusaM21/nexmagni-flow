import pytest

from deterministic_intent import Action, Context, Intent, Reason, decide, interpret

OPEN = Context.OPEN_CONVERSATION
REMINDER = Context.REMINDER_REPLY


@pytest.mark.parametrize(
    "message",
    [
        "I don't want to cancel",
        "I do not need to reschedule",
        "never cancel my appointments",
        "no need to cancel",
    ],
)
def test_negated_requests_in_open_conversation_do_nothing(message):
    result = interpret(message, OPEN)
    assert (result.intent, result.reason) == (Intent.NO_INTENT, Reason.NEGATED)
    assert decide(result, OPEN).action is Action.NO_ACTION


@pytest.mark.parametrize(
    "message",
    ["No need to reschedule", "I don't want to cancel", "I won't cancel"],
)
def test_negated_requests_in_reminder_ask_for_clarification(message):
    result = interpret(message, REMINDER)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.NEGATED)
    assert decide(result, REMINDER).action is Action.ASK_CLARIFICATION


@pytest.mark.parametrize(
    "message",
    [
        "If I need to cancel, what happens?",
        "What if I have to reschedule?",
        "In case I cancel later, will you remind me?",
        "Should I reschedule?",
        "I'm wondering whether to cancel",
    ],
)
def test_hypothetical_wording_is_not_a_request(message):
    result = interpret(message, OPEN)
    assert (result.intent, result.reason) == (Intent.NO_INTENT, Reason.HYPOTHETICAL)
    assert decide(result, OPEN).action is Action.NO_ACTION


@pytest.mark.parametrize(
    "message",
    [
        "What is your cancellation policy?",
        "Is there a fee to reschedule?",
        "How far in advance can I cancel",
        "Do you charge for cancellation?",
    ],
)
def test_policy_questions_are_not_requests(message):
    result = interpret(message, OPEN)
    assert (result.intent, result.reason) == (Intent.NO_INTENT, Reason.POLICY_QUESTION)
    assert decide(result, OPEN).action is Action.NO_ACTION


def test_request_next_to_policy_question_still_counts():
    result = interpret("Please cancel it. What's the fee?", OPEN)
    assert (result.intent, result.reason) == (Intent.REQUEST_CANCEL, Reason.EXPLICIT)


def test_request_next_to_hypothetical_is_ambiguous():
    result = interpret("Cancel it. If I can't, reschedule", OPEN)
    assert (result.intent, result.reason) == (Intent.UNCLEAR, Reason.CONFLICTING)


def test_hypothetical_in_cancellation_confirmation_never_cancels():
    context = Context.CANCELLATION_CONFIRMATION
    result = interpret("if I cancel, do I lose my spot?", context)
    assert result.intent is Intent.UNCLEAR
    assert decide(result, context).destructive is False


def test_negation_does_not_cross_clauses():
    result = interpret("not today, but tomorrow I can make it", REMINDER)
    assert result.reason is Reason.CONFLICTING  # a refusal and an attendance cue
