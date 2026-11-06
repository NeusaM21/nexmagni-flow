"""Authorization policy: turns an interpretation into a permitted action.

Understanding a message (`interpret`) and being allowed to act on it
(`decide`) are separate steps. The table below is complete: every
(context, intent) pair has exactly one action. Two guards then downgrade any
state-changing or destructive action whose evidence is not strong enough: a
cancellation requires an explicit AFFIRM to a cancellation question.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .models import (
    DESTRUCTIVE_ACTIONS,
    STATE_CHANGING_ACTIONS,
    Action,
    Context,
    Decision,
    Intent,
    Interpretation,
    Reason,
)

_B = Context.BOOKING_CONFIRMATION
_C = Context.CANCELLATION_CONFIRMATION
_R = Context.REMINDER_REPLY
_O = Context.OPEN_CONVERSATION

ASK = Action.ASK_CLARIFICATION

POLICY_TABLE: Mapping[tuple[Context, Intent], Action] = MappingProxyType(
    {
        # Booking confirmation: "Shall I book Tuesday at 10:00?"
        (_B, Intent.AFFIRM): Action.CONFIRM_BOOKING,
        (_B, Intent.DENY): Action.NO_ACTION,
        (_B, Intent.REQUEST_CANCEL): Action.NO_ACTION,  # unreachable: cancel cues read as DENY here
        (_B, Intent.CONFIRM_ATTENDANCE): ASK,
        (_B, Intent.REQUEST_RESCHEDULE): ASK,
        (_B, Intent.UNCLEAR): ASK,
        (_B, Intent.NO_INTENT): ASK,  # unreachable: only open conversation yields NO_INTENT
        # Cancellation confirmation: "Do you want me to cancel it?"
        (_C, Intent.AFFIRM): Action.CANCEL_APPOINTMENT,
        (_C, Intent.DENY): Action.KEEP_APPOINTMENT,
        (_C, Intent.REQUEST_CANCEL): ASK,  # only an explicit AFFIRM may cancel
        (_C, Intent.CONFIRM_ATTENDANCE): ASK,
        (_C, Intent.REQUEST_RESCHEDULE): ASK,
        (_C, Intent.UNCLEAR): ASK,
        (_C, Intent.NO_INTENT): ASK,
        # Reminder reply: "Reply 1 to confirm, 2 to reschedule, 3 to cancel."
        (_R, Intent.AFFIRM): Action.RECORD_ATTENDANCE_CONFIRMATION,
        (_R, Intent.DENY): ASK,
        (_R, Intent.REQUEST_CANCEL): Action.START_CANCELLATION_FLOW,  # never cancels directly
        (_R, Intent.CONFIRM_ATTENDANCE): Action.RECORD_ATTENDANCE_CONFIRMATION,
        (_R, Intent.REQUEST_RESCHEDULE): Action.START_RESCHEDULE_FLOW,
        (_R, Intent.UNCLEAR): ASK,
        (_R, Intent.NO_INTENT): ASK,
        # Open conversation: no pending question.
        (_O, Intent.AFFIRM): Action.NO_ACTION,
        (_O, Intent.DENY): Action.NO_ACTION,
        (_O, Intent.REQUEST_CANCEL): Action.START_CANCELLATION_FLOW,
        (_O, Intent.CONFIRM_ATTENDANCE): Action.NO_ACTION,
        (_O, Intent.REQUEST_RESCHEDULE): Action.START_RESCHEDULE_FLOW,
        (_O, Intent.UNCLEAR): ASK,
        (_O, Intent.NO_INTENT): Action.NO_ACTION,
    }
)

_STRONG_REASONS = frozenset({Reason.EXPLICIT, Reason.MENU_OPTION})


def decide(interpretation: Interpretation, context: Context) -> Decision:
    """Return the action permitted for `interpretation` in `context`. Pure."""
    if not isinstance(interpretation, Interpretation):
        raise TypeError("interpretation must be an Interpretation")
    if not isinstance(context, Context):
        raise TypeError(f"context must be a Context, got {type(context).__name__}")

    action = POLICY_TABLE[(context, interpretation.intent)]
    reason = interpretation.reason

    if action in STATE_CHANGING_ACTIONS and reason not in _STRONG_REASONS:
        action = ASK
    if action in DESTRUCTIVE_ACTIONS and not (
        context is Context.CANCELLATION_CONFIRMATION
        and interpretation.intent is Intent.AFFIRM
        and reason is Reason.EXPLICIT
    ):
        action = ASK
    return Decision(action, reason)
