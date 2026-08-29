from desk.asset_performance import hierarchy_sort_key


def by_hierarchy(winners, losers, rows):
    return [symbol for symbol, _ in sorted(rows, key=lambda r: hierarchy_sort_key(winners, losers, r[0], r[1]))]


def test_winners_before_losers_before_unranked():
    winners, losers = {"BTCUSDT": 1, "ETHUSDT": 2}, {"BADUSDT": 1}
    rows = [("BADUSDT", 5), ("XXXUSDT", 9), ("ETHUSDT", 3), ("BTCUSDT", 1)]
    assert by_hierarchy(winners, losers, rows) == ["BTCUSDT", "ETHUSDT", "BADUSDT", "XXXUSDT"]


def test_rank_ascending_within_group():
    out = by_hierarchy({"Z": 3, "A": 1}, {}, [("Z", 0), ("A", 0)])
    assert out == ["A", "Z"]


def test_unranked_fallback_keeps_id_order():
    out = by_hierarchy({}, {}, [("B", 99), ("A", 7)])
    assert out == ["A", "B"]


def test_loser_before_unranked_even_with_high_rank():
    out = by_hierarchy({}, {"L": 100}, [("U", 1), ("L", 50)])
    assert out == ["L", "U"]