from src.application.live_signal_service import SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.interfaces.cli.signal_review.enhanced_display import (
    EnhancedSignalDisplay,
    calculate_risk_score,
)


class TestCalculateRiskScore:
    def _make_display(
        self,
        direction: SignalDirection = SignalDirection.BUY,
        required_capital: float = 10_000.0,
        confidence_score: float = 0.8,
    ) -> SignalDisplay:
        return SignalDisplay(
            symbol="600000.SH",
            direction=direction,
            current_price=10.0,
            suggested_price=10.01,
            suggested_volume=1000,
            required_capital=required_capital,
            reason="test",
            strategy_name="test",
            confidence_score=confidence_score,
        )

    def _make_asset(self, total: float = 1_000_000) -> Asset:
        return Asset(account_id="test", total_asset=total, available_cash=500_000)

    def test_low_risk_buy(self):
        d = self._make_display(required_capital=5_000, confidence_score=0.95)
        score = calculate_risk_score(d, None, self._make_asset())
        assert score < 0.3

    def test_high_concentration_increases_risk(self):
        d = self._make_display(required_capital=200_000)
        score = calculate_risk_score(d, None, self._make_asset(total=500_000))
        assert score > 0.5

    def test_sell_direction_lower_risk_than_buy(self):
        buy_score = calculate_risk_score(
            self._make_display(direction=SignalDirection.BUY), None, self._make_asset(),
        )
        sell_score = calculate_risk_score(
            self._make_display(direction=SignalDirection.SELL), None, self._make_asset(),
        )
        assert sell_score < buy_score

    def test_low_confidence_increases_risk(self):
        high_conf = calculate_risk_score(
            self._make_display(confidence_score=0.95), None, self._make_asset(),
        )
        low_conf = calculate_risk_score(
            self._make_display(confidence_score=0.1), None, self._make_asset(),
        )
        assert low_conf > high_conf

    def test_score_bounded_0_to_1(self):
        d = self._make_display(required_capital=999_999, confidence_score=0.0)
        score = calculate_risk_score(d, None, self._make_asset(total=1_000))
        assert 0.0 <= score <= 1.0

    def test_with_position(self):
        pos = Position(account_id="test", ticker="600000.SH", total_volume=100)
        d = self._make_display()
        score_with = calculate_risk_score(d, pos, self._make_asset())
        score_without = calculate_risk_score(d, None, self._make_asset())
        assert score_with == score_without  # position not used in current impl


class TestEnhancedSignalDisplay:
    def test_inherits_signal_display(self):
        d = EnhancedSignalDisplay(
            symbol="600000.SH",
            direction=SignalDirection.BUY,
            current_price=10.0,
            suggested_price=10.01,
            suggested_volume=1000,
            required_capital=10_010,
            reason="test",
            strategy_name="test",
            confidence_score=0.8,
            risk_score=0.3,
            ml_confidence=0.85,
            signal_age_hours=1.5,
            historical_win_rate=0.62,
        )
        assert isinstance(d, SignalDisplay)
        assert d.risk_score == 0.3
        assert d.ml_confidence == 0.85
        assert d.signal_age_hours == 1.5
        assert d.historical_win_rate == 0.62

    def test_default_values(self):
        d = EnhancedSignalDisplay(
            symbol="600000.SH",
            direction=SignalDirection.BUY,
            current_price=10.0,
            suggested_price=10.01,
            suggested_volume=1000,
            required_capital=10_010,
            reason="test",
            strategy_name="test",
            confidence_score=0.8,
        )
        assert d.risk_score == 0.0
        assert d.ml_confidence == 0.0
        assert d.historical_win_rate == 0.0
