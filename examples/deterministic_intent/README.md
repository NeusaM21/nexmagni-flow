# deterministic_intent

**Deterministic interpretation of short customer replies, with a separate authorization policy.**

A scheduling assistant constantly receives short replies such as "yes", "cancel", "I can't make it", or "no, go ahead". Acting on them with keyword matching or an unconstrained language model is risky: "I don't want to cancel" contains "cancel", "yesterday" starts with "yes", and "no, go ahead" contains both answers.

This example shows one way to handle these replies with explicit, testable rules:

1. **`interpret()`** describes what a message most likely means in its conversational context.
2. **`decide()`** determines what the application is *allowed* to do with that interpretation.

Understanding a message and authorizing an action are deliberately separate steps.

> Independently written to illustrate the concept; this is **not** the production algorithm of NEXMAGNI Flow. All messages are fictional.

---

## Quick start

Requirements: Python 3.10+ and pytest 7+. The package uses a `src/` layout and does **not** need to be installed.

**bash**

```bash
cd examples/deterministic_intent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

pytest                                     # pyproject.toml adds src/ to the path
PYTHONPATH=src python -m deterministic_intent                      # built-in demo
PYTHONPATH=src python -m deterministic_intent --context reminder "I can't make it"
```

**PowerShell**

```powershell
cd examples\deterministic_intent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest
$env:PYTHONPATH = "src"
python -m deterministic_intent
python -m deterministic_intent --context reminder "I can't make it"
```

Example output:

```text
[reminder] "I can't make it"
    intent=REQUEST_CANCEL reason=EXPLICIT evidence=(can not make it)
    action=START_CANCELLATION_FLOW changes_state=False destructive=False
```

## Usage

```python
from deterministic_intent import Context, interpret, decide

result = interpret("Don't cancel, I'll be there", Context.CANCELLATION_CONFIRMATION)
# Interpretation(intent=DENY, reason=EXPLICIT, evidence=('cancel [negated]', 'i will be there'))

decision = decide(result, Context.CANCELLATION_CONFIRMATION)
# Decision(action=KEEP_APPOINTMENT, ...)  decision.destructive -> False
```

## Contracts

```python
def interpret(message: str | None, context: Context) -> Interpretation
def decide(interpretation: Interpretation, context: Context) -> Decision
```

| Type | Values |
|---|---|
| `Context` | `BOOKING_CONFIRMATION`, `CANCELLATION_CONFIRMATION`, `REMINDER_REPLY`, `OPEN_CONVERSATION` |
| `Intent` | `AFFIRM`, `DENY`, `REQUEST_CANCEL`, `CONFIRM_ATTENDANCE`, `REQUEST_RESCHEDULE`, `UNCLEAR`, `NO_INTENT` |
| `Reason` | `EXPLICIT`, `MENU_OPTION`, `NEGATED`, `HYPOTHETICAL`, `POLICY_QUESTION`, `CONFLICTING`, `NO_SIGNAL`, `EMPTY` |
| `Action` | `CONFIRM_BOOKING`, `CANCEL_APPOINTMENT`, `KEEP_APPOINTMENT`, `RECORD_ATTENDANCE_CONFIRMATION`, `START_CANCELLATION_FLOW`, `START_RESCHEDULE_FLOW`, `ASK_CLARIFICATION`, `NO_ACTION` |

- Both functions are **pure and deterministic**: no I/O, no global mutable state, no network.
- `Interpretation` and `Decision` are frozen dataclasses. `Decision.changes_state` and `Decision.destructive` are derived from the action, so they cannot disagree with it.
- `None`, empty, whitespace-only, and emoji-only messages return `Interpretation(UNCLEAR, EMPTY)` without raising.
- Passing a non-`str` message or a non-`Context` value raises `TypeError` (a programming error, not a customer error).

## How interpretation works

```text
message → fold (case, accents, apostrophes) → split into clauses → expand contractions
        → match cue phrases (whole tokens, longest first) → apply modifiers → resolve per context
```

- **Clauses** are split on punctuation and on "but / however / though". Negation and hypothetical markers only affect cues *later in the same clause*, so in "no, go ahead" the "no" cannot negate "go ahead"; the two answers conflict instead.
- **Cue phrases** live in [`lexicon.py`](src/deterministic_intent/lexicon.py) as plain data. Matching uses whole tokens, so "yesterday" never matches "yes" and "okra" never matches "ok".
- **Modifiers**:
  - *Negation* ("not", "never", "no need to"): "I don't want to cancel" is not a cancellation request. Two negators ("I don't not want to cancel") are treated as conflicting.
  - *Hypothetical* ("if", "in case", "what if", "should I", "whether"): "If I need to cancel, what happens?" is a question, not a request.
  - *Policy question* ("policy", "fee", "how far in advance"...): "What is your cancellation policy?" does not open a cancellation.
  - *Stray negation*: a "not" in a clause with no other cue ("sure, I guess not") makes a non-refusal answer doubtful.
- **Context changes meaning**: "cancel" means *no* when confirming a booking, *yes* when confirming a cancellation, and *a request* in a reminder reply or open conversation.
- **Resolution**: exactly one intent with no doubtful modifier → `EXPLICIT`. More than one intent, or a clear intent next to a negated/hypothetical cue → `UNCLEAR / CONFLICTING`. Otherwise the strongest modifier explains why nothing was understood.
- **Reminder menu**: `1` / `2` / `3` (also `option 3`, `#2`) count only when they are the entire message. "I'll be there at 3" is an attendance confirmation, not option 3.

