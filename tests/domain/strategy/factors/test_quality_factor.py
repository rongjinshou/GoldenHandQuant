from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.quality_factor import ROEQualityFactor


def _make_snapshot(symbol: str, roe: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, roe_ttm=roe,
    )


class TestROEQualityFactor:
    def test_compute_returns_raw_roe(self):
        factor = ROEQualityFactor()
        snapshots = [_make_snapshot("A", roe=0.15), _make_snapshot("B", roe=0.08)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 0.15
        assert raw["B"] == 0.08

    def test_compute_skips_none_roe(self):
        factor = ROEQualityFactor()
        snapshots = [_make_snapshot("A", roe=0.15), _make_snapshot("B", roe=None)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_skips_negative_roe(self):
        factor = ROEQualityFactor()
        snapshots = [_make_snapshot("A", roe=-0.05)]
        raw = factor.compute(snapshots)
        assert "A" not in raw
