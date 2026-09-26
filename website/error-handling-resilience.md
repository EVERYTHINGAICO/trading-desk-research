---
title: Trading Bot Error Handling and Operational Resilience
description: Failure handling for exchange timeouts, stale data, duplicate orders, missing protection, attribution gaps, reconciliation discrepancies, scheduler failures, and recoverable incidents.
keywords: trading bot error handling, exchange retry logic, idempotent orders, stale market data, trade protection monitoring, operational resilience
canonical: https://everythingaico.github.io/trading-desk-research/error-handling-resilience/
---

# Error Handling And Operational Resilience

The system treats errors as evidence. A failure must be visible, attributable and recoverable without inventing successful state.

## Failure Matrix

| Failure | Detection | Containment | Recovery evidence |
| --- | --- | --- | --- |
| Transient exchange GET failure | HTTP/network exception | Bounded retry with timeout | Attempt outcome and final status |
| Timestamp drift | Binance error response | Refresh exchange time and retry signed request | Corrected timestamp request |
| Stale market input | Freshness monitor | Block or degrade affected decision | Feed health state and age |
| Duplicate execution | Existing client/order identity | Idempotent skip | Original intent and exchange ID |
| Entry without confirmed fill | Position/order verification | Do not create fictional protection success | Intent remains unresolved or failed |
| Missing native protection | Position/protection audit | Attempt exact frozen levels or watcher fallback | Protection order or explicit incident |
| Attribution conflict | Ownership invariant and reconciliation | Prevent silent assignment | Unattributed/conflicted event |
| Local/exchange mismatch | Reconciliation cycle | Record discrepancy before repair | Before/after reconciliation record |
| Scheduler crash or timeout | Heartbeat and job timeout | Isolate failed job; continue supervised loop | Job status and heartbeat |
| Unknown exception | Boundary exception recorder | Preserve context and avoid false success | Persistent error and alert |

## Reliability Principles

1. **Fail closed for orders:** absence of permission, credentials, attribution or valid Demo origin blocks submission.
2. **Bound retries:** only operations safe to repeat receive automatic retry.
3. **Idempotency before recovery:** repeated execution must not duplicate economic action.
4. **Exchange state wins:** local belief is reconciled against observed exchange state.
5. **No invented data:** missing fills, prices, timestamps or ownership remain missing.
6. **Early alerts:** attribution and protection failures should surface before performance reports become misleading.
7. **Permanent evidence:** repairs preserve the incident and resolution trail.

## What Resilience Does Not Mean

No software can guarantee continuous exchange availability, successful protection placement or freedom from loss. The project documents detected failure modes and conservative responses; it does not claim production-grade live trading reliability.
