# hitl_fail_closed

**Human-in-the-loop control for an automated assistant: fail-closed state reads, human-only reactivation, per-conversation locking, and a recheck immediately before every send.**

When a human operator takes over a conversation, the automation must stop, including any reply it is already preparing. That sounds simple until a mute arrives while a reply is being generated, two messages from the same customer are processed at once, the state store fails, or an old approval tries to reactivate a conversation that was muted again. This example handles each of those cases explicitly and tests them under concurrency.

> Independently written to illustrate the concept; this is **not** the production code of NEXMAGNI Flow. Storage and transport are simulated, no real messages are sent, and all identifiers are fictional.

---

## Quick start

Requirements: Python 3.10+ and pytest 7+. The package uses a `src/` layout and does **not** need to be installed.

**bash**

```bash
cd examples/hitl_fail_closed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest                                       # pyproject.toml adds src/ to the path
PYTHONPATH=src python -m hitl_fail_closed    # scripted race demo
```

**PowerShell**

```powershell
cd examples\hitl_fail_closed
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest
$env:PYTHONPATH = "src"
python -m hitl_fail_closed
```

Demo output:

```text
1. operator mutes during generation   -> CHANGED
   pending automated reply            -> BLOCKED_AT_SEND, messages sent: 0
2. reactivate with a stale approval   -> REJECTED_STALE
3. mute while the store rejects writes -> STORE_FAILURE (state still ACTIVE)
4. store unreadable                   -> BLOCKED_UNKNOWN
5. reactivate with a valid approval   -> CHANGED
   next automated reply               -> SENT
audit conv-001: v1 ACTIVE->MUTED by HUMAN_OPERATOR, v2 MUTED->ACTIVE by HUMAN_OPERATOR
```

## States

| State | Stored? | Automation may reply? | How it arises |
|---|---|---|---|
| `ACTIVE` | Yes, or no record | Yes, if confirmed again right before sending | Default for a conversation the store confirms it has never seen; or a human reactivation |
| `MUTED` | Yes | No | `mute()` by automation (handoff) or by an operator |
| `UNKNOWN` | **Never** | No | Store read raised, record has the wrong type, an invalid state, or an invalid version |

`read_state()` never raises. Anything it cannot trust becomes `UNKNOWN`, and `UNKNOWN` blocks.

## Contracts

```python
def read_state(store, conversation_id) -> StateReading            # (state, version | None)
def mute(store, locks, conversation_id, actor: Actor) -> ChangeResult
def reactivate(store, locks, conversation_id, approval: HumanApproval) -> ChangeResult
def handle_message(conversation_id, text, *, store, locks, generate, transport) -> Outcome
```

| Type | Values |
|---|---|
| `Actor` | `AUTOMATION`, `HUMAN_OPERATOR` |
| `ChangeResult` | `CHANGED`, `UNCHANGED`, `REJECTED_INVALID`, `REJECTED_MISMATCH`, `REJECTED_STALE`, `LOCK_TIMEOUT`, `STORE_FAILURE` |
| `Outcome` | `SENT`, `BLOCKED_MUTED`, `BLOCKED_UNKNOWN`, `BLOCKED_AT_SEND`, `LOCK_TIMEOUT`, `GENERATION_FAILED`, `SEND_FAILED` |

The store is a small protocol (`get`, `compare_and_set`, `history`) with a thread-safe, versioned in-memory implementation and a `FaultyStore` wrapper for fault injection. Results contain only enums and versions, never message text.

## Muting

- Anyone may request a mute. It is idempotent.
- **Check the result.** Only `CHANGED` or `UNCHANGED` confirm that the conversation is muted.
- **A failed mute is not a block.** `STORE_FAILURE` or `LOCK_TIMEOUT` means the write did not happen. Nothing guarantees that later reads will return `UNKNOWN`: the store may still report `ACTIVE`, and automation will keep replying. The caller must retry or escalate; the tests demonstrate this case explicitly instead of hiding it.

## Reactivation

Only `reactivate()` can write `ACTIVE`, and it requires a `HumanApproval`:

```python
HumanApproval(operator_id="operator-a", conversation_id="conv-001", expected_version=3)
```

| Check | Failure result |
|---|---|
| Non-empty `operator_id`, `str` conversation, non-negative `int` version | `REJECTED_INVALID` |
| Approval belongs to this conversation | `REJECTED_MISMATCH` |
| `expected_version` equals the current version (no newer mute since the approval) | `REJECTED_STALE` |
| Current state is readable | `STORE_FAILURE` |

Defense in depth: the store itself refuses to write `ACTIVE` on behalf of `Actor.AUTOMATION`, so automation has no code path to reactivate a conversation.

