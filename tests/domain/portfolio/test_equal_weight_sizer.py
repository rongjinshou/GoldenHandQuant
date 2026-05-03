from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.strategy.value_objects.signal import Signal
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from datetime import datetime


def test_equal_weight_within_threshold_returns_zero():
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    # 目标: 20000, 当前: 20000 (exactly at target)
    pos = Position(account_id="TEST", ticker="000001.SZ", total_volume=2000, available_volume=2000, average_cost=10.0)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=pos)
    assert volume == 0  # 无偏离，不调整


def test_equal_weight_underweight_buys():
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    # 目标: 20000, 当前: 0 (严重 underweight)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert volume > 0  # 应买入至目标仓位


def test_equal_weight_mismatched_signal_direction_returns_zero():
    sizer = EqualWeightSizer(n_symbols=5, rebalance_threshold=0.05)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.SELL, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    # Underweight but signal is SELL -> no action
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert volume == 0


from src.domain.portfolio.entities.order_target import OrderTarget

def _signal(symbol, direction=OrderDirection.BUY):
    return Signal(symbol=symbol, direction=direction, confidence_score=1.0, generated_at=datetime.now())

def _asset(total=100000.0):
    return Asset(account_id="TEST", total_asset=total, available_cash=total, frozen_cash=0)

def _pos(symbol, total_vol, avail_vol, avg_cost=10.0):
    return Position(account_id="TEST", ticker=symbol, total_volume=total_vol, available_volume=avail_vol, average_cost=avg_cost)

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
