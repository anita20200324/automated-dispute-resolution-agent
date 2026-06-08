# Architecture Decisions

This document records major project decisions and the rationale behind them.

---

# Decision 001

## Title

Small Dollar Threshold

## Date

2026-06-07

## Decision

Transactions with disputed amounts less than or equal to $25 qualify for Small Dollar Resolution.

```text
Amount <= $25
```

## Reason

Allows rapid demonstration of straight-through processing without requiring a full investigation lifecycle.

## Impact

Amounts greater than $25 route to Pending Investigation.

---

# Decision 002

## Title

Duplicate Validation Scope

## Date

2026-06-07

## Decision

MVP 1 only supports Duplicate Case Detection.

Duplicate Transaction Validation is deferred.

## Reason

Workflow stability is prioritized over transaction matching sophistication.

## Impact

Future Duplicate Transaction Validation will be added as a separate LangGraph node.

Planned insertion point:

duplicate_case_check

↓

duplicate_transaction_validation

↓

early_resolution_check

---

# Decision 003

## Title

Unified Customer Communication Node

## Date

2026-06-07

## Decision

All resolution paths route through a single customer_communication node.

## Reason

Avoids silent case closure and provides a consistent communication experience.

## Impact

Future resolution types can reuse the same communication framework.

Examples:

* duplicate_case
* small_dollar_writeoff
* under_review
* approved
* denied

---

# Decision 004

## Title

Pending Investigation Remains Open

## Date

2026-06-07

## Decision

Pending Investigation does not enter close_case.

## Reason

The dispute remains active and requires future processing.

## Impact

Customer communication is generated, but the case remains open.

---

# Decision 005

## Title

LangGraph Adoption Strategy

## Date

2026-06-07

## Decision

Workflow orchestration will be migrated incrementally into LangGraph.

## Reason

The existing system already includes intake, RAG, STP, communication, and case management capabilities.

The goal is to improve workflow orchestration without rewriting the entire platform.

## Impact

Current sprint focuses on:

* Workflow State
* Node Trace
* Human-in-the-Loop
* Replay
* Checkpoint Recovery

---

# Decision 006

## Title

Checkpoint Before Database

## Date

2026-06-07

## Decision

Workflow replay and checkpoint functionality will be implemented before introducing database persistence.

## Reason

Checkpointing demonstrates one of the primary advantages of LangGraph and provides immediate architectural value.

## Impact

Replay capability is prioritized ahead of Postgres integration.

---

# Future Decisions

Additional decisions will be recorded here as the architecture evolves.
