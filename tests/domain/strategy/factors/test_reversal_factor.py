from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.reversal_factor import ReversalFactor


def _make_snapshot(symbol: str, return_20d: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, return_20d=return_20d,
    )


class TestReversalFactor:
    def test_compute_returns_raw_return(self):
        factor = ReversalFactor()
        snapshots = [_make_snapshot("A", return_20d=0.10), _make_snapshot("B", return_20d=-0.05)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.10
        assert raw["B"] == -0.05

    def test_compute_skips_none(self):
        factor = ReversalFactor()
        snapshots = [_make_snapshot("A", return_20d=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
