import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from import_pre_ny_review import normalize


def test_pre_ny_contract_caps_plans_and_validates_probabilities():
    payload = {
        'scenario_map': {
            'base': {'probability': 50},
            'bull': {'probability': 30},
            'bear': {'probability': 20},
        },
        'plans': [
            {'direction': 'LONG', 'status': 'WAIT'},
            {'direction': 'SHORT', 'status': 'READY'},
            {'direction': 'NONE', 'status': 'NO_TRADE'},
            {'direction': 'LONG', 'status': 'WAIT'},
        ],
    }
    normalized = normalize(payload)
    assert normalized['probabilities'] == [50.0, 30.0, 20.0]
    assert len(normalized['plans']) == 3
