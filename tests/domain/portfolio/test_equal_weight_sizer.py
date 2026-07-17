from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.strategy.value_objects.signal import Signal
from src.domain.trade.value_objects.order_direction import OrderDirection


def test_equal_weight_within_threshold_returns_zero():
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime(2026, 1, 1))
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    # 目标: 20000, 当前: 20000 (exactly at target)
    pos = Position(account_id="TEST", ticker="000001.SZ", total_volume=2000, available_volume=2000, average_cost=10.0)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=pos)
    assert volume == 0  # 无偏离，不调整


def test_equal_weight_underweight_buys():
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime(2026, 1, 1))
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    # 目标: 20000, 当前: 0 (严重 underweight)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert volume > 0  # 应买入至目标仓位


def test_equal_weight_mismatched_signal_direction_returns_zero():
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.SELL, generated_at=datetime(2026, 1, 1))
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    # Underweight but signal is SELL -> no action
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert volume == 0


def test_equal_weight_zero_total_asset_returns_zero_instead_of_crashing():
    """confirmed-bug(2026-07-05 全项目排查发现): calculate_target() 是实盘路径
    (strategy_runner.py/live_signal_service.py 唯一调用), total_asset=0(新开户
    尚未同步资金/账户被打光都是真实可达状态)会让 target_value_per_symbol 精确为 0,
    直接 ZeroDivisionError 崩到调用方——calculate_targets() 批量法早有同款
    `target_value_per > 0` 守卫, 单数法一直缺这一条。"""
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime(2026, 1, 1))
    asset = Asset(account_id="TEST", total_asset=0.0, available_cash=0.0, frozen_cash=0)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert volume == 0



def _signal(symbol, direction=OrderDirection.BUY, strategy_name=""):
    return Signal(
        symbol=symbol, direction=direction, confidence_score=1.0,
        generated_at=datetime(2026, 1, 1), strategy_name=strategy_name,
    )

def _asset(total=100000.0):
    return Asset(account_id="TEST", total_asset=total, available_cash=total, frozen_cash=0)

def _pos(symbol, total_vol, avail_vol, avg_cost=10.0):
    return Position(account_id="TEST", ticker=symbol, total_volume=total_vol,
                    available_volume=avail_vol, average_cost=avg_cost)

class TestEqualWeightSizerBatch:
    def test_calculate_targets_clears_all_when_no_signals(self):
        sizer = EqualWeightSizer(n_symbols=5)
        targets = sizer.calculate_targets(
            signals=[], prices={"A": 10.0, "B": 10.0},
            asset=_asset(), positions=[_pos("A", 1000, 1000)],
        )
        assert len(targets) == 1
        assert targets[0].symbol == "A"
        assert targets[0].direction == OrderDirection.SELL

    def test_calculate_targets_sells_positions_not_in_target_pool(self):
        sizer = EqualWeightSizer(n_symbols=2)
        signals = [_signal("A", OrderDirection.BUY), _signal("B", OrderDirection.BUY)]
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "B": 10.0, "C": 10.0},
            asset=_asset(), positions=[_pos("C", 500, 500)],
        )
        sell_targets = [t for t in targets if t.direction == OrderDirection.SELL]
        assert len(sell_targets) == 1
        assert sell_targets[0].symbol == "C"

    def test_calculate_targets_buys_underweight_targets(self):
        sizer = EqualWeightSizer(n_symbols=2)
        signals = [_signal("A", OrderDirection.BUY), _signal("B", OrderDirection.BUY)]
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "B": 10.0},
            asset=_asset(100000), positions=[],
        )
        buy_targets = [t for t in targets if t.direction == OrderDirection.BUY]
        assert len(buy_targets) == 2
        # Each should be ~5000 value / 10.0 = 500, but rounded to 100s = 500
        for t in buy_targets:
            assert t.volume >= 100
            assert t.volume % 100 == 0

    def test_calculate_targets_skips_within_threshold(self):
        """偏离度在阈值内时不应产生交易目标。"""
        sizer = EqualWeightSizer(n_symbols=2, rebalance_threshold=0.05)
        # 目标每 symbol: 50000, 当前持仓 A: 51000 (偏离 2%, < 5% 阈值)
        pos = _pos("A", 5100, 5100, avg_cost=10.0)
        signals = [_signal("A", OrderDirection.BUY), _signal("B", OrderDirection.BUY)]
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "B": 10.0},
            asset=_asset(100000), positions=[pos],
        )
        a_targets = [t for t in targets if t.symbol == "A"]
        assert len(a_targets) == 0  # A 在阈值内，不应产生目标


