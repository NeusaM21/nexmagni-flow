"""Fake reply generator and transport. No real messages, no network."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass

from .models import ControlState
from .store import InMemoryControlStore

WAIT_LIMIT_S = 5.0  # every wait is bounded so a broken test can never hang


@dataclass(frozen=True, slots=True)
class SentRecord:
    conversation_id: str
    state_at_send: ControlState  # read directly from the store at the moment of sending


class RecordingTransport:
    """Records each send together with the stored state observed at that instant."""

    def __init__(self, observe: InMemoryControlStore, *, fail: bool = False) -> None:
        self._observe = observe
        self.fail = fail
        self._lock = threading.Lock()
        self.sent: list[SentRecord] = []

    def send(self, conversation_id: str, text: str) -> None:
        if self.fail:
            raise ConnectionError("simulated transport failure")
        record = self._observe.get(conversation_id)
        state = record.state if record else ControlState.ACTIVE
        with self._lock:
            self.sent.append(SentRecord(conversation_id, state))


class GatedReplyGenerator:
    """Produces a fixed reply. When gated, waits for `release` before returning.

    `started` is set as soon as a call begins, so a test can act "during" generation.
    Tracks how many calls are in flight per conversation.
    """

    def __init__(self, reply: str = "Thanks! We will confirm shortly.", *, gated: bool = False,
                 fail: bool = False, barrier: threading.Barrier | None = None) -> None:
        self.reply = reply
        self.fail = fail
        self.barrier = barrier
        self.started = threading.Event()
        self.release = threading.Event()
        if not gated:
            self.release.set()
        self._lock = threading.Lock()
        self._in_flight: dict[str, int] = defaultdict(int)
        self.max_in_flight: dict[str, int] = defaultdict(int)

    def __call__(self, conversation_id: str, text: str) -> str:
        with self._lock:
            self._in_flight[conversation_id] += 1
            self.max_in_flight[conversation_id] = max(
                self.max_in_flight[conversation_id], self._in_flight[conversation_id]
            )
        try:
            self.started.set()
            if self.barrier is not None:
                self.barrier.wait(timeout=WAIT_LIMIT_S)
            if not self.release.wait(timeout=WAIT_LIMIT_S):
                raise TimeoutError("generator was never released")
            if self.fail:
                raise RuntimeError("simulated generation failure")
            return self.reply
        finally:
            with self._lock:
                self._in_flight[conversation_id] -= 1
