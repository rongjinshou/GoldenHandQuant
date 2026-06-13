"""分层回测引擎测试。"""

import math
from datetime import datetime

import pytest

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

    def test_long_short_is_net_of_costs(self):
        """多空收益须扣交易成本: 换手越高扣得越多。"""
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        # 因子排名每日翻转 -> 高换手
        snapshots_by_date = {
            "2024-01-01": [_make_snapshot("A", 1.0), _make_snapshot("B", 2.0),
                           _make_snapshot("C", 3.0), _make_snapshot("D", 4.0)],
            "2024-01-02": [_make_snapshot("A", 4.0), _make_snapshot("B", 3.0),
                           _make_snapshot("C", 2.0), _make_snapshot("D", 1.0)],
            "2024-01-03": [_make_snapshot("A", 4.0), _make_snapshot("B", 3.0),
                           _make_snapshot("C", 2.0), _make_snapshot("D", 1.0)],
        }
        # 按实现日键入: factor@d1 预测 returns@d2; factor@d2 预测 returns@d3
        returns_by_date = {
            "2024-01-02": {"A": -0.05, "B": -0.05, "C": 0.05, "D": 0.05},
            "2024-01-03": {"A": 0.05, "B": 0.05, "C": -0.05, "D": -0.05},
        }
        gross = bt.run(expr, snapshots_by_date, returns_by_date, num_layers=2, cost_rate=0.0)
        net = bt.run(expr, snapshots_by_date, returns_by_date, num_layers=2, cost_rate=0.05)
        assert gross.long_short_return > net.long_short_return

    def test_empty_data(self):
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        result = bt.run(expr, {}, {}, num_layers=5)
        assert result.layer_count == 5
        assert result.long_short_return == 0.0


class TestLongOnlyExcess:
    """long-only 记分牌: Top 层纯多头超额 vs 等权覆盖池基准。"""

    def test_top_excess_positive_when_top_beats_market(self):
        """Top 层(高 pe)每日跑赢等权全体 → 超额为正, 信息比为正, 正率=1。"""
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        # pe 稳定 1..10; 每个实现日高 pe 收益更高 (3 个实现步保证 n>=2)
        snaps = [_make_snapshot(f"S{i}", float(i + 1)) for i in range(10)]
        snapshots_by_date = {"2024-01-01": snaps, "2024-01-02": snaps, "2024-01-03": snaps}
        ret = {f"S{i}": 0.01 * (i + 1) for i in range(10)}
        # 各实现日同序、量级不同 → Top 持续跑赢但超额量级变化 → excess_ir 有意义(>0)。
        # (对称扣成本后, 恒定收益会让超额恒定→IR=0; 故用变量级而非常量, 见 L4 修复)
        returns_by_date = {
            "2024-01-02": {k: v for k, v in ret.items()},
            "2024-01-03": {k: v * 1.5 for k, v in ret.items()},
            "2024-01-04": {k: v * 0.7 for k, v in ret.items()},
        }
        res = bt.run(expr, snapshots_by_date, returns_by_date, num_layers=5)
        assert res.top_layer_return > res.benchmark_return
        assert res.top_excess_return > 0
        assert res.excess_positive_rate == pytest.approx(1.0)
        assert res.excess_ir > 0

    def test_top_excess_zero_when_uniform_returns(self):
        """全体同收益 → Top 与等权基准相等 → 超额≈0, 但基准本身有正收益。"""
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        snaps = [_make_snapshot(f"S{i}", float(i + 1)) for i in range(10)]
        snapshots_by_date = {"2024-01-01": snaps, "2024-01-02": snaps, "2024-01-03": snaps}
        ret = {f"S{i}": 0.01 for i in range(10)}
        returns_by_date = {
            "2024-01-02": dict(ret), "2024-01-03": dict(ret), "2024-01-04": dict(ret),
        }
        res = bt.run(expr, snapshots_by_date, returns_by_date, num_layers=5, cost_rate=0.0)
        assert abs(res.top_excess_return) < 1e-9
        assert res.benchmark_return > 0

    def test_empty_data_top_excess_zero(self):
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        res = bt.run(expr, {}, {}, num_layers=5)
        assert res.top_excess_return == 0.0
        assert res.excess_ir == 0.0
        assert res.excess_positive_rate == 0.0


