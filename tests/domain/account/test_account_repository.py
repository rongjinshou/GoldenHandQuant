from src.domain.account.entities.account_repository import AccountRepository
from src.domain.account.entities.position import Position


def test_create_account_initializes_asset_and_empty_positions():
    repo = AccountRepository()
    asset = repo.create_account("ACC_001", 500000.0)
    assert asset.account_id == "ACC_001"
    assert asset.available_cash == 500000.0
    assert repo.get_positions("ACC_001") == []


def test_create_duplicate_account_raises_error():
    repo = AccountRepository()
    repo.create_account("ACC_001", 100000.0)
    try:
        repo.create_account("ACC_001", 200000.0)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_upsert_and_get_position():
    repo = AccountRepository()
    repo.create_account("ACC_001", 100000.0)
    pos = Position(
        account_id="ACC_001", ticker="000001.SZ",
        total_volume=500, available_volume=500, average_cost=10.0,
    )
    repo.upsert_position("ACC_001", pos)
    retrieved = repo.get_position("ACC_001", "000001.SZ")
    assert retrieved is not None
    assert retrieved.total_volume == 500


def test_list_accounts_returns_all_ids():
    repo = AccountRepository()
    repo.create_account("A", 1000)
    repo.create_account("B", 2000)
    assert sorted(repo.list_accounts()) == ["A", "B"]


def test_get_asset_nonexistent_returns_none():
    repo = AccountRepository()
    assert repo.get_asset("NONEXISTENT") is None


def test_remove_position():
    repo = AccountRepository()
    repo.create_account("ACC_001", 100000.0)
    pos = Position(
        account_id="ACC_001", ticker="000001.SZ",
        total_volume=500, available_volume=500, average_cost=10.0,
    )
    repo.upsert_position("ACC_001", pos)
    repo.remove_position("ACC_001", "000001.SZ")
    assert repo.get_position("ACC_001", "000001.SZ") is None
