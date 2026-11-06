import pytest

from hitl_fail_closed import Actor, ChangeResult, ControlState, FaultyStore, mute, read_state

from conftest import CONV


@pytest.mark.parametrize("actor", list(Actor))
def test_anyone_can_mute(store, locks, actor):
    assert mute(store, locks, CONV, actor) is ChangeResult.CHANGED
    assert read_state(store, CONV).state is ControlState.MUTED


def test_mute_is_idempotent(store, locks):
    mute(store, locks, CONV, Actor.AUTOMATION)
    assert mute(store, locks, CONV, Actor.HUMAN_OPERATOR) is ChangeResult.UNCHANGED
    assert len(store.history(CONV)) == 1


def test_failed_mute_write_is_not_a_block(store, locks):
    faulty = FaultyStore(store)
    faulty.fail_writes = True
    assert mute(faulty, locks, CONV, Actor.HUMAN_OPERATOR) is ChangeResult.STORE_FAILURE
    # No assumption that later reads turn UNKNOWN: the store still says ACTIVE.
    assert read_state(faulty, CONV).state is ControlState.ACTIVE


def test_mute_with_unreadable_state_reports_failure(store, locks):
    faulty = FaultyStore(store)
    faulty.fail_get = True
    assert mute(faulty, locks, CONV, Actor.HUMAN_OPERATOR) is ChangeResult.STORE_FAILURE
    assert store.history(CONV) == ()


def test_mute_lock_timeout_is_reported(store):
    from hitl_fail_closed import ConversationLocks

    locks = ConversationLocks(timeout_s=0.05)
    lock = locks.control(CONV)
    lock.acquire()
    try:
        assert mute(store, locks, CONV, Actor.HUMAN_OPERATOR) is ChangeResult.LOCK_TIMEOUT
    finally:
        lock.release()
    assert read_state(store, CONV).state is ControlState.ACTIVE


@pytest.mark.parametrize(("conversation_id", "actor"), [("", Actor.AUTOMATION), (None, Actor.AUTOMATION), (CONV, "bot")])
def test_invalid_mute_requests(store, locks, conversation_id, actor):
    assert mute(store, locks, conversation_id, actor) is ChangeResult.REJECTED_INVALID


def test_history_versions_increase_by_one(store, locks):
    from hitl_fail_closed import HumanApproval, reactivate

    for _ in range(3):
        mute(store, locks, CONV, Actor.AUTOMATION)
        version = read_state(store, CONV).version
        reactivate(store, locks, CONV, HumanApproval("operator-a", CONV, version))
    versions = [t.version for t in store.history(CONV)]
    assert versions == list(range(1, 7))