class TestLiquidationPriceGuard:
    """清仓路径价格防线（2026-07-10 六西格玛体检 A1）。"""

    def test_liquidation_skips_position_with_nonpositive_price_fallback(self):
        """confirmed-bug(2026-07-10 六西格玛体检): 两条清仓分支在 prices 缺该持仓时
        回退用建仓成本当限价——QMT 真账户止盈摊薄后 average_cost 可为负
        (2026-06-30 dry-run 实证: 000021.SZ average_cost=-0.32165, 负价卖单已写入
        execution_records)。买入分支早有 price<=0 守卫, 清仓分支一直缺。"""
        sizer = EqualWeightSizer(n_symbols=5)
        neg_cost_pos = _pos("000021.SZ", 600, 600, avg_cost=-0.32165)
        targets = sizer.calculate_targets(
            signals=[], prices={},  # 持仓不在本轮扫描宇宙 → 无市价可用
            asset=_asset(), positions=[neg_cost_pos],
        )
        assert targets == []

    def test_liquidation_keeps_positive_cost_fallback(self):
        """市价缺失但建仓成本为正时保留原回退行为（下游还有 ±10% 价格带闸兜底）。"""
        sizer = EqualWeightSizer(n_symbols=5)
        pos = _pos("A", 1000, 1000, avg_cost=9.5)
        targets = sizer.calculate_targets(
            signals=[], prices={}, asset=_asset(), positions=[pos],
        )
        assert len(targets) == 1
        assert targets[0].price == 9.5

    def test_not_in_pool_liquidation_skips_nonpositive_price(self):
        """「不在目标池」清仓分支与「空目标池」分支是同款缺陷, 一并设防。"""
        sizer = EqualWeightSizer(n_symbols=2)
        signals = [_signal("A"), _signal("B")]
        zero_cost_pos = _pos("C", 500, 500, avg_cost=0.0)
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "B": 10.0},
            asset=_asset(), positions=[zero_cost_pos],
        )
        assert [t for t in targets if t.symbol == "C"] == []


class TestLiquidationStrategyName:
    """清仓目标的策略归因（2026-07-10 六西格玛体检 A1）。"""

    def test_liquidation_falls_back_to_scan_signal_strategy_name(self):
        """confirmed-bug(2026-07-10 六西格玛体检): 清仓目标找不到同标的 SELL 信号时
        strategy_name 被误记为 sizer 类名 'EqualWeightSizer'(2026-06-30
        execution_records 实证), 审计无法回溯真正策略。同轮信号全部来自同一策略,
        应回退到本轮任一信号的策略名。"""
        sizer = EqualWeightSizer(n_symbols=2)
        signals = [_signal("A", strategy_name="micro_value")]
        pos = _pos("C", 500, 500, avg_cost=10.0)
        targets = sizer.calculate_targets(
            signals=signals, prices={"A": 10.0, "C": 10.0},
            asset=_asset(), positions=[pos],
        )
        c_targets = [t for t in targets if t.symbol == "C"]
        assert len(c_targets) == 1
        assert c_targets[0].strategy_name == "micro_value"

    def test_liquidation_with_no_signals_uses_semantic_constant(self):
        """全无信号的防御性清仓, 归因用语义常量而非 sizer 类名。"""
        sizer = EqualWeightSizer(n_symbols=5)
        pos = _pos("A", 1000, 1000, avg_cost=9.5)
        targets = sizer.calculate_targets(
            signals=[], prices={"A": 10.0}, asset=_asset(), positions=[pos],
        )
        assert targets[0].strategy_name == "liquidation"
