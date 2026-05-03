from datetime import datetime
from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot

def _snap(symbol, date_str, name="Test", mcap=1e10):
    return FundamentalSnapshot(
        symbol=symbol,
        date=datetime.strptime(date_str, "%Y-%m-%d"),
        name=name,
        list_date=datetime(2000, 1, 1),
        market_cap=mcap,
    )

class TestFundamentalRegistry:
    def test_add_and_get_by_symbol(self):
        registry = FundamentalRegistry()
        s1 = _snap("000001.SZ", "2024-06-15", "Stock A")
        s2 = _snap("000001.SZ", "2024-06-16", "Stock A")
        registry.add(s1)
        registry.add(s2)

        assert registry.get("000001.SZ", datetime(2024, 6, 15)) is s1
        assert registry.get("000001.SZ", datetime(2024, 6, 16)) is s2
        assert registry.get("000001.SZ", datetime(2024, 6, 17)) is None

    def test_get_all_at_date_returns_all_symbols(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2024-06-15", "A"))
        registry.add(_snap("000002.SZ", "2024-06-15", "B"))
        registry.add(_snap("000003.SZ", "2024-06-16", "C"))

        results = registry.get_all_at_date(datetime(2024, 6, 15))
        assert len(results) == 2
        symbols = {s.symbol for s in results}
        assert symbols == {"000001.SZ", "000002.SZ"}

    def test_get_all_at_date_empty_returns_empty_list(self):
        registry = FundamentalRegistry()
        results = registry.get_all_at_date(datetime(2024, 6, 15))
        assert results == []
