import pytest
from src.domain.account.entities.account_group import AccountGroup
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


class TestAccountGroup:
    def test_init_should_set_default_values(self):
        group = AccountGroup(group_id="G1", group_name="Test Group")
        assert group.group_id == "G1"
        assert group.group_name == "Test Group"
        assert group.account_ids == []

    def test_add_account_should_append_to_list(self):
        group = AccountGroup(group_id="G1", group_name="Test")
        group.add_account("ACC_001")
        assert "ACC_001" in group.account_ids

    def test_add_duplicate_account_should_raise(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["ACC_001"])
        with pytest.raises(ValueError, match="already in group"):
            group.add_account("ACC_001")

    def test_remove_account_should_remove_from_list(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["ACC_001", "ACC_002"])
        group.remove_account("ACC_001")
        assert "ACC_001" not in group.account_ids
        assert "ACC_002" in group.account_ids

    def test_remove_nonexistent_account_should_raise(self):
        group = AccountGroup(group_id="G1", group_name="Test")
        with pytest.raises(ValueError, match="not in group"):
            group.remove_account("ACC_999")


class TestAccountGroupAggregateAssets:
    def test_aggregate_assets_should_sum_all_accounts(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        assets = [
            Asset(account_id="A1", total_asset=100000, available_cash=60000, frozen_cash=10000),
            Asset(account_id="A2", total_asset=200000, available_cash=150000, frozen_cash=20000),
        ]
        result = group.aggregate_assets(assets)
        assert result["total_asset"] == 300000
        assert result["available_cash"] == 210000
        assert result["frozen_cash"] == 30000

    def test_aggregate_assets_should_ignore_accounts_not_in_group(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        assets = [
            Asset(account_id="A1", total_asset=100000, available_cash=100000, frozen_cash=0),
            Asset(account_id="A2", total_asset=200000, available_cash=200000, frozen_cash=0),
        ]
        result = group.aggregate_assets(assets)
        assert result["total_asset"] == 100000

    def test_aggregate_assets_empty_should_return_zeros(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        result = group.aggregate_assets([])
        assert result["total_asset"] == 0.0
        assert result["available_cash"] == 0.0
        assert result["frozen_cash"] == 0.0


class TestAccountGroupAggregatePositions:
    def test_aggregate_positions_should_merge_by_ticker(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1", "A2"])
        positions = [
            Position(account_id="A1", ticker="600000.SH", total_volume=500, available_volume=500, average_cost=10.0),
            Position(account_id="A2", ticker="600000.SH", total_volume=300, available_volume=300, average_cost=12.0),
        ]
        result = group.aggregate_positions(positions)
        assert "600000.SH" in result
        merged = result["600000.SH"]
        assert merged.total_volume == 800
        assert merged.available_volume == 800
        # weighted avg cost: (500*10 + 300*12) / 800 = 8600/800 = 10.75
        assert abs(merged.average_cost - 10.75) < 0.001

    def test_aggregate_positions_should_use_group_id_as_account_id(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        positions = [
            Position(account_id="A1", ticker="000001.SZ", total_volume=100, available_volume=100, average_cost=5.0),
        ]
        result = group.aggregate_positions(positions)
        assert result["000001.SZ"].account_id == "G1"

    def test_aggregate_positions_should_skip_positions_from_other_accounts(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        positions = [
            Position(account_id="A1", ticker="600000.SH", total_volume=500, available_volume=500, average_cost=10.0),
            Position(account_id="A3", ticker="600000.SH", total_volume=200, available_volume=200, average_cost=11.0),
        ]
        result = group.aggregate_positions(positions)
        assert result["600000.SH"].total_volume == 500

    def test_aggregate_positions_empty_should_return_empty(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        result = group.aggregate_positions([])
        assert result == {}


class TestAccountGroupConcentration:
    def test_compute_concentration_returns_max_ratio(self):
        group = AccountGroup(group_id="G1", group_name="Test", account_ids=["A1"])
        agg_assets = {"total_asset": 100000, "available_cash": 50000, "frozen_cash": 0}
        agg_positions = {
            "600000.SH": Position(account_id="G1", ticker="600000.SH", total_volume=100, average_cost=10.0),
            "000001.SZ": Position(account_id="G1", ticker="000001.SZ", total_volume=50, average_cost=20.0),
        }
        result = group.compute_concentration(agg_assets, agg_positions, {"600000.SH": 12.0, "000001.SZ": 20.0})
        # 600000.SH: 100 * 12 = 1200, ratio = 1200/100000 = 0.012
        # 000001.SZ: 50 * 20 = 1000, ratio = 1000/100000 = 0.01
        assert result["max_concentration_ticker"] == "600000.SH"
        assert abs(result["max_concentration"] - 0.012) < 0.0001
        assert result["position_count"] == 2

    def test_compute_concentration_zero_asset_returns_zeros(self):
        group = AccountGroup(group_id="G1", group_name="Test")
        result = group.compute_concentration({"total_asset": 0, "available_cash": 0, "frozen_cash": 0}, {})
        assert result["max_concentration"] == 0.0
        assert result["position_count"] == 0
