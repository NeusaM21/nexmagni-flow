"""Control-state storage: protocol, in-memory implementation, and fault injection."""

from __future__ import annotations

import threading
from typing import Protocol

from .models import STORABLE_STATES, Actor, ControlRecord, ControlState, Transition


class ControlStore(Protocol):
    def get(self, conversation_id: str) -> ControlRecord | None:
        """Return the record, or None when the store confirms there is none. May raise."""

    def compare_and_set(
        self, conversation_id: str, expected_version: int, new_state: ControlState, actor: Actor
    ) -> bool:
        """Write only if the current version equals `expected_version`. May raise."""

    def history(self, conversation_id: str) -> tuple[Transition, ...]:
        """Append-only audit trail of state changes."""


class InMemoryControlStore:
    """Thread-safe, versioned store. A missing record has version 0 (state ACTIVE)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, ControlRecord] = {}
        self._history: dict[str, list[Transition]] = {}

    def get(self, conversation_id: str) -> ControlRecord | None:
        with self._lock:
            return self._records.get(conversation_id)

    def compare_and_set(
        self, conversation_id: str, expected_version: int, new_state: ControlState, actor: Actor
    ) -> bool:
        if new_state not in STORABLE_STATES:
            raise ValueError(f"cannot store {new_state}")
        if new_state is ControlState.ACTIVE and actor is not Actor.HUMAN_OPERATOR:
            raise PermissionError("only a human operator can set ACTIVE")
        with self._lock:
            current = self._records.get(conversation_id)
            current_version = current.version if current else 0
            if current_version != expected_version:
                return False
            old_state = current.state if current else ControlState.ACTIVE
            record = ControlRecord(new_state, current_version + 1)
            self._records[conversation_id] = record
            self._history.setdefault(conversation_id, []).append(
                Transition(conversation_id, actor, old_state, new_state, record.version)
            )
            return True

    def history(self, conversation_id: str) -> tuple[Transition, ...]:
        with self._lock:
            return tuple(self._history.get(conversation_id, ()))


_NO_OVERRIDE = object()


class FaultyStore:
    """Wraps a store and injects failures. Flags can be flipped while threads run.

    - fail_get: `get` raises ConnectionError.
    - fail_writes: `compare_and_set` raises ConnectionError and writes nothing.
    - get_override: `get` returns this value instead (to simulate corrupted records).
    """

    def __init__(self, inner: InMemoryControlStore) -> None:
        self.inner = inner
        self.fail_get = False
        self.fail_writes = False
        self.get_override: object = _NO_OVERRIDE

    def get(self, conversation_id: str) -> ControlRecord | None:
        if self.fail_get:
            raise ConnectionError("simulated read failure")
        if self.get_override is not _NO_OVERRIDE:
            return self.get_override  # type: ignore[return-value]
        return self.inner.get(conversation_id)

    def compare_and_set(
        self, conversation_id: str, expected_version: int, new_state: ControlState, actor: Actor
    ) -> bool:
        if self.fail_writes:
            raise ConnectionError("simulated write failure")
        return self.inner.compare_and_set(conversation_id, expected_version, new_state, actor)

    def history(self, conversation_id: str) -> tuple[Transition, ...]:
        return self.inner.history(conversation_id)

    def clear_override(self) -> None:
        self.get_override = _NO_OVERRIDE
