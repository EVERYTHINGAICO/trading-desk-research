import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from desk import telegram_alerts


def test_sent_error_is_not_delivered_twice(monkeypatch):
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE demo_alert_deliveries(error_id INTEGER,channel TEXT,status TEXT)')
    conn.execute("INSERT INTO demo_alert_deliveries VALUES(1,'telegram','SENT')")
    monkeypatch.setattr(telegram_alerts, '_token', lambda: (_ for _ in ()).throw(AssertionError('must not send')))
    telegram_alerts.notify_error({'symbol': 'X'}, error_id=1, conn=conn)