class TestRebalanceDays:
    """可配置调仓间隔: 持有期内不重排、不计换手成本。"""

    def test_holding_keeps_membership_between_rebalances(self):
        """rebalance_days=2 时, 第2日不按新因子值重排, 沿用第1日成员。

        构造: 第2日因子排名翻转。日频模式会换成新顶层吃到 +10%;
        持有模式仍持第1日的顶层(此时变成 -10%) → 多空收益一正一负。
        """
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        snapshots_by_date = {
            "2024-01-01": [_make_snapshot("A", 1.0), _make_snapshot("B", 2.0),
                           _make_snapshot("C", 3.0), _make_snapshot("D", 4.0)],
            "2024-01-02": [_make_snapshot("A", 4.0), _make_snapshot("B", 3.0),
                           _make_snapshot("C", 2.0), _make_snapshot("D", 1.0)],
        }
        returns_by_date = {
            "2024-01-02": {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
            "2024-01-03": {"A": 0.10, "B": 0.10, "C": -0.10, "D": -0.10},
        }
        daily = bt.run(expr, snapshots_by_date, returns_by_date,
                       num_layers=2, cost_rate=0.0, rebalance_days=1)
        hold = bt.run(expr, snapshots_by_date, returns_by_date,
                      num_layers=2, cost_rate=0.0, rebalance_days=2)
        # 日频: 第2日重排后顶层={A,B} 吃 +10% → 多空为正
        assert daily.long_short_return > 0
        # 持有: 顶层仍={C,D} 吃 -10% → 多空为负
        assert hold.long_short_return < 0

    def test_costs_charged_only_on_rebalance_days(self):
        """持有期内换手成本为 0, 只在调仓日扣。

        构造: 收益全为 0(隔离成本效应), 因子排名每日翻转(日频高换手)。
        日频模式每天都付重建成本; 持有模式只付首日建仓成本 → 净值更高。
        """
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        snapshots_by_date = {
            "2024-01-01": [_make_snapshot("A", 1.0), _make_snapshot("B", 2.0),
                           _make_snapshot("C", 3.0), _make_snapshot("D", 4.0)],
            "2024-01-02": [_make_snapshot("A", 4.0), _make_snapshot("B", 3.0),
                           _make_snapshot("C", 2.0), _make_snapshot("D", 1.0)],
            "2024-01-03": [_make_snapshot("A", 1.0), _make_snapshot("B", 2.0),
                           _make_snapshot("C", 3.0), _make_snapshot("D", 4.0)],
        }
        zero = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0}
        returns_by_date = {
            "2024-01-02": dict(zero),
            "2024-01-03": dict(zero),
            "2024-01-04": dict(zero),
        }
        daily = bt.run(expr, snapshots_by_date, returns_by_date,
                       num_layers=2, cost_rate=0.05, rebalance_days=1)
        hold = bt.run(expr, snapshots_by_date, returns_by_date,
                      num_layers=2, cost_rate=0.05, rebalance_days=3)
        # 两者都为负(纯成本), 但持有模式只扣一次建仓成本, 亏得更少
        assert daily.long_short_return < 0
        assert hold.long_short_return > daily.long_short_return

    def test_stable_ranks_equivalent_across_rebalance_days(self):
        """因子排名稳定时, 任何调仓间隔结果一致(成员不变 → 换手为 0)。"""
        bt = LayerBacktester()
        expr = FactorRefExpr(field_name="pe_ratio")
        stable = [_make_snapshot("A", 1.0), _make_snapshot("B", 2.0),
                  _make_snapshot("C", 3.0), _make_snapshot("D", 4.0)]
        snapshots_by_date = {
            "2024-01-01": stable, "2024-01-02": stable, "2024-01-03": stable,
        }
        returns_by_date = {
            "2024-01-02": {"A": -0.01, "B": 0.0, "C": 0.01, "D": 0.02},
            "2024-01-03": {"A": 0.02, "B": 0.01, "C": 0.0, "D": -0.01},
            "2024-01-04": {"A": 0.005, "B": 0.005, "C": 0.005, "D": 0.005},
        }
        daily = bt.run(expr, snapshots_by_date, returns_by_date,
                       num_layers=2, cost_rate=0.003, rebalance_days=1)
        hold = bt.run(expr, snapshots_by_date, returns_by_date,
                      num_layers=2, cost_rate=0.003, rebalance_days=3)
        assert hold.long_short_return == pytest.approx(daily.long_short_return)
        assert hold.layer_returns == pytest.approx(daily.layer_returns)


class TestScorecardRefinement:
    """L3: excess_ir 用非重叠块 IR(去持有期内日超额自相关高估); L4: 基准腿对称扣换手成本。"""

    @staticmethod
    def _excess(top_gross, top_turn, bench, bench_turn, cost, rebal):
        # num_layers=2 → top=index 1; 底层填 0, 不影响超额
        n = len(top_gross)
        lg = [[0.0] * n, list(top_gross)]
        lt = [[0.0] * n, list(top_turn)]
        return LayerBacktester._top_excess_net(
            lg, lt, list(bench), list(bench_turn),
            num_layers=2, cost_rate=cost, trading_days_per_year=244,
            layer_annual_returns=[0.0, 0.0], rebalance_days=rebal,
        )

    def test_excess_ir_daily_matches_naive_formula(self):
        # rebalance_days=1 → 块大小 1 → IR 退化为日 mean/std×√244 (无回归)
        e = [0.02, -0.01, 0.03, 0.0, 0.015]
        n = len(e)
        _, _, _, ir, _ = self._excess(e, [0.0] * n, [0.0] * n, [0.0] * n, cost=0.0, rebal=1)
        mean = sum(e) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in e) / (n - 1))
        assert ir == pytest.approx(mean / std * math.sqrt(244), rel=1e-9)

    def test_excess_ir_block_lower_than_daily_when_autocorrelated(self):
        # 正自相关序列(3 高 3 低): 日频 √244 高估 IR; 3 日块 IR 应更保守(更低)
        e = [0.02, 0.02, 0.02, -0.01, -0.01, -0.01]
        n = len(e)
        _, _, _, ir_daily, _ = self._excess(e, [0.0] * n, [0.0] * n, [0.0] * n, cost=0.0, rebal=1)
        _, _, _, ir_block, _ = self._excess(e, [0.0] * n, [0.0] * n, [0.0] * n, cost=0.0, rebal=3)
        assert ir_daily > 0 and ir_block > 0
        assert ir_block < ir_daily

    def test_benchmark_charged_symmetric_turnover_cost(self):
        # 基准腿有换手时对称扣成本 → 基准净收益低于 costless
        n = 4
        top = [0.0] * n
        bench = [0.01] * n
        _, bench_costless, _, _, _ = self._excess(top, [0.0] * n, bench, [0.0] * n, cost=0.01, rebal=1)
        _, bench_charged, _, _, _ = self._excess(top, [0.0] * n, bench, [0.5, 0.0, 0.0, 0.0], cost=0.01, rebal=1)
        assert bench_charged < bench_costless
