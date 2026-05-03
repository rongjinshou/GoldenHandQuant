from datetime import datetime
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

def test_fundamental_snapshot_creation():
    snap = FundamentalSnapshot(
        symbol="000001.SZ",
        date=datetime(2024, 6, 15),
        name="平安银行",
        list_date=datetime(1991, 4, 3),
        market_cap=2.5e11,
        roe_ttm=0.12,
        ocf_ttm=1.5e10,
    )
    assert snap.symbol == "000001.SZ"
    assert snap.name == "平安银行"
    assert snap.market_cap == 2.5e11
    assert snap.roe_ttm == 0.12
    assert snap.ocf_ttm == 1.5e10

def test_fundamental_snapshot_nullable_fields():
    snap = FundamentalSnapshot(
        symbol="000002.SZ",
        date=datetime(2024, 6, 15),
        name="万科A",
        list_date=datetime(1991, 1, 29),
        market_cap=1.0e11,
        roe_ttm=None,
        ocf_ttm=None,
    )
    assert snap.roe_ttm is None
    assert snap.ocf_ttm is None
