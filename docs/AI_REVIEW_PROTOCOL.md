# AI Review Protocol

The deterministic shadow scanner remains the source of numeric truth. OpenClaw
uses ChatGPT OAuth (`openai-codex/gpt-5.4`) for one hourly market-context review.
The configured 9router provider is the fallback when the OAuth model is
unavailable; Gemini is not in the automatic fallback chain.
The full contract is in `docs/MASTER_PROMPT.md`.

## Contract

- Read `docs/AUTHORITY.md` and the PDF reference before reviewing.
- Read `docs/MASTER_PROMPT.md` and follow it as the operating prompt.
- Read `data/ai_review_queue.json`.
- Review at most 10 candidates per run.
- Do not invent missing indicators, news, or derivatives data.
- Do not change frozen entry, stop, or target levels.
- Return JSONL records to `data/ai_reviews.jsonl` with:
  `opportunity_id`, `symbol`, `context_summary`, `contradictions`, `risk_flags`,
  `shadow_recommendation`, `confidence`, `model`, `reviewed_at`.
- Use `NO_TRADE` when mandatory context is missing or contradictory.
- Never place an order, use a wallet, sign a transaction, or send a real trade.
- Use Brave web search for current external context when required; record sources.

## Token budget

The queue is capped at 10 candidates per run. OpenClaw cron history records input
and output tokens. The review job must stop after its configured timeout and write
an error note instead of retrying indefinitely.
