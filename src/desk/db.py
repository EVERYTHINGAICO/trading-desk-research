from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .types import Opportunity, TradePlan

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  run_type TEXT NOT NULL,
  state TEXT NOT NULL,
  setup_type TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  thesis TEXT NOT NULL,
  confidence REAL NOT NULL,
  data_quality TEXT NOT NULL,
  score REAL NOT NULL,
  btc_context TEXT NOT NULL,
  market_context TEXT NOT NULL,
  news_risk TEXT NOT NULL,
  rejection_reasons_json TEXT NOT NULL,
  diagnostics_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER NOT NULL,
  entry REAL NOT NULL,
  invalidation_level REAL NOT NULL,
  stop_loss REAL NOT NULL,
  tp1 REAL NOT NULL,
  tp2 REAL NOT NULL,
  primary_tp REAL NOT NULL,
  rr_to_tp1 REAL NOT NULL,
  rr_to_primary REAL NOT NULL,
  trigger_type TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_plans_opportunity_id_unique
ON trade_plans(opportunity_id);

CREATE TRIGGER IF NOT EXISTS trg_trade_plans_immutable_update
BEFORE UPDATE ON trade_plans
BEGIN
  SELECT RAISE(ABORT, 'trade_plans are immutable; create a new opportunity instead');
END;

CREATE TRIGGER IF NOT EXISTS trg_trade_plans_immutable_delete
BEFORE DELETE ON trade_plans
BEGIN
  SELECT RAISE(ABORT, 'trade_plans are immutable; create a new opportunity instead');
END;

CREATE TABLE IF NOT EXISTS state_transitions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER NOT NULL,
  from_state TEXT,
  to_state TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS event_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  event_type TEXT NOT NULL,
  symbol TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_dedupe_state (
  dedupe_key TEXT PRIMARY KEY,
  last_fingerprint TEXT NOT NULL,
  last_emitted_at TEXT NOT NULL,
  suppressed_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shadow_trade_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER NOT NULL UNIQUE,
  symbol TEXT NOT NULL,
  status TEXT NOT NULL,
  entry_triggered INTEGER NOT NULL,
  entry_time TEXT,
  entry_price REAL,
  exit_time TEXT,
  exit_price REAL,
  exit_reason TEXT,
  tp_hit TEXT,
  mfe REAL,
  mae REAL,
  r_multiple REAL,
  resolution_notes TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);
CREATE INDEX IF NOT EXISTS idx_shadow_trade_results_symbol_status
ON shadow_trade_results(symbol,status);

CREATE TABLE IF NOT EXISTS shadow_asset_performance (
  symbol TEXT NOT NULL,
  window TEXT NOT NULL CHECK(window IN ('ALL','24H','7D','30D')),
  closed_trades INTEGER NOT NULL,
  wins INTEGER NOT NULL,
  losses INTEGER NOT NULL,
  open_trades INTEGER NOT NULL,
  win_rate_pct REAL,
  expectancy_r REAL,
  total_r REAL NOT NULL,
  average_win_r REAL,
  average_loss_r REAL,
  profit_factor REAL,
  average_score REAL,
  distinct_setups INTEGER NOT NULL,
  first_signal_at TEXT,
  last_signal_at TEXT,
  source_trade_count INTEGER NOT NULL,
  winner_rank INTEGER,
  loser_rank INTEGER,
  refreshed_at TEXT NOT NULL,
  PRIMARY KEY(symbol,window)
);
CREATE INDEX IF NOT EXISTS idx_shadow_asset_performance_winner
ON shadow_asset_performance(window,winner_rank);
CREATE INDEX IF NOT EXISTS idx_shadow_asset_performance_loser
ON shadow_asset_performance(window,loser_rank);

CREATE VIEW IF NOT EXISTS shadow_asset_top_100_winners AS
SELECT * FROM shadow_asset_performance
WHERE window='ALL' AND closed_trades>=30 AND expectancy_r>0 AND winner_rank<=100
ORDER BY winner_rank;

CREATE VIEW IF NOT EXISTS shadow_asset_top_100_losers AS
SELECT * FROM shadow_asset_performance
WHERE window='ALL' AND closed_trades>=30 AND expectancy_r<0 AND loser_rank<=100
ORDER BY loser_rank;

CREATE TABLE IF NOT EXISTS shadow_hour_performance (
  hour_utc INTEGER NOT NULL CHECK(hour_utc BETWEEN 0 AND 23),
  window TEXT NOT NULL CHECK(window IN ('ALL','30D','7D')),
  closed_trades INTEGER NOT NULL,
  wins INTEGER NOT NULL,
  losses INTEGER NOT NULL,
  win_rate_pct REAL,
  expectancy_r REAL,
  total_r REAL NOT NULL,
  average_win_r REAL,
  average_loss_r REAL,
  profit_factor REAL,
  tier TEXT NOT NULL DEFAULT 'NEUTRAL',
  refreshed_at TEXT NOT NULL,
  PRIMARY KEY(hour_utc,window)
);
CREATE INDEX IF NOT EXISTS idx_shadow_hour_performance_tier
ON shadow_hour_performance(window,tier,hour_utc);

CREATE TABLE IF NOT EXISTS shadow_edge_performance (
  symbol TEXT NOT NULL,
  setup_type TEXT NOT NULL,
  hour_utc INTEGER NOT NULL CHECK(hour_utc BETWEEN 0 AND 23),
  closed_trades INTEGER NOT NULL,
  train_trades INTEGER NOT NULL,
  validation_trades INTEGER NOT NULL,
  gross_expectancy_r REAL,
  net_expectancy_r REAL,
  net_profit_factor REAL,
  net_total_r REAL NOT NULL,
  train_net_expectancy_r REAL,
  validation_net_expectancy_r REAL,
  validation_net_profit_factor REAL,
  status TEXT NOT NULL CHECK(status IN ('APPROVED','WATCH','BLOCKED')),
  refreshed_at TEXT NOT NULL,
  PRIMARY KEY(symbol,setup_type,hour_utc)
);
CREATE INDEX IF NOT EXISTS idx_shadow_edge_performance_status
ON shadow_edge_performance(status,net_expectancy_r DESC);

CREATE TABLE IF NOT EXISTS shadow_asset_setup_performance (
  symbol TEXT NOT NULL,
  setup_type TEXT NOT NULL,
  closed_trades INTEGER NOT NULL,
  train_trades INTEGER NOT NULL,
  validation_trades INTEGER NOT NULL,
  gross_expectancy_r REAL,
  net_expectancy_r REAL,
  net_profit_factor REAL,
  net_total_r REAL NOT NULL,
  train_net_expectancy_r REAL,
  validation_net_expectancy_r REAL,
  validation_net_profit_factor REAL,
  status TEXT NOT NULL CHECK(status IN ('APPROVED','WATCH','BLOCKED')),
  refreshed_at TEXT NOT NULL,
  PRIMARY KEY(symbol,setup_type)
);
CREATE INDEX IF NOT EXISTS idx_shadow_asset_setup_performance_status
ON shadow_asset_setup_performance(status,net_expectancy_r DESC);

