from src.domain.portfolio.services.kelly_sizer import KellySizer
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.strategy.value_objects.signal import Signal
from src.domain.account.entities.asset import Asset
from datetime import datetime


class KellySizer(KellySizer):
    def calculate_targets(self, signals, prices, asset, positions):
        pass

def test_kelly_sizer_positive_expectation_buys():
    sizer = KellySizer(win_rate=0.60, profit_loss_ratio=2.0, half_kelly=False, max_ratio=1.0)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    # 满凯利: f* = (0.6*2 - 0.4)/2 = 0.4, target_value = 40000, volume = 4000
    assert volume == 4000


def test_kelly_sizer_half_kelly_reduces_exposure():
    sizer_full = KellySizer(win_rate=0.60, profit_loss_ratio=2.0, half_kelly=False, max_ratio=1.0)
    sizer_half = KellySizer(win_rate=0.60, profit_loss_ratio=2.0, half_kelly=True, max_ratio=1.0)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    vol_full = sizer_full.calculate_target(signal, price=10.0, asset=asset, position=None)
    vol_half = sizer_half.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert vol_half == vol_full // 2


def test_kelly_sizer_negative_expectation_returns_zero():
    sizer = KellySizer(win_rate=0.40, profit_loss_ratio=0.5)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    assert volume == 0


def test_kelly_sizer_respects_max_ratio():
    sizer = KellySizer(win_rate=0.80, profit_loss_ratio=3.0, half_kelly=False, max_ratio=0.10)
    signal = Signal(symbol="000001.SZ", direction=OrderDirection.BUY, generated_at=datetime.now())
    asset = Asset(account_id="TEST", total_asset=100000, available_cash=100000, frozen_cash=0)
    volume = sizer.calculate_target(signal, price=10.0, asset=asset, position=None)
    # 满凯利 > max_ratio -> 被截断至 10%
    assert volume == 1000  # 10% * 100000 / 10 = 1000
