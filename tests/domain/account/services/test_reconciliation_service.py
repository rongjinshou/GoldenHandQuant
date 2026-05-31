"""ReconciliationService 对账领域服务测试。"""

from datetime import date

import pytest

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.services.reconciliation_service import (
    ReconciliationConfig,
    ReconciliationService,
)
from src.domain.account.value_objects.position_difference import DifferenceType


class TestReconciliationService:
    """对账领域服务测试。"""

    def _make_asset(
        self,
        account_id: str = "TEST",
        available_cash: float = 100_000.0,
        frozen_cash: float = 0.0,
    ) -> Asset:
        return Asset(
            account_id=account_id,
            total_asset=available_cash + frozen_cash,
            available_cash=available_cash,
            frozen_cash=frozen_cash,
        )

    def _make_position(
        self,
        ticker: str = "600000.SH",
        total_volume: int = 100,
        available_volume: int = 100,
        average_cost: float = 10.0,
    ) -> Position:
        return Position(
            account_id="TEST",
            ticker=ticker,
            total_volume=total_volume,
            available_volume=available_volume,
            average_cost=average_cost,
        )

    # ========== 完全匹配 ==========

    def test_reconcile_fully_consistent(self):
        """系统与券商数据完全一致时，报告应标记为一致。"""
        service = ReconciliationService()

        sys_asset = self._make_asset(available_cash=50_000.0)
        broker_asset = self._make_asset(available_cash=50_000.0)
        positions = [self._make_position()]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=sys_asset,
            system_positions=positions,
            broker_asset=broker_asset,
            broker_positions=positions,
        )

        assert report.is_consistent is True
        assert report.positions_match is True
        assert report.cash_match is True
        assert len(report.position_differences) == 0
        assert len(report.alerts) == 0

    def test_reconcile_empty_account(self):
        """空账户对账应一致。"""
        service = ReconciliationService()

        empty_asset = self._make_asset(available_cash=100_000.0)

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=empty_asset,
            system_positions=[],
            broker_asset=empty_asset,
            broker_positions=[],
        )

        assert report.is_consistent is True

    # ========== 资金差异 ==========

    def test_reconcile_cash_mismatch(self):
        """资金不一致时应检测到差异。"""
        service = ReconciliationService()

        sys_asset = self._make_asset(available_cash=50_000.0)
        broker_asset = self._make_asset(available_cash=49_500.0)

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=sys_asset,
            system_positions=[],
            broker_asset=broker_asset,
            broker_positions=[],
        )

        assert report.cash_match is False
        assert report.cash_difference == pytest.approx(500.0)
        assert report.is_consistent is False
        assert any("资金差异" in a for a in report.alerts)

    def test_reconcile_cash_within_tolerance(self):
        """资金差异在容差范围内应视为匹配。"""
        service = ReconciliationService(ReconciliationConfig(cash_tolerance=1.0))

        sys_asset = self._make_asset(available_cash=50_000.0)
        broker_asset = self._make_asset(available_cash=50_000.5)

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=sys_asset,
            system_positions=[],
            broker_asset=broker_asset,
            broker_positions=[],
        )

        assert report.cash_match is True

    # ========== 持仓差异：缺失 ==========

    def test_reconcile_missing_in_broker(self):
        """系统有持仓、券商无持仓应检测到差异。"""
        service = ReconciliationService()

        sys_positions = [self._make_position(ticker="600000.SH", total_volume=100)]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=self._make_asset(),
            system_positions=sys_positions,
            broker_asset=self._make_asset(),
            broker_positions=[],
        )

        assert report.positions_match is False
        assert len(report.position_differences) == 1
        diff = report.position_differences[0]
        assert diff.ticker == "600000.SH"
        assert diff.diff_type == DifferenceType.MISSING_IN_BROKER
        assert diff.system_volume == 100

    def test_reconcile_missing_in_system(self):
        """券商有持仓、系统无持仓应检测到差异。"""
        service = ReconciliationService()

        broker_positions = [self._make_position(ticker="000001.SZ", total_volume=200)]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=self._make_asset(),
            system_positions=[],
            broker_asset=self._make_asset(),
            broker_positions=broker_positions,
        )

        assert report.positions_match is False
        diff = report.position_differences[0]
        assert diff.diff_type == DifferenceType.MISSING_IN_SYSTEM
        assert diff.broker_volume == 200

    # ========== 持仓差异：数量不一致 ==========

    def test_reconcile_volume_mismatch(self):
        """持仓数量不一致应检测到差异。"""
        service = ReconciliationService()

        sys_pos = [self._make_position(ticker="600000.SH", total_volume=100)]
        broker_pos = [self._make_position(ticker="600000.SH", total_volume=200)]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=self._make_asset(),
            system_positions=sys_pos,
            broker_asset=self._make_asset(),
            broker_positions=broker_pos,
        )

        assert report.positions_match is False
        diff = report.position_differences[0]
        assert diff.diff_type == DifferenceType.VOLUME_MISMATCH
        assert diff.system_volume == 100
        assert diff.broker_volume == 200

    # ========== 持仓差异：成本不一致 ==========

    def test_reconcile_cost_mismatch(self):
        """持仓成本不一致应检测到差异。"""
        service = ReconciliationService(ReconciliationConfig(cost_tolerance=0.01))

        sys_pos = [self._make_position(
            ticker="600000.SH", total_volume=100, average_cost=10.0,
        )]
        broker_pos = [self._make_position(
            ticker="600000.SH", total_volume=100, average_cost=10.5,
        )]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=self._make_asset(),
            system_positions=sys_pos,
            broker_asset=self._make_asset(),
            broker_positions=broker_pos,
        )

        assert report.positions_match is False
        diff = report.position_differences[0]
        assert diff.diff_type == DifferenceType.COST_MISMATCH
        assert diff.system_cost == pytest.approx(10.0)
        assert diff.broker_cost == pytest.approx(10.5)

    def test_reconcile_cost_within_tolerance(self):
        """成本差异在容差范围内应视为匹配。"""
        service = ReconciliationService(ReconciliationConfig(cost_tolerance=0.1))

        sys_pos = [self._make_position(
            ticker="600000.SH", total_volume=100, average_cost=10.0,
        )]
        broker_pos = [self._make_position(
            ticker="600000.SH", total_volume=100, average_cost=10.05,
        )]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=self._make_asset(),
            system_positions=sys_pos,
            broker_asset=self._make_asset(),
            broker_positions=broker_pos,
        )

        assert report.positions_match is True

    # ========== 多标的混合差异 ==========

    def test_reconcile_multiple_differences(self):
        """多个标的同时存在不同类型差异。"""
        service = ReconciliationService()

        sys_pos = [
            self._make_position(ticker="600000.SH", total_volume=100),  # 数量不一致
            self._make_position(ticker="600519.SH", total_volume=200),  # 券商无
        ]
        broker_pos = [
            self._make_position(ticker="600000.SH", total_volume=300),
            self._make_position(ticker="000001.SZ", total_volume=500),  # 系统无
        ]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=self._make_asset(),
            system_positions=sys_pos,
            broker_asset=self._make_asset(),
            broker_positions=broker_pos,
        )

        assert report.positions_match is False
        assert len(report.position_differences) == 3
        types = {d.diff_type for d in report.position_differences}
        assert DifferenceType.VOLUME_MISMATCH in types
        assert DifferenceType.MISSING_IN_BROKER in types
        assert DifferenceType.MISSING_IN_SYSTEM in types

    # ========== 报告属性 ==========

    def test_report_date_and_account(self):
        """报告应正确记录日期和账户 ID。"""
        service = ReconciliationService()

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="ACC_001",
            system_asset=self._make_asset(),
            system_positions=[],
            broker_asset=self._make_asset(),
            broker_positions=[],
        )

        assert report.report_date == date(2026, 6, 1)
        assert report.account_id == "ACC_001"

    def test_alerts_generated_for_all_differences(self):
        """每条差异都应生成对应的告警消息。"""
        service = ReconciliationService()

        sys_asset = self._make_asset(available_cash=50_000.0)
        broker_asset = self._make_asset(available_cash=49_000.0)
        sys_pos = [self._make_position(ticker="600000.SH", total_volume=100)]
        broker_pos = [self._make_position(ticker="600000.SH", total_volume=200)]

        report = service.reconcile(
            report_date=date(2026, 6, 1),
            account_id="TEST",
            system_asset=sys_asset,
            system_positions=sys_pos,
            broker_asset=broker_asset,
            broker_positions=broker_pos,
        )

        # 1 条资金告警 + 1 条持仓告警
        assert len(report.alerts) >= 2
        assert report.is_consistent is False
