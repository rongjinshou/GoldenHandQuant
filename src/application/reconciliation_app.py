"""对账应用服务 — 编排盘后自动对账、报告生成与告警推送。"""

import logging
from datetime import date

from src.application.notification_hub import NotificationHub
from src.domain.account.entities.asset import Asset
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.account.interfaces.reconciliation_repository import (
    IReconciliationRepository,
)
from src.domain.account.services.reconciliation_service import (
    ReconciliationConfig,
    ReconciliationService,
)
from src.domain.account.value_objects.reconciliation_report import ReconciliationReport
from src.domain.notification.value_objects.notification_message import (
    NotificationLevel,
    NotificationMessage,
)

logger = logging.getLogger(__name__)


class ReconciliationAppService:
    """对账应用服务。

    职责:
    - 每日盘后自动执行对账（系统数据 vs 券商数据）。
    - 生成对账报告并持久化。
    - 检测到差异时通过 NotificationHub 推送告警。

    用法:
        service = ReconciliationAppService(
            account_gateway=qmt_gateway,
            broker_account_gateway=qmt_gateway,   # 同一网关或不同网关
            repository=file_repo,
            notification_hub=hub,
        )
        report = service.run_daily_reconciliation("ACC001")
    """

    def __init__(
        self,
        account_gateway: IAccountGateway,
        broker_account_gateway: IAccountGateway,
        repository: IReconciliationRepository,
        notification_hub: NotificationHub,
        config: ReconciliationConfig | None = None,
    ) -> None:
        self._account_gateway = account_gateway
        self._broker_gateway = broker_account_gateway
        self._repository = repository
        self._notification_hub = notification_hub
        self._service = ReconciliationService(config)

    def run_daily_reconciliation(
        self,
        account_id: str | None = None,
        report_date: date | None = None,
    ) -> ReconciliationReport:
        """执行每日盘后对账。

        流程:
        1. 从系统获取持仓和资金。
        2. 从券商获取持仓和资金。
        3. 执行对账对比。
        4. 持久化对账报告。
        5. 若有差异，推送告警通知。

        Args:
            account_id: 账户 ID，为 None 时使用默认账户。
            report_date: 对账日期，默认为今天。

        Returns:
            ReconciliationReport: 对账报告。
        """
        if report_date is None:
            report_date = date.today()

        effective_account_id = account_id or "default"

        # 1. 获取系统数据
        sys_asset = self._account_gateway.get_asset(account_id)
        sys_positions = self._account_gateway.get_positions(account_id)

        # 2. 获取券商数据
        broker_asset = self._broker_gateway.get_asset(account_id)
        broker_positions = self._broker_gateway.get_positions(account_id)

        # 处理空数据
        if sys_asset is None:
            sys_asset = Asset(account_id=effective_account_id)
        if broker_asset is None:
            broker_asset = Asset(account_id=effective_account_id)

        # 3. 执行对账
        report = self._service.reconcile(
            report_date=report_date,
            account_id=effective_account_id,
            system_asset=sys_asset,
            system_positions=sys_positions,
            broker_asset=broker_asset,
            broker_positions=broker_positions,
        )

        # 4. 持久化
        try:
            self._repository.save(report)
        except Exception:
            logger.exception("对账报告持久化失败")

        # 5. 推送告警
        if not report.is_consistent:
            self._send_alert(report)

        logger.info(
            "对账完成: date=%s account=%s consistent=%s",
            report.report_date,
            report.account_id,
            report.is_consistent,
        )

        return report

    def _send_alert(self, report: ReconciliationReport) -> None:
        """将对账差异通过 NotificationHub 推送。"""
        level = NotificationLevel.WARNING
        if not report.cash_match or any(
            d.diff_type.value in ("missing_in_broker", "missing_in_system")
            for d in report.position_differences
        ):
            level = NotificationLevel.CRITICAL

        body_lines = [f"账户: {report.account_id}", f"日期: {report.report_date}", ""]

        if not report.cash_match:
            body_lines.append(
                f"[资金差异] 系统: {report.system_cash:.2f}, "
                f"券商: {report.broker_cash:.2f}, 差额: {report.cash_difference:.2f}"
            )

        for diff in report.position_differences:
            body_lines.append(f"[{diff.diff_type.value}] {diff.detail}")

        self._notification_hub.notify(NotificationMessage(
            title=f"对账告警: {report.account_id}",
            body="\n".join(body_lines),
            level=level,
            category="reconciliation",
        ))
