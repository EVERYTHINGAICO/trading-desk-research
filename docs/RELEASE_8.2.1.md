# Release 8.2.1 - Partial time-exit protection stability

A partial TIME_EXIT that retains a protected residual position now moves to `TIME_EXIT_PARTIAL_PROTECTED`. The regular monitor no longer cancels and recreates that residual position's SL/TP every cycle. Reconciliation and protection runtimes continue supervising it.

TIME_EXIT now waits for Binance to confirm native algo cancellation before submitting reduce-only MARKET, preventing the recurring `-2022` cancel/repair loop.
