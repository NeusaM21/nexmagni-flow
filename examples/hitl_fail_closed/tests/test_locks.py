import pytest

from hitl_fail_closed import (
    ConversationLocks,
    GatedReplyGenerator,
    InMemoryControlStore,
    Outcome,
    RecordingTransport,
    handle_message,
)
from hitl_fail_closed.locks import hold

from conftest import CONV


def test_same_conversation_shares_locks():
    locks = ConversationLocks()
    assert locks.processing(CONV) is locks.processing(CONV)
    assert locks.control(CONV) is locks.control(CONV)
    assert locks.processing(CONV) is not locks.control(CONV)
    assert locks.processing(CONV) is not locks.processing("conv-002")


def test_invalid_timeout():
    with pytest.raises(ValueError):
        ConversationLocks(timeout_s=0)


def test_hold_releases_on_exception():
    locks = ConversationLocks()
    lock = locks.control(CONV)
    with pytest.raises(RuntimeError):
        with hold(lock, 1.0) as acquired:
            assert acquired
            raise RuntimeError
    assert not lock.locked()


@pytest.mark.parametrize("which", ["processing", "control"])
def test_lock_timeout_blocks_sending(which):
    store = InMemoryControlStore()
    transport = RecordingTransport(store)
    locks = ConversationLocks(timeout_s=0.05)
    lock = getattr(locks, which)(CONV)
    lock.acquire()
    try:
        outcome = handle_message(CONV, "hi", store=store, locks=locks,
                                 generate=GatedReplyGenerator(), transport=transport)
    finally:
        lock.release()
    assert outcome is Outcome.LOCK_TIMEOUT
    assert transport.sent == []


@pytest.mark.parametrize("failure", ["generation", "transport"])
def test_locks_are_released_after_failures(failure):
    store = InMemoryControlStore()
    locks = ConversationLocks()
    transport = RecordingTransport(store, fail=failure == "transport")
    generator = GatedReplyGenerator(fail=failure == "generation")
    handle_message(CONV, "hi", store=store, locks=locks, generate=generator, transport=transport)
    assert not locks.processing(CONV).locked()
    assert not locks.control(CONV).locked()
    ok = RecordingTransport(store)
    assert handle_message(CONV, "hi", store=store, locks=locks,
                          generate=GatedReplyGenerator(), transport=ok) is Outcome.SENT