## Authorization policy

The policy is a complete, read-only table: every one of the **28** `(Context, Intent)` combinations maps to exactly one action.

| Intent \ Context | Booking confirmation | Cancellation confirmation | Reminder reply | Open conversation |
|---|---|---|---|---|
| `AFFIRM` | **CONFIRM_BOOKING** | **CANCEL_APPOINTMENT** ⚠️ | RECORD_ATTENDANCE_CONFIRMATION | NO_ACTION |
| `DENY` | NO_ACTION | KEEP_APPOINTMENT | ASK_CLARIFICATION | NO_ACTION |
| `REQUEST_CANCEL` | NO_ACTION¹ | **CANCEL_APPOINTMENT**¹ ⚠️ | START_CANCELLATION_FLOW | START_CANCELLATION_FLOW |
| `CONFIRM_ATTENDANCE` | ASK_CLARIFICATION | ASK_CLARIFICATION | RECORD_ATTENDANCE_CONFIRMATION | NO_ACTION |
| `REQUEST_RESCHEDULE` | ASK_CLARIFICATION | ASK_CLARIFICATION | START_RESCHEDULE_FLOW | START_RESCHEDULE_FLOW |
| `UNCLEAR` | ASK_CLARIFICATION | ASK_CLARIFICATION | ASK_CLARIFICATION | ASK_CLARIFICATION |
| `NO_INTENT` | ASK_CLARIFICATION¹ | ASK_CLARIFICATION | ASK_CLARIFICATION | NO_ACTION |

¹ Not produced by `interpret()` in that context (for example, "cancel" reads as `DENY` while confirming a booking). The cells exist so the table stays total for any `Interpretation` a caller constructs.

Two guards run after the table lookup:

1. A **state-changing** action requires reason `EXPLICIT` or `MENU_OPTION`; otherwise it becomes `ASK_CLARIFICATION`.
2. The only **destructive** action, `CANCEL_APPOINTMENT`, additionally requires context `CANCELLATION_CONFIRMATION` and reason `EXPLICIT`.

Consequences:

- A reminder reply **never cancels directly**: "3", "cancel", and "I can't make it" start the cancellation flow, which must then ask for explicit confirmation.
- `UNCLEAR` always becomes `ASK_CLARIFICATION`. The cost of uncertainty is one extra question, never an unintended action.

## Tests

The test suite contains over 500 parametrized cases:

| File | Focus |
|---|---|
| `test_normalize.py` | Accents, apostrophes, contractions, clause splitting |
| `test_yes_no.py` | Yes/no answers, look-alike words, conflicts, negated "yes" |
| `test_cancellation.py` | Cancellation confirmation and open-conversation requests |
| `test_reminder.py` | Menu options, written replies, "I can't make it", no direct cancellation |
| `test_negation_hypothetical.py` | Negation, hypothetical wording, policy questions |
| `test_ambiguity.py` | `None`, empty and emoji input, very long input, type errors |
| `test_policy.py` | All 28 table cells; guards checked for every `Context × Intent × Reason` |
| `test_invariants.py` | Safety properties over a fictional corpus in every context; determinism |
| `test_cli.py` | Demo command |

Invariants checked across the corpus:

1. A destructive action happens only in `CANCELLATION_CONFIRMATION`, with intent `AFFIRM` and reason `EXPLICIT`.
2. Any state change requires reason `EXPLICIT` or `MENU_OPTION`.
3. `UNCLEAR` always results in `ASK_CLARIFICATION`.
4. Negated, hypothetical, policy, conflicting, empty, or no-signal input never changes state.
5. Reminder replies never produce `CANCEL_APPOINTMENT`.
6. The same input always produces the same output.

## Limitations

This is a teaching-sized rule set, not a general language model:

- English only, with a deliberately small vocabulary. Unknown phrasing falls back to `ASK_CLARIFICATION` or `NO_ACTION`.
- No sarcasm, spelling correction, or semantic similarity.
- "when" is not treated as a hypothetical marker, because "when can you cancel it?" is usually a real request.
- Words outside the vocabulary are ignored, so "yes but later" is read as a plain yes. A production system would need a richer vocabulary or a follow-up question.
- A clear request next to an unrelated negative clause ("Keep it, I don't want to lose my spot") is treated as doubtful and triggers a clarification question.
- Status questions such as "did you cancel it?" are read as cancellation requests. This is safe because requests only start a flow.

## Project layout

```text
deterministic_intent/
├── README.md
├── pyproject.toml          # pytest configuration only (pythonpath = ["src"])
├── requirements-dev.txt    # pytest>=7.0
├── src/deterministic_intent/
│   ├── __init__.py         # public API
│   ├── __main__.py         # CLI demo
│   ├── models.py           # enums and frozen dataclasses
│   ├── normalize.py        # folding, contractions, clauses
│   ├── lexicon.py          # cue phrases (data)
│   ├── interpreter.py      # interpret()
│   └── policy.py           # decide() and the authorization table
└── tests/
```

## License

Copyright © 2026 [NeusaM21](https://github.com/NeusaM21). **All rights reserved.**

This example is published for technical evaluation. Public access does not grant permission to reproduce, modify, or redistribute it.