CREATE TABLE IF NOT EXISTS waterfall_config_versions (config_hash TEXT PRIMARY KEY,version TEXT NOT NULL,config_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS waterfall_raw_klines (symbol TEXT NOT NULL,interval TEXT NOT NULL,open_time INTEGER NOT NULL,close_time INTEGER NOT NULL,open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,volume REAL NOT NULL,quote_volume REAL NOT NULL,trade_count INTEGER NOT NULL,taker_buy_base REAL NOT NULL,taker_buy_quote REAL NOT NULL,ingested_at TEXT NOT NULL,PRIMARY KEY(symbol,interval,open_time));
CREATE TABLE IF NOT EXISTS waterfall_derivatives_snapshots (id INTEGER PRIMARY KEY,symbol TEXT NOT NULL,timestamp_ms INTEGER NOT NULL,mark_price REAL,index_price REAL,funding_rate REAL,basis REAL,open_interest REAL,quality TEXT NOT NULL,ingested_at TEXT NOT NULL,UNIQUE(symbol,timestamp_ms));
CREATE TABLE IF NOT EXISTS waterfall_snapshots (id INTEGER PRIMARY KEY,symbol TEXT NOT NULL,cutoff_ms INTEGER NOT NULL,config_hash TEXT NOT NULL,features_json TEXT NOT NULL,UNIQUE(symbol,cutoff_ms,config_hash));
CREATE TABLE IF NOT EXISTS waterfall_events (id INTEGER PRIMARY KEY,symbol TEXT NOT NULL,config_hash TEXT NOT NULL,state TEXT NOT NULL,started_ms INTEGER NOT NULL,last_revalidation_ms INTEGER NOT NULL,last_low REAL NOT NULL,reason_json TEXT NOT NULL,ended_ms INTEGER);
CREATE TABLE IF NOT EXISTS waterfall_signals (id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL,revalidation_id TEXT NOT NULL UNIQUE,symbol TEXT NOT NULL,decision_ms INTEGER NOT NULL,cutoff_ms INTEGER NOT NULL,snapshot_id INTEGER NOT NULL,reason_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS waterfall_legs (id INTEGER PRIMARY KEY,variant_id TEXT NOT NULL,event_id INTEGER NOT NULL,signal_id INTEGER NOT NULL,entry_ms INTEGER NOT NULL,entry_price REAL NOT NULL,stop_price REAL NOT NULL,tp_price REAL NOT NULL,risk_price REAL NOT NULL,notional REAL NOT NULL,entry_type TEXT NOT NULL,fee_open REAL NOT NULL,fee_close REAL NOT NULL DEFAULT 0,slippage REAL NOT NULL,status TEXT NOT NULL,exit_ms INTEGER,exit_price REAL,exit_reason TEXT,pnl_gross REAL,pnl_net REAL,mfe_r REAL,mae_r REAL,UNIQUE(variant_id,signal_id));
CREATE TABLE IF NOT EXISTS waterfall_event_transitions (id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL,from_state TEXT,to_state TEXT NOT NULL,at_ms INTEGER NOT NULL,reason_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS waterfall_pending_entries (id INTEGER PRIMARY KEY,variant_id TEXT NOT NULL,event_id INTEGER NOT NULL,signal_id INTEGER NOT NULL,created_ms INTEGER NOT NULL,limit_price REAL NOT NULL,entry_type TEXT NOT NULL,UNIQUE(variant_id,signal_id));
CREATE TABLE IF NOT EXISTS waterfall_event_metrics (event_id INTEGER PRIMARY KEY,leg_count INTEGER NOT NULL,open_legs INTEGER NOT NULL,wins INTEGER NOT NULL,losses INTEGER NOT NULL,gross_r REAL NOT NULL,net_r REAL NOT NULL,total_fees_r REAL NOT NULL,max_drawdown_r REAL NOT NULL,updated_ms INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS binance_demo_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER NOT NULL UNIQUE,
  symbol TEXT NOT NULL,
  status TEXT NOT NULL,
  notional_usdt REAL NOT NULL,
  quantity REAL,
  entry_order_id TEXT,
  exit_order_ids_json TEXT,
  payload_json TEXT NOT NULL,
  error TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS demo_order_intents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER NOT NULL,
  shadow_order_id TEXT,
  symbol TEXT NOT NULL,
  client_order_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  entry_price REAL NOT NULL,
  quantity REAL NOT NULL,
  notional_usdt REAL NOT NULL,
  stop_price REAL NOT NULL,
  tp1 REAL NOT NULL,
  tp2 REAL NOT NULL,
  primary_tp REAL NOT NULL,
  leverage INTEGER NOT NULL,
  margin_type TEXT NOT NULL,
  position_mode TEXT NOT NULL DEFAULT 'ONE_WAY',
  position_side TEXT NOT NULL DEFAULT 'BOTH',
  exchange_order_id TEXT,
  error TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_order_intents_opportunity ON demo_order_intents(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_demo_order_intents_status ON demo_order_intents(status);

CREATE TABLE IF NOT EXISTS demo_one_way_orders (
  intent_id INTEGER PRIMARY KEY,
  opportunity_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  position_side TEXT NOT NULL DEFAULT 'BOTH',
  FOREIGN KEY(intent_id) REFERENCES demo_order_intents(id),
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS demo_hedge_orders (
  intent_id INTEGER PRIMARY KEY,
  opportunity_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  position_side TEXT NOT NULL,
  FOREIGN KEY(intent_id) REFERENCES demo_order_intents(id),
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS demo_order_errors (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opportunity_id INTEGER,
  symbol TEXT NOT NULL,
  client_order_id TEXT,
  exchange_order_id TEXT,
  error_code TEXT,
  error_type TEXT NOT NULL,
  error_message TEXT NOT NULL,
  order_status_at_error TEXT,
  action_taken TEXT NOT NULL,
  asset_blocked INTEGER NOT NULL DEFAULT 1,
  resolved_at TEXT,
  resolution_note TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS demo_asset_blocks (
  symbol TEXT PRIMARY KEY,
  reason TEXT NOT NULL,
  error_id INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT,
  resolution_note TEXT,
  FOREIGN KEY(error_id) REFERENCES demo_order_errors(id)
);

CREATE TABLE IF NOT EXISTS demo_exchange_orders (
  exchange_order_id TEXT PRIMARY KEY,
  intent_id INTEGER,
  shadow_order_id TEXT,
  opportunity_id INTEGER,
  symbol TEXT NOT NULL,
  client_order_id TEXT,
  order_type TEXT NOT NULL,
  side TEXT NOT NULL,
  position_side TEXT NOT NULL,
  price REAL,
  stop_price REAL,
  orig_qty REAL,
  executed_qty REAL,
  cumulative_quote_qty REAL,
  status TEXT NOT NULL,
  raw_response_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demo_order_fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exchange_order_id TEXT NOT NULL,
  intent_id INTEGER,
  shadow_order_id TEXT,
  trade_id TEXT,
  symbol TEXT NOT NULL,
  price REAL NOT NULL,
  quantity REAL NOT NULL,
  quote_quantity REAL,
  commission REAL,
  commission_asset TEXT,
  realized_pnl REAL,
  trade_time INTEGER,
  raw_fill_json TEXT NOT NULL,
  position_cycle_id INTEGER,
  UNIQUE(exchange_order_id, trade_id)
);

CREATE TABLE IF NOT EXISTS demo_income_events (
  transaction_id TEXT PRIMARY KEY,
  symbol TEXT,
  income_type TEXT NOT NULL,
  income REAL NOT NULL,
  asset TEXT,
  trade_info TEXT,
  event_time INTEGER NOT NULL,
  raw_income_json TEXT NOT NULL,
  intent_id INTEGER,
  position_cycle_id INTEGER,
  imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demo_account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_type TEXT NOT NULL DEFAULT 'BINANCE_FUTURES_DEMO',
  total_wallet_balance REAL NOT NULL,
  available_balance REAL NOT NULL,
  total_margin_balance REAL,
  total_unrealized_pnl REAL,
  total_position_initial_margin REAL,
  total_open_order_initial_margin REAL,
  asset TEXT NOT NULL DEFAULT 'USDT',
  raw_account_json TEXT NOT NULL,
  captured_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_demo_account_snapshots_captured
ON demo_account_snapshots(captured_at DESC);

CREATE TABLE IF NOT EXISTS demo_cycle_performance (
  position_cycle_id INTEGER PRIMARY KEY,
  intent_id INTEGER,
  symbol TEXT NOT NULL,
  strategy_version TEXT,
  setup_type TEXT,
  status TEXT NOT NULL,
  result TEXT NOT NULL,
  opened_at TEXT,
  closed_at TEXT,
  fill_count INTEGER NOT NULL,
  realized_pnl REAL NOT NULL,
  commission REAL NOT NULL,
  funding REAL NOT NULL,
  net_pnl REAL NOT NULL,
  attribution_complete INTEGER NOT NULL,
  refreshed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS demo_position_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  position_mode TEXT NOT NULL,
  position_side TEXT NOT NULL,
  position_amt REAL NOT NULL,
  entry_price REAL,
  break_even_price REAL,
  notional REAL NOT NULL,
  initial_margin REAL,
  isolated INTEGER,
  leverage INTEGER,
  unrealized_pnl REAL,
  open_order_initial_margin REAL,
  raw_position_json TEXT NOT NULL,
  captured_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demo_protection_orders (
  algo_id TEXT PRIMARY KEY,
  intent_id INTEGER,
  shadow_order_id TEXT,
  opportunity_id INTEGER,
  symbol TEXT NOT NULL,
  protection_type TEXT NOT NULL,
  position_side TEXT NOT NULL,
  trigger_price REAL NOT NULL,
  close_position INTEGER NOT NULL,
  status TEXT NOT NULL,
  raw_response_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demo_symbol_preflights (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  shadow_order_id TEXT NOT NULL,
  opportunity_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  position_mode TEXT NOT NULL,
  expected_margin_type TEXT NOT NULL,
  expected_leverage INTEGER NOT NULL,
  observed_margin_type TEXT,
  observed_leverage INTEGER,
  orders_present INTEGER NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS demo_position_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  position_mode TEXT NOT NULL,
  position_side TEXT NOT NULL,
  status TEXT NOT NULL,
  aggregated_quantity REAL NOT NULL DEFAULT 0,
  aggregated_notional REAL NOT NULL DEFAULT 0,
  aggregated_entry_price REAL,
  realized_pnl REAL,
  attribution_method TEXT NOT NULL DEFAULT 'FIFO',
  opened_at TEXT,
  closed_at TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, position_mode, position_side, status)
);

CREATE TABLE IF NOT EXISTS demo_position_group_orders (
  position_group_id INTEGER NOT NULL,
  exchange_order_id TEXT NOT NULL,
  intent_id INTEGER,
  opportunity_id INTEGER,
  contributed_quantity REAL,
  contributed_notional REAL,
  sequence_number INTEGER,
  PRIMARY KEY(position_group_id, exchange_order_id)
);

CREATE TABLE IF NOT EXISTS demo_reconciliation_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  status TEXT NOT NULL,
  positions_seen INTEGER NOT NULL DEFAULT 0,
  orders_seen INTEGER NOT NULL DEFAULT 0,
  algos_seen INTEGER NOT NULL DEFAULT 0,
  matched_count INTEGER NOT NULL DEFAULT 0,
  orphan_count INTEGER NOT NULL DEFAULT 0,
  discrepancy_count INTEGER NOT NULL DEFAULT 0,
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS demo_reconciliation_issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reconciliation_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  opportunity_id INTEGER,
  intent_id INTEGER,
  exchange_order_id TEXT,
  algo_id TEXT,
  issue_type TEXT NOT NULL,
  severity TEXT NOT NULL,
  expected_value TEXT,
  observed_value TEXT,
  action_required TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'OPEN',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS demo_manual_protection_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  intent_id INTEGER,
  opportunity_id INTEGER,
  symbol TEXT NOT NULL,
  position_side TEXT NOT NULL,
  protection_type TEXT NOT NULL,
  trigger_price REAL NOT NULL,
  observed_price REAL,
  action TEXT NOT NULL,
  exchange_order_id TEXT,
  status TEXT NOT NULL,
  error TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(intent_id) REFERENCES demo_order_intents(id),
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);
CREATE INDEX IF NOT EXISTS idx_demo_manual_protection_events_open
ON demo_manual_protection_events(symbol, position_side, status);

CREATE TABLE IF NOT EXISTS demo_position_cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  position_mode TEXT NOT NULL,
  position_side TEXT NOT NULL,
  direction TEXT NOT NULL,
  status TEXT NOT NULL,
  protection_owner_intent_id INTEGER,
  opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT,
  last_quantity REAL NOT NULL,
  last_entry_price REAL,
  last_mark_price REAL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_demo_position_cycles_one_open
ON demo_position_cycles(symbol, position_mode, position_side) WHERE status='OPEN';

CREATE TABLE IF NOT EXISTS demo_strategy_sources (
  source_key TEXT PRIMARY KEY,
  strategy_id TEXT NOT NULL,
  strategy_version TEXT NOT NULL,
  source_id TEXT NOT NULL,
  opportunity_id INTEGER NOT NULL UNIQUE,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS demo_fix_trade_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  status TEXT NOT NULL,
  mode TEXT NOT NULL,
  model TEXT NOT NULL,
  total_positions INTEGER NOT NULL DEFAULT 0,
  protected_positions INTEGER NOT NULL DEFAULT 0,
  unprotected_positions INTEGER NOT NULL DEFAULT 0,
  repaired_positions INTEGER NOT NULL DEFAULT 0,
  closed_positions INTEGER NOT NULL DEFAULT 0,
  failed_positions INTEGER NOT NULL DEFAULT 0,
  summary_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS demo_fix_trade_actions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  position_cycle_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  position_side TEXT NOT NULL,
  policy TEXT NOT NULL,
  decision TEXT NOT NULL,
  stop_price REAL,
  take_profit_price REAL,
  level_source TEXT,
  reason TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 0,
  native_stop_before INTEGER NOT NULL,
  native_tp_before INTEGER NOT NULL,
  watcher_stop_before INTEGER NOT NULL,
  watcher_tp_before INTEGER NOT NULL,
  result_status TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  ai_input_json TEXT NOT NULL,
  ai_output_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES demo_fix_trade_runs(id),
  FOREIGN KEY(position_cycle_id) REFERENCES demo_position_cycles(id)
);

CREATE TABLE IF NOT EXISTS demo_alert_deliveries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  error_id INTEGER,
  channel TEXT NOT NULL,
  destination TEXT,
  status TEXT NOT NULL,
  error TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(error_id) REFERENCES demo_order_errors(id)
);

CREATE TABLE IF NOT EXISTS shadow_ai_reviews (
  opportunity_id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  status TEXT NOT NULL,
  shadow_recommendation TEXT NOT NULL,
  context_summary TEXT NOT NULL,
  contradictions_json TEXT NOT NULL,
  risk_flags_json TEXT NOT NULL,
  missing_data_json TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  confidence REAL NOT NULL,
  model TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  raw_review_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
);

CREATE TABLE IF NOT EXISTS pre_ny_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  generated_at TEXT NOT NULL,
  session_status TEXT NOT NULL,
  market_regime TEXT NOT NULL,
  data_quality TEXT NOT NULL,
  base_probability REAL,
  bull_probability REAL,
  bear_probability REAL,
  scenario_map_json TEXT NOT NULL,
  macro_context TEXT NOT NULL,
  btc_context TEXT NOT NULL,
  stocks_context TEXT NOT NULL,
  summary TEXT NOT NULL,
  model TEXT NOT NULL,
  raw_output_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pre_ny_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  instrument TEXT NOT NULL,
  direction TEXT NOT NULL CHECK(direction IN ('LONG','SHORT','NONE')),
  status TEXT NOT NULL CHECK(status IN ('READY','WAIT','MISSED','INVALIDATED','NO_TRADE')),
  setup_type TEXT NOT NULL,
  scenario TEXT NOT NULL,
  plan_label TEXT NOT NULL,
  entry_low REAL,
  entry_high REAL,
  technical_invalidation REAL,
  stop_loss REAL,
  tp1 REAL,
  tp2 REAL,
  primary_tp REAL,
  rr_primary REAL,
  score REAL,
  timing_action TEXT NOT NULL,
  trigger TEXT NOT NULL,
  cancel_if_json TEXT NOT NULL,
  thesis TEXT NOT NULL,
  risks_json TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  raw_plan_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES pre_ny_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_pre_ny_plans_run ON pre_ny_plans(run_id);

CREATE TABLE IF NOT EXISTS quality_stock_dip_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  generated_at TEXT NOT NULL,
  session_status TEXT NOT NULL,
  market_regime TEXT NOT NULL,
  data_quality TEXT NOT NULL CHECK(data_quality IN ('A','B','C')),
  stocks_context TEXT NOT NULL,
  macro_context TEXT NOT NULL,
  summary TEXT NOT NULL,
  model TEXT NOT NULL,
  universe_count INTEGER NOT NULL,
  raw_output_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quality_stock_dip_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  underlying_ticker TEXT NOT NULL,
  instrument TEXT NOT NULL,
  classification TEXT NOT NULL CHECK(classification IN ('A_PRICE_DISLOCATION','B_FUNDAMENTAL_BREAK','C_VALUATION_RESET')),
  status TEXT NOT NULL CHECK(status IN ('BUY_ZONE','ACCUMULATE_GRADUALLY','WATCH_LOWER','WAIT_FOR_STABILIZATION','FUNDAMENTAL_BREAK_PASS','VALUATION_STILL_RICH','MISSED_DO_NOT_CHASE','NO_QUALITY_DIP')),
  quality_score REAL NOT NULL,
  dip_score REAL NOT NULL,
  entry_timing_score REAL NOT NULL,
  current_price REAL,
  drawdown_pct REAL,
  technical_invalidation REAL,
  fundamental_invalidation TEXT NOT NULL,
  base_target REAL,
  extension_target REAL,
  expected_horizon TEXT NOT NULL,
  thesis TEXT NOT NULL,
  drop_cause TEXT NOT NULL,
  data_quality TEXT NOT NULL,
  missing_data_json TEXT NOT NULL,
  risks_json TEXT NOT NULL,
  sources_json TEXT NOT NULL,
  raw_plan_json TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES quality_stock_dip_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_quality_stock_dip_plans_run ON quality_stock_dip_plans(run_id);
CREATE TRIGGER IF NOT EXISTS trg_quality_stock_dip_plans_immutable_update
BEFORE UPDATE ON quality_stock_dip_plans BEGIN
  SELECT RAISE(ABORT, 'quality stock dip plans are frozen');
END;
CREATE TRIGGER IF NOT EXISTS trg_quality_stock_dip_plans_immutable_delete
BEFORE DELETE ON quality_stock_dip_plans BEGIN
  SELECT RAISE(ABORT, 'quality stock dip plans are frozen');
END;

CREATE TABLE IF NOT EXISTS quality_stock_dip_tranches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id INTEGER NOT NULL,
  tranche_number INTEGER NOT NULL,
  zone_low REAL NOT NULL,
  zone_high REAL NOT NULL,
  relative_size REAL NOT NULL,
  technical_invalidation REAL,
  status TEXT NOT NULL DEFAULT 'NO_FILL',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(plan_id,tranche_number),
  FOREIGN KEY(plan_id) REFERENCES quality_stock_dip_plans(id)
);
CREATE TRIGGER IF NOT EXISTS trg_quality_stock_dip_tranche_levels_immutable
BEFORE UPDATE ON quality_stock_dip_tranches
WHEN NEW.plan_id != OLD.plan_id OR NEW.tranche_number != OLD.tranche_number
  OR NEW.zone_low != OLD.zone_low OR NEW.zone_high != OLD.zone_high
  OR NEW.relative_size != OLD.relative_size OR NEW.technical_invalidation IS NOT OLD.technical_invalidation
BEGIN
  SELECT RAISE(ABORT, 'quality stock dip tranche levels are frozen');
END;

CREATE TABLE IF NOT EXISTS quality_stock_dip_results (
  tranche_id INTEGER PRIMARY KEY,
  plan_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  status TEXT NOT NULL,
  entry_time INTEGER,
  entry_price REAL,
  exit_time INTEGER,
  exit_price REAL,
  exit_reason TEXT,
  mfe_pct REAL,
  mae_pct REAL,
  result_pct REAL,
  r_multiple REAL,
  resolution_notes TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(tranche_id) REFERENCES quality_stock_dip_tranches(id),
  FOREIGN KEY(plan_id) REFERENCES quality_stock_dip_plans(id)
);
CREATE VIEW IF NOT EXISTS quality_stock_dip_metrics AS
SELECT
  COUNT(*) FILTER (WHERE status != 'NO_FILL') AS tranches_triggered,
  COUNT(*) FILTER (WHERE status IN ('BASE_TARGET','EXTENSION_TARGET')) AS wins,
  COUNT(*) FILTER (WHERE status='STOP') AS losses,
  COUNT(*) FILTER (WHERE status='OPEN') AS open,
  COUNT(*) FILTER (WHERE status='NO_FILL') AS no_fill,
  AVG(r_multiple) FILTER (WHERE status IN ('BASE_TARGET','EXTENSION_TARGET','STOP')) AS expectancy_r,
  AVG(result_pct) FILTER (WHERE status IN ('BASE_TARGET','EXTENSION_TARGET','STOP')) AS average_result_pct,
  SUM(CASE WHEN r_multiple > 0 THEN r_multiple ELSE 0 END) /
    NULLIF(ABS(SUM(CASE WHEN r_multiple < 0 THEN r_multiple ELSE 0 END)),0) AS profit_factor
FROM quality_stock_dip_results;

CREATE TABLE IF NOT EXISTS desk_agents (
  agent_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL,
  task TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS desk_agent_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  status TEXT NOT NULL,
  task TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  FOREIGN KEY(agent_id) REFERENCES desk_agents(agent_id)
);
CREATE INDEX IF NOT EXISTS idx_desk_agent_runs_agent_finished ON desk_agent_runs(agent_id, finished_at DESC);
CREATE TABLE IF NOT EXISTS desk_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(agent_id) REFERENCES desk_agents(agent_id)
);
CREATE TABLE IF NOT EXISTS strategy_registry (
  strategy_id TEXT NOT NULL,
  version TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  config_json TEXT NOT NULL,
  owner_agent_id TEXT NOT NULL,
  environment TEXT NOT NULL,
  promotion_state TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(strategy_id, version)
);
CREATE TRIGGER IF NOT EXISTS trg_strategy_registry_immutable
BEFORE UPDATE OF strategy_id,version,config_hash,config_json ON strategy_registry
BEGIN
  SELECT RAISE(ABORT, 'strategy versions are immutable; insert a new version');
END;
CREATE TABLE IF NOT EXISTS runtime_job_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  runtime_profile TEXT NOT NULL,
  job_name TEXT NOT NULL,
  expected_at TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  delay_seconds REAL NOT NULL,
  duration_seconds REAL NOT NULL,
  returncode INTEGER NOT NULL,
  error TEXT,
  UNIQUE(runtime_profile, job_name, started_at)
);
CREATE INDEX IF NOT EXISTS idx_runtime_job_runs_latest
ON runtime_job_runs(runtime_profile, job_name, finished_at DESC);
CREATE TABLE IF NOT EXISTS data_feed_health (
  feed_name TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  age_seconds REAL,
  delay_seconds REAL,
  detail_json TEXT NOT NULL,
  checked_at TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=120)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=120000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    migrations = {
        "demo_order_intents": (
            ("position_mode", "TEXT NOT NULL DEFAULT 'ONE_WAY'"),
            ("position_side", "TEXT NOT NULL DEFAULT 'BOTH'"),
            ("shadow_order_id", "TEXT"),
            ("position_cycle_id", "INTEGER"),
        ),
        "demo_exchange_orders": (("shadow_order_id", "TEXT"),),
        "demo_order_fills": (("intent_id", "INTEGER"), ("shadow_order_id", "TEXT"), ("position_cycle_id", "INTEGER")),
        "demo_protection_orders": (("position_cycle_id", "INTEGER"),),
        "demo_manual_protection_events": (("position_cycle_id", "INTEGER"),),
        "demo_fix_trade_runs": (
            ("decision_source", "TEXT NOT NULL DEFAULT 'AI'"),
            ("trigger_source", "TEXT NOT NULL DEFAULT 'MANUAL'"),
            ("deferred_positions", "INTEGER NOT NULL DEFAULT 0"),
        ),
    }
    for table, additions in migrations.items():
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in additions:
            if name not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_demo_order_intents_shadow_order_id ON demo_order_intents(shadow_order_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_demo_order_intents_cycle ON demo_order_intents(position_cycle_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_demo_manual_events_cycle ON demo_manual_protection_events(position_cycle_id,protection_type,status)")
    conn.commit()


def upsert_demo_fill(conn: sqlite3.Connection, payload: dict) -> None:
    order_id = str(payload['orderId'])
    owner = conn.execute(
        """SELECT intent_id,shadow_order_id FROM demo_exchange_orders WHERE exchange_order_id=?
           UNION ALL SELECT id,shadow_order_id FROM demo_order_intents WHERE exchange_order_id=? LIMIT 1""",
        (order_id, order_id),
    ).fetchone()
    conn.execute(
        """INSERT INTO demo_order_fills(exchange_order_id,intent_id,shadow_order_id,trade_id,symbol,price,
             quantity,quote_quantity,commission,commission_asset,realized_pnl,trade_time,raw_fill_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(exchange_order_id,trade_id) DO UPDATE SET
             intent_id=COALESCE(excluded.intent_id,demo_order_fills.intent_id),
             shadow_order_id=COALESCE(excluded.shadow_order_id,demo_order_fills.shadow_order_id),
             price=excluded.price,quantity=excluded.quantity,quote_quantity=excluded.quote_quantity,
             commission=excluded.commission,realized_pnl=excluded.realized_pnl,raw_fill_json=excluded.raw_fill_json""",
        (order_id, owner['intent_id'] if owner else None, owner['shadow_order_id'] if owner else None,
         str(payload['id']), payload['symbol'], float(payload['price']), float(payload['qty']),
         float(payload.get('quoteQty', 0)), float(payload.get('commission', 0)), payload.get('commissionAsset'),
         float(payload.get('realizedPnl', 0)), int(payload['time']), json.dumps(payload, ensure_ascii=False)),
    )


def upsert_demo_income(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        """INSERT INTO demo_income_events(transaction_id,symbol,income_type,income,asset,trade_info,event_time,raw_income_json)
           VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(transaction_id) DO UPDATE SET
             income_type=excluded.income_type,income=excluded.income,trade_info=excluded.trade_info,
             raw_income_json=excluded.raw_income_json""",
        (str(payload['tranId']), payload.get('symbol'), payload['incomeType'], float(payload['income']),
         payload.get('asset'), payload.get('info'), int(payload['time']), json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


def insert_demo_account_snapshot(conn: sqlite3.Connection, account: dict) -> int:
    cur = conn.execute(
        """INSERT INTO demo_account_snapshots (
          total_wallet_balance,available_balance,total_margin_balance,total_unrealized_pnl,
          total_position_initial_margin,total_open_order_initial_margin,asset,raw_account_json
        ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            float(account.get('totalWalletBalance', 0)),
            float(account.get('availableBalance', 0)),
            float(account.get('totalMarginBalance', 0)) if account.get('totalMarginBalance') is not None else None,
            float(account.get('totalUnrealizedProfit', 0)) if account.get('totalUnrealizedProfit') is not None else None,
            float(account.get('totalPositionInitialMargin', 0)) if account.get('totalPositionInitialMargin') is not None else None,
            float(account.get('totalOpenOrderInitialMargin', 0)) if account.get('totalOpenOrderInitialMargin') is not None else None,
            account.get('assets', [{}])[0].get('asset', 'USDT') if isinstance(account.get('assets'), list) else 'USDT',
            json.dumps(account, ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_opportunity(conn: sqlite3.Connection, opp: Opportunity) -> int:
    cur = conn.execute(
        """
        INSERT INTO opportunities (
          symbol, run_type, state, setup_type, detected_at, thesis, confidence,
          data_quality, score, btc_context, market_context, news_risk,
          rejection_reasons_json, diagnostics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            opp.symbol,
            opp.run_type,
            opp.state,
            opp.setup_type,
            opp.detected_at,
            opp.thesis,
            opp.confidence,
            opp.data_quality,
            opp.score,
            opp.btc_context,
            opp.market_context,
            opp.news_risk,
            json.dumps(opp.rejection_reasons, ensure_ascii=False),
            json.dumps(opp.diagnostics, ensure_ascii=False),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_trade_plan(conn: sqlite3.Connection, opportunity_id: int, plan: TradePlan) -> None:
    conn.execute(
        """
        INSERT INTO trade_plans (
          opportunity_id, entry, invalidation_level, stop_loss, tp1, tp2,
          primary_tp, rr_to_tp1, rr_to_primary, trigger_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            opportunity_id,
            plan.entry,
            plan.invalidation_level,
            plan.stop_loss,
            plan.tp1,
            plan.tp2,
            plan.primary_tp,
            plan.rr_to_tp1,
            plan.rr_to_primary,
            plan.trigger_type,
        ),
    )
    conn.commit()


def insert_transition(conn: sqlite3.Connection, opportunity_id: int, from_state: str | None, to_state: str, reason: str) -> None:
    conn.execute(
        "INSERT INTO state_transitions (opportunity_id, from_state, to_state, reason) VALUES (?, ?, ?, ?)",
        (opportunity_id, from_state, to_state, reason),
    )
    conn.commit()


def insert_event(conn: sqlite3.Connection, timestamp: str, event_type: str, symbol: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO event_log (timestamp, event_type, symbol, payload_json) VALUES (?, ?, ?, ?)",
        (timestamp, event_type, symbol, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


def get_open_opportunities(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
             SELECT o.*, tp.entry, tp.invalidation_level, tp.stop_loss, tp.tp1, tp.tp2, tp.primary_tp, tp.rr_to_tp1, tp.rr_to_primary, tp.trigger_type,
                    sr.status AS previous_status, sr.entry_triggered AS previous_entry_triggered,
                    sr.entry_time AS previous_entry_time, sr.entry_price AS previous_entry_price,
                    sr.tp_hit AS previous_tp_hit
            FROM opportunities o
            JOIN trade_plans tp ON tp.opportunity_id = o.id
             LEFT JOIN shadow_trade_results sr ON sr.opportunity_id = o.id
             WHERE o.state IN ('WATCH', 'PRE_ENTRY', 'ENTRY_READY')
               AND (sr.opportunity_id IS NULL OR sr.status = 'OPEN')
            ORDER BY o.id ASC
            """
        )
    )


def update_opportunity_state(conn: sqlite3.Connection, opportunity_id: int, new_state: str) -> None:
    conn.execute("UPDATE opportunities SET state = ? WHERE id = ?", (new_state, opportunity_id))
    conn.commit()


def insert_shadow_result(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO shadow_trade_results (
          opportunity_id, symbol, status, entry_triggered, entry_time, entry_price,
          exit_time, exit_price, exit_reason, tp_hit, mfe, mae, r_multiple, resolution_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload['opportunity_id'],
            payload['symbol'],
            payload['status'],
            1 if payload['entry_triggered'] else 0,
            payload.get('entry_time'),
            payload.get('entry_price'),
            payload.get('exit_time'),
            payload.get('exit_price'),
            payload.get('exit_reason'),
            payload.get('tp_hit'),
            payload.get('mfe'),
            payload.get('mae'),
            payload.get('r_multiple'),
            payload.get('resolution_notes', ''),
        ),
    )
    conn.commit()


def get_demo_order(conn: sqlite3.Connection, opportunity_id: int) -> sqlite3.Row | None:
    return conn.execute(
        'SELECT * FROM binance_demo_orders WHERE opportunity_id = ?', (opportunity_id,)
    ).fetchone()


def get_demo_intent(conn: sqlite3.Connection, opportunity_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM demo_order_intents WHERE opportunity_id = ? ORDER BY id DESC LIMIT 1",
        (opportunity_id,),
    ).fetchone()


def get_demo_intent_or_order(conn: sqlite3.Connection, opportunity_id: int) -> sqlite3.Row | None:
    intent = get_demo_intent(conn, opportunity_id)
    if intent:
        return intent
    return conn.execute(
        "SELECT opportunity_id, symbol, status, entry_order_id AS exchange_order_id, "
        "NULL AS client_order_id, error, payload_json FROM binance_demo_orders "
        "WHERE opportunity_id = ?", (opportunity_id,)
    ).fetchone()


def insert_demo_intent(conn: sqlite3.Connection, payload: dict) -> int:
    cur = conn.execute(
        """INSERT INTO demo_order_intents (
          opportunity_id,shadow_order_id,symbol,client_order_id,status,entry_price,quantity,notional_usdt,
          stop_price,tp1,tp2,primary_tp,leverage,margin_type,position_mode,position_side,payload_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (payload['opportunity_id'], payload['shadow_order_id'], payload['symbol'], payload['client_order_id'], payload['status'],
         payload['entry_price'], payload['quantity'], payload['notional_usdt'], payload['stop_price'],
         payload['tp1'], payload['tp2'], payload['primary_tp'], payload['leverage'], payload['margin_type'],
         payload.get('position_mode', 'ONE_WAY'), payload.get('position_side', 'BOTH'),
         json.dumps(payload, ensure_ascii=False)),
    )
    intent_id = int(cur.lastrowid)
    if payload.get('position_mode', 'ONE_WAY') == 'HEDGE':
        conn.execute(
            "INSERT OR IGNORE INTO demo_hedge_orders(intent_id,opportunity_id,symbol,position_side) VALUES(?,?,?,?)",
            (intent_id, payload['opportunity_id'], payload['symbol'], payload.get('position_side', 'LONG')),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO demo_one_way_orders(intent_id,opportunity_id,symbol) VALUES(?,?,?)",
            (intent_id, payload['opportunity_id'], payload['symbol']),
        )
    conn.commit()
    return intent_id


def update_demo_intent(conn: sqlite3.Connection, client_order_id: str, payload: dict) -> None:
    existing = conn.execute(
        "SELECT quantity,exchange_order_id,error FROM demo_order_intents WHERE client_order_id=?",
        (client_order_id,),
    ).fetchone()
    quantity = payload["quantity"] if "quantity" in payload else (existing[0] if existing else 0)
    exchange_order_id = payload["exchange_order_id"] if "exchange_order_id" in payload else (existing[1] if existing else None)
    error = payload["error"] if "error" in payload else (existing[2] if existing else None)
    conn.execute(
        """UPDATE demo_order_intents SET status=?, quantity=?, exchange_order_id=?, error=?, payload_json=?, updated_at=CURRENT_TIMESTAMP
           WHERE client_order_id=?""",
        (payload['status'], quantity, exchange_order_id, error, json.dumps(payload, ensure_ascii=False), client_order_id),
    )
    conn.commit()


def insert_preflight(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        """INSERT INTO demo_symbol_preflights (
          shadow_order_id,opportunity_id,symbol,position_mode,expected_margin_type,expected_leverage,
          observed_margin_type,observed_leverage,orders_present,status,error
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (payload['shadow_order_id'], payload['opportunity_id'], payload['symbol'], payload['position_mode'],
         payload['expected_margin_type'], payload['expected_leverage'], payload.get('observed_margin_type'),
         payload.get('observed_leverage'), 1 if payload.get('orders_present') else 0, payload['status'], payload.get('error')),
    )
    conn.commit()


def upsert_protection_order(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        """INSERT INTO demo_protection_orders (
           algo_id,intent_id,shadow_order_id,opportunity_id,symbol,protection_type,position_side,
           trigger_price,close_position,status,raw_response_json,position_cycle_id
         ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
         ON CONFLICT(algo_id) DO UPDATE SET status=excluded.status,raw_response_json=excluded.raw_response_json,
           position_cycle_id=COALESCE(excluded.position_cycle_id,demo_protection_orders.position_cycle_id),updated_at=CURRENT_TIMESTAMP""",
        (str(payload['algoId']), payload.get('intent_id'), payload.get('shadow_order_id'), payload.get('opportunity_id'),
         payload['symbol'], payload.get('orderType'), payload.get('positionSide', 'BOTH'), payload.get('triggerPrice'),
         1 if payload.get('closePosition') else 0, payload.get('algoStatus', 'NEW'), json.dumps(payload, ensure_ascii=False),
         payload.get('position_cycle_id')),
    )
    conn.commit()


def insert_demo_error(conn: sqlite3.Connection, payload: dict) -> int:
    existing = conn.execute(
        "SELECT id FROM demo_order_errors WHERE symbol=? AND client_order_id IS ? AND exchange_order_id IS ? AND error_message=? AND resolved_at IS NULL",
        (payload['symbol'], payload.get('client_order_id'), payload.get('exchange_order_id'), payload['error_message']),
    ).fetchone()
    if existing:
        return int(existing[0])
    cur = conn.execute(
        """INSERT INTO demo_order_errors (
          opportunity_id,symbol,client_order_id,exchange_order_id,error_code,error_type,
          error_message,order_status_at_error,action_taken,asset_blocked
         ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (payload.get('opportunity_id'), payload['symbol'], payload.get('client_order_id'),
         payload.get('exchange_order_id'), payload.get('error_code'), payload['error_type'],
         payload['error_message'], payload.get('order_status_at_error'), payload['action_taken'],
         1 if payload.get('asset_blocked', True) else 0),
    )
    error_id = int(cur.lastrowid)
    if payload.get('asset_blocked', True):
        conn.execute(
            """INSERT INTO demo_asset_blocks(symbol,reason,error_id) VALUES(?,?,?)
               ON CONFLICT(symbol) DO UPDATE SET reason=excluded.reason,error_id=excluded.error_id,active=1,resolved_at=NULL,resolution_note=NULL""",
            (payload['symbol'], payload['error_message'], error_id),
        )
    conn.commit()
    return error_id


def record_demo_exception(conn: sqlite3.Connection, payload: dict, exc: Exception, *, block_asset: bool = True) -> int:
    text = str(exc)
    code = text.split('"code":', 1)[1].split(',', 1)[0].strip() if '"code":' in text else None
    return insert_demo_error(conn, {
        **payload,
        'error_code': payload.get('error_code', code),
        'error_message': text,
        'asset_blocked': block_asset,
    })


def insert_manual_protection_event(conn: sqlite3.Connection, payload: dict) -> int:
    cur = conn.execute(
        """INSERT INTO demo_manual_protection_events(
           intent_id,opportunity_id,symbol,position_side,protection_type,trigger_price,
           observed_price,action,exchange_order_id,status,error,position_cycle_id
         ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (payload.get('intent_id'), payload.get('opportunity_id'), payload['symbol'], payload.get('position_side', 'BOTH'),
         payload['protection_type'], payload['trigger_price'], payload.get('observed_price'), payload['action'],
          payload.get('exchange_order_id'), payload['status'], payload.get('error'), payload.get('position_cycle_id')),
    )
    conn.commit()
    return int(cur.lastrowid)


def insert_alert_delivery(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        "INSERT INTO demo_alert_deliveries(error_id,channel,destination,status,error) VALUES(?,?,?,?,?)",
        (payload.get('error_id'), payload['channel'], payload.get('destination'), payload['status'], payload.get('error')),
    )
    conn.commit()


def insert_demo_error_from_exception(conn: sqlite3.Connection, payload: dict, exc: Exception) -> int:
    text = str(exc)
    code = None
    if '"code":' in text:
        code = text.split('"code":', 1)[1].split(',', 1)[0].strip()
    return insert_demo_error(conn, {**payload, 'error_code': code, 'error_message': text})


def is_demo_asset_blocked(conn: sqlite3.Connection, symbol: str) -> bool:
    row = conn.execute("SELECT active FROM demo_asset_blocks WHERE symbol=?", (symbol,)).fetchone()
    return bool(row and row[0])


def list_demo_errors(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM demo_order_errors ORDER BY id DESC LIMIT 50"))


def upsert_exchange_order(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        """INSERT INTO demo_exchange_orders (
          exchange_order_id,intent_id,shadow_order_id,opportunity_id,symbol,client_order_id,order_type,side,position_side,
          price,stop_price,orig_qty,executed_qty,cumulative_quote_qty,status,raw_response_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(exchange_order_id) DO UPDATE SET
          intent_id=COALESCE(excluded.intent_id,demo_exchange_orders.intent_id),
          opportunity_id=COALESCE(excluded.opportunity_id,demo_exchange_orders.opportunity_id),
          status=excluded.status, executed_qty=excluded.executed_qty,
          cumulative_quote_qty=excluded.cumulative_quote_qty,
          raw_response_json=excluded.raw_response_json, updated_at=CURRENT_TIMESTAMP""",
        (str(payload['orderId']), payload.get('intent_id'), payload.get('shadow_order_id'), payload.get('opportunity_id'), payload['symbol'],
         payload.get('clientOrderId'), payload.get('type', 'LIMIT'), payload['side'], payload.get('positionSide', 'BOTH'),
         payload.get('price'), payload.get('stopPrice'), payload.get('origQty'), payload.get('executedQty'),
         payload.get('cumQuote'), payload['status'], json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


def insert_position_snapshot(conn: sqlite3.Connection, position: dict, position_mode: str) -> None:
    conn.execute(
        """INSERT INTO demo_position_snapshots (
          symbol,position_mode,position_side,position_amt,entry_price,break_even_price,notional,
          initial_margin,isolated,leverage,unrealized_pnl,open_order_initial_margin,raw_position_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (position['symbol'], position_mode, position.get('positionSide', 'BOTH'), float(position.get('positionAmt', 0)),
         position.get('entryPrice'), position.get('breakEvenPrice'), float(position.get('notional', 0)),
         position.get('initialMargin'), 1 if position.get('isolated') else 0, position.get('leverage'),
         position.get('unrealizedProfit'), position.get('openOrderInitialMargin'), json.dumps(position, ensure_ascii=False)),
    )
    conn.commit()


def create_reconciliation_run(conn: sqlite3.Connection) -> int:
    conn.execute(
        """UPDATE demo_reconciliation_runs SET status='DEGRADED',finished_at=CURRENT_TIMESTAMP
           WHERE status='RUNNING' AND started_at < datetime('now','-5 minutes')"""
    )
    cur = conn.execute("INSERT INTO demo_reconciliation_runs(status) VALUES ('RUNNING')")
    conn.commit()
    return int(cur.lastrowid)


def finish_reconciliation_run(conn: sqlite3.Connection, run_id: int, counts: dict[str, int], status: str) -> None:
    conn.execute(
        """UPDATE demo_reconciliation_runs SET status=?,positions_seen=?,orders_seen=?,algos_seen=?,matched_count=?,orphan_count=?,discrepancy_count=?,finished_at=CURRENT_TIMESTAMP WHERE id=?""",
        (status, counts.get('positions', 0), counts.get('orders', 0), counts.get('algos', 0), counts.get('matched', 0), counts.get('orphans', 0), counts.get('discrepancies', 0), run_id),
    )
    conn.commit()


def insert_reconciliation_issue(conn: sqlite3.Connection, run_id: int, payload: dict) -> None:
    conn.execute(
        """INSERT INTO demo_reconciliation_issues (
          reconciliation_id,symbol,opportunity_id,intent_id,exchange_order_id,algo_id,issue_type,severity,expected_value,observed_value,action_required
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (run_id, payload['symbol'], payload.get('opportunity_id'), payload.get('intent_id'), payload.get('exchange_order_id'), payload.get('algo_id'), payload['issue_type'], payload.get('severity', 'WARNING'), json.dumps(payload.get('expected_value')), json.dumps(payload.get('observed_value')), payload['action_required']),
    )
    conn.commit()


def insert_demo_order(conn: sqlite3.Connection, payload: dict) -> None:
    conn.execute(
        '''
        INSERT INTO binance_demo_orders (
          opportunity_id, symbol, status, notional_usdt, quantity,
          entry_order_id, exit_order_ids_json, payload_json, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(opportunity_id) DO UPDATE SET
          status=excluded.status, quantity=excluded.quantity,
          entry_order_id=excluded.entry_order_id,
          exit_order_ids_json=excluded.exit_order_ids_json,
          payload_json=excluded.payload_json, error=excluded.error,
          updated_at=CURRENT_TIMESTAMP
        ''',
        (
            payload['opportunity_id'], payload['symbol'], payload['status'],
            payload['notional_usdt'], payload.get('quantity'),
            payload.get('entry_order_id'), json.dumps(payload.get('exit_order_ids', [])),
            json.dumps(payload, ensure_ascii=False), payload.get('error'),
        ),
    )
    conn.commit()


def get_submitted_demo_orders(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM binance_demo_orders WHERE status IN ('SUBMITTED','PROTECTED') ORDER BY id"))


def update_demo_order_status(conn: sqlite3.Connection, opportunity_id: int, status: str, payload: dict) -> None:
    conn.execute(
        "UPDATE binance_demo_orders SET status=?, payload_json=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE opportunity_id=?",
        (status, json.dumps(payload, ensure_ascii=False), payload.get("error"), opportunity_id),
    )
    conn.commit()
