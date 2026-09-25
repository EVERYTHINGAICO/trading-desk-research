# Release 1.1.2 - Linked pending LIMIT cancellation

- Reconciles every executor-owned open LIMIT directly from Binance, regardless of local intent status.
- Cancels `NEW` or `PARTIALLY_FILLED` entries when the linked setup is `PASS`, `INVALIDATED`, `MISSED`, or `CLOSED_WIN`.
- Persists `CANCELED_SETUP_INVALIDATED` and the exact `cancel_reason`.
- Leaves valid `ENTRY_READY` orders open.
- Leaves true orphan orders untouched for manual review.
- Prevents a transient SQLite lock while auditing Telegram delivery from failing the entire reconciliation.

Controlled validation canceled HEMIUSDT, YBUSDT, SOLUSDT, and KMNOUSDT. Valid TRXUSDT and FIGHTUSDT entries remained open; orphan GASUSDT remained untouched.
