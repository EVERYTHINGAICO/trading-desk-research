#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from desk.config import load_settings, project_root
from desk.db import connect, init_db


def main() -> None:
    settings = load_settings()
    configs = (
        ('waterfall', 'waterfall-forward-v1', 'config/waterfall_v1.json', 'vega', 'FORWARD_SHADOW', 'INVALIDATED_LOOKAHEAD'),
        ('waterfall', 'waterfall-forward-v2', 'config/waterfall_v2.json', 'vega', 'FORWARD_SHADOW', 'FORWARD_SHADOW'),
        ('pedro-ultra', 'pedro-ultra-v1', 'config/pedro_ultra_v1.json', 'pedro-ultra', 'FORWARD_SHADOW', 'FORWARD_SHADOW'),
        ('pete-panic-dip', 'pete-panic-dip-v1', 'config/pete_panic_dip_v1.json', 'pete', 'FORWARD_SHADOW', 'FORWARD_SHADOW'),
        ('reverse-waterfall', 'reverse-waterfall-forward-v1', 'config/reverse_waterfall_config.yaml', 'pedro-ultra', 'FORWARD_SHADOW', 'FORWARD_SHADOW'),
        ('reverse-waterfall-demo-canary', 'reverse-waterfall-demo-canary-v1', 'config/reverse_waterfall_demo_canary_v1.json', 'mercury', 'BINANCE_DEMO', 'RESEARCH'),
    )
    conn = connect(project_root() / settings['db_path'])
    init_db(conn)
    for strategy_id, version, relative, owner, environment, state in configs:
        raw = (ROOT / relative).read_bytes()
        conn.execute(
            """INSERT OR IGNORE INTO strategy_registry(strategy_id,version,config_hash,config_json,owner_agent_id,environment,promotion_state)
               VALUES(?,?,?,?,?,?,?)""",
            (strategy_id, version, hashlib.sha256(raw).hexdigest(), json.dumps(json.loads(raw), sort_keys=True), owner, environment, state),
        )
        conn.execute(
            "UPDATE strategy_registry SET promotion_state=?,updated_at=CURRENT_TIMESTAMP WHERE strategy_id=? AND version=? AND config_hash=?",
            (state, strategy_id, version, hashlib.sha256(raw).hexdigest()),
        )
    rollout_path = ROOT / 'config' / 'demo_strategy_rollout.json'
    rollout = json.loads(rollout_path.read_text())
    for strategy_id, enrollment in rollout.get('strategies', {}).items():
        source_version = enrollment['source_version']
        source = conn.execute(
            'SELECT config_json FROM strategy_registry WHERE version=? ORDER BY updated_at DESC LIMIT 1',
            (source_version,),
        ).fetchone()
        if not source:
            continue
        demo_config = {
            'source_version': source_version,
            'source_config': json.loads(source['config_json']),
            'demo_limits': {key: value for key, value in enrollment.items() if key not in {'source_version'}},
        }
        raw_demo = json.dumps(demo_config, sort_keys=True, separators=(',', ':')).encode()
        demo_hash = hashlib.sha256(raw_demo).hexdigest()
        conn.execute(
            """INSERT OR IGNORE INTO strategy_registry(strategy_id,version,config_hash,config_json,owner_agent_id,environment,promotion_state)
               VALUES(?,?,?,?,?,'BINANCE_DEMO','DEMO_CANARY')""",
            (strategy_id, enrollment['version'], demo_hash, raw_demo.decode(), strategy_id),
        )
        conn.execute(
            "UPDATE strategy_registry SET promotion_state='DEMO_CANARY',updated_at=CURRENT_TIMESTAMP WHERE strategy_id=? AND version=? AND config_hash=?",
            (strategy_id, enrollment['version'], demo_hash),
        )
    long_cfg = settings['long_v1']
    raw = json.dumps(long_cfg, sort_keys=True, separators=(',', ':')).encode()
    conn.execute(
        """INSERT OR IGNORE INTO strategy_registry(strategy_id,version,config_hash,config_json,owner_agent_id,environment,promotion_state)
           VALUES('long-v1',?,?,?,?, 'BINANCE_DEMO','DEMO_ACTIVE')""",
        (long_cfg['strategy_version'], hashlib.sha256(raw).hexdigest(), json.dumps(long_cfg, sort_keys=True), 'orion'),
    )
    conn.commit()
    print(json.dumps({'strategies': conn.execute('SELECT COUNT(*) FROM strategy_registry').fetchone()[0]}))


if __name__ == '__main__':
    main()
