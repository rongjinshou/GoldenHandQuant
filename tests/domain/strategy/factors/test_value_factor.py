from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.value_factor import PBValueFactor, PEValueFactor


def _make_snapshot(symbol: str, pb: float | None = None, pe: float | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name="test", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pb_ratio=pb, pe_ratio=pe,
    )


class TestPBValueFactor:
    def test_compute_returns_raw_pb_values(self):
        factor = PBValueFactor()
        snapshots = [_make_snapshot("A", pb=1.0), _make_snapshot("B", pb=3.0), _make_snapshot("C", pb=2.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 1.0
        assert raw["B"] == 3.0
        assert raw["C"] == 2.0

    def test_compute_skips_none_pb(self):
        factor = PBValueFactor()
        snapshots = [_make_snapshot("A", pb=1.0), _make_snapshot("B", pb=None)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw

    def test_compute_empty(self):
        factor = PBValueFactor()
        assert factor.compute([]) == {}


class TestPEValueFactor:
    def test_compute_returns_raw_pe_values(self):
        factor = PEValueFactor()
        snapshots = [_make_snapshot("A", pe=10.0), _make_snapshot("B", pe=30.0), _make_snapshot("C", pe=20.0)]
        raw = factor.compute(snapshots)
        assert raw["A"] == 10.0
        assert raw["B"] == 30.0

    def test_compute_skips_negative_pe(self):
        factor = PEValueFactor()
        snapshots = [_make_snapshot("A", pe=10.0), _make_snapshot("B", pe=-5.0)]
        raw = factor.compute(snapshots)
        assert "A" in raw
        assert "B" not in raw
