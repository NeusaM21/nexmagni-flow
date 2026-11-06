import pytest

from hitl_fail_closed import (
    Actor,
    ChangeResult,
    ControlState,
    FaultyStore,
    HumanApproval,
    mute,
    reactivate,
    read_state,
)

from conftest import CONV


@pytest.fixture
def muted(store, locks):
    mute(store, locks, CONV, Actor.AUTOMATION)
    return read_state(store, CONV).version


def test_valid_approval_reactivates(store, locks, muted):
    result = reactivate(store, locks, CONV, HumanApproval("operator-a", CONV, muted))
    assert result is ChangeResult.CHANGED
    assert read_state(store, CONV).state is ControlState.ACTIVE
    assert store.history(CONV)[-1].actor is Actor.HUMAN_OPERATOR


def test_stale_approval_is_rejected(store, locks, muted):
    approval = HumanApproval("operator-a", CONV, muted)
    reactivate(store, locks, CONV, approval)
    mute(store, locks, CONV, Actor.AUTOMATION)  # muted again after the approval was issued
    assert reactivate(store, locks, CONV, approval) is ChangeResult.REJECTED_STALE
    assert read_state(store, CONV).state is ControlState.MUTED


def test_approval_for_another_conversation_is_rejected(store, locks, muted):
    approval = HumanApproval("operator-a", "conv-999", muted)
    assert reactivate(store, locks, CONV, approval) is ChangeResult.REJECTED_MISMATCH
    assert read_state(store, CONV).state is ControlState.MUTED


@pytest.mark.parametrize(
    "approval",
    [
        HumanApproval("", CONV, 1),
        HumanApproval("   ", CONV, 1),
        HumanApproval(None, CONV, 1),
        HumanApproval("operator-a", CONV, -1),
        HumanApproval("operator-a", CONV, True),
        HumanApproval("operator-a", CONV, "1"),
        HumanApproval("operator-a", None, 1),
        None,
        "approved",
        {"operator_id": "operator-a"},
    ],
)
def test_invalid_approvals_are_rejected(store, locks, muted, approval):
    assert reactivate(store, locks, CONV, approval) is ChangeResult.REJECTED_INVALID
    assert read_state(store, CONV).state is ControlState.MUTED


def test_unreadable_state_cannot_be_reactivated(store, locks, muted):
    faulty = FaultyStore(store)
    faulty.fail_get = True
    approval = HumanApproval("operator-a", CONV, muted)
    assert reactivate(faulty, locks, CONV, approval) is ChangeResult.STORE_FAILURE


def test_failed_reactivation_write_keeps_muted(store, locks, muted):
    faulty = FaultyStore(store)
    faulty.fail_writes = True
    approval = HumanApproval("operator-a", CONV, muted)
    assert reactivate(faulty, locks, CONV, approval) is ChangeResult.STORE_FAILURE
    assert read_state(store, CONV).state is ControlState.MUTED


def test_reactivating_an_active_conversation_is_unchanged(store, locks):
    assert reactivate(store, locks, CONV, HumanApproval("operator-a", CONV, 0)) is ChangeResult.UNCHANGED
    assert store.history(CONV) == ()


def test_automation_has_no_path_to_active(store, locks, muted):
    # The only writer of ACTIVE is reactivate(), which always records HUMAN_OPERATOR,
    # and the store itself refuses ACTIVE from AUTOMATION.
    with pytest.raises(PermissionError):
        store.compare_and_set(CONV, muted, ControlState.ACTIVE, Actor.AUTOMATION)
    assert mute(store, locks, CONV, Actor.AUTOMATION) is ChangeResult.UNCHANGED
    assert read_state(store, CONV).state is ControlState.MUTED
