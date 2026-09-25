#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
sys.path.insert(0, str(SRC))

from desk.config import load_settings, project_root
from desk.db import connect, init_db

SCRIPTS = ROOT / 'scripts'


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


FAST_JOBS = {'waterfall_v2_forward_shadow', 'reverse_waterfall_forward_shadow', 'pedro_ultra_forward_shadow', 'lumen_data_freshness'}
RETIRED_JOBS = {'waterfall_forward_shadow'}
RISK_JOBS = {'binance_demo_reconcile'}
MONITOR_JOBS = {'binance_demo_monitor'}
PROTECTION_JOBS = {'binance_manual_protection_watcher'}


def build_jobs(settings: dict, profile: str = 'slow') -> list[dict[str, object]]:
    scheduler = settings['scheduler']
    jobs = [
        {
            'name': 'broad_scan',
            'script': 'run_shadow_once.py',
            'interval_seconds': int(scheduler['scan_every_seconds']),
        },
        {
            'name': 'ai_review_queue_export',
            'script': 'export_ai_review_queue.py',
            'interval_seconds': int(scheduler.get('ai_review_queue_every_seconds', 3600)),
        },
        {
            'name': 'pre_ny_context_export',
            'script': 'export_pre_ny_context.py',
            'interval_seconds': int(scheduler.get('pre_ny_context_every_seconds', 3600)),
        },
        {
            'name': 'pre_ny_review_import',
            'script': 'import_pre_ny_review.py',
            'interval_seconds': int(scheduler.get('pre_ny_import_every_seconds', 60)),
        },
        {
            'name': 'quality_stock_dip_context_export',
            'script': 'export_quality_stock_dip_context.py',
            'interval_seconds': int(scheduler.get('quality_stock_dip_context_every_seconds', 3600)),
        },
        {
            'name': 'quality_stock_dip_review_import',
            'script': 'import_quality_stock_dip_review.py',
            'interval_seconds': int(scheduler.get('quality_stock_dip_import_every_seconds', 60)),
        },
        {
            'name': 'quality_stock_dip_resolver',
            'script': 'resolve_quality_stock_dip.py',
            'interval_seconds': int(scheduler.get('quality_stock_dip_resolve_every_seconds', 3600)),
        },
        {
            'name': 'trigger_monitor',
            'script': 'run_trigger_monitor_once.py',
            'interval_seconds': int(scheduler['trigger_monitor_every_seconds']),
        },
        {
            'name': 'stateful_open_monitor',
            'script': 'run_stateful_open_monitor_once.py',
            'interval_seconds': int(scheduler['stateful_open_monitor_every_seconds']),
        },
        {
            'name': 'shadow_resolver',
            'script': 'resolve_shadow_open_trades.py',
            'interval_seconds': int(scheduler['resolve_every_seconds']),
        },
        {
            'name': 'shadow_asset_performance_refresh',
            'script': 'refresh_shadow_asset_performance.py',
            'interval_seconds': int(scheduler.get('asset_performance_every_seconds', 3600)),
        },
        {
            'name': 'shadow_hour_performance_refresh',
            'script': 'refresh_shadow_hour_performance.py',
            'interval_seconds': int(scheduler.get('hour_performance_every_seconds', 3600)),
        },
        {
            'name': 'shadow_edge_performance_refresh',
            'script': 'refresh_shadow_edge_performance.py',
            'interval_seconds': int(scheduler.get('edge_performance_every_seconds', 3600)),
        },
        {
            'name': 'waterfall_forward_shadow',
            'script': 'run_waterfall_forward_shadow_once.py',
            'interval_seconds': int(scheduler.get('waterfall_forward_shadow_every_seconds', 60)),
        },
        {
            'name': 'waterfall_v2_forward_shadow',
            'script': 'run_waterfall_v2_forward_shadow_once.py',
            'interval_seconds': int(scheduler.get('waterfall_v2_forward_shadow_every_seconds', 15)),
        },
        {
            'name': 'reverse_waterfall_forward_shadow',
            'script': 'run_reverse_waterfall_forward_shadow_once.py',
            'interval_seconds': int(scheduler.get('reverse_waterfall_forward_shadow_every_seconds', 15)),
        },
        {
            'name': 'waterfall_report',
            'script': 'generate_waterfall_report.py',
            'interval_seconds': int(scheduler.get('waterfall_report_every_seconds', 3600)),
        },
        {
            'name': 'reverse_waterfall_report',
            'script': 'generate_reverse_waterfall_report.py',
            'interval_seconds': int(scheduler.get('reverse_waterfall_report_every_seconds', 3600)),
        },
        {
            'name': 'reverse_waterfall_validation',
            'script': 'generate_reverse_waterfall_validation.py',
            'interval_seconds': int(scheduler.get('reverse_waterfall_validation_every_seconds', 3600)),
        },
        {
            'name': 'nova_waterfall_v2_validation',
            'script': 'run_nova_waterfall_v2_once.py',
            'interval_seconds': int(scheduler.get('nova_waterfall_v2_validation_every_seconds', 3600)),
        },
        {
            'name': 'desk_agent_sync',
            'script': 'sync_desk_agents_once.py',
            'interval_seconds': int(scheduler.get('desk_agent_sync_every_seconds', 60)),
        },
        {
            'name': 'reymon_incident_detection',
            'script': 'detect_reymon_incidents.py',
            'interval_seconds': int(scheduler.get('reymon_incident_detection_every_seconds', 300)),
        },
        {
            'name': 'strategy_registry_sync',
            'script': 'sync_strategy_registry_once.py',
            'interval_seconds': int(scheduler.get('strategy_registry_sync_every_seconds', 3600)),
        },
        {
            'name': 'pedro_ultra_forward_shadow',
            'script': 'run_pedro_ultra_shadow_once.py',
            'interval_seconds': int(scheduler.get('pedro_ultra_forward_shadow_every_seconds', 60)),
        },
        {
            'name': 'lumen_data_freshness',
            'script': 'check_data_freshness_once.py',
            'interval_seconds': int(scheduler.get('lumen_freshness_every_seconds', 15)),
        },
        {
            'name': 'pete_panic_dip',
            'script': 'run_pete_panic_dip_once.py',
            'interval_seconds': int(scheduler.get('pete_panic_dip_every_seconds', 21600)),
        },
        {
            'name': 'binance_demo_executor',
            'script': 'run_binance_demo_once.py',
            'interval_seconds': int(scheduler.get('demo_executor_every_seconds', 300)),
        },
        {
            'name': 'multi_strategy_demo_canary',
            'script': 'run_multi_strategy_demo_once.py',
            'interval_seconds': int(scheduler.get('multi_strategy_demo_every_seconds', 60)),
        },
        {
            'name': 'binance_demo_monitor',
            'script': 'monitor_binance_demo_once.py',
            'interval_seconds': int(scheduler.get('demo_monitor_every_seconds', 15)),
        },
        {
            'name': 'binance_demo_reconcile',
            'script': 'reconcile_binance_demo.py',
            'interval_seconds': int(scheduler.get('demo_reconcile_every_seconds', 15)),
        },
        {
            'name': 'binance_demo_history_sync',
            'script': 'sync_binance_demo_history_once.py',
            'interval_seconds': int(scheduler.get('demo_history_sync_every_seconds', 900)),
        },
        {
            'name': 'binance_demo_performance_report',
            'script': 'generate_demo_performance_report.py',
            'interval_seconds': int(scheduler.get('demo_performance_report_every_seconds', 900)),
        },
        {
            'name': 'binance_manual_protection_watcher',
            'script': 'manual_protection_watcher_once.py',
            'interval_seconds': int(scheduler.get('demo_manual_protection_every_seconds', 15)),
        },
    ]
    selected = FAST_JOBS if profile == 'fast' else RISK_JOBS if profile == 'risk' else MONITOR_JOBS if profile == 'monitor' else PROTECTION_JOBS if profile == 'protection' else {str(job['name']) for job in jobs} - FAST_JOBS - RISK_JOBS - MONITOR_JOBS - PROTECTION_JOBS - RETIRED_JOBS
    return [job for job in jobs if job['name'] in selected]


