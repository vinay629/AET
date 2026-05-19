# SYSTEM_TRUTH.md — BAET Canonical Truth Definition

This document defines the foundational invariants for BAET.
All code must conform to these rules. If any invariant is violated,
the system must halt and alert — not continue trading.

---

## 1. Truth Sources (Priority Order)

| Priority | Source | What It's Truth For |
|----------|--------|-------------------|
| 1 | Exchange API | Actual balances, orders, fills |
| 2 | Event Journal | Historical reconstruction, replay |
| 3 | Portfolio Reducer | Current internal state (derived from #2) |
| 4 | Analytics Engine | Derived metrics (derived from #3) |

When sources diverge, exchange reality wins.
Internal state is always a cache, never a source of truth.

---

## 2. Immutable Invariants

Every state mutation originates from a persisted event.
No signal at time T uses data from time > T.
Portfolio state is always reconstructable from the event journal.
Cash balance must never be negative.
Event timestamps are strictly monotonically increasing.

---

## 3. Time Semantics

Signals generated on candle T can only execute on candle T+1 earliest.
Exchange timestamp is authoritative; local timestamp is diagnostic.
A candle is considered final only after the next candle's open_time.

---

## 4. Event Store Rules

Events are append-only. Never modify or delete an event.
Events are stored as JSONL files: `events/YYYY-MM-DD.jsonl`.
Each event has a unique event_id and a monotonically increasing sequence number.
Every event records both exchange timestamp and local receipt timestamp.

---

## 5. State Reconstruction Rules

On restart, portfolio state is fully restored from the event journal.
Reconstruction is deterministic: same events → same state.
If reconstruction fails, the system halts and alerts.

---

## 6. Learning Constraints

No model trains on future data (strict temporal split).
No production deployment without out-of-sample validation.
Previous production model is always retained for rollback.
Retraining happens on schedule (daily/week), never continuously.

---

## 7. Failure Semantics

Reconciliation failure → halt trading immediately.
Exchange API unreachable for >60s → cancel all orders, halt.
State invariant violation → halt and alert.
Model performance below threshold → disable model, don't halt trading.
