"""RealtimeRiskAppService 测试。"""

from datetime import datetime

from src.application.realtime_risk_app import RealtimeRiskAppService
from src.domain.risk.services.realtime_risk_monitor import TickData
from src.domain.risk.services.realtime_stop_loss import RealtimeStopLossService
from src.domain.risk.value_objects.risk_alert import (
    RiskAlertAction,
    RiskAlertSeverity,
    RiskAlertType,
)


class TestRealtimeRiskAppService:
    """RealtimeRiskAppService 测试。"""

    def _make_tick(
        self,
        symbol: str = "600000.SH",
        price: float = 10.0,
        volume: int = 1000,
        bid: float = 9.99,
        ask: float = 10.01,
        pre_close: float = 10.0,
    ) -> TickData:
        return TickData(
            symbol=symbol,
            price=price,
            volume=volume,
            bid_price=bid,
            ask_price=ask,
            pre_close=pre_close,
        )

    def test_normal_tick_no_pause(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService()

        # Act
        result = svc.check_tick(self._make_tick())

        # Assert
        assert result.trading_paused is False
        assert result.alerts == []
        assert result.stop_triggers == []

    def test_price_anomaly_pauses_trading(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService(auto_pause_on_critical=True)
        svc.check_tick(self._make_tick(price=10.0))

        # Act - 价格跳变 6%
        result = svc.check_tick(self._make_tick(price=10.6))

        # Assert
        assert result.trading_paused is True
        assert svc.is_paused is True
        assert svc.paused_reason != ""

    def test_stop_loss_pauses_trading(self) -> None:
        # Arrange
        stop_svc = RealtimeStopLossService()
        stop_svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)
        svc = RealtimeRiskAppService(
            stop_loss_service=stop_svc,
            auto_pause_on_critical=True,
        )

        # Act
        result = svc.check_tick(self._make_tick(price=9.4))

        # Assert
        assert len(result.stop_triggers) == 1
        assert result.trading_paused is True
        assert svc.is_paused is True

    def test_auto_pause_disabled(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService(auto_pause_on_critical=False)
        svc.check_tick(self._make_tick(price=10.0))

        # Act - 价格跳变
        result = svc.check_tick(self._make_tick(price=10.6))

        # Assert
        assert result.trading_paused is False
        assert svc.is_paused is False

    def test_resume_clears_pause(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService(auto_pause_on_critical=True)
        svc.check_tick(self._make_tick(price=10.0))
        svc.check_tick(self._make_tick(price=10.6))  # 触发暂停

        # Act
        svc.resume()

        # Assert
        assert svc.is_paused is False
        assert svc.paused_reason == ""

    def test_check_ticks_batch(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService(auto_pause_on_critical=True)
        ticks = [
            self._make_tick(price=10.0, pre_close=10.0),
            self._make_tick(price=10.1, pre_close=10.0),
            self._make_tick(price=10.8, pre_close=10.0),  # 6.9% 变动，触发异常
        ]

        # Act
        result = svc.check_ticks(ticks)

        # Assert
        assert result.trading_paused is True
        assert len(result.alerts) > 0

    def test_check_history_recorded(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService()
        svc.check_tick(self._make_tick(price=10.0))
        svc.check_tick(self._make_tick(price=10.1))

        # Act
        history = svc.get_check_history()

        # Assert
        assert len(history) == 2
        assert history[0].timestamp is not None

    def test_stop_loss_rule_configurable(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService()

        # Act - 通过 stop_loss_service 配置止损
        svc.stop_loss_service.set_percentage_stop(
            "600000.SH", cost_price=10.0, stop_pct=0.05, volume=1000,
        )

        # Assert
        rules = svc.stop_loss_service.rules
        assert "600000.SH" in rules

    def test_risk_monitor_configurable(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService()

        # Act
        svc.risk_monitor.on_tick(self._make_tick(price=10.0))
        tracker = svc.risk_monitor.get_tracker("600000.SH")

        # Assert
        assert tracker is not None
        assert tracker.last_price == 10.0

    def test_wide_spread_generates_warning(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService(auto_pause_on_critical=True)

        # Act - 买卖价差大但不会暂停（WARNING 级别）
        tick = self._make_tick(bid=9.7, ask=10.0, price=9.85)
        result = svc.check_tick(tick)

        # Assert
        warning_alerts = [a for a in result.alerts if a.severity == RiskAlertSeverity.WARNING]
        assert len(warning_alerts) >= 1
        assert result.trading_paused is False  # WARNING 不暂停

    def test_empty_ticks_batch(self) -> None:
        # Arrange
        svc = RealtimeRiskAppService()

        # Act
        result = svc.check_ticks([])

        # Assert
        assert result.alerts == []
        assert result.stop_triggers == []
