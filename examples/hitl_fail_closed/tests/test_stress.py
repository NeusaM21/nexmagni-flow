"""Randomized concurrent workload (fixed seeds) checked against the nine invariants."""

import random
import threading

import pytest

from hitl_fail_closed import (
    Actor,
    ChangeResult,
    ControlState,
    ConversationLocks,
    GatedReplyGenerator,
    HumanApproval,
    InMemoryControlStore,
    Outcome,
    RecordingTransport,
    handle_message,
    mute,
    reactivate,
    read_state,
)
from hitl_fail_closed.fakes import WAIT_LIMIT_S

CONVERSATIONS = ("conv-001", "conv-002", "conv-003")
SECRET_TEXT = "fictional-message-7f3a"
THREADS = 8
OPERATIONS = 200


def worker(seed, store, locks, transport, generator, outcomes, errors):
    rng = random.Random(seed)
    try:
        for _ in range(OPERATIONS):
            conversation = rng.choice(CONVERSATIONS)
            roll = rng.random()
            if roll < 0.6:
                outcomes.append(handle_message(conversation, SECRET_TEXT, store=store, locks=locks,
                                               generate=generator, transport=transport))
            elif roll < 0.8:
                mute(store, locks, conversation, rng.choice(list(Actor)))
            else:
                reading = read_state(store, conversation)
                reactivate(store, locks, conversation,
                           HumanApproval("operator-b", conversation, reading.version or 0))
    except Exception as exc:  # surfaced by the test
        errors.append(exc)


@pytest.mark.parametrize("base_seed", [11, 23, 42])
def test_concurrent_workload_respects_invariants(base_seed):
    store = InMemoryControlStore()
    locks = ConversationLocks(timeout_s=WAIT_LIMIT_S)
    transport = RecordingTransport(store)
    generator = GatedReplyGenerator(reply=f"auto reply to {SECRET_TEXT}")
    outcomes, errors = [], []

    threads = [
        threading.Thread(target=worker, args=(base_seed * 100 + n, store, locks, transport,
                                              generator, outcomes, errors), daemon=True)
        for n in range(THREADS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
        assert not thread.is_alive(), "worker hung"
    assert errors == []

    # 1. Every send observed ACTIVE in the store at the instant of sending.
    assert transport.sent, "workload produced no sends"
    assert all(record.state_at_send is ControlState.ACTIVE for record in transport.sent)
    assert outcomes.count(Outcome.SENT) == len(transport.sent)
    # 2. No unexpected outcomes with a healthy store and generous lock timeout.
    assert set(outcomes) <= {Outcome.SENT, Outcome.BLOCKED_MUTED, Outcome.BLOCKED_AT_SEND}
    for conversation in CONVERSATIONS:
        history = store.history(conversation)
        # 3/4. Only human operators ever set ACTIVE.
        assert all(t.actor is Actor.HUMAN_OPERATOR for t in history if t.new_state is ControlState.ACTIVE)
        # 8. Versions increase by exactly one, and transitions chain correctly.
        assert [t.version for t in history] == list(range(1, len(history) + 1))
        for previous, current in zip(history, history[1:]):
            assert current.old_state is previous.new_state
        # 6. At most one generation per conversation at a time.
        assert generator.max_in_flight[conversation] <= 1
        # 7. All locks released.
        assert not locks.processing(conversation).locked()
        assert not locks.control(conversation).locked()
        # 9. No message text in the audit trail.
        assert SECRET_TEXT not in repr(history)
    assert all(isinstance(outcome, Outcome) for outcome in outcomes)
    assert SECRET_TEXT not in repr(outcomes)


def test_failed_operations_never_report_success():
    store = InMemoryControlStore()
    locks = ConversationLocks()
    assert mute(store, locks, "conv-001", Actor.AUTOMATION) is ChangeResult.CHANGED
    approval = HumanApproval("operator-b", "conv-001", 0)  # stale on purpose
    assert reactivate(store, locks, "conv-001", approval) is ChangeResult.REJECTED_STALE
