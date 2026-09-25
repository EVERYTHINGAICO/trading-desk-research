import json
import sys
from pathlib import Path
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from desk import market


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps({'ok': True}).encode()


def test_get_json_retries_transient_tls_error(monkeypatch):
    attempts = []

    def open_url(*_args, **_kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise URLError('TLS/SSL connection has been closed (EOF)')
        return Response()

    monkeypatch.setattr(market, 'urlopen', open_url)
    monkeypatch.setattr(market.time, 'sleep', lambda _: None)

    assert market._get_json('/test', {}) == {'ok': True}
    assert len(attempts) == 3
