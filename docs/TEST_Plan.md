# Test Plan

## Objective

Validate that the dispute workflow behaves correctly across all currently supported paths.

The test plan is organized around business scenarios rather than individual functions.

---

# Scenario A – Duplicate Case Resolution

## Input

```json
{
  "transaction_id": "TXN-001",
  "existing_open_case_id": "CASE-1001",
  "amount": 217.37,
  "dispute_type": "duplicate_charge"
}
```

## Expected Workflow

intake

→ classify_dispute

→ duplicate_case_check

→ resolve_duplicate_case

→ customer_communication

→ close_case

## Expected Result

```json
{
  "status": "closed",
  "resolution_type": "duplicate_case"
}
```

## Expected Communication

Customer is informed that an existing dispute already exists and the request has been linked or resolved as a duplicate.

---

# Scenario B – Small Dollar Resolution

## Input

```json
{
  "transaction_id": "TXN-002",
  "amount": 25.00,
  "dispute_type": "billing_error"
}
```

## Expected Workflow

intake

→ classify_dispute

→ duplicate_case_check

→ early_resolution_check

→ resolve_small_dollar

→ customer_communication

→ close_case

## Expected Result

```json
{
  "status": "closed",
  "resolution_type": "small_dollar_writeoff"
}
```

## Expected Communication

Customer is informed that the dispute has been resolved and credited.

---

# Scenario C – Pending Investigation

## Input

```json
{
  "transaction_id": "TXN-003",
  "amount": 900.00,
  "dispute_type": "fraud"
}
```

## Expected Workflow

intake

→ classify_dispute

→ duplicate_case_check

→ early_resolution_check

→ pending_investigation

→ customer_communication

## Expected Result

```json
{
  "status": "pending_investigation",
  "resolution_type": "under_review"
}
```

## Expected Communication

Customer is informed that the dispute is under review.

## Expected Behavior

Case remains open.

Case does not enter close_case.

---

# Scenario D – Workflow Replay

## Initial Input

```json
{
  "amount": 900
}
```

## Initial Result

pending_investigation

## Replay Action

Rollback to checkpoint before early_resolution_check.

Update amount to 25.

Replay workflow.

## Expected Workflow

intake

→ classify_dispute

→ duplicate_case_check

→ early_resolution_check

→ resolve_small_dollar

→ customer_communication

→ close_case

## Expected Result

```json
{
  "status": "closed",
  "resolution_type": "small_dollar_writeoff"
}
```

---

# Validation Checklist

## Workflow Execution

* [ ] Intake executed
* [ ] Classification executed
* [ ] Duplicate check executed
* [ ] Resolution routing correct
* [ ] Communication generated
* [ ] Final status correct

## Node Trace

* [ ] Node trace captured
* [ ] Node trace displayed
* [ ] Trace matches workflow path

## Replay

* [ ] Checkpoint created
* [ ] Checkpoint retrieved
* [ ] Replay successful
* [ ] Alternate path demonstrated
