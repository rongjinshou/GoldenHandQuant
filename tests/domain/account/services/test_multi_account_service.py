import pytest
from src.domain.account.entities.account_group import AccountGroup
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.services.multi_account_service import (
    CrossAccountRiskError,
    FundAllocationRule,
    MultiAccountService,
    RiskLimits,
)


class TestMultiAccountServiceRiskCheck:
    def test_check_global_risk_no_violations(self):
        service = MultiAccountService(risk_limits=RiskLimits(max_single_concentration=0.5))
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        assets = [
            Asset(account_id="A1", total_asset=100000, available_cash=50000, frozen_cash=0),
            Asset(account_id="A2", total_asset=100000, available_cash=50000, frozen_cash=0),
        ]
        positions = [
            Position(account_id="A1", ticker="600000.SH", total_volume=100, average_cost=10.0),
        ]
        violations = service.check_global_risk(group, assets, positions, {"600000.SH": 10.0})
        assert violations == []

    def test_check_global_risk_account_count_exceeded(self):
        service = MultiAccountService(risk_limits=RiskLimits(max_account_count=2))
        group = AccountGroup(
            group_id="G1", group_name="Test", account_ids=["A1", "A2", "A3"],
        )
        violations = service.check_global_risk(group, [], [])
        assert len(violations) == 1
        assert "Account count" in violations[0]

    def test_check_global_risk_concentration_exceeded(self):
        service = MultiAccountService(risk_limits=RiskLimits(max_single_concentration=0.05))
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        assets = [Asset(account_id="A1", total_asset=100000, available_cash=0, frozen_cash=0)]
        positions = [
            Position(account_id="A1", ticker="600000.SH", total_volume=1000, average_cost=10.0),
        ]
        violations = service.check_global_risk(group, assets, positions, {"600000.SH": 10.0})
        # concentration = 1000 * 10 / 100000 = 0.1 > 0.05
        assert len(violations) == 1
        assert "Concentration" in violations[0]

    def test_check_global_risk_total_exposure_exceeded(self):
        service = MultiAccountService(risk_limits=RiskLimits(max_total_exposure=50000))
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        assets = [Asset(account_id="A1", total_asset=100000, available_cash=100000, frozen_cash=0)]
        violations = service.check_global_risk(group, assets, [])
        assert len(violations) == 1
        assert "Total exposure" in violations[0]


class TestMultiAccountServiceAllocation:
    def test_compute_allocation_even_split(self):
        service = MultiAccountService()
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        assets = [
            Asset(account_id="A1", total_asset=100000, available_cash=100000, frozen_cash=0),
            Asset(account_id="A2", total_asset=100000, available_cash=100000, frozen_cash=0),
        ]
        rules = [
            FundAllocationRule(target_account_id="A1", target_ratio=0.5),
            FundAllocationRule(target_account_id="A2", target_ratio=0.5),
        ]
        result = service.compute_allocation(group, assets, rules)
        # Total transferable = 200000, each target = 100000
        # A1: 100000 - 100000 = 0, A2: 100000 - 100000 = 0
        assert result["A1"] == pytest.approx(0.0)
        assert result["A2"] == pytest.approx(0.0)

    def test_compute_allocation_rebalance(self):
        service = MultiAccountService()
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        assets = [
            Asset(account_id="A1", total_asset=150000, available_cash=150000, frozen_cash=0),
            Asset(account_id="A2", total_asset=50000, available_cash=50000, frozen_cash=0),
        ]
        rules = [
            FundAllocationRule(target_account_id="A1", target_ratio=0.5),
            FundAllocationRule(target_account_id="A2", target_ratio=0.5),
        ]
        result = service.compute_allocation(group, assets, rules)
        # Total = 200000, each target = 100000
        # A1: 100000 - 150000 = -50000 (should transfer out)
        # A2: 100000 - 50000 = 50000 (should transfer in)
        assert result["A1"] == pytest.approx(-50000.0)
        assert result["A2"] == pytest.approx(50000.0)

    def test_compute_allocation_with_explicit_total(self):
        service = MultiAccountService()
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        assets = [
            Asset(account_id="A1", total_asset=100000, available_cash=100000, frozen_cash=0),
            Asset(account_id="A2", total_asset=100000, available_cash=100000, frozen_cash=0),
        ]
        rules = [
            FundAllocationRule(target_account_id="A1", target_ratio=0.8),
            FundAllocationRule(target_account_id="A2", target_ratio=0.2),
        ]
        result = service.compute_allocation(group, assets, rules, total_transferable=100000)
        # A1 target = 80000, current = 100000, diff = -20000
        # A2 target = 20000, current = 100000, diff = -80000
        assert result["A1"] == pytest.approx(-20000.0)
        assert result["A2"] == pytest.approx(-80000.0)


class TestMultiAccountServiceMergePositions:
    def test_merge_positions_delegates_to_group(self):
        service = MultiAccountService()
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        positions = [
            Position(account_id="A1", ticker="600000.SH", total_volume=500, available_volume=500, average_cost=10.0),
            Position(account_id="A2", ticker="600000.SH", total_volume=300, available_volume=200, average_cost=12.0),
        ]
        result = service.merge_positions(group, positions)
        assert "600000.SH" in result
        assert result["600000.SH"].total_volume == 800
        assert result["600000.SH"].available_volume == 700
