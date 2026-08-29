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

SCRIPTS = ROOT / 'scripts'


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def build_jobs(settings: dict) -> list[dict[str, object]]:
    scheduler = settings['scheduler']
    return [
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
            'name': 'binance_demo_executor',
            'script': 'run_binance_demo_once.py',
            'interval_seconds': int(scheduler.get('demo_executor_every_seconds', 300)),
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
            'name': 'binance_manual_protection_watcher',
            'script': 'manual_protection_watcher_once.py',
            'interval_seconds': int(scheduler.get('demo_manual_protection_every_seconds', 15)),
        },
        {
            'name': 'telegram_responder',
            'script': 'telegram_poller_once.py',
            'interval_seconds': int(scheduler.get('telegram_responder_every_seconds', 20)),
        },
    ]


def write_heartbeat(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


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
            (exc.stdout or ''),
            f'timeout after {timeout_seconds}s',
        )


def execute_due_jobs(
    jobs: list[dict[str, object]],
    last_run: dict[str, float],
    heartbeat_path: Path,
    job_timeout_seconds: int,
) -> bool:
    now_ts = time.time()
    cycle_ran = False
    for job in jobs:
        name = str(job['name'])
        interval_seconds = int(job['interval_seconds'])
        if now_ts - last_run.get(name, 0.0) < interval_seconds:
            continue

        cycle_ran = True
        started_at = iso_now()
        result = run_job(str(job['script']), job_timeout_seconds)
        finished_at = iso_now()
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    root = project_root()
    scheduler = settings['scheduler']
    heartbeat_path = root / scheduler['heartbeat_path']
    lock_path = root / scheduler['lock_path']
    job_timeout_seconds = int(scheduler['job_timeout_seconds'])
    loop_sleep_seconds = int(scheduler['loop_sleep_seconds'])
    jobs = build_jobs(settings)

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
            execute_due_jobs(jobs, last_run, heartbeat_path, job_timeout_seconds)
            return

        while True:
            ran_any = execute_due_jobs(jobs, last_run, heartbeat_path, job_timeout_seconds)
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
