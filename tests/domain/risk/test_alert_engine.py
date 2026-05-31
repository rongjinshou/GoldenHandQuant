from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.risk.services.alert_engine import AlertEngine
from src.domain.risk.services.alert_rules.concentration_rule import ConcentrationRule
from src.domain.risk.services.alert_rules.daily_loss_rule import DailyLossRule
from src.domain.risk.services.alert_rules.position_ratio_rule import PositionRatioRule
from src.domain.risk.services.alert_rules.stock_loss_rule import StockLossRule
from src.domain.risk.value_objects.risk_metrics import RiskMetrics


def _make_snapshot(
    total_asset: float = 1_000_000,
    yesterday_asset: float = 1_000_000,
    positions: list[PositionDetail] | None = None,
) -> MonitorSnapshot:
    return MonitorSnapshot(
        timestamp=datetime(2026, 1, 1),
        asset=Asset(account_id="test", total_asset=total_asset, available_cash=500_000),
        positions=positions or [],
        risk_metrics=RiskMetrics(
            total_position_ratio=0.5, max_concentration=0.1, position_count=1,
        ),
        yesterday_asset=yesterday_asset,
    )


class TestDailyLossRule:
    def test_no_alert_when_loss_below_threshold(self):
        rule = DailyLossRule(threshold=0.03)
        snapshot = _make_snapshot(total_asset=980_000, yesterday_asset=1_000_000)
        alert = rule.evaluate(snapshot)
        assert alert is None

    def test_alert_when_loss_exceeds_threshold(self):
        rule = DailyLossRule(threshold=0.03)
        snapshot = _make_snapshot(total_asset=960_000, yesterday_asset=1_000_000)
        alert = rule.evaluate(snapshot)
        assert alert is not None
        assert alert.level == "CRITICAL"
        assert alert.category == "LOSS"


class TestStockLossRule:
    def test_alert_when_stock_loss_exceeds_threshold(self):
        rule = StockLossRule(threshold=0.05)
        pos = PositionDetail(
            ticker="600000.SH", total_volume=500, available_volume=500,
            average_cost=10.0, current_price=9.0,
        )
        snapshot = _make_snapshot(positions=[pos])
        alert = rule.evaluate(snapshot)
        assert alert is not None
        assert "600000.SH" in alert.message


class TestPositionRatioRule:
    def test_alert_when_position_too_high(self):
        rule = PositionRatioRule(max_ratio=0.80, min_ratio=0.10)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.90, max_concentration=0.1, position_count=3,
        )
        alerts = rule.evaluate(snapshot)
        assert len(alerts) == 1
        assert alerts[0].category == "POSITION"

    def test_alert_when_position_too_low(self):
        rule = PositionRatioRule(max_ratio=0.80, min_ratio=0.10)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.05, max_concentration=0.05, position_count=1,
        )
        alerts = rule.evaluate(snapshot)
        assert len(alerts) == 1

    def test_no_alert_when_position_normal(self):
        rule = PositionRatioRule(max_ratio=0.80, min_ratio=0.10)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.50, max_concentration=0.1, position_count=3,
        )
        alerts = rule.evaluate(snapshot)
        assert len(alerts) == 0


class TestConcentrationRule:
    def test_alert_when_concentration_too_high(self):
        rule = ConcentrationRule(threshold=0.30)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.5, max_concentration=0.35, position_count=2,
        )
        alert = rule.evaluate(snapshot)
        assert alert is not None
        assert alert.category == "CONCENTRATION"


class TestAlertEngine:
    def test_engine_aggregates_alerts_from_all_rules(self):
        engine = AlertEngine(rules=[
            DailyLossRule(threshold=0.03),
            StockLossRule(threshold=0.05),
        ])
        pos = PositionDetail(
            ticker="600000.SH", total_volume=500, available_volume=500,
            average_cost=10.0, current_price=9.0,
        )
        snapshot = _make_snapshot(
            total_asset=960_000, yesterday_asset=1_000_000, positions=[pos],
        )
        alerts = engine.check(snapshot)
        assert len(alerts) >= 2  # daily loss + stock loss
