"""handle_message(): lock -> check -> generate -> recheck under control lock -> send."""

from __future__ import annotations

from typing import Callable, Protocol

from .control import read_state
from .locks import ConversationLocks, hold
from .models import ControlState, Outcome
from .store import ControlStore

ReplyGenerator = Callable[[str, str], str]


class Transport(Protocol):
    def send(self, conversation_id: str, text: str) -> None: ...


def handle_message(
    conversation_id: str,
    text: str,
    *,
    store: ControlStore,
    locks: ConversationLocks,
    generate: ReplyGenerator,
    transport: Transport,
) -> Outcome:
    """Process one incoming message. Returns an Outcome; never returns message text."""
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError("conversation_id must be a non-empty str")

    with hold(locks.processing(conversation_id), locks.timeout_s) as processing:
        if not processing:
            return Outcome.LOCK_TIMEOUT

        first = read_state(store, conversation_id)
        if first.state is ControlState.UNKNOWN:
            return Outcome.BLOCKED_UNKNOWN
        if first.state is ControlState.MUTED:
            return Outcome.BLOCKED_MUTED

        # Slow step. The control lock is NOT held, so an operator can mute meanwhile.
        try:
            reply = generate(conversation_id, text)
        except Exception:
            return Outcome.GENERATION_FAILED
        if not isinstance(reply, str) or not reply.strip():
            return Outcome.GENERATION_FAILED

        # Recheck and send atomically with respect to state changes.
        with hold(locks.control(conversation_id), locks.timeout_s) as control:
            if not control:
                return Outcome.LOCK_TIMEOUT
            final = read_state(store, conversation_id)
            if final.state is ControlState.UNKNOWN:
                return Outcome.BLOCKED_UNKNOWN
            if final.state is not ControlState.ACTIVE:
                return Outcome.BLOCKED_AT_SEND
            try:
                transport.send(conversation_id, reply)
            except Exception:
                return Outcome.SEND_FAILED
            return Outcome.SENT
