"""Per-conversation locks.

Each conversation has two locks:

- processing: serializes message handling (held for the whole, possibly slow, reply);
- control: short; guards state writes and the final "recheck + send" step.

Lock order is always processing -> control. State changes take only the
control lock, so they never wait for a slow reply to be generated, and no
code path takes the two locks in the opposite order (no deadlock).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class ConversationLocks:
    """Creates locks on demand. Locks are kept for the lifetime of the object."""

    def __init__(self, timeout_s: float = 2.0) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self.timeout_s = timeout_s
        self._guard = threading.Lock()
        self._processing: dict[str, threading.Lock] = {}
        self._control: dict[str, threading.Lock] = {}

    def processing(self, conversation_id: str) -> threading.Lock:
        with self._guard:
            return self._processing.setdefault(conversation_id, threading.Lock())

    def control(self, conversation_id: str) -> threading.Lock:
        with self._guard:
            return self._control.setdefault(conversation_id, threading.Lock())


@contextmanager
def hold(lock: threading.Lock, timeout_s: float) -> Iterator[bool]:
    """Try to acquire `lock`; yield whether it was acquired; always release if it was."""
    acquired = lock.acquire(timeout=timeout_s)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()
