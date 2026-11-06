"""Value types for the human-in-the-loop control."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ControlState(Enum):
    """Whether automation may reply in a conversation.

    UNKNOWN is never stored: it is what a read returns when the stored value
    cannot be trusted (store error, corrupted record, invalid state).
    """

    ACTIVE = "active"
    MUTED = "muted"
    UNKNOWN = "unknown"


STORABLE_STATES: frozenset[ControlState] = frozenset({ControlState.ACTIVE, ControlState.MUTED})


class Actor(Enum):
    AUTOMATION = "automation"
    HUMAN_OPERATOR = "human_operator"


class Outcome(Enum):
    """Result of handling one incoming message. Only SENT means a reply went out."""

    SENT = "sent"
    BLOCKED_MUTED = "blocked_muted"
    BLOCKED_UNKNOWN = "blocked_unknown"
    BLOCKED_AT_SEND = "blocked_at_send"
    LOCK_TIMEOUT = "lock_timeout"
    GENERATION_FAILED = "generation_failed"
    SEND_FAILED = "send_failed"


class ChangeResult(Enum):
    """Result of a state change request. Only CHANGED/UNCHANGED mean the target state holds."""

    CHANGED = "changed"
    UNCHANGED = "unchanged"
    REJECTED_INVALID = "rejected_invalid"
    REJECTED_MISMATCH = "rejected_mismatch"
    REJECTED_STALE = "rejected_stale"
    LOCK_TIMEOUT = "lock_timeout"
    STORE_FAILURE = "store_failure"


@dataclass(frozen=True, slots=True)
class ControlRecord:
    state: ControlState
    version: int


@dataclass(frozen=True, slots=True)
class StateReading:
    """A read of the control state. `version` is None when the state is UNKNOWN."""

    state: ControlState
    version: int | None


@dataclass(frozen=True, slots=True)
class Transition:
    """Audit entry. Contains no message text."""

    conversation_id: str
    actor: Actor
    old_state: ControlState
    new_state: ControlState
    version: int


@dataclass(frozen=True, slots=True)
class HumanApproval:
    """Simulates a trusted human authorization to reactivate one conversation.

    This example performs NO authentication: whoever constructs this object is
    trusted to be an operator. A real system must create it only after
    authenticating and authorizing the operator (for example, behind a
    protected dashboard endpoint).
    """

    operator_id: str
    conversation_id: str
    expected_version: int
