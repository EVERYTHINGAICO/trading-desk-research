from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone


def _metrics(results: list[tuple[float, float]]) -> tuple[float | None, float | None, float]:
    if not results:
        return None, None, 0.0
    net = [gross - fee_r for gross, fee_r in results]
    gains = sum(value for value in net if value > 0)
    losses = abs(sum(value for value in net if value < 0))
    return sum(net) / len(net), gains / losses if losses else None, sum(net)


def refresh_edge_performance(conn: sqlite3.Connection, settings: dict) -> int:
    cfg = settings['shadow_evaluation']
    fee_rate = float(cfg['round_trip_fee_rate'])
    minimum_closed = int(cfg['minimum_closed_trades'])
    minimum_pf = float(cfg['minimum_profit_factor'])
    train_fraction = float(cfg['train_fraction'])
    if not 0 < train_fraction < 1:
        raise ValueError('shadow_evaluation.train_fraction must be between 0 and 1')

    rows = conn.execute("""
      SELECT sr.symbol,o.setup_type,
        CAST(strftime('%H', CAST(sr.entry_time AS INTEGER)/1000, 'unixepoch') AS INTEGER) AS hour_utc,
        sr.entry_time,sr.r_multiple,tp.entry,tp.stop_loss
      FROM shadow_trade_results sr
      JOIN opportunities o ON o.id=sr.opportunity_id
      JOIN trade_plans tp ON tp.opportunity_id=sr.opportunity_id
      WHERE sr.status IN ('WON','STOPPED') AND sr.entry_triggered=1 AND sr.entry_time IS NOT NULL
      ORDER BY sr.entry_time
    """).fetchall()
    groups: dict[tuple[str, str, int], list[tuple[float, float]]] = defaultdict(list)
    asset_setup_groups: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        risk = float(row['entry']) - float(row['stop_loss'])
        if risk <= 0:
            continue
        # Fee is round-trip notional cost expressed in this plan's R units.
        fee_r = float(row['entry']) * fee_rate / risk
        result = (float(row['r_multiple']), fee_r)
        groups[(row['symbol'], row['setup_type'], int(row['hour_utc']))].append(result)
        asset_setup_groups[(row['symbol'], row['setup_type'])].append(result)

    refreshed_at = datetime.now(timezone.utc).isoformat()
    conn.execute('DELETE FROM shadow_edge_performance')
    conn.execute('DELETE FROM shadow_asset_setup_performance')
    for (symbol, setup_type, hour_utc), results in groups.items():
        split = max(1, int(len(results) * train_fraction))
        train, validation = results[:split], results[split:]
        gross_expectancy = sum(value for value, _ in results) / len(results)
        net_expectancy, net_pf, net_total = _metrics(results)
        train_expectancy, _, _ = _metrics(train)
        validation_expectancy, validation_pf, _ = _metrics(validation)
        approved = (
            len(results) >= minimum_closed
            and validation
            and (train_expectancy or 0) > 0
            and (validation_expectancy or 0) > 0
            and (validation_pf or 0) >= minimum_pf
        )
        status = 'APPROVED' if approved else ('WATCH' if (net_expectancy or 0) > 0 else 'BLOCKED')
        conn.execute("""
          INSERT INTO shadow_edge_performance(
            symbol,setup_type,hour_utc,closed_trades,train_trades,validation_trades,gross_expectancy_r,
            net_expectancy_r,net_profit_factor,net_total_r,train_net_expectancy_r,validation_net_expectancy_r,
            validation_net_profit_factor,status,refreshed_at
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (symbol, setup_type, hour_utc, len(results), len(train), len(validation), gross_expectancy,
              net_expectancy, net_pf, net_total, train_expectancy, validation_expectancy, validation_pf,
              status, refreshed_at))
    for (symbol, setup_type), results in asset_setup_groups.items():
        split = max(1, int(len(results) * train_fraction))
        train, validation = results[:split], results[split:]
        gross_expectancy = sum(value for value, _ in results) / len(results)
        net_expectancy, net_pf, net_total = _metrics(results)
        train_expectancy, _, _ = _metrics(train)
        validation_expectancy, validation_pf, _ = _metrics(validation)
        approved = (len(results) >= minimum_closed and validation and (train_expectancy or 0) > 0
                    and (validation_expectancy or 0) > 0 and (validation_pf or 0) >= minimum_pf)
        status = 'APPROVED' if approved else ('WATCH' if (net_expectancy or 0) > 0 else 'BLOCKED')
        conn.execute("""
          INSERT INTO shadow_asset_setup_performance(
            symbol,setup_type,closed_trades,train_trades,validation_trades,gross_expectancy_r,net_expectancy_r,
            net_profit_factor,net_total_r,train_net_expectancy_r,validation_net_expectancy_r,
            validation_net_profit_factor,status,refreshed_at
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (symbol, setup_type, len(results), len(train), len(validation), gross_expectancy, net_expectancy,
              net_pf, net_total, train_expectancy, validation_expectancy, validation_pf, status, refreshed_at))
    conn.commit()
    return len(groups) + len(asset_setup_groups)
