"""MinedFactor 适配器单元测试。"""

from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.mined_factor import MinedFactor


def _make_snapshot(symbol: str, dt: datetime | None = None) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol,
        date=dt or datetime(2024, 6, 15),
        open=10.0, high=11.0, low=9.0, close=10.5,
        volume=100000.0, name=f"Stock {symbol}",
        list_date=datetime(2000, 1, 1),
        market_cap=1e10,
    )


class TestMinedFactor:
    def test_compute_returns_correct_values(self):
        values = {
            "2024-06-15": {"000001": 0.5, "000002": 0.3},
        }
        factor = MinedFactor(name="test", values_by_date=values)
        snapshots = [_make_snapshot("000001"), _make_snapshot("000002")]
        result = factor.compute(snapshots)
        assert result == {"000001": 0.5, "000002": 0.3}

    def test_compute_returns_empty_for_missing_date(self):
        values = {"2024-06-16": {"000001": 0.5}}
        factor = MinedFactor(name="test", values_by_date=values)
        snapshots = [_make_snapshot("000001")]
        result = factor.compute(snapshots)
        assert result == {}

    def test_compute_returns_empty_for_empty_snapshots(self):
        factor = MinedFactor(name="test", values_by_date={})
        result = factor.compute([])
        assert result == {}

    def test_compute_skips_missing_symbols(self):
        values = {"2024-06-15": {"000001": 0.5}}
        factor = MinedFactor(name="test", values_by_date=values)
        snapshots = [_make_snapshot("000001"), _make_snapshot("000003")]
        result = factor.compute(snapshots)
        assert result == {"000001": 0.5}

    def test_satisfies_factor_protocol(self):
        """MinedFactor 应满足 Factor Protocol (duck typing)。"""
        factor = MinedFactor(name="test", values_by_date={})
        assert hasattr(factor, "name")
        assert hasattr(factor, "compute")
        assert callable(factor.compute)

    def test_inverted_attribute(self):
        factor = MinedFactor(name="test", values_by_date={}, inverted=True)
        assert factor.inverted is True
        factor2 = MinedFactor(name="test", values_by_date={}, inverted=False)
        assert factor2.inverted is False
