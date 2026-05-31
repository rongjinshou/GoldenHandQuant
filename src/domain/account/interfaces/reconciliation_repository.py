"""对账报告持久化接口。"""

from typing import Protocol

from src.domain.account.value_objects.reconciliation_report import ReconciliationReport


class IReconciliationRepository(Protocol):
    """对账报告仓储接口。"""

    def save(self, report: ReconciliationReport) -> None:
        """持久化对账报告。"""
        ...

    def get_by_date(self, account_id: str, report_date) -> ReconciliationReport | None:
        """按日期查询对账报告。"""
        ...
