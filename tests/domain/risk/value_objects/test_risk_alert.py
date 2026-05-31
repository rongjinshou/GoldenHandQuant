"""RiskAlert 值对象测试。"""

from datetime import datetime

from src.domain.risk.value_objects.risk_alert import (
    RiskAlert,
    RiskAlertAction,
    RiskAlertSeverity,
    RiskAlertType,
)


class TestRiskAlert:
    """RiskAlert 值对象测试。"""

    def test_create_with_required_fields(self) -> None:
        # Arrange & Act
        alert = RiskAlert(
            alert_type=RiskAlertType.STOP_LOSS,
            severity=RiskAlertSeverity.CRITICAL,
            symbol="600000.SH",
            message="止损触发",
        )

        # Assert
        assert alert.alert_type == RiskAlertType.STOP_LOSS
        assert alert.severity == RiskAlertSeverity.CRITICAL
        assert alert.symbol == "600000.SH"
        assert alert.message == "止损触发"
        assert isinstance(alert.timestamp, datetime)
        assert alert.action_required == RiskAlertAction.NOTIFY
        assert alert.current_price == 0.0
        assert alert.reference_price == 0.0
        assert alert.loss_rate == 0.0

    def test_create_with_all_fields(self) -> None:
        # Arrange
        ts = datetime(2026, 6, 1, 10, 30, 0)

        # Act
        alert = RiskAlert(
            alert_type=RiskAlertType.TRAILING_STOP,
            severity=RiskAlertSeverity.WARNING,
            symbol="000001.SZ",
            message="移动止损触发",
            timestamp=ts,
            action_required=RiskAlertAction.CLOSE_POSITION,
            current_price=9.5,
            reference_price=10.0,
            loss_rate=-0.05,
        )

        # Assert
        assert alert.timestamp == ts
        assert alert.action_required == RiskAlertAction.CLOSE_POSITION
        assert alert.current_price == 9.5
        assert alert.reference_price == 10.0
        assert alert.loss_rate == -0.05

    def test_frozen_immutable(self) -> None:
        # Arrange
        alert = RiskAlert(
            alert_type=RiskAlertType.PRICE_ANOMALY,
            severity=RiskAlertSeverity.INFO,
            symbol="600000.SH",
            message="test",
        )

        # Act & Assert
        try:
            alert.symbol = "other"  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass

    def test_alert_type_enum_values(self) -> None:
        assert RiskAlertType.STOP_LOSS == "stop_loss"
        assert RiskAlertType.TRAILING_STOP == "trailing_stop"
        assert RiskAlertType.PRICE_ANOMALY == "price_anomaly"
        assert RiskAlertType.VOLUME_ANOMALY == "volume_anomaly"
        assert RiskAlertType.WIDE_SPREAD == "wide_spread"
        assert RiskAlertType.RAPID_DROP == "rapid_drop"

    def test_severity_enum_values(self) -> None:
        assert RiskAlertSeverity.INFO == "info"
        assert RiskAlertSeverity.WARNING == "warning"
        assert RiskAlertSeverity.CRITICAL == "critical"

    def test_action_enum_values(self) -> None:
        assert RiskAlertAction.NONE == "none"
        assert RiskAlertAction.NOTIFY == "notify"
        assert RiskAlertAction.CLOSE_POSITION == "close_position"
        assert RiskAlertAction.PAUSE_TRADING == "pause_trading"
