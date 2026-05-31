"""ReconciliationAppService 对账应用服务测试。"""

from datetime import date

from src.application.notification_hub import NotificationHub
from src.application.reconciliation_app import ReconciliationAppService
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.value_objects.reconciliation_report import ReconciliationReport
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)

# ========== 测试替身 ==========

class StubAccountGateway:
    """可配置的账户网关测试替身。"""

    def __init__(
        self,
        asset: Asset | None = None,
        positions: list[Position] | None = None,
    ) -> None:
        self._asset = asset
        self._positions = positions or []
        self.get_asset_calls: list[str | None] = []
        self.get_positions_calls: list[str | None] = []

    def get_asset(self, account_id: str | None = None) -> Asset | None:
        self.get_asset_calls.append(account_id)
        return self._asset

    def get_positions(self, account_id: str | None = None) -> list[Position]:
        self.get_positions_calls.append(account_id)
        return self._positions


class InMemoryReconciliationRepository:
    """内存对账报告仓储。"""

    def __init__(self) -> None:
        self.saved_reports: list[ReconciliationReport] = []

    def save(self, report: ReconciliationReport) -> None:
        self.saved_reports.append(report)

    def get_by_date(self, account_id: str, report_date) -> ReconciliationReport | None:
        for r in self.saved_reports:
            if r.account_id == account_id and r.report_date == report_date:
                return r
        return None


class SpyNotificationGateway:
    """记录发送消息的 Spy 网关。"""

    def __init__(self) -> None:
        self.sent_messages: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> None:
        self.sent_messages.append(message)


# ========== 辅助函数 ==========

def _make_asset(available_cash: float = 50_000.0) -> Asset:
    return Asset(
        account_id="TEST",
        total_asset=available_cash,
        available_cash=available_cash,
        frozen_cash=0.0,
    )


def _make_position(
    ticker: str = "600000.SH",
    total_volume: int = 100,
    average_cost: float = 10.0,
) -> Position:
    return Position(
        account_id="TEST",
        ticker=ticker,
        total_volume=total_volume,
        available_volume=total_volume,
        average_cost=average_cost,
    )


def _build_app(
    *,
    sys_asset: Asset | None = None,
    sys_positions: list[Position] | None = None,
    broker_asset: Asset | None = None,
    broker_positions: list[Position] | None = None,
) -> tuple[ReconciliationAppService, InMemoryReconciliationRepository, SpyNotificationGateway]:
    """构建带测试替身的应用服务实例。"""
    sys_gw = StubAccountGateway(
        asset=sys_asset or _make_asset(),
        positions=sys_positions or [],
    )
    broker_gw = StubAccountGateway(
        asset=broker_asset or _make_asset(),
        positions=broker_positions or [],
    )
    repo = InMemoryReconciliationRepository()
    spy_gw = SpyNotificationGateway()
    hub = NotificationHub(gateways=[spy_gw])

    app = ReconciliationAppService(
        account_gateway=sys_gw,
        broker_account_gateway=broker_gw,
        repository=repo,
        notification_hub=hub,
    )
    return app, repo, spy_gw


# ========== 测试用例 ==========

