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

    def test_rebalance_days_passed_through_and_recorded(self):
        """rebalance_days 应传入分层回测并记录在报告中。

        构造: 第2日因子排名翻转 → 日频重排吃到 +10%, 持有2日反向吃 -10%。
        """
        runner = FactorTestRunner()

        snapshots_by_date = {
            "2024-01-01": [_make_snapshot("A", 1.0), _make_snapshot("B", 2.0),
                           _make_snapshot("C", 3.0), _make_snapshot("D", 4.0)],
            "2024-01-02": [_make_snapshot("A", 4.0), _make_snapshot("B", 3.0),
                           _make_snapshot("C", 2.0), _make_snapshot("D", 1.0)],
        }
        # 按实现日键入 (引擎 next_date 约定)
        returns_by_date = {
            "2024-01-02": {"A": 0.001, "B": 0.002, "C": 0.001, "D": 0.002},
            "2024-01-03": {"A": 0.10, "B": 0.10, "C": -0.10, "D": -0.10},
        }
        prices_by_date = {
            "2024-01-01": {s: 10.0 for s in "ABCD"},
            "2024-01-02": {s: 10.0 for s in "ABCD"},
        }

        daily = runner.run(
            expression_str="pe_ratio",
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=("2024-01-01", "2024-01-02"),
            num_layers=2,
        )
        hold = runner.run(
            expression_str="pe_ratio",
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=("2024-01-01", "2024-01-02"),
            num_layers=2,
            rebalance_days=2,
        )

        assert daily.report.rebalance_days == 1
        assert hold.report.rebalance_days == 2
        assert hold.rebalance_days == 2  # ScoredFactorTestReport 代理属性
        # 行为差异: 日频多空为正, 持有2日多空为负
        assert daily.report.long_short_return > 0
        assert hold.report.long_short_return < 0

    def test_long_only_populates_top_excess(self):
        """objective=long_only 时 report 携带 Top 超额, 代理属性可达。"""
        runner = FactorTestRunner()
        dates = [f"2024-01-{d:02d}" for d in range(1, 8)]
        snapshots_by_date, returns_by_date, prices_by_date = {}, {}, {}
        for date_str in dates:
            snapshots_by_date[date_str] = [_make_snapshot(f"S{i}", float(i + 1)) for i in range(10)]
            prices_by_date[date_str] = {f"S{i}": 10.0 for i in range(10)}
        # 高 pe 收益更高 → Top 层跑赢等权基准
        # 各日同序、量级不同 → Top 持续跑赢但超额量级变化 → excess_ir 有意义(对称扣成本下
        # 恒定收益会使超额恒定→IR=0, 见 L4 修复)
        scales = [1.0, 1.4, 0.8, 1.2, 0.9, 1.3]
        for i in range(len(dates) - 1):
            returns_by_date[dates[i]] = {f"S{j}": 0.005 * (j + 1) * scales[i] for j in range(10)}

        scored = runner.run(
            expression_str="pe_ratio",
            snapshots_by_date=snapshots_by_date,
            returns_by_date=returns_by_date,
            prices_by_date=prices_by_date,
            test_period=("2024-01-01", "2024-01-07"),
            num_layers=5,
            objective="long_only",
        )
        assert scored.report.top_excess_return > 0
        assert scored.top_excess_return == scored.report.top_excess_return  # 代理属性
        assert scored.excess_ir > 0

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
