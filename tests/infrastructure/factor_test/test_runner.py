"""TestRunner 编排器集成测试。"""

from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.infrastructure.factor_test.test_runner import FactorTestRunner


def _make_snapshot(symbol: str, pe_ratio: float, earnings_growth: float = 0.0) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pe_ratio=pe_ratio, earnings_growth=earnings_growth,
    )


class TestFactorTestRunner:
    def test_simple_expression(self):
        runner = FactorTestRunner()

        dates = [f"2024-01-{d:02d}" for d in range(1, 11)]
        snapshots_by_date = {}
        returns_by_date = {}
        prices_by_date = {}

        for i, date_str in enumerate(dates):
            snapshots_by_date[date_str] = [
                _make_snapshot("A", 10.0, 0.1),
                _make_snapshot("B", 20.0, 0.2),
                _make_snapshot("C", 30.0, 0.3),
            ]
            prices_by_date[date_str] = {"A": 10.0 + i, "B": 20.0 + i, "C": 30.0 + i}

        for i in range(len(dates) - 1):
            d0, d1 = dates[i], dates[i + 1]
            p0, p1 = prices_by_date[d0], prices_by_date[d1]
            returns_by_date[d0] = {
                sym: p1[sym] / p0[sym] - 1 for sym in p0 if sym in p1
            }

        report = runner.run(
            expression_str="pe_ratio",
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=("2024-01-01", "2024-01-10"),
            num_layers=3,
        )

        assert report.expression == "pe_ratio"
        assert report.test_period == ("2024-01-01", "2024-01-10")
        assert report.layer_count == 3
        assert len(report.layer_returns) == 3
        assert 0 <= report.score <= 100
        assert report.grade in ("A", "B", "C", "D")
        assert len(report.grade_reasons) == 5
        assert report.universe_count > 0

    def test_composite_expression(self):
        runner = FactorTestRunner()

        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        snapshots_by_date = {}
        returns_by_date = {}
        prices_by_date = {}

        for i, date_str in enumerate(dates):
            snapshots_by_date[date_str] = [
                _make_snapshot("A", 10.0, 0.05),
                _make_snapshot("B", 20.0, 0.10),
                _make_snapshot("C", 30.0, 0.15),
                _make_snapshot("D", 40.0, 0.20),
                _make_snapshot("E", 50.0, 0.25),
            ]
            prices_by_date[date_str] = {f"{s}": 10.0 + i for s in "ABCDE"}

        for i in range(len(dates) - 1):
            d0, d1 = dates[i], dates[i + 1]
            p0, p1 = prices_by_date[d0], prices_by_date[d1]
            returns_by_date[d0] = {sym: p1[sym] / p0[sym] - 1 for sym in p0 if sym in p1}

        report = runner.run(
            expression_str="earnings_growth / pe_ratio",
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=("2024-01-01", "2024-01-03"),
        )
        assert report.expression == "earnings_growth / pe_ratio"
        assert 0 <= report.score <= 100

    def test_rank_expression(self):
        runner = FactorTestRunner()

        dates = ["2024-01-01", "2024-01-02"]
        snapshots_by_date = {
            d: [_make_snapshot(f"S{i}", float(i + 1)) for i in range(5)]
            for d in dates
        }
        prices_by_date = {
            d: {f"S{i}": 10.0 for i in range(5)}
            for d in dates
        }
        returns_by_date = {"2024-01-01": {f"S{i}": 0.01 * (i + 1) for i in range(5)}}

        report = runner.run(
            expression_str="rank(pe_ratio)",
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=("2024-01-01", "2024-01-02"),
        )
        assert report.expression == "rank(pe_ratio)"
