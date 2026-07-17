"""IC 计算器测试。"""

from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.expressions import FactorRefExpr
from src.domain.strategy.factor_test.ic_calculator import ICCalculator, _rankdata


def _make_snapshot(symbol: str, pe_ratio: float, close: float = 10.0) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=close, high=close, low=close, close=close, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pe_ratio=pe_ratio,
    )


class TestRankdata:
    def test_basic_ranking(self):
        import numpy as np
        arr = np.array([3.0, 1.0, 2.0])
        result = _rankdata(arr)
        assert result[0] == 3.0  # 最大，排名 3
        assert result[1] == 1.0  # 最小，排名 1
        assert result[2] == 2.0

    def test_ties(self):
        import numpy as np
        arr = np.array([5.0, 5.0, 1.0])
        result = _rankdata(arr)
        # sorted: 1.0(rank1), 5.0(rank2), 5.0(rank3) → 5.0s get avg rank (2+3)/2=2.5
        assert result[0] == 2.5
        assert result[1] == 2.5
        assert result[2] == 1.0


class TestSpearmanCorrelation:
    def test_perfect_positive(self):
        x = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        y = {"A": 10.0, "B": 20.0, "C": 30.0, "D": 40.0}
        corr = ICCalculator._spearman_rank_correlation(x, y)
        assert abs(corr - 1.0) < 1e-10

    def test_perfect_negative(self):
        x = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        y = {"A": 40.0, "B": 30.0, "C": 20.0, "D": 10.0}
        corr = ICCalculator._spearman_rank_correlation(x, y)
        assert abs(corr - (-1.0)) < 1e-10

    def test_no_correlation(self):
        x = {"A": 1.0, "B": 2.0, "C": 3.0}
        y = {"A": 2.0, "B": 2.0, "C": 2.0}
        corr = ICCalculator._spearman_rank_correlation(x, y)
        assert corr == 0.0

    def test_insufficient_data(self):
        x = {"A": 1.0, "B": 2.0}
        y = {"A": 10.0, "B": 20.0}
        corr = ICCalculator._spearman_rank_correlation(x, y)
        assert corr == 0.0

    def test_only_common_keys(self):
        x = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        y = {"A": 10.0, "B": 20.0, "C": 30.0, "E": 99.0}
        corr = ICCalculator._spearman_rank_correlation(x, y)
        assert abs(corr - 1.0) < 1e-10


class TestICCalculator:
    def test_calculate_ir(self):
        calc = ICCalculator()
        ic_series = [0.05, 0.03, -0.02, 0.04, 0.01]
        mean, std, ir = calc.calculate_ir(ic_series)
        assert abs(mean - 0.022) < 1e-6
        assert std > 0
        assert abs(ir - mean / std) < 1e-6

    def test_calculate_ir_empty(self):
        calc = ICCalculator()
        mean, std, ir = calc.calculate_ir([])
        assert mean == 0.0
        assert std == 0.0
        assert ir == 0.0

    def test_calculate_ic_series(self):
        calc = ICCalculator()
        expr = FactorRefExpr(field_name="pe_ratio")

        snapshots_by_date = {
            "2024-01-01": [
                _make_snapshot("A", pe_ratio=10.0),
                _make_snapshot("B", pe_ratio=20.0),
                _make_snapshot("C", pe_ratio=30.0),
            ],
            "2024-01-02": [
                _make_snapshot("A", pe_ratio=10.0),
                _make_snapshot("B", pe_ratio=20.0),
                _make_snapshot("C", pe_ratio=30.0),
            ],
        }
        # 下期收益：pe 越高，收益越高（正相关）
        returns_by_date = {
            "2024-01-02": {"A": 0.01, "B": 0.02, "C": 0.03},
        }

        ic_series = calc.calculate_ic_series(expr, snapshots_by_date, returns_by_date)
        assert len(ic_series) == 1
        assert ic_series[0][0] == "2024-01-01"
        assert ic_series[0][1] > 0.5  # 强正相关