class TestReconciliationAppService:

    def test_consistent_data_no_alert(self):
        """系统与券商数据一致时，不应发送告警通知。"""
        positions = [_make_position()]
        asset = _make_asset()

        app, repo, spy = _build_app(
            sys_asset=asset,
            sys_positions=positions,
            broker_asset=asset,
            broker_positions=positions,
        )

        report = app.run_daily_reconciliation("TEST")

        assert report.is_consistent is True
        assert len(spy.sent_messages) == 0
        assert len(repo.saved_reports) == 1

    def test_cash_mismatch_sends_alert(self):
        """资金差异应触发告警通知。"""
        sys_asset = _make_asset(available_cash=50_000.0)
        broker_asset = _make_asset(available_cash=49_000.0)

        app, repo, spy = _build_app(
            sys_asset=sys_asset,
            broker_asset=broker_asset,
        )

        report = app.run_daily_reconciliation("TEST")

        assert report.cash_match is False
        assert len(spy.sent_messages) == 1
        msg = spy.sent_messages[0]
        assert msg.category == "reconciliation"
        assert msg.level == NotificationLevel.CRITICAL
        assert "资金差异" in msg.body

    def test_position_mismatch_sends_alert(self):
        """持仓差异应触发告警通知。"""
        sys_pos = [_make_position(ticker="600000.SH", total_volume=100)]
        broker_pos = [_make_position(ticker="600000.SH", total_volume=200)]

        app, repo, spy = _build_app(
            sys_positions=sys_pos,
            broker_positions=broker_pos,
        )

        report = app.run_daily_reconciliation("TEST")

        assert report.positions_match is False
        assert len(spy.sent_messages) == 1
        assert "数量不一致" in spy.sent_messages[0].body

    def test_missing_position_critical_alert(self):
        """券商缺失持仓应触发 CRITICAL 级别告警。"""
        sys_pos = [_make_position(ticker="600000.SH")]

        app, repo, spy = _build_app(
            sys_positions=sys_pos,
            broker_positions=[],
        )

        app.run_daily_reconciliation("TEST")

        assert spy.sent_messages[0].level == NotificationLevel.CRITICAL

    def test_report_persisted_even_on_failure(self):
        """即使持久化失败，对账仍应完成（不抛异常）。"""
        # 使用一个会抛异常的仓储
        class FailingRepository:
            def save(self, report):
                raise RuntimeError("disk full")
            def get_by_date(self, account_id, report_date):
                return None

        sys_gw = StubAccountGateway(asset=_make_asset(), positions=[])
        broker_gw = StubAccountGateway(asset=_make_asset(), positions=[])
        spy_gw = SpyNotificationGateway()
        hub = NotificationHub(gateways=[spy_gw])

        app = ReconciliationAppService(
            account_gateway=sys_gw,
            broker_account_gateway=broker_gw,
            repository=FailingRepository(),
            notification_hub=hub,
        )

        # 不应抛异常
        report = app.run_daily_reconciliation("TEST")
        assert report.is_consistent is True

    def test_default_date_is_today(self):
        """不指定日期时应使用当天日期。"""
        app, repo, spy = _build_app()

        report = app.run_daily_reconciliation("TEST")

        assert report.report_date == date.today()

    def test_custom_report_date(self):
        """应支持自定义对账日期。"""
        app, repo, spy = _build_app()

        target_date = date(2026, 5, 15)
        report = app.run_daily_reconciliation("TEST", report_date=target_date)

        assert report.report_date == target_date
        assert repo.saved_reports[0].report_date == target_date

    def test_default_account_id(self):
        """account_id 为 None 时应使用 'default'。"""
        app, repo, spy = _build_app()

        report = app.run_daily_reconciliation()

        assert report.account_id == "default"

    def test_empty_asset_returns_default(self):
        """网关返回 None 资产时应使用空 Asset。"""
        class NoneAssetGateway:
            def get_asset(self, account_id=None):
                return None
            def get_positions(self, account_id=None):
                return []

        spy_gw = SpyNotificationGateway()
        hub = NotificationHub(gateways=[spy_gw])
        repo = InMemoryReconciliationRepository()

        app = ReconciliationAppService(
            account_gateway=NoneAssetGateway(),
            broker_account_gateway=NoneAssetGateway(),
            repository=repo,
            notification_hub=hub,
        )

        report = app.run_daily_reconciliation("TEST")

        # 两个 None 都变成空 Asset，应该一致
        assert report.is_consistent is True

    def test_gateway_called_with_account_id(self):
        """应将 account_id 正确传递给网关。"""
        sys_gw = StubAccountGateway(asset=_make_asset())
        broker_gw = StubAccountGateway(asset=_make_asset())
        spy_gw = SpyNotificationGateway()
        hub = NotificationHub(gateways=[spy_gw])
        repo = InMemoryReconciliationRepository()

        app = ReconciliationAppService(
            account_gateway=sys_gw,
            broker_account_gateway=broker_gw,
            repository=repo,
            notification_hub=hub,
        )

        app.run_daily_reconciliation("MY_ACCOUNT")

        assert sys_gw.get_asset_calls == ["MY_ACCOUNT"]
        assert sys_gw.get_positions_calls == ["MY_ACCOUNT"]
        assert broker_gw.get_asset_calls == ["MY_ACCOUNT"]
        assert broker_gw.get_positions_calls == ["MY_ACCOUNT"]

    def test_report_accessible_via_repository(self):
        """对账报告应可通过仓储查询。"""
        sys_pos = [_make_position(ticker="600000.SH", total_volume=100)]
        broker_pos = [_make_position(ticker="600000.SH", total_volume=200)]

        app, repo, spy = _build_app(
            sys_positions=sys_pos,
            broker_positions=broker_pos,
        )

        target_date = date(2026, 6, 1)
        app.run_daily_reconciliation("TEST", report_date=target_date)

        stored = repo.get_by_date("TEST", target_date)
        assert stored is not None
        assert stored.positions_match is False
        assert len(stored.position_differences) == 1
