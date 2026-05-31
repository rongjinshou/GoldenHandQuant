"""对账报告值对象。"""

from dataclasses import dataclass
from datetime import date

from src.domain.account.value_objects.position_difference import PositionDifference


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciliationReport:
    """对账报告 — 记录某日盘后对账的结果。

    Attributes:
        report_date: 对账日期。
        account_id: 账户 ID。
        positions_match: 持仓是否完全匹配。
        cash_match: 资金余额是否匹配。
        system_cash: 系统记录的可用资金。
        broker_cash: 券商返回的可用资金。
        cash_difference: 资金差异金额（system - broker）。
        position_differences: 持仓差异列表。
        alerts: 告警消息列表。
        is_consistent: 总体是否一致（无任何差异和告警）。
    """

    report_date: date
    account_id: str
    positions_match: bool
    cash_match: bool
    system_cash: float = 0.0
    broker_cash: float = 0.0
    cash_difference: float = 0.0
    position_differences: tuple[PositionDifference, ...] = ()
    alerts: tuple[str, ...] = ()

    @property
    def is_consistent(self) -> bool:
        """总体是否一致。"""
        return self.positions_match and self.cash_match and len(self.alerts) == 0
