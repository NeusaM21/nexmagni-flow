"""Fail-closed human-in-the-loop control with per-conversation locking.

Automation may reply only while the conversation is confirmed ACTIVE, checked
again immediately before sending. Anything uncertain blocks. Only an explicit
human approval, bound to the conversation and its current version, reactivates.
"""

from .control import mute, reactivate, read_state
from .dispatcher import Transport, handle_message
from .fakes import GatedReplyGenerator, RecordingTransport, SentRecord
from .locks import ConversationLocks
from .models import (
    Actor,
    ChangeResult,
    ControlRecord,
    ControlState,
    HumanApproval,
    Outcome,
    StateReading,
    Transition,
)
from .store import ControlStore, FaultyStore, InMemoryControlStore

__all__ = [
    "Actor",
    "ChangeResult",
    "ControlRecord",
    "ControlState",
    "ControlStore",
    "ConversationLocks",
    "FaultyStore",
    "GatedReplyGenerator",
    "HumanApproval",
    "InMemoryControlStore",
    "Outcome",
    "RecordingTransport",
    "SentRecord",
    "StateReading",
    "Transition",
    "Transport",
    "handle_message",
    "mute",
    "reactivate",
    "read_state",
]
