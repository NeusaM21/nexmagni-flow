"""Deterministic race scenarios, orchestrated with threading.Event and Barrier.

Each scenario is repeated 20 times to catch ordering assumptions.
"""

import threading

import pytest

from hitl_fail_closed import (
    Actor,
    ChangeResult,
    ControlState,
    FaultyStore,
    GatedReplyGenerator,
    HumanApproval,
    Outcome,
    handle_message,
    mute,
    reactivate,
    read_state,
)
from hitl_fail_closed.fakes import WAIT_LIMIT_S

from conftest import CONV, finish, start

REPEAT = pytest.mark.parametrize("repetition", range(20))


def handler(store, locks, transport, generator, conversation_id=CONV):
    return lambda: handle_message(conversation_id, "Is Friday free?", store=store, locks=locks,
                                  generate=generator, transport=transport)


@REPEAT
def test_mute_during_generation_blocks_at_send(store, locks, transport, repetition):
    generator = GatedReplyGenerator(gated=True)
    thread, results = start(handler(store, locks, transport, generator))
    assert generator.started.wait(WAIT_LIMIT_S)

    # The mute completes while the reply is still being generated (no wait on processing).
    assert mute(store, locks, CONV, Actor.HUMAN_OPERATOR) is ChangeResult.CHANGED
    assert thread.is_alive()

    generator.release.set()
    finish(thread)
    assert results == [Outcome.BLOCKED_AT_SEND]
    assert transport.sent == []


@REPEAT
def test_store_failure_at_recheck_blocks(store, locks, transport, repetition):
    faulty = FaultyStore(store)
    generator = GatedReplyGenerator(gated=True)
    thread, results = start(handler(faulty, locks, transport, generator))
    assert generator.started.wait(WAIT_LIMIT_S)
    faulty.fail_get = True
    generator.release.set()
    finish(thread)
    assert results == [Outcome.BLOCKED_UNKNOWN]
    assert transport.sent == []


@REPEAT
def test_same_conversation_is_serialized(store, locks, transport, repetition):
    generator = GatedReplyGenerator(gated=True)
    first, first_result = start(handler(store, locks, transport, generator))
    assert generator.started.wait(WAIT_LIMIT_S)
    second, second_result = start(handler(store, locks, transport, generator))
    generator.release.set()
    finish(first)
    finish(second)
    assert first_result == second_result == [Outcome.SENT]
    assert generator.max_in_flight[CONV] == 1


@REPEAT
def test_different_conversations_run_in_parallel(store, locks, transport, repetition):
    # Both calls must be inside generation at the same time to pass the barrier.
    generator = GatedReplyGenerator(barrier=threading.Barrier(2))
    a, a_result = start(handler(store, locks, transport, generator, "conv-a"))
    b, b_result = start(handler(store, locks, transport, generator, "conv-b"))
    finish(a)
    finish(b)
    assert a_result == b_result == [Outcome.SENT]


@REPEAT
def test_stale_approval_after_concurrent_mute(store, locks, repetition):
    mute(store, locks, CONV, Actor.AUTOMATION)
    approval = HumanApproval("operator-a", CONV, read_state(store, CONV).version)
    assert reactivate(store, locks, CONV, approval) is ChangeResult.CHANGED
    mute(store, locks, CONV, Actor.AUTOMATION)  # a new handoff happens
    assert reactivate(store, locks, CONV, approval) is ChangeResult.REJECTED_STALE
    assert read_state(store, CONV).state is ControlState.MUTED


@REPEAT
def test_mute_waits_only_for_an_in_progress_send(store, locks, repetition):
    """While a send holds the control lock, a mute waits and then takes effect."""
    send_started = threading.Event()
    allow_send = threading.Event()

    class SlowTransport:
        def __init__(self):
            self.sent = []

        def send(self, conversation_id, text):
            send_started.set()
            assert allow_send.wait(WAIT_LIMIT_S)
            self.sent.append(read_state(store, conversation_id).state)

    transport = SlowTransport()
    sender, send_result = start(handler(store, locks, transport, GatedReplyGenerator()))
    assert send_started.wait(WAIT_LIMIT_S)
    muter, mute_result = start(lambda: mute(store, locks, CONV, Actor.HUMAN_OPERATOR))
    assert not muter.join(0.05) and muter.is_alive()  # blocked behind the send
    allow_send.set()
    finish(sender)
    finish(muter)
    assert send_result == [Outcome.SENT]
    assert transport.sent == [ControlState.ACTIVE]  # the send was authorized before the mute
    assert mute_result == [ChangeResult.CHANGED]
    assert read_state(store, CONV).state is ControlState.MUTED
