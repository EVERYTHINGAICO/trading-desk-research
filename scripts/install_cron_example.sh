#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/node/.openclaw/workspace/research/trading-desk-shadow"
LOG_DIR="$ROOT/data/cron-logs"
mkdir -p "$LOG_DIR"

cat <<CRON
# Example crontab entries for trading-desk-shadow
# Broad screener hourly
0 * * * * cd /home/node/.openclaw/workspace && python3 research/trading-desk-shadow/scripts/run_shadow_once.py >> research/trading-desk-shadow/data/cron-logs/shadow_scan.log 2>&1

# Trigger monitor every 5 minutes
*/5 * * * * cd /home/node/.openclaw/workspace && python3 research/trading-desk-shadow/scripts/run_trigger_monitor_once.py >> research/trading-desk-shadow/data/cron-logs/trigger_monitor.log 2>&1

# Stateful monitor over open opportunities every 5 minutes
*/5 * * * * cd /home/node/.openclaw/workspace && python3 research/trading-desk-shadow/scripts/run_stateful_open_monitor_once.py >> research/trading-desk-shadow/data/cron-logs/stateful_open_monitor.log 2>&1

# Resolver every 5 minutes
*/5 * * * * cd /home/node/.openclaw/workspace && python3 research/trading-desk-shadow/scripts/resolve_shadow_open_trades.py >> research/trading-desk-shadow/data/cron-logs/shadow_resolver.log 2>&1
CRON
