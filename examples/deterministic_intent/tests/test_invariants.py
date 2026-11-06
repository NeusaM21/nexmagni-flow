"""Safety properties checked over every fictional message in every context."""

import pytest

from deterministic_intent import Action, Context, Intent, Reason, decide, interpret

CORPUS = (
    None, "", "yes", "no", "ok", "sure, go ahead", "no, go ahead", "cancel", "please cancel",
    "yes, cancel it", "don't cancel", "I don't not want to cancel", "keep it",
    "I can't make it", "I'll be there", "1", "2", "3", "option 3", "reschedule",
    "move it to another day", "if I need to cancel", "what is your cancellation policy?",
    "is there a fee?", "not sure", "maybe", "yesterday", "cancel and reschedule",
    "Can you cancel my booking?", "never mind", "I'm not coming", "\U0001F44D",
    "Something came up", "see you then", "absolutely not", "thanks!",
    "Did you cancel it?", "did you cancel it", "Can you cancel it?", "Is it cancelled?",
    "yes but later", "ok, not yet", "later", "see you later", "No problem", "No worries",
    "no problem, cancel it",
)

WEAK_REASONS = {
    Reason.NEGATED, Reason.HYPOTHETICAL, Reason.POLICY_QUESTION, Reason.QUESTION,
    Reason.CONFLICTING, Reason.EMPTY, Reason.NO_SIGNAL,
}

CASES = [(message, context) for message in CORPUS for context in Context]


@pytest.mark.parametrize(("message", "context"), CASES)
def test_safety_invariants(message, context):
    result = interpret(message, context)
    decision = decide(result, context)

    # 1. Destructive only after an explicit answer to a cancellation question.
    if decision.destructive:
        assert context is Context.CANCELLATION_CONFIRMATION
        assert result.intent is Intent.AFFIRM
        assert result.reason is Reason.EXPLICIT
    # 2. State changes need explicit or menu evidence.
    if decision.changes_state:
        assert result.reason in (Reason.EXPLICIT, Reason.MENU_OPTION)
    # 3. Unclear always asks.
    if result.intent is Intent.UNCLEAR:
        assert decision.action is Action.ASK_CLARIFICATION
    # 4. Weak evidence never changes state.
    if result.reason in WEAK_REASONS:
        assert not decision.changes_state
    # 5. Reminders never cancel directly.
    if context is Context.REMINDER_REPLY:
        assert decision.action is not Action.CANCEL_APPOINTMENT


@pytest.mark.parametrize("context", list(Context))
def test_determinism(context):
    for message in CORPUS:
        first = interpret(message, context)
        assert all(interpret(message, context) == first for _ in range(100))
