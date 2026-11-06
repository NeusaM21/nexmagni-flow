import itertools

import pytest

from deterministic_intent import (
    POLICY_TABLE,
    Action,
    Context,
    Decision,
    Intent,
    Interpretation,
    Reason,
    decide,
)

ALL_COMBINATIONS = list(itertools.product(Context, Intent, Reason))


def test_policy_table_covers_all_28_combinations():
    expected = set(itertools.product(Context, Intent))
    assert len(expected) == 28
    assert set(POLICY_TABLE) == expected


def test_policy_table_is_read_only():
    with pytest.raises(TypeError):
        POLICY_TABLE[(Context.OPEN_CONVERSATION, Intent.AFFIRM)] = Action.CANCEL_APPOINTMENT


@pytest.mark.parametrize(("context", "intent", "reason"), ALL_COMBINATIONS)
def test_guards_hold_for_every_possible_input(context, intent, reason):
    decision = decide(Interpretation(intent, reason), context)
    if decision.destructive:
        assert context is Context.CANCELLATION_CONFIRMATION
        assert intent is Intent.AFFIRM
        assert reason is Reason.EXPLICIT
    if decision.changes_state:
        assert reason in (Reason.EXPLICIT, Reason.MENU_OPTION)
    if intent is Intent.UNCLEAR:
        assert decision.action is Action.ASK_CLARIFICATION


def test_menu_option_can_never_cancel_directly():
    for context in Context:
        for intent in Intent:
            decision = decide(Interpretation(intent, Reason.MENU_OPTION), context)
            assert decision.action is not Action.CANCEL_APPOINTMENT


def test_destructive_action_requires_explicit_reason():
    context = Context.CANCELLATION_CONFIRMATION
    strong = decide(Interpretation(Intent.AFFIRM, Reason.EXPLICIT), context)
    weak = decide(Interpretation(Intent.AFFIRM, Reason.HYPOTHETICAL), context)
    assert strong.action is Action.CANCEL_APPOINTMENT
    assert weak.action is Action.ASK_CLARIFICATION


def test_cancel_appointment_only_for_explicit_affirm_to_cancellation_question():
    allowed = [
        (context, intent, reason)
        for context, intent, reason in ALL_COMBINATIONS
        if decide(Interpretation(intent, reason), context).action is Action.CANCEL_APPOINTMENT
    ]
    assert allowed == [(Context.CANCELLATION_CONFIRMATION, Intent.AFFIRM, Reason.EXPLICIT)]


def test_request_cancel_never_cancels_directly():
    for context in Context:
        decision = decide(Interpretation(Intent.REQUEST_CANCEL, Reason.EXPLICIT), context)
        assert decision.destructive is False
    decision = decide(
        Interpretation(Intent.REQUEST_CANCEL, Reason.EXPLICIT), Context.CANCELLATION_CONFIRMATION
    )
    assert decision.action is Action.ASK_CLARIFICATION


def test_question_reason_never_changes_state():
    for context in Context:
        for intent in Intent:
            assert not decide(Interpretation(intent, Reason.QUESTION), context).changes_state


def test_decision_flags_are_derived_from_action():
    assert Decision(Action.CANCEL_APPOINTMENT, Reason.EXPLICIT).destructive
    assert Decision(Action.KEEP_APPOINTMENT, Reason.EXPLICIT).changes_state
    assert not Decision(Action.START_CANCELLATION_FLOW, Reason.EXPLICIT).changes_state


def test_models_are_immutable():
    result = Interpretation(Intent.AFFIRM, Reason.EXPLICIT)
    with pytest.raises(AttributeError):
        result.intent = Intent.DENY
