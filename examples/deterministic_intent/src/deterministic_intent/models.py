"""Value types shared by the interpreter and the authorization policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Context(Enum):
    """What the conversation is waiting for when the message arrives."""

    BOOKING_CONFIRMATION = "booking"
    CANCELLATION_CONFIRMATION = "cancellation"
    REMINDER_REPLY = "reminder"
    OPEN_CONVERSATION = "open"


class Intent(Enum):
    """What the customer most likely means. Understanding only, never permission."""

    AFFIRM = "affirm"
    DENY = "deny"
    REQUEST_CANCEL = "request_cancel"
    CONFIRM_ATTENDANCE = "confirm_attendance"
    REQUEST_RESCHEDULE = "request_reschedule"
    UNCLEAR = "unclear"
    NO_INTENT = "no_intent"


class Reason(Enum):
    """Why the interpreter reached its conclusion."""

    EXPLICIT = "explicit"
    MENU_OPTION = "menu_option"
    NEGATED = "negated"
    HYPOTHETICAL = "hypothetical"
    POLICY_QUESTION = "policy_question"
    CONFLICTING = "conflicting"
    NO_SIGNAL = "no_signal"
    EMPTY = "empty"


class Action(Enum):
    """What the application is allowed to do next."""

    CONFIRM_BOOKING = "confirm_booking"
    CANCEL_APPOINTMENT = "cancel_appointment"
    KEEP_APPOINTMENT = "keep_appointment"
    RECORD_ATTENDANCE_CONFIRMATION = "record_attendance_confirmation"
    START_CANCELLATION_FLOW = "start_cancellation_flow"
    START_RESCHEDULE_FLOW = "start_reschedule_flow"
    ASK_CLARIFICATION = "ask_clarification"
    NO_ACTION = "no_action"


STATE_CHANGING_ACTIONS: frozenset[Action] = frozenset(
    {
        Action.CONFIRM_BOOKING,
        Action.CANCEL_APPOINTMENT,
        Action.KEEP_APPOINTMENT,
        Action.RECORD_ATTENDANCE_CONFIRMATION,
    }
)

DESTRUCTIVE_ACTIONS: frozenset[Action] = frozenset({Action.CANCEL_APPOINTMENT})


@dataclass(frozen=True, slots=True)
class Interpretation:
    """Result of `interpret()`: an intent, the reason for it, and matched cues."""

    intent: Intent
    reason: Reason
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    """Result of `decide()`. Safety flags are derived from the action itself."""

    action: Action
    reason: Reason

    @property
    def changes_state(self) -> bool:
        return self.action in STATE_CHANGING_ACTIONS

    @property
    def destructive(self) -> bool:
        return self.action in DESTRUCTIVE_ACTIONS
