# Release 6.2.0 - Telegram responder (interactive commands)

## Why

Alerts (notify_error) were one-way: the bot sent error messages but never listened
to inbound messages. Add an interactive responder so /status and /help work from the
authorized chat.

## Changes

- `src/desk/telegram_alerts.py`: shared `telegram_account()` / `telegram_chat_id()`
  helpers (env or /openclaw-config/openclaw.json); `_token()` refactored onto them.
- `scripts/telegram_poller_once.py` (new): drains getUpdates every scheduler cycle,
  persists `data/telegram_updates_offset.json`, replies only to the authorized alert
  chat id. Commands: `/status` (VERSION + scheduler heartbeat + wallet + open
  positions), `/help`, `/start`; anything else -> hint.
- `scripts/run_scheduler_loop.py`: new job `telegram_responder` every
  `telegram_responder_every_seconds` (default 20s).

## Verification

- Tests: 39 passed.
- Manual run in container: poller exits ok, no token leak in output.
- Scheduler restarted to load the new job.

## Rollback

- Remove the job block in `run_scheduler_loop.py` and/or the poller script; no DB
  change. Offset file `data/telegram_updates_offset.json` is safe to delete.