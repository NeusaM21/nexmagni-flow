import pytest

from hitl_fail_closed import (
    Actor,
    ControlState,
    FaultyStore,
    GatedReplyGenerator,
    Outcome,
    handle_message,
    mute,
)

from conftest import CONV


def handle(store, locks, transport, generate=None, conversation_id=CONV):
    return handle_message(
        conversation_id, "Is Friday free?", store=store, locks=locks,
        generate=generate or GatedReplyGenerator(), transport=transport,
    )


def test_active_conversation_gets_a_reply(store, locks, transport):
    assert handle(store, locks, transport) is Outcome.SENT
    assert [r.state_at_send for r in transport.sent] == [ControlState.ACTIVE]


def test_muted_conversation_is_blocked_before_generation(store, locks, transport):
    mute(store, locks, CONV, Actor.HUMAN_OPERATOR)
    generator = GatedReplyGenerator()
    assert handle(store, locks, transport, generator) is Outcome.BLOCKED_MUTED
    assert not generator.started.is_set()
    assert transport.sent == []


def test_unknown_state_blocks(store, locks, transport):
    faulty = FaultyStore(store)
    faulty.fail_get = True
    assert handle(faulty, locks, transport) is Outcome.BLOCKED_UNKNOWN
    assert transport.sent == []


def test_corrupted_state_blocks(store, locks, transport):
    faulty = FaultyStore(store)
    faulty.get_override = "ACTIVE"
    assert handle(faulty, locks, transport) is Outcome.BLOCKED_UNKNOWN


@pytest.mark.parametrize("reply", ["", "   ", None, 42])
def test_empty_or_invalid_reply_is_not_sent(store, locks, transport, reply):
    def generate(_conversation_id, _text):
        return reply

    assert handle(store, locks, transport, generate) is Outcome.GENERATION_FAILED
    assert transport.sent == []


def test_generation_exception(store, locks, transport):
    assert handle(store, locks, transport, GatedReplyGenerator(fail=True)) is Outcome.GENERATION_FAILED


def test_transport_failure(store, locks):
    from hitl_fail_closed import RecordingTransport

    failing = RecordingTransport(store, fail=True)
    assert handle(store, locks, failing) is Outcome.SEND_FAILED


def test_failed_mute_does_not_block_replies(store, locks, transport):
    faulty = FaultyStore(store)
    faulty.fail_writes = True
    mute(faulty, locks, CONV, Actor.HUMAN_OPERATOR)  # STORE_FAILURE, documented as not a block
    assert handle(faulty, locks, transport) is Outcome.SENT


def test_outcome_never_contains_message_text(store, locks, transport):
    outcome = handle(store, locks, transport)
    assert isinstance(outcome, Outcome)


def test_invalid_conversation_id(store, locks, transport):
    with pytest.raises(ValueError):
        handle(store, locks, transport, conversation_id="")
