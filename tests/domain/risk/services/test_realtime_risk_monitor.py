"""RealtimeRiskMonitor 测试。"""

from datetime import datetime

from src.domain.risk.services.realtime_risk_monitor import (
    RealtimeRiskMonitor,
    TickData,
)
from src.domain.risk.value_objects.risk_alert import (
    RiskAlertAction,
    RiskAlertSeverity,
    RiskAlertType,
)


class TestRealtimeRiskMonitor:
    """RealtimeRiskMonitor 测试。"""

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

    def test_first_tick_no_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor()
        tick = self._make_tick()

        # Act
        alerts = monitor.on_tick(tick)

        # Assert
        assert alerts == []

    def test_normal_price_change_no_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor(max_price_change_pct=0.05)
        monitor.on_tick(self._make_tick(price=10.0))

        # Act
        alerts = monitor.on_tick(self._make_tick(price=10.1))

        # Assert
        assert alerts == []

    def test_abnormal_price_change_triggers_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor(max_price_change_pct=0.05)
        monitor.on_tick(self._make_tick(price=10.0))

        # Act - 价格跳变 6%
        alerts = monitor.on_tick(self._make_tick(price=10.6))

        # Assert
        assert len(alerts) >= 1
        price_alerts = [a for a in alerts if a.alert_type == RiskAlertType.PRICE_ANOMALY]
        assert len(price_alerts) >= 1
        assert price_alerts[0].severity == RiskAlertSeverity.CRITICAL
        assert price_alerts[0].action_required == RiskAlertAction.PAUSE_TRADING

    def test_limit_up_alert(self) -> None:
        # Arrange - 先以接近 pre_close 的价格建仓，再小幅触及涨停
        monitor = RealtimeRiskMonitor(max_price_change_pct=0.05)
        monitor.on_tick(self._make_tick(price=10.0, pre_close=10.0))
        # 小幅上涨到 10.04（0.4% 变动，不触发价格异常），然后跳到接近涨停
        monitor.on_tick(self._make_tick(price=10.04, pre_close=10.0))

        # Act - 接近涨停（从 10.04 到 10.98，变动 9.36% > 5%，会触发 CRITICAL 价格异常）
        alerts = monitor.on_tick(self._make_tick(price=10.98, pre_close=10.0))

        # Assert - 涨停检查会产生 WARNING 级别的告警
        limit_alerts = [
            a for a in alerts
            if a.alert_type == RiskAlertType.PRICE_ANOMALY
            and a.severity == RiskAlertSeverity.WARNING
            and "涨跌停" in a.message
        ]
        assert len(limit_alerts) >= 1

    def test_wide_spread_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor(max_spread_pct=0.02)

        # Act - 买卖价差 3%
        tick = self._make_tick(bid=9.7, ask=10.0)
        alerts = monitor.on_tick(tick)

        # Assert
        spread_alerts = [a for a in alerts if a.alert_type == RiskAlertType.WIDE_SPREAD]
        assert len(spread_alerts) == 1
        assert spread_alerts[0].severity == RiskAlertSeverity.WARNING

    def test_normal_spread_no_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor(max_spread_pct=0.02)

        # Act
        tick = self._make_tick(bid=9.99, ask=10.01)
        alerts = monitor.on_tick(tick)

        # Assert
        spread_alerts = [a for a in alerts if a.alert_type == RiskAlertType.WIDE_SPREAD]
        assert len(spread_alerts) == 0

    def test_volume_spike_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor(max_volume_spike_ratio=5.0)
        # 建立基准成交量
        monitor.on_tick(self._make_tick(price=10.0, volume=1000))
        monitor.on_tick(self._make_tick(price=10.0, volume=1000))

        # Act - 成交量放大 6 倍
        alerts = monitor.on_tick(self._make_tick(price=10.0, volume=6000))

        # Assert
        vol_alerts = [a for a in alerts if a.alert_type == RiskAlertType.VOLUME_ANOMALY]
        assert len(vol_alerts) == 1

    def test_rapid_drop_alert(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor(max_rapid_drop_pct=0.03, rapid_drop_window=5)
        # 先建立价格序列
        for p in [10.0, 10.1, 10.2, 10.3, 10.4]:
            monitor.on_tick(self._make_tick(price=p))

        # Act - 价格从高点 10.4 跌到 9.9 (约 4.8%)
        alerts = monitor.on_tick(self._make_tick(price=9.9))

        # Assert
        drop_alerts = [a for a in alerts if a.alert_type == RiskAlertType.RAPID_DROP]
        assert len(drop_alerts) == 1
        assert drop_alerts[0].severity == RiskAlertSeverity.CRITICAL
        assert drop_alerts[0].action_required == RiskAlertAction.CLOSE_POSITION

    def test_collect_alerts_clears_buffer(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor()
        monitor.on_tick(self._make_tick(price=10.0))
        monitor.on_tick(self._make_tick(price=10.6))  # 触发异常

        # Act
        alerts1 = monitor.collect_alerts()
        alerts2 = monitor.collect_alerts()

        # Assert
        assert len(alerts1) > 0
        assert alerts2 == []

    def test_multiple_symbols(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor()
        monitor.on_tick(self._make_tick(symbol="600000.SH", price=10.0, pre_close=10.0))
        monitor.on_tick(self._make_tick(symbol="000001.SZ", price=20.0, pre_close=20.0))

        # Act
        alerts_a = monitor.on_tick(self._make_tick(symbol="600000.SH", price=10.6, pre_close=10.0))
        alerts_b = monitor.on_tick(self._make_tick(symbol="000001.SZ", price=20.5, pre_close=20.0))

        # Assert - 600000 触发异常，000001 正常
        assert any(a.symbol == "600000.SH" for a in alerts_a)
        assert alerts_b == []

    def test_tracker_created_on_first_tick(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor()

        # Act
        monitor.on_tick(self._make_tick(symbol="600000.SH", price=10.0))

        # Assert
        tracker = monitor.get_tracker("600000.SH")
        assert tracker is not None
        assert tracker.symbol == "600000.SH"
        assert tracker.last_price == 10.0
        assert tracker.tick_count == 1

    def test_tracker_updated_on_subsequent_ticks(self) -> None:
        # Arrange
        monitor = RealtimeRiskMonitor()
        monitor.on_tick(self._make_tick(symbol="600000.SH", price=10.0))

        # Act
        monitor.on_tick(self._make_tick(symbol="600000.SH", price=10.5))

        # Assert
        tracker = monitor.get_tracker("600000.SH")
        assert tracker is not None
        assert tracker.last_price == 10.5
        assert tracker.tick_count == 2
