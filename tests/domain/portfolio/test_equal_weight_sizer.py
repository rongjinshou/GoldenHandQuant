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
