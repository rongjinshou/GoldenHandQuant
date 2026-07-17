"""因子衰减分析测试。"""

from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.decay_analyzer import DecayAnalyzer
from src.domain.strategy.factor_test.expressions import FactorRefExpr


def _make_snapshot(symbol: str, pe_ratio: float) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pe_ratio=pe_ratio,
    )


class TestDecayAnalyzer:
    def test_basic_decay(self):
        analyzer = DecayAnalyzer()
        expr = FactorRefExpr(field_name="pe_ratio")

        # 10 个交易日的数据
        dates = [f"2024-01-{d:02d}" for d in range(1, 21)]
        snapshots_by_date = {}
        prices_by_date = {}

        for date_str in dates:
            snapshots_by_date[date_str] = [
                _make_snapshot(f"S{i}", float(i + 1)) for i in range(5)
            ]
            prices_by_date[date_str] = {f"S{i}": 10.0 + i for i in range(5)}

        periods, decay_ics = analyzer.analyze(
            expr, snapshots_by_date, prices_by_date, holding_periods=[1, 5]
        )
        assert periods == [1, 5]
        assert len(decay_ics) == 2

    def test_default_periods(self):
        analyzer = DecayAnalyzer()
        expr = FactorRefExpr(field_name="pe_ratio")

        dates = [f"2024-01-{d:02d}" for d in range(1, 31)]
        snapshots_by_date = {}
        prices_by_date = {}
        for date_str in dates:
            snapshots_by_date[date_str] = [_make_snapshot("A", 10.0)]
            prices_by_date[date_str] = {"A": 10.0}

        periods, decay_ics = analyzer.analyze(expr, snapshots_by_date, prices_by_date)
        assert periods == [1, 5, 10, 20, 60]
        assert len(decay_ics) == 5
