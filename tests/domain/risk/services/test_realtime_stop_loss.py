"""RealtimeStopLossService 测试。"""

from datetime import datetime

from src.domain.risk.services.realtime_stop_loss import (
    RealtimeStopLossService,
    StopLossType,
)
from src.domain.risk.value_objects.risk_alert import (
    RiskAlertAction,
    RiskAlertSeverity,
    RiskAlertType,
)


class TestRealtimeStopLossService:
    """RealtimeStopLossService 测试。"""

    def test_fixed_stop_no_trigger(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)

        # Act
        trigger = svc.on_price_update("600000.SH", price=10.0)

        # Assert
        assert trigger is None

    def test_fixed_stop_triggers(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)

        # Act
        trigger = svc.on_price_update("600000.SH", price=9.4)

        # Assert
        assert trigger is not None
        assert trigger.symbol == "600000.SH"
        assert trigger.trigger_price == 9.4
        assert trigger.stop_price == 9.5
        assert trigger.volume == 1000
        assert trigger.stop_type == StopLossType.FIXED
        assert trigger.loss_rate < 0

    def test_percentage_stop_triggers(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_percentage_stop("600000.SH", cost_price=10.0, stop_pct=0.05, volume=1000)
        # 止损价 = 10.0 * (1 - 0.05) = 9.5

        # Act
        trigger = svc.on_price_update("600000.SH", price=9.4)

        # Assert
        assert trigger is not None
        assert trigger.stop_price == 9.5
        assert trigger.stop_type == StopLossType.PERCENTAGE

    def test_percentage_stop_no_trigger(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_percentage_stop("600000.SH", cost_price=10.0, stop_pct=0.05, volume=1000)

        # Act
        trigger = svc.on_price_update("600000.SH", price=9.6)

        # Assert
        assert trigger is None

    def test_trailing_stop_follows_price_up(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_trailing_stop("600000.SH", current_price=10.0, stop_pct=0.05, volume=1000)
        # 初始止损价 = 10.0 * 0.95 = 9.5

        # Act - 价格上涨
        svc.on_price_update("600000.SH", price=11.0)
        # 止损价应更新为 11.0 * 0.95 = 10.45

        rules = svc.rules
        assert rules["600000.SH"].highest_price == 11.0
        assert rules["600000.SH"].stop_price == 10.45

    def test_trailing_stop_triggers_on_pullback(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_trailing_stop("600000.SH", current_price=10.0, stop_pct=0.05, volume=1000)

        # Act - 价格上涨后回调
        svc.on_price_update("600000.SH", price=11.0)  # 止损价升至 10.45
        trigger = svc.on_price_update("600000.SH", price=10.3)  # 低于止损价

        # Assert
        assert trigger is not None
        assert trigger.stop_type == StopLossType.TRAILING
        assert trigger.stop_price == 10.45

    def test_trailing_stop_does_not_lower(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_trailing_stop("600000.SH", current_price=10.0, stop_pct=0.05, volume=1000)

        # Act - 价格下跌（最高价不变）
        svc.on_price_update("600000.SH", price=9.8)

        rules = svc.rules
        assert rules["600000.SH"].highest_price == 10.0  # 最高价不变

    def test_trigger_disables_rule(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)

        # Act - 触发止损
        svc.on_price_update("600000.SH", price=9.4)
        # 再次触发
        trigger2 = svc.on_price_update("600000.SH", price=9.3)

        # Assert - 规则已禁用，不会重复触发
        assert trigger2 is None

    def test_remove_rule(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)

        # Act
        svc.remove_rule("600000.SH")
        trigger = svc.on_price_update("600000.SH", price=9.0)

        # Assert
        assert trigger is None
        assert "600000.SH" not in svc.rules

    def test_no_rule_returns_none(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()

        # Act
        trigger = svc.on_price_update("600000.SH", price=10.0)

        # Assert
        assert trigger is None

    def test_collect_triggers_clears_buffer(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)
        svc.on_price_update("600000.SH", price=9.4)

        # Act
        triggers1 = svc.collect_triggers()
        triggers2 = svc.collect_triggers()

        # Assert
        assert len(triggers1) == 1
        assert triggers2 == []

    def test_trigger_generates_alert(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)

        # Act
        svc.on_price_update("600000.SH", price=9.4)
        alerts = svc.collect_alerts()

        # Assert
        assert len(alerts) == 1
        assert alerts[0].alert_type == RiskAlertType.STOP_LOSS
        assert alerts[0].severity == RiskAlertSeverity.CRITICAL
        assert alerts[0].action_required == RiskAlertAction.CLOSE_POSITION

    def test_trailing_stop_alert_type(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_trailing_stop("600000.SH", current_price=10.0, stop_pct=0.05, volume=1000)

        # Act
        svc.on_price_update("600000.SH", price=11.0)
        svc.on_price_update("600000.SH", price=10.3)
        alerts = svc.collect_alerts()

        # Assert
        assert len(alerts) == 1
        assert alerts[0].alert_type == RiskAlertType.TRAILING_STOP

    def test_multiple_symbols(self) -> None:
        # Arrange
        svc = RealtimeStopLossService()
        svc.set_fixed_stop("600000.SH", stop_price=9.5, cost_price=10.0, volume=1000)
        svc.set_percentage_stop("000001.SZ", cost_price=20.0, stop_pct=0.10, volume=500)

        # Act
        trigger_a = svc.on_price_update("600000.SH", price=10.0)
        trigger_b = svc.on_price_update("000001.SZ", price=20.0)

        # Assert
        assert trigger_a is None
        assert trigger_b is None

        # Act - 600000 触发止损
        trigger_a = svc.on_price_update("600000.SH", price=9.4)
        assert trigger_a is not None
        assert trigger_a.symbol == "600000.SH"
