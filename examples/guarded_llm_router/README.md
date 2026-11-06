# guarded_llm_router

**Intent routing that uses a language model without trusting it: deterministic rules first, strict output validation, bounded retries, and a safe fallback.**

A conversational assistant often uses an LLM to decide which part of the application should handle a message. Left unguarded, that call can fail, time out, return free text, be manipulated by prompt injection, or retry forever. This example shows a small router that keeps every one of those failure modes inside explicit limits.

> Independently written to illustrate the concept; this is **not** the production code of NEXMAGNI Flow. The model is simulated, and all messages are fictional. No API key, SDK, network access, or paid service is needed.

---

## Quick start

Requirements: Python 3.10+ and pytest 7+. The package uses a `src/` layout and does **not** need to be installed.

**bash**

```bash
cd examples/guarded_llm_router
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest                                          # pyproject.toml adds src/ to the path
PYTHONPATH=src python -m guarded_llm_router     # built-in demo with a fake model
PYTHONPATH=src python -m guarded_llm_router --fail 3 "is the 14th any good"
```

**PowerShell**

```powershell
cd examples\guarded_llm_router
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest
$env:PYTHONPATH = "src"
python -m guarded_llm_router
python -m guarded_llm_router --fail 3 "is the 14th any good"
```

Example output:

```text
'is the 14th any good'
    intent=SERVICE_INFO source=FALLBACK attempts=3 failures=(TIMEOUT, TIMEOUT, TIMEOUT) rule=-
```

## Usage

```python
from guarded_llm_router import RouterConfig, ScriptedClient, route

client = ScriptedClient([TimeoutError(), "Booking."])   # fake model: fails once, then answers
result = route("I was wondering about Saturday", client=client)

result.intent     # Intent.BOOKING
result.source     # Source.MODEL
result.attempts   # 2
result.failures   # (Failure.TIMEOUT,)
```

Any object with a `complete(prompt: str) -> str` method can be used as the client. A real provider adapter would implement the same one-method protocol; none is included here on purpose.

## Contracts

```python
class Intent(Enum):  BOOKING | SERVICE_INFO | HUMAN_HANDOFF | SMALL_TALK
class Source(Enum):  RULE | MODEL | FALLBACK
class Failure(Enum): EMPTY_INPUT | ERROR | TIMEOUT | INVALID_OUTPUT

class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...

@dataclass(frozen=True)
class RouterConfig:
    max_attempts: int = 3            # 1..5, enforced
    retry_delay_s: float = 0.5       # linear backoff: delay * attempt number
    fallback: Intent = Intent.SERVICE_INFO   # BOOKING is rejected
    max_input_chars: int = 500

@dataclass(frozen=True)
class RouteResult:
    intent: Intent
    source: Source
    attempts: int                    # model calls made; 0 when a rule decided
    failures: tuple[Failure, ...]    # enums only, never message text
    rule: str | None                 # name of the matching rule, if any
    degraded: bool                   # property: True when source is FALLBACK

def route(message: str | None, *, client: LLMClient, config: RouterConfig = RouterConfig(),
          in_booking_flow: bool = False, sleep: Callable[[float], None] = time.sleep) -> RouteResult
def parse_label(raw: object) -> Intent | None
```

`route()` never raises because of the model or the message content. It raises `TypeError` or `ValueError` only for programming errors (wrong argument types, invalid configuration). `KeyboardInterrupt` and other non-`Exception` signals are not swallowed.

## Decision order

| Step | Condition | Result | Model called? |
|---|---|---|---|
| 1 | `None`, empty, or only invisible characters | `fallback`, `FALLBACK`, `EMPTY_INPUT` | No |
| 2 | Asks for a person ("a person", "human", "speak to someone", "manager", "supervisor"...) | `HUMAN_HANDOFF`, `RULE` | No |
| 3 | `in_booking_flow=True` | `BOOKING`, `RULE` | No |
| 4 | The whole message is a greeting or thanks | `SMALL_TALK`, `RULE` | No |
| 5 | Mentions prices, services, hours, or location | `SERVICE_INFO`, `RULE` | No |
| 6 | Explicitly asks to book or reserve | `BOOKING`, `RULE` | No |
| 7 | No rule matched | Strictly validated model label, `MODEL` | Up to `max_attempts` |
| 8 | All attempts failed | `fallback`, `FALLBACK` | — |

Rules match whole words only ("bookshelf" is not "book"; "humanity" is not "human"). A request for a person always wins, even in the middle of a booking flow.

## Failure policy

