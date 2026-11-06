"""Deterministic intent interpretation with a separate authorization policy.

    >>> from deterministic_intent import Context, interpret, decide
    >>> result = interpret("I can't make it", Context.REMINDER_REPLY)
    >>> decide(result, Context.REMINDER_REPLY).action.name
    'START_CANCELLATION_FLOW'
"""

from .interpreter import interpret
from .models import Action, Context, Decision, Intent, Interpretation, Reason
from .policy import POLICY_TABLE, decide

__all__ = [
    "Action",
    "Context",
    "Decision",
    "Intent",
    "Interpretation",
    "POLICY_TABLE",
    "Reason",
    "decide",
    "interpret",
]
