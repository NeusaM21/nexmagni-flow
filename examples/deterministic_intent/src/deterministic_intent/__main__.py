"""Command-line demo: python -m deterministic_intent [--context CTX] [MESSAGE]

Without MESSAGE, runs a short built-in demo with fictional messages.
"""

from __future__ import annotations

import argparse
from typing import Sequence

from .interpreter import interpret
from .models import Context
from .policy import decide

_CONTEXTS = {context.value: context for context in Context}

DEMO: tuple[tuple[Context, str], ...] = (
    (Context.BOOKING_CONFIRMATION, "Yes, go ahead"),
    (Context.BOOKING_CONFIRMATION, "No, go ahead"),
    (Context.CANCELLATION_CONFIRMATION, "Yes, please cancel it"),
    (Context.CANCELLATION_CONFIRMATION, "Don't cancel, I'll be there"),
    (Context.REMINDER_REPLY, "3"),
    (Context.REMINDER_REPLY, "I can't make it"),
    (Context.REMINDER_REPLY, "No need to reschedule"),
    (Context.OPEN_CONVERSATION, "I need to cancel my appointment"),
    (Context.OPEN_CONVERSATION, "If I need to cancel, is there a fee?"),
    (Context.OPEN_CONVERSATION, "I don't want to cancel"),
)


def describe(message: str | None, context: Context) -> str:
    interpretation = interpret(message, context)
    decision = decide(interpretation, context)
    evidence = ", ".join(interpretation.evidence) or "-"
    return (
        f"[{context.value}] {message!r}\n"
        f"    intent={interpretation.intent.name} reason={interpretation.reason.name} "
        f"evidence=({evidence})\n"
        f"    action={decision.action.name} changes_state={decision.changes_state} "
        f"destructive={decision.destructive}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m deterministic_intent",
        description="Interpret a customer message and show the permitted action.",
    )
    parser.add_argument("message", nargs="?", help="message to interpret (omit to run the demo)")
    parser.add_argument(
        "--context",
        choices=sorted(_CONTEXTS),
        default=Context.OPEN_CONVERSATION.value,
        help="what the conversation is waiting for (default: open)",
    )
    args = parser.parse_args(argv)

    if args.message is None:
        print("\n".join(describe(message, context) for context, message in DEMO))
    else:
        print(describe(args.message, _CONTEXTS[args.context]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
