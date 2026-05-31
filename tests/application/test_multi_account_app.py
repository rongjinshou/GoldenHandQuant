import pytest
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.account_group_repository import AccountGroupRepository
from src.domain.account.interfaces.account_repository import AccountRepository
from src.domain.account.services.multi_account_service import FundAllocationRule, RiskLimits
from src.application.multi_account_app import GlobalSnapshot, MultiAccountAppService


@pytest.fixture
def app_service():
    account_repo = AccountRepository()
    group_repo = AccountGroupRepository()

    # 创建两个账户
    account_repo.create_account("ACC_001", 100000.0)
    account_repo.create_account("ACC_002", 200000.0)

    return MultiAccountAppService(
        account_repo=account_repo,
        group_repo=group_repo,
        risk_limits=RiskLimits(max_single_concentration=0.5, max_account_count=10),
    )


class TestMultiAccountAppServiceGroupManagement:
    def test_create_group(self, app_service):
        group = app_service.create_group("G1", "Test Group", ["ACC_001", "ACC_002"])
        assert group.group_id == "G1"
        assert group.group_name == "Test Group"
        assert group.account_ids == ["ACC_001", "ACC_002"]

    def test_create_duplicate_group_raises(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001"])
        with pytest.raises(ValueError, match="already exists"):
            app_service.create_group("G1", "Test2", ["ACC_002"])

    def test_create_group_with_nonexistent_account_raises(self, app_service):
        with pytest.raises(ValueError, match="does not exist"):
            app_service.create_group("G1", "Test", ["ACC_999"])

    def test_add_account_to_group(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001"])
        app_service.add_account_to_group("G1", "ACC_002")
        snapshot = app_service.get_global_snapshot("G1")
        assert "ACC_001" in snapshot.account_details
        assert "ACC_002" in snapshot.account_details

    def test_remove_account_from_group(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001", "ACC_002"])
        app_service.remove_account_from_group("G1", "ACC_002")
        snapshot = app_service.get_global_snapshot("G1")
        assert "ACC_001" in snapshot.account_details
        assert "ACC_002" not in snapshot.account_details

    def test_add_to_nonexistent_group_raises(self, app_service):
        with pytest.raises(ValueError, match="not found"):
            app_service.add_account_to_group("G1", "ACC_001")


class TestMultiAccountAppServiceSnapshot:
    def test_get_global_snapshot_aggregates_assets(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001", "ACC_002"])
        snapshot = app_service.get_global_snapshot("G1")
        assert isinstance(snapshot, GlobalSnapshot)
        assert snapshot.total_asset == 300000.0
        assert snapshot.available_cash == 300000.0
        assert snapshot.group_id == "G1"

    def test_get_global_snapshot_includes_account_details(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001", "ACC_002"])
        snapshot = app_service.get_global_snapshot("G1")
        assert snapshot.account_details["ACC_001"]["total_asset"] == 100000.0
        assert snapshot.account_details["ACC_002"]["total_asset"] == 200000.0

    def test_get_global_snapshot_with_positions(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001", "ACC_002"])
        # 添加持仓到 account_repo
        app_service._account_repo.upsert_position(
            "ACC_001",
            Position(account_id="ACC_001", ticker="600000.SH", total_volume=500, available_volume=500, average_cost=10.0),
        )
        app_service._account_repo.upsert_position(
            "ACC_002",
            Position(account_id="ACC_002", ticker="600000.SH", total_volume=300, available_volume=300, average_cost=12.0),
        )
        snapshot = app_service.get_global_snapshot("G1", {"600000.SH": 11.0})
        assert snapshot.position_count == 1
        assert snapshot.max_concentration > 0

    def test_get_nonexistent_group_raises(self, app_service):
        with pytest.raises(ValueError, match="not found"):
            app_service.get_global_snapshot("G1")


class TestMultiAccountAppServiceRiskCheck:
    def test_run_global_risk_check_no_violations(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001", "ACC_002"])
        violations = app_service.run_global_risk_check("G1")
        assert violations == []

    def test_run_global_risk_check_concentration_violation(self, app_service):
        # 小账户组，高集中度阈值
        app_service.create_group("G1", "Test", ["ACC_001"])
        app_service._account_repo.upsert_position(
            "ACC_001",
            Position(account_id="ACC_001", ticker="600000.SH", total_volume=10000, average_cost=10.0),
        )
        violations = app_service.run_global_risk_check("G1", {"600000.SH": 10.0})
        # 10000 * 10 / 100000 = 1.0 > 0.5
        assert len(violations) == 1
        assert "Concentration" in violations[0]


class TestMultiAccountAppServiceFundAllocation:
    def test_compute_fund_allocation(self, app_service):
        app_service.create_group("G1", "Test", ["ACC_001", "ACC_002"])
        rules = [
            FundAllocationRule(target_account_id="ACC_001", target_ratio=0.5),
            FundAllocationRule(target_account_id="ACC_002", target_ratio=0.5),
        ]
        result = app_service.compute_fund_allocation("G1", rules)
        # Total = 300000, each target = 150000
        # ACC_001: 150000 - 100000 = 50000
        # ACC_002: 150000 - 200000 = -50000
        assert result["ACC_001"] == pytest.approx(50000.0)
        assert result["ACC_002"] == pytest.approx(-50000.0)

    def test_compute_fund_allocation_nonexistent_group_raises(self, app_service):
        with pytest.raises(ValueError, match="not found"):
            app_service.compute_fund_allocation("G1", [])


class TestBackwardCompatibilitySingleAccount:
    """验证单账户模式下行为不受影响。"""

    def test_single_account_group_works_like_normal(self):
        account_repo = AccountRepository()
        group_repo = AccountGroupRepository()
        account_repo.create_account("SOLO", 500000.0)

        service = MultiAccountAppService(account_repo=account_repo, group_repo=group_repo)
        group = service.create_group("SOLO_GROUP", "Solo", ["SOLO"])

        snapshot = service.get_global_snapshot("SOLO_GROUP")
        assert snapshot.total_asset == 500000.0
        assert snapshot.position_count == 0
        assert snapshot.violations == []

    def test_account_repo_still_works_independently(self):
        """AccountRepository 本身不受 multi-account 影响。"""
        repo = AccountRepository()
        repo.create_account("A", 100000.0)
        repo.create_account("B", 200000.0)
        assert sorted(repo.list_accounts()) == ["A", "B"]
        assert repo.get_asset("A").total_asset == 100000.0