> **`HumanApproval` simulates a trusted human authorization. This example performs no authentication.** Whoever constructs the object is trusted to be an operator. A real system must create it only after authenticating and authorizing the operator (for example, behind a protected administrative endpoint) and should record who approved what.

## Concurrency and TOCTOU

A time-of-check-to-time-of-use (TOCTOU) bug would let a reply go out after a mute because the state was checked *before* a slow generation step. Each conversation has two locks:

| Lock | Held by | Duration |
|---|---|---|
| **processing** | `handle_message` | The whole handling, including slow reply generation |
| **control** | `mute`, `reactivate`, and the final *recheck + send* | Short |

```text
handle_message
  acquire processing lock (timeout → LOCK_TIMEOUT)
  read_state: MUTED → BLOCKED_MUTED, UNKNOWN → BLOCKED_UNKNOWN
  generate reply            ← control lock NOT held: an operator can mute right now
  acquire control lock (timeout → LOCK_TIMEOUT)
      read_state again: UNKNOWN → BLOCKED_UNKNOWN, not ACTIVE → BLOCKED_AT_SEND
      transport.send        ← no state change can interleave between recheck and send
  release both locks (always, also after exceptions)
```

- A mute during generation is seen by the recheck, so the pending reply is dropped (`BLOCKED_AT_SEND`).
- A mute that arrives during a send waits for the control lock and takes effect immediately after it. A reply that was authorized before the mute is the only one that can still go out.
- Lock order is always processing → control, and state changes take only the control lock, so there is no lock-order inversion and no deadlock.
- Messages for the same conversation are serialized; different conversations run in parallel.

**Trade-off:** the send happens while holding the control lock. With a slow real transport, an operator's mute waits for that one send to finish. The alternative (sending outside the lock) reopens the TOCTOU window.

In a multi-process deployment these in-memory locks would be replaced by a shared mechanism, such as a database or distributed lock, with the same ordering rules.

## Tests

| File | Focus |
|---|---|
| `test_state.py` | Confirmed absence, corrupted records, store-level guards |
| `test_transitions.py` | Muting, idempotency, failed writes, lock timeout, version history |
| `test_reactivation.py` | Valid, stale, mismatched, and malformed approvals |
| `test_dispatcher.py` | Each `Outcome`, including the failed-mute case |
| `test_locks.py` | Lock identity, timeouts, release after failures |
| `test_races.py` | Six orchestrated race scenarios, each repeated 20 times |
| `test_stress.py` | 8 threads × 200 random operations, three fixed seeds |
| `test_cli.py` | Demo command |

Race scenarios are orchestrated with `threading.Event` and `threading.Barrier`, not with sleeps, and every wait is bounded, so a broken test fails instead of hanging.

Invariants:

1. No message is sent unless the state was read as `ACTIVE` under the control lock immediately before sending (the fake transport records the stored state at the instant of each send).
2. `UNKNOWN`, store failures, and lock timeouts never result in a send.
3. `MUTED` → `ACTIVE` happens only with a valid `HumanApproval` for the same conversation and the current version.
4. Automation never produces a transition to `ACTIVE`.
5. A mute completes without waiting for an in-progress reply generation.
6. At most one message per conversation is processed at a time.
7. Locks are always released, including after exceptions.
8. The audit history is append-only and versions increase by exactly one.
9. No message text appears in results or in the audit history.

## Limitations

- In-memory, single-process locks and store. Locks are kept for the lifetime of `ConversationLocks` (no eviction).
- No authentication: see the `HumanApproval` note above.
- A failed mute does not retry automatically; that policy belongs to the caller.
- `LOCK_TIMEOUT` drops the message rather than queueing it; a real system would decide whether to retry, queue, or escalate.
- Conversations with no record are treated as `ACTIVE` only because the in-memory store can confirm absence. A store that cannot distinguish "absent" from "failed" should report a failure instead, which this design maps to `UNKNOWN`.

## Project layout

```text
hitl_fail_closed/
├── README.md
├── pyproject.toml          # pytest configuration only (pythonpath = ["src"])
├── requirements-dev.txt    # pytest>=7.0
├── src/hitl_fail_closed/
│   ├── __init__.py         # public API
│   ├── __main__.py         # scripted race demo
│   ├── models.py           # states, actors, outcomes, records, HumanApproval
│   ├── store.py            # ControlStore protocol, in-memory store, FaultyStore
│   ├── control.py          # read_state(), mute(), reactivate()
│   ├── locks.py            # per-conversation locks
│   ├── dispatcher.py       # handle_message()
│   └── fakes.py            # RecordingTransport, GatedReplyGenerator
└── tests/
```

## License

Copyright © 2026 [NeusaM21](https://github.com/NeusaM21). **All rights reserved.**

This example is published for technical evaluation. Public access does not grant permission to reproduce, modify, or redistribute it.
