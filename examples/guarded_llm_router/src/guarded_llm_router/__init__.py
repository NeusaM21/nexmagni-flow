"""Guarded LLM routing: deterministic rules, a strictly validated model call
with bounded retries, and a safe fallback.

    >>> from guarded_llm_router import ScriptedClient, route
    >>> route("I was wondering about Saturday", client=ScriptedClient(["BOOKING"])).intent.name
    'BOOKING'
"""

from .fakes import FlakyClient, KeywordClient, ScriptedClient
from .models import MAX_ATTEMPTS_LIMIT, Failure, Intent, RouteResult, RouterConfig, Source
from .prompt import build_prompt, sanitize_message
from .router import LLMClient, route
from .validation import parse_label

__all__ = [
    "MAX_ATTEMPTS_LIMIT",
    "Failure",
    "FlakyClient",
    "Intent",
    "KeywordClient",
    "LLMClient",
    "RouteResult",
    "RouterConfig",
    "ScriptedClient",
    "Source",
    "build_prompt",
    "parse_label",
    "route",
    "sanitize_message",
]
