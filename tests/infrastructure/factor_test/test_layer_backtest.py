"""分层回测引擎测试。"""

from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.expressions import FactorRefExpr
from src.infrastructure.factor_test.layer_backtest import LayerBacktester


def _make_snapshot(symbol: str, pe_ratio: float) -> StockSnapshot:
    return StockSnapshot(
        symbol=symbol, date=datetime(2024, 1, 1),
        open=10, high=10, low=10, close=10, volume=1000,
        name=f"stock_{symbol}", list_date=datetime(2020, 1, 1),
        market_cap=1e10, pe_ratio=pe_ratio,
    )


class TestLayerBacktester:
    def test_basic_layering(self):
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")

        snapshots_by_date = {
            "2024-01-01": [_make_snapshot(f"S{i}", float(i)) for i in range(10)],
            "2024-01-02": [_make_snapshot(f"S{i}", float(i)) for i in range(10)],
        }
        returns_by_date = {
            "2024-01-02": {f"S{i}": 0.01 * (i + 1) for i in range(10)},
        }

        result = bt.run(expr, snapshots_by_date, returns_by_date, num_layers=2)
        assert result.layer_count == 2
        assert len(result.layer_returns) == 2
        assert len(result.layer_cumulative) == 2

    def test_long_short_positive(self):
        """因子值高的组收益高于因子值低的组 → 多空收益为正。"""
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")

        # 10 只股票，pe 从 1 到 10
        # 下期收益：pe 越高收益越高
        snapshots_by_date = {
            "2024-01-01": [_make_snapshot(f"S{i}", float(i + 1)) for i in range(10)],
            "2024-01-02": [_make_snapshot(f"S{i}", float(i + 1)) for i in range(10)],
        }
        returns_by_date = {
            "2024-01-02": {f"S{i}": 0.01 * (i + 1) for i in range(10)},
        }

        result = bt.run(expr, snapshots_by_date, returns_by_date, num_layers=5)
        # 最高层收益应高于最低层
        assert result.layer_returns[-1] > result.layer_returns[0]
        assert result.long_short_return > 0

    def test_monotonicity_score(self):
        bt = LayerBacktester()
        # 完美单调
        assert bt._monotonicity_score([1.0, 2.0, 3.0, 4.0, 5.0]) == 1.0
        # 完全逆序
        assert bt._monotonicity_score([5.0, 4.0, 3.0, 2.0, 1.0]) == 0.0
        # 部分单调
        score = bt._monotonicity_score([1.0, 3.0, 2.0, 4.0])
        assert 0.5 < score < 1.0

    def test_empty_data(self):
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        result = bt.run(expr, {}, {}, num_layers=5)
        assert result.layer_count == 5
        assert result.long_short_return == 0.0
