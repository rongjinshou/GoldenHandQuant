import pytest
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


class TestFixedRatioSizerRatioMode:
    def test_buy_with_sufficient_cash_returns_round_lot(self):
        sizer = FixedRatioSizer(ratio=0.2, mode="ratio")
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=100000.0, frozen_cash=0.0)
        signal = Signal(symbol="000001.SZ", direction=SignalDirection.BUY, confidence_score=1.0)

        volume = sizer.calculate_target(signal, current_price=10.0, asset=asset, position=None)

        # budget = 100000 * 0.2 * 1.0 = 20000, volume = 20000 / 10 = 2000 -> 2000 (整手)
        assert volume == 2000
        assert volume % 100 == 0

    def test_buy_respects_available_cash_limit(self):
        sizer = FixedRatioSizer(ratio=0.5, mode="ratio")
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=5000.0, frozen_cash=0.0)
        signal = Signal(symbol="000001.SZ", direction=SignalDirection.BUY, confidence_score=1.0)

        volume = sizer.calculate_target(signal, current_price=10.0, asset=asset, position=None)

        # budget = min(100000*0.5=50000, available_cash=5000) = 5000, volume = 5000/10 = 500
        assert volume == 500

    def test_sell_with_confidence_one_sells_all_available(self):
        sizer = FixedRatioSizer(ratio=0.2, mode="ratio")
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=50000.0, frozen_cash=0.0)
        position = Position(account_id="TEST", ticker="000001.SZ", total_volume=300, available_volume=300, average_cost=9.0)
        signal = Signal(symbol="000001.SZ", direction=SignalDirection.SELL, confidence_score=1.0)

        volume = sizer.calculate_target(signal, current_price=10.0, asset=asset, position=position)

        assert volume == 300

    def test_buy_with_zero_price_returns_zero(self):
        sizer = FixedRatioSizer(ratio=0.2)
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=100000.0)
        signal = Signal(symbol="000001.SZ", direction=SignalDirection.BUY)

        volume = sizer.calculate_target(signal, current_price=0.0, asset=asset, position=None)

        assert volume == 0


class TestFixedRatioSizerRiskMode:
    def test_risk_based_buy_calculates_position_from_risk(self):
        # risk_pct=1%, stop_loss_pct=2%, price=10 -> volume = (100000*0.01)/(10*0.02) = 1000/0.2 = 5000
        sizer = FixedRatioSizer(mode="risk_per_trade", risk_pct=0.01, stop_loss_pct=0.02)
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=100000.0)
        signal = Signal(symbol="000001.SZ", direction=SignalDirection.BUY, confidence_score=1.0)

        volume = sizer.calculate_target(signal, current_price=10.0, asset=asset, position=None)

        assert volume == 5000
        assert volume % 100 == 0

    def test_risk_based_buy_respects_cash_limit(self):
        sizer = FixedRatioSizer(mode="risk_per_trade", risk_pct=0.05, stop_loss_pct=0.01)
        asset = Asset(account_id="TEST", total_asset=100000.0, available_cash=10000.0)
        signal = Signal(symbol="000001.SZ", direction=SignalDirection.BUY, confidence_score=1.0)

        volume = sizer.calculate_target(signal, current_price=10.0, asset=asset, position=None)

        # risk-based: (100000*0.05)/(10*0.01) = 5000/0.1 = 50000 shares
        # cash limit: 10000/10 = 1000 shares
        assert volume == 1000

    def test_invalid_mode_raises_value_error(self):
        with pytest.raises(ValueError, match="mode must be"):
            FixedRatioSizer(mode="invalid")

    def test_invalid_risk_pct_raises_value_error(self):
        with pytest.raises(ValueError, match="risk_pct must be"):
            FixedRatioSizer(mode="risk_per_trade", risk_pct=0.10)
