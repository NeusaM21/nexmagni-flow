"""Value types for the router."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

MAX_ATTEMPTS_LIMIT = 5


class Intent(Enum):
    """The only four routes the router can ever return."""

    BOOKING = "booking"
    SERVICE_INFO = "service_info"
    HUMAN_HANDOFF = "human_handoff"
    SMALL_TALK = "small_talk"


class Source(Enum):
    """Who decided the route."""

    RULE = "rule"
    MODEL = "model"
    FALLBACK = "fallback"


class Failure(Enum):
    """Why an attempt (or the whole request) did not produce a valid route."""

    EMPTY_INPUT = "empty_input"
    ERROR = "error"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True, slots=True)
class RouterConfig:
    """Router limits. Invalid values are rejected at construction time."""

    max_attempts: int = 3
    retry_delay_s: float = 0.5
    fallback: Intent = Intent.SERVICE_INFO
    max_input_chars: int = 500

    def __post_init__(self) -> None:
        if not isinstance(self.max_attempts, int) or isinstance(self.max_attempts, bool):
            raise TypeError("max_attempts must be an int")
        if not 1 <= self.max_attempts <= MAX_ATTEMPTS_LIMIT:
            raise ValueError(f"max_attempts must be between 1 and {MAX_ATTEMPTS_LIMIT}")
        if not isinstance(self.retry_delay_s, (int, float)) or isinstance(self.retry_delay_s, bool):
            raise TypeError("retry_delay_s must be a number")
        if not math.isfinite(self.retry_delay_s) or self.retry_delay_s < 0:
            raise ValueError("retry_delay_s must be a finite number >= 0")
        if not isinstance(self.fallback, Intent):
            raise TypeError("fallback must be an Intent")
        if self.fallback is Intent.BOOKING:
            raise ValueError("fallback must not be BOOKING: a failure must not start a transaction")
        if not isinstance(self.max_input_chars, int) or isinstance(self.max_input_chars, bool):
            raise TypeError("max_input_chars must be an int")
        if not 1 <= self.max_input_chars <= 10_000:
            raise ValueError("max_input_chars must be between 1 and 10000")


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Outcome of `route()`. Contains no message text, only enums and counters."""

    intent: Intent
    source: Source
    attempts: int
    failures: tuple[Failure, ...] = ()
    rule: str | None = None

    @property
    def degraded(self) -> bool:
        return self.source is Source.FALLBACK