| Event | Retried? | Recorded as |
|---|---|---|
| Client raises `TimeoutError` | Yes | `TIMEOUT` |
| Client raises any other `Exception` | Yes | `ERROR` |
| Client returns a non-string or an invalid label | Yes | `INVALID_OUTPUT` |
| `KeyboardInterrupt` / `SystemExit` | No, propagated | — |

- At most `max_attempts` calls (default 3, hard limit 5).
- Between attempt *n* and *n + 1* the router calls `sleep(retry_delay_s * n)`; it never sleeps after the last attempt. `sleep` is injectable, so tests run instantly.
- The fallback is configurable but can **never** be `BOOKING`: a failure must not start a transactional flow. The default is `SERVICE_INFO`, which only provides information.

## Strict output validation

`parse_label()` accepts exactly one label, in any letter case, with optional surrounding whitespace and at most one trailing period. Everything else is rejected, with no substring search:

| Model output | Result |
|---|---|
| `"BOOKING"`, `" booking\n"`, `"Booking."` | `Intent.BOOKING` |
| `"The answer is BOOKING"`, `"NOT_BOOKING"`, `"BOOKING SERVICE_INFO"` | rejected |
| `'{"intent": "BOOKING"}'`, `` "`BOOKING`" ``, `"BOOK​ING"`, `"Booking.."` | rejected |
| `None`, numbers, bytes, lists, anything longer than 32 characters | rejected |

## Prompt injection

The customer message is treated as data:

- Control and invisible formatting characters are removed, whitespace is collapsed, and the text is truncated to `max_input_chars`.
- `<` and `>` are replaced with look-alike characters, so the message can never close or reopen the `<customer_message>` tags around it.
- The prompt states that the tagged text is data, not instructions.

These measures reduce the risk; they do not eliminate it. The real guarantee is structural: whatever the model is persuaded to say, **the router can only return one of four labels**, and free text from the model never reaches the rest of the application.

## Routing is not authorization

A route only selects which part of the application handles the message. Reaching `BOOKING` does not book, cancel, or change anything. Operational actions must still pass explicit application rules, as shown in the companion example [`deterministic_intent`](../deterministic_intent/).

## Tests

| File | Focus |
|---|---|
| `test_rules.py` | Rule order, human-request priority, booking flow, whole-word matching |
| `test_validation.py` | Accepted and rejected model outputs |
| `test_prompt.py` | Four labels, single tag pair, sanitization, truncation |
| `test_retries.py` | Recovery, linear backoff, attempt limits, `KeyboardInterrupt` |
| `test_fallback.py` | Empty input, configurable fallback, `BOOKING` rejected, config validation |
| `test_injection.py` | Injection attempts combined with manipulated model outputs |
| `test_invariants.py` | The nine invariants over messages × fake model behaviors × configs |
| `test_cli.py` | Demo command |

Invariants:

1. The result is always one of the four intents.
2. The model is called at most `max_attempts` times.
3. A rule decision never calls the model.
4. A fallback returns the configured fallback, which is never `BOOKING`.
5. A model decision is always the validated parse of the last model output.
6. A request for a person always yields `HUMAN_HANDOFF`.
7. The result contains no message text: only enums, counters, and rule names.
8. The same message with the same scripted model always yields the same result.
9. `route()` never raises for `str` or `None` input, whatever the model does.

## Limitations

- English only, with small keyword lists. Rules can misfire, which is acceptable because they only route and never act.
- Human-request words win even when they are not a request ("Is the manager in on Saturday?" or "I don't need a human" also go to `HUMAN_HANDOFF`). This errs toward a person, never toward an automated transaction.
- When a message matches several rules, the first one in the table wins (for example, a price question that also says "book" goes to `SERVICE_INFO`).
- There is no total time budget: worst-case latency is `max_attempts` × the client's own timeout plus the backoff delays.
- Sanitization is not a complete prompt-injection defense; the four-label output contract is.
- The fake clients are deliberately simple; `KeywordClient` exists only for the demo.

## Project layout

```text
guarded_llm_router/
├── README.md
├── pyproject.toml          # pytest configuration only (pythonpath = ["src"])
├── requirements-dev.txt    # pytest>=7.0
├── src/guarded_llm_router/
│   ├── __init__.py         # public API
│   ├── __main__.py         # CLI demo
│   ├── models.py           # enums, RouterConfig, RouteResult
│   ├── rules.py            # deterministic pre-routing
│   ├── prompt.py           # prompt template and sanitization
│   ├── validation.py       # parse_label()
│   ├── router.py           # route()
│   └── fakes.py            # ScriptedClient, KeywordClient, FlakyClient
└── tests/
```

## License

Copyright © 2026 [NeusaM21](https://github.com/NeusaM21). **All rights reserved.**

This example is published for technical evaluation. Public access does not grant permission to reproduce, modify, or redistribute it.
