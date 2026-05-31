"""对账领域服务 — 系统持仓/资金 vs 券商数据的差异检测。"""

from dataclasses import dataclass

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.value_objects.position_difference import (
    DifferenceType,
    PositionDifference,
)
from src.domain.account.value_objects.reconciliation_report import ReconciliationReport


@dataclass(frozen=True, slots=True, kw_only=True)
class ReconciliationConfig:
    """对账配置（不可变值对象）。"""
    cost_tolerance: float = 0.01       # 成本价容差（元），在此范围内视为一致
    cash_tolerance: float = 0.01       # 资金容差（元）
    volume_alert_threshold: int = 0    # 数量差异告警阈值，0 表示任何差异都告警


class ReconciliationService:
    """对账领域服务。

    职责:
    - 对比系统持仓与券商持仓，检测数量/成本差异。
    - 对比系统资金与券商资金，检测余额差异。
    - 生成差异告警消息。

    用法:
        service = ReconciliationService()
        report = service.reconcile(
            report_date=date.today(),
            account_id="ACC001",
            system_asset=asset,
            system_positions=positions,
            broker_asset=broker_asset,
            broker_positions=broker_positions,
        )
    """

    def __init__(self, config: ReconciliationConfig | None = None) -> None:
        self._config = config or ReconciliationConfig()

    def reconcile(
        self,
        report_date,  # datetime.date — 避免额外 import
        account_id: str,
        system_asset: Asset,
        system_positions: list[Position],
        broker_asset: Asset,
        broker_positions: list[Position],
    ) -> ReconciliationReport:
        """执行对账并生成报告。

        Args:
            report_date: 对账日期。
            account_id: 账户 ID。
            system_asset: 系统记录的资产。
            system_positions: 系统记录的持仓列表。
            broker_asset: 券商返回的资产。
            broker_positions: 券商返回的持仓列表。

        Returns:
            ReconciliationReport: 对账报告。
        """
        cfg = self._config
        alerts: list[str] = []

        # --- 资金对账 ---
        cash_diff = system_asset.available_cash - broker_asset.available_cash
        cash_match = abs(cash_diff) <= cfg.cash_tolerance
        if not cash_match:
            alerts.append(
                f"资金差异: 系统 {system_asset.available_cash:.2f} vs "
                f"券商 {broker_asset.available_cash:.2f}, 差额 {cash_diff:.2f}"
            )

        # --- 持仓对账 ---
        pos_diffs = self._compare_positions(system_positions, broker_positions)
        for diff in pos_diffs:
            alerts.append(f"[{diff.diff_type.value}] {diff.ticker}: {diff.detail}")

        positions_match = len(pos_diffs) == 0

        return ReconciliationReport(
            report_date=report_date,
            account_id=account_id,
            positions_match=positions_match,
            cash_match=cash_match,
            system_cash=system_asset.available_cash,
            broker_cash=broker_asset.available_cash,
            cash_difference=cash_diff,
            position_differences=tuple(pos_diffs),
            alerts=tuple(alerts),
        )

    def _compare_positions(
        self,
        system_positions: list[Position],
        broker_positions: list[Position],
    ) -> list[PositionDifference]:
        """对比系统持仓与券商持仓。"""
        cfg = self._config
        diffs: list[PositionDifference] = []

        sys_map = {p.ticker: p for p in system_positions}
        brk_map = {p.ticker: p for p in broker_positions}

        all_tickers = set(sys_map) | set(brk_map)

        for ticker in sorted(all_tickers):
            sys_pos = sys_map.get(ticker)
            brk_pos = brk_map.get(ticker)

            if sys_pos and not brk_pos:
                diffs.append(PositionDifference(
                    ticker=ticker,
                    diff_type=DifferenceType.MISSING_IN_BROKER,
                    system_volume=sys_pos.total_volume,
                    broker_volume=0,
                    system_cost=sys_pos.average_cost,
                    broker_cost=0.0,
                    detail=f"系统有持仓 {sys_pos.total_volume} 股，券商无此持仓",
                ))
            elif brk_pos and not sys_pos:
                diffs.append(PositionDifference(
                    ticker=ticker,
                    diff_type=DifferenceType.MISSING_IN_SYSTEM,
                    system_volume=0,
                    broker_volume=brk_pos.total_volume,
                    system_cost=0.0,
                    broker_cost=brk_pos.average_cost,
                    detail=f"券商有持仓 {brk_pos.total_volume} 股，系统无此持仓",
                ))
            else:
                # 双方都有持仓，比较数量和成本
                assert sys_pos is not None and brk_pos is not None
                if sys_pos.total_volume != brk_pos.total_volume:
                    diffs.append(PositionDifference(
                        ticker=ticker,
                        diff_type=DifferenceType.VOLUME_MISMATCH,
                        system_volume=sys_pos.total_volume,
                        broker_volume=brk_pos.total_volume,
                        system_cost=sys_pos.average_cost,
                        broker_cost=brk_pos.average_cost,
                        detail=(
                            f"数量不一致: 系统 {sys_pos.total_volume} vs "
                            f"券商 {brk_pos.total_volume}"
                        ),
                    ))

                if abs(sys_pos.average_cost - brk_pos.average_cost) > cfg.cost_tolerance:
                    diffs.append(PositionDifference(
                        ticker=ticker,
                        diff_type=DifferenceType.COST_MISMATCH,
                        system_volume=sys_pos.total_volume,
                        broker_volume=brk_pos.total_volume,
                        system_cost=sys_pos.average_cost,
                        broker_cost=brk_pos.average_cost,
                        detail=(
                            f"成本不一致: 系统 {sys_pos.average_cost:.4f} vs "
                            f"券商 {brk_pos.average_cost:.4f}"
                        ),
                    ))

        return diffs
