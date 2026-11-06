"""Reading and changing the control state.

- `read_state` fails closed: anything it cannot trust is UNKNOWN.
- `mute` may be requested by anyone. Its result must be checked: only
  CHANGED or UNCHANGED mean the conversation is muted. A failed write is NOT
  an effective block, and nothing guarantees that later reads will return
  UNKNOWN; the store may still report ACTIVE.
- `reactivate` requires a HumanApproval bound to the conversation and to the
  current version. Automation has no way to set ACTIVE.
"""

from __future__ import annotations

from .locks import ConversationLocks, hold
from .models import (
    STORABLE_STATES,
    Actor,
    ChangeResult,
    ControlRecord,
    ControlState,
    HumanApproval,
    StateReading,
)
from .store import ControlStore

_UNKNOWN = StateReading(ControlState.UNKNOWN, None)


def read_state(store: ControlStore, conversation_id: str) -> StateReading:
    """Read the state. Never raises; returns UNKNOWN when the value cannot be trusted."""
    try:
        record = store.get(conversation_id)
    except Exception:
        return _UNKNOWN
    if record is None:
        return StateReading(ControlState.ACTIVE, 0)  # confirmed absence: never muted
    if not isinstance(record, ControlRecord):
        return _UNKNOWN
    version = record.version
    if (
        record.state not in STORABLE_STATES
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version < 1
    ):
        return _UNKNOWN
    return StateReading(record.state, version)


def mute(
    store: ControlStore,
    locks: ConversationLocks,
    conversation_id: str,
    actor: Actor,
) -> ChangeResult:
    """Request MUTED. Check the result: only CHANGED/UNCHANGED confirm the block."""
    if not isinstance(conversation_id, str) or not conversation_id or not isinstance(actor, Actor):
        return ChangeResult.REJECTED_INVALID
    with hold(locks.control(conversation_id), locks.timeout_s) as acquired:
        if not acquired:
            return ChangeResult.LOCK_TIMEOUT
        reading = read_state(store, conversation_id)
        if reading.state is ControlState.MUTED:
            return ChangeResult.UNCHANGED
        if reading.state is ControlState.UNKNOWN or reading.version is None:
            return ChangeResult.STORE_FAILURE
        try:
            written = store.compare_and_set(
                conversation_id, reading.version, ControlState.MUTED, actor
            )
        except Exception:
            return ChangeResult.STORE_FAILURE
        return ChangeResult.CHANGED if written else ChangeResult.STORE_FAILURE


def _valid_approval(approval: object) -> bool:
    return (
        isinstance(approval, HumanApproval)
        and isinstance(approval.operator_id, str)
        and bool(approval.operator_id.strip())
        and isinstance(approval.conversation_id, str)
        and isinstance(approval.expected_version, int)
        and not isinstance(approval.expected_version, bool)
        and approval.expected_version >= 0
    )


def reactivate(
    store: ControlStore,
    locks: ConversationLocks,
    conversation_id: str,
    approval: HumanApproval,
) -> ChangeResult:
    """Set ACTIVE only with a valid approval for this conversation and current version."""
    if not isinstance(conversation_id, str) or not conversation_id or not _valid_approval(approval):
        return ChangeResult.REJECTED_INVALID
    if approval.conversation_id != conversation_id:
        return ChangeResult.REJECTED_MISMATCH
    with hold(locks.control(conversation_id), locks.timeout_s) as acquired:
        if not acquired:
            return ChangeResult.LOCK_TIMEOUT
        reading = read_state(store, conversation_id)
        if reading.state is ControlState.UNKNOWN or reading.version is None:
            return ChangeResult.STORE_FAILURE
        if reading.version != approval.expected_version:
            return ChangeResult.REJECTED_STALE
        if reading.state is ControlState.ACTIVE:
            return ChangeResult.UNCHANGED
        try:
            written = store.compare_and_set(
                conversation_id, reading.version, ControlState.ACTIVE, Actor.HUMAN_OPERATOR
            )
        except Exception:
            return ChangeResult.STORE_FAILURE
        return ChangeResult.CHANGED if written else ChangeResult.REJECTED_STALE
