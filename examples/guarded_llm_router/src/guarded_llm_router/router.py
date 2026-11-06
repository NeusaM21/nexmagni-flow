"""route(): deterministic rules first, then a bounded number of model calls,
then a safe fallback.

Routing only selects which part of the application handles the message.
It never authorizes an operational action.
"""

from __future__ import annotations

import time
from typing import Callable, Protocol, runtime_checkable

from .models import Failure, RouteResult, RouterConfig, Source
from .prompt import build_prompt, sanitize_message
from .rules import match_rule
from .validation import parse_label

DEFAULT_CONFIG = RouterConfig()


@runtime_checkable
class LLMClient(Protocol):
    """Anything with `complete(prompt) -> str`. It may raise or return garbage."""

    def complete(self, prompt: str) -> str: ...


def route(
    message: str | None,
    *,
    client: LLMClient,
    config: RouterConfig = DEFAULT_CONFIG,
    in_booking_flow: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> RouteResult:
    """Route `message` to one of four intents. Never raises because of the model."""
    if message is not None and not isinstance(message, str):
        raise TypeError(f"message must be str or None, got {type(message).__name__}")
    if not isinstance(client, LLMClient):
        raise TypeError("client must provide complete(prompt) -> str")
    if not isinstance(config, RouterConfig):
        raise TypeError("config must be a RouterConfig")
    if not isinstance(in_booking_flow, bool):
        raise TypeError("in_booking_flow must be a bool")
    if not callable(sleep):
        raise TypeError("sleep must be callable")

    if not message or not sanitize_message(message, config.max_input_chars):
        return RouteResult(config.fallback, Source.FALLBACK, 0, (Failure.EMPTY_INPUT,))

    rule = match_rule(message, in_booking_flow)
    if rule is not None:
        return RouteResult(rule.intent, Source.RULE, 0, (), rule.name)

    prompt = build_prompt(message, config.max_input_chars)
    failures: list[Failure] = []
    for attempt in range(1, config.max_attempts + 1):
        try:
            raw = client.complete(prompt)
        except TimeoutError:
            failures.append(Failure.TIMEOUT)
        except Exception:  # any provider error is contained; BaseException propagates
            failures.append(Failure.ERROR)
        else:
            intent = parse_label(raw)
            if intent is not None:
                return RouteResult(intent, Source.MODEL, attempt, tuple(failures))
            failures.append(Failure.INVALID_OUTPUT)
        if attempt < config.max_attempts:
            sleep(config.retry_delay_s * attempt)

    return RouteResult(config.fallback, Source.FALLBACK, config.max_attempts, tuple(failures))
