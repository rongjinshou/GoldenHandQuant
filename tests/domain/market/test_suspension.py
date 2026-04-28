from datetime import datetime
from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry


def test_normal_stock_is_tradable():
    status = StockStatus(symbol="000001.SZ", date=datetime(2024, 1, 3))
    assert status.is_tradable() is True


def test_suspended_stock_is_not_tradable():
    status = StockStatus(symbol="000001.SZ", date=datetime(2024, 1, 3), is_suspended=True)
    assert status.is_tradable() is False


def test_star_st_stock_is_not_tradable():
    status = StockStatus(symbol="000001.SZ", date=datetime(2024, 1, 3), is_star_st=True)
    assert status.is_tradable() is False


def test_registry_returns_true_for_unknown_symbol():
    registry = StockStatusRegistry()
    assert registry.is_tradable("UNKNOWN.SZ", datetime(2024, 1, 3)) is True


def test_registry_tracks_status_by_date():
    registry = StockStatusRegistry()
    d1 = datetime(2024, 1, 3)
    d2 = datetime(2024, 1, 4)
    registry.add(StockStatus(symbol="000001.SZ", date=d1, is_suspended=True))
    registry.add(StockStatus(symbol="000001.SZ", date=d2))
    assert registry.is_tradable("000001.SZ", d1) is False
    assert registry.is_tradable("000001.SZ", d2) is True