def write_heartbeat(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    tmp_path.replace(path)


def _process_text(value: str | bytes | None) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode(errors='replace')
    return value


def remove_stale_lock(lock_path: Path) -> None:
    if not lock_path.exists():
        return
    try:
        lock_pid = int(lock_path.read_text().strip())
        if lock_pid == os.getpid():
            lock_path.unlink(missing_ok=True)
            return
        os.kill(lock_pid, 0)
    except (OSError, ValueError):
        lock_path.unlink(missing_ok=True)


def run_job(script: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    path = SCRIPTS / script
    try:
        return subprocess.run(
            ['python3', str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            ['python3', str(path)],
            124,
            _process_text(exc.stdout),
            f'timeout after {timeout_seconds}s',
        )


def execute_due_jobs(
    jobs: list[dict[str, object]],
    last_run: dict[str, float],
    heartbeat_path: Path,
    job_timeout_seconds: int,
    runtime_profile: str = 'slow',
) -> bool:
    now_ts = time.time()
    cycle_ran = False
    for job in jobs:
        name = str(job['name'])
        interval_seconds = int(job['interval_seconds'])
        if now_ts - last_run.get(name, 0.0) < interval_seconds:
            continue

        cycle_ran = True
        previous_ts = last_run.get(name, 0.0)
        expected_ts = previous_ts + interval_seconds if previous_ts else now_ts
        started_ts = time.time()
        started_at = datetime.fromtimestamp(started_ts, timezone.utc).isoformat()
        result = run_job(str(job['script']), job_timeout_seconds)
        finished_ts = time.time()
        finished_at = datetime.fromtimestamp(finished_ts, timezone.utc).isoformat()
        heartbeat = {
            'scheduler_state': 'ok' if result.returncode == 0 else 'degraded',
            'last_job': name,
            'last_script': job['script'],
            'started_at_utc': started_at,
            'finished_at_utc': finished_at,
            'returncode': result.returncode,
            'stdout_tail': result.stdout.strip().splitlines()[-20:],
            'stderr_tail': result.stderr.strip().splitlines()[-20:],
            'job_intervals_seconds': {
                str(item['name']): int(item['interval_seconds'])
                for item in jobs
            },
        }
        write_heartbeat(heartbeat_path, heartbeat)
        try:
            conn = connect(project_root() / load_settings()['db_path'])
            init_db(conn)
            conn.execute(
                """INSERT OR IGNORE INTO runtime_job_runs(runtime_profile,job_name,expected_at,started_at,finished_at,
                   delay_seconds,duration_seconds,returncode,error) VALUES(?,?,?,?,?,?,?,?,?)""",
                (runtime_profile, name, datetime.fromtimestamp(expected_ts, timezone.utc).isoformat(), started_at,
                 finished_at, max(0.0, started_ts - expected_ts), finished_ts - started_ts, result.returncode,
                 result.stderr[-2000:] or None),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            print(f"[{finished_at}] {name}: telemetry failed: {exc}", file=sys.stderr)

        if result.returncode == 0:
            print(f"[{finished_at}] {name}: ok")
        else:
            print(f"[{finished_at}] {name}: failed rc={result.returncode}", file=sys.stderr)
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)

        last_run[name] = now_ts
    return cycle_ran


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the local shadow-desk scheduler loop.')
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run all due jobs once, write heartbeat status, then exit.',
    )
    parser.add_argument('--profile', choices=('slow', 'fast', 'risk', 'monitor', 'protection'), default='slow')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    root = project_root()
    scheduler = settings['scheduler']
    profile = args.profile
    heartbeat_path = root / ('data/scheduler_heartbeat.json' if profile == 'slow' else f'data/{profile}_runtime_heartbeat.json')
    lock_path = root / ('data/scheduler.lock' if profile == 'slow' else f'data/{profile}_runtime.lock')
    job_timeout_seconds = int(scheduler['job_timeout_seconds'])
    loop_sleep_seconds = int(scheduler['loop_sleep_seconds'])
    jobs = build_jobs(settings, profile)

    last_run = {str(job['name']): 0.0 for job in jobs}

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    remove_stale_lock(lock_path)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f'scheduler already running: {lock_path}', file=sys.stderr)
        return
    os.write(lock_fd, str(os.getpid()).encode())
    os.close(lock_fd)

    try:
        if args.once:
            execute_due_jobs(jobs, last_run, heartbeat_path, job_timeout_seconds, profile)
            return

        while True:
            ran_any = execute_due_jobs(jobs, last_run, heartbeat_path, job_timeout_seconds, profile)
            if not ran_any:
                write_heartbeat(
                    heartbeat_path,
                    {
                        'scheduler_state': 'idle',
                        'checked_at_utc': iso_now(),
                        'job_intervals_seconds': {
                            str(item['name']): int(item['interval_seconds'])
                            for item in jobs
                        },
                    },
                )
            time.sleep(loop_sleep_seconds)
    finally:
        lock_path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
