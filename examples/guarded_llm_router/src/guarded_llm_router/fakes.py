"""Fake model clients for tests and the demo. No network, no SDK, no cost."""

from __future__ import annotations

from collections import deque
from typing import Iterable

from .rules import tokenize


class ScriptedClient:
    """Returns (or raises) the scripted items in order and records every prompt."""

    def __init__(self, script: Iterable[object]) -> None:
        self._script = deque(script)
        self.prompts: list[str] = []

    @property
    def calls(self) -> int:
        return len(self.prompts)

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._script:
            raise RuntimeError("script exhausted")
        item = self._script.popleft()
        if isinstance(item, BaseException):
            raise item
        return item  # type: ignore[return-value]  # deliberately unchecked


class KeywordClient:
    """A toy stand-in for a model, used by the demo: looks only at the customer text."""

    _BOOKING_HINTS = frozenset({"appointment", "availability", "available", "slot", "tomorrow", "saturday"})

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        customer_text = prompt.rsplit("<customer_message>", 1)[-1]
        if self._BOOKING_HINTS.intersection(tokenize(customer_text)):
            return "BOOKING"
        return "SMALL_TALK"


class FlakyClient:
    """Raises TimeoutError for the first `failures` calls, then delegates."""

    def __init__(self, inner: object, failures: int) -> None:
        self._inner = inner
        self._remaining = failures
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if self._remaining > 0:
            self._remaining -= 1
            raise TimeoutError("simulated timeout")
        return self._inner.complete(prompt)  # type: ignore[attr-defined]
