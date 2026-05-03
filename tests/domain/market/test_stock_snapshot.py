from datetime import datetime
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def test_stock_snapshot_creation():
    snap = StockSnapshot(
        symbol="000001.SZ",
        date=datetime(2024, 6, 15),
        open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
        name="平安银行",
        list_date=datetime(1991, 4, 3),
        market_cap=2.5e11,
        roe_ttm=0.12,
        ocf_ttm=1.5e10,
    )
    assert snap.open == 10.0
    assert snap.close == 10.2
    assert snap.volume == 1e6
    assert snap.name == "平安银行"
    assert snap.roe_ttm == 0.12

def test_stock_snapshot_nullable_financials():
    snap = StockSnapshot(
        symbol="000002.SZ",
        date=datetime(2024, 6, 15),
        open=8.0, high=8.3, low=7.9, close=8.1, volume=5e5,
        name="万科A",
        list_date=datetime(1991, 1, 29),
        market_cap=1.0e11,
    )
    assert snap.roe_ttm is None
    assert snap.ocf_ttm is None
