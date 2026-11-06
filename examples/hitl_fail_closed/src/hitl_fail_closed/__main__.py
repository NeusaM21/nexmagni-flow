"""Scripted demo of the race this example protects against:

    python -m hitl_fail_closed

All conversations, operators, and messages are fictional.
"""

from __future__ import annotations

import argparse
import threading
from typing import Sequence

from .control import mute, reactivate, read_state
from .dispatcher import handle_message
from .fakes import WAIT_LIMIT_S, GatedReplyGenerator, RecordingTransport
from .locks import ConversationLocks
from .models import Actor, HumanApproval
from .store import FaultyStore, InMemoryControlStore

CONVERSATION = "conv-001"


def run_demo() -> list[str]:
    lines: list[str] = []
    store = InMemoryControlStore()
    locks = ConversationLocks()
    transport = RecordingTransport(store)

    # 1. A reply is being generated when the operator takes over.
    generator = GatedReplyGenerator(gated=True)
    outcome: list[object] = []
    worker = threading.Thread(
        target=lambda: outcome.append(
            handle_message(CONVERSATION, "Is Friday free?", store=store, locks=locks,
                           generate=generator, transport=transport)
        ),
        daemon=True,
    )
    worker.start()
    generator.started.wait(WAIT_LIMIT_S)
    lines.append(f"1. operator mutes during generation   -> {mute(store, locks, CONVERSATION, Actor.HUMAN_OPERATOR).name}")
    generator.release.set()
    worker.join(WAIT_LIMIT_S)
    lines.append(f"   pending automated reply            -> {outcome[0].name}, messages sent: {len(transport.sent)}")

    # 2. An approval prepared earlier is stale after a newer mute.
    muted_version = read_state(store, CONVERSATION).version
    stale = HumanApproval("operator-a", CONVERSATION, (muted_version or 0) - 1)
    lines.append(f"2. reactivate with a stale approval   -> {reactivate(store, locks, CONVERSATION, stale).name}")

    # 3. A failed mute is not a block.
    faulty = FaultyStore(store)
    faulty.fail_writes = True
    other = "conv-002"
    lines.append(f"3. mute while the store rejects writes -> {mute(faulty, locks, other, Actor.AUTOMATION).name}"
                 f" (state still {read_state(faulty, other).state.name})")

    # 4. Unknown state blocks.
    faulty.fail_writes = False
    faulty.fail_get = True
    result = handle_message(other, "Hello?", store=faulty, locks=locks,
                            generate=GatedReplyGenerator(), transport=transport)
    lines.append(f"4. store unreadable                   -> {result.name}")
    faulty.fail_get = False

    # 5. Valid human approval reactivates; automation replies again.
    current = read_state(store, CONVERSATION)
    approval = HumanApproval("operator-a", CONVERSATION, current.version or 0)
    lines.append(f"5. reactivate with a valid approval   -> {reactivate(store, locks, CONVERSATION, approval).name}")
    result = handle_message(CONVERSATION, "Thanks!", store=store, locks=locks,
                            generate=GatedReplyGenerator(), transport=transport)
    lines.append(f"   next automated reply               -> {result.name}")

    history = ", ".join(
        f"v{t.version} {t.old_state.name}->{t.new_state.name} by {t.actor.name}"
        for t in store.history(CONVERSATION)
    )
    lines.append(f"audit {CONVERSATION}: {history}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hitl_fail_closed",
        description="Run a scripted human-in-the-loop race demo with fake components.",
    )
    parser.parse_args(argv)
    print("\n".join(run_demo()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
