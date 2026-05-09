from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.low_volatility_factor import LowVolatilityFactor


def _make_snapshot(symbol: str, vol: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, volatility_20d=vol,
    )


class TestLowVolatilityFactor:
    def test_compute_returns_raw_volatility(self):
        factor = LowVolatilityFactor()
        snapshots = [_make_snapshot("A", vol=0.02), _make_snapshot("B", vol=0.05)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.02
        assert raw["B"] == 0.05

    def test_compute_skips_none(self):
        factor = LowVolatilityFactor()
        snapshots = [_make_snapshot("A", vol=None)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
