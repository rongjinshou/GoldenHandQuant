
from datetime import datetime
from src.domain.strategy.services.filters.filter_st import filter_st
from src.domain.strategy.services.filters.filter_new_listing import filter_new_listing
from src.domain.strategy.services.filters.filter_penny_stock import filter_penny_stock
from src.domain.strategy.services.filters.filter_trading_status import filter_trading_status
from src.domain.strategy.services.filters.filter_quality import filter_quality
from src.domain.market.value_objects.stock_snapshot import StockSnapshot

def _snap(symbol, **kwargs):
    defaults = dict(
        symbol=symbol, date=datetime(2024, 6, 15),
        open=10.0, high=10.5, low=9.8, close=10.2, volume=1e6,
        name="Normal Stock",
        list_date=datetime(2000, 1, 1),
        market_cap=1e10, roe_ttm=0.15, ocf_ttm=5e8,
    )
    defaults.update(kwargs)
    return StockSnapshot(**defaults)

class TestFilterST:
    def test_removes_st_stocks(self):
        snaps = [
            _snap("000001.SZ", name="ST 股票"),
            _snap("000002.SZ", name="*ST 退市"),
            _snap("000003.SZ", name="平安银行"),
        ]
        result = filter_st(snaps)
        assert len(result) == 1
        assert result[0].symbol == "000003.SZ"

    def test_keeps_st_in_middle_of_name(self):
        snaps = [_snap("000001.SZ", name="BEST Inc")]
        result = filter_st(snaps)
        assert len(result) == 1

    def test_empty_list(self):
        assert filter_st([]) == []

class TestFilterNewListing:
    def test_removes_stocks_listed_less_than_365_days(self):
        date = datetime(2024, 6, 15)
        snaps = [
            _snap("000001.SZ", list_date=datetime(2024, 1, 1)),   # < 365 days
            _snap("000002.SZ", list_date=datetime(2000, 1, 1)),   # old stock
        ]
        result = filter_new_listing(snaps, date)
        assert len(result) == 1
        assert result[0].symbol == "000002.SZ"

    def test_keeps_stock_exactly_365_days(self):
        date = datetime(2024, 6, 15)
        snaps = [_snap("000001.SZ", list_date=datetime(2023, 6, 16))]
        result = filter_new_listing(snaps, date)
        assert len(result) == 1  # exactly 365 days is >= 365

class TestFilterPennyStock:
    def test_removes_stocks_below_min_price(self):
        snaps = [
            _snap("000001.SZ", close=1.2),
            _snap("000002.SZ", close=1.5),
            _snap("000003.SZ", close=5.0),
        ]
        result = filter_penny_stock(snaps, min_price=1.5)
        assert len(result) == 2
        symbols = {s.symbol for s in result}
        assert symbols == {"000002.SZ", "000003.SZ"}

    def test_default_min_price(self):
        snaps = [_snap("000001.SZ", close=1.49)]
        assert len(filter_penny_stock(snaps)) == 0

class TestFilterTradingStatus:
    def test_removes_suspended_stocks(self):
        snaps = [_snap("000001.SZ", volume=0), _snap("000002.SZ", volume=1e6)]
        result = filter_trading_status(snaps)
        assert len(result) == 1
        assert result[0].symbol == "000002.SZ"

    def test_removes_limit_up_or_down_lock(self):
        snaps = [
            _snap("000001.SZ", open=10.0, high=10.0, low=10.0, close=10.0),
            _snap("000002.SZ", open=10.0, high=11.0, low=9.5, close=10.5),
        ]
        result = filter_trading_status(snaps)
        assert len(result) == 1
        assert result[0].symbol == "000002.SZ"

class TestFilterQuality:
    def test_keeps_stocks_above_median_roe_and_positive_ocf(self):
        snaps = [
            _snap("A", roe_ttm=0.20, ocf_ttm=1e8),   # ROE high, OCF > 0 → keep
            _snap("B", roe_ttm=0.10, ocf_ttm=1e8),   # ROE mid, OCF > 0 → ?
            _snap("C", roe_ttm=0.05, ocf_ttm=1e8),   # ROE low, OCF > 0 → drop
            _snap("D", roe_ttm=0.25, ocf_ttm=-1e8),  # ROE high, OCF < 0 → drop
        ]
        result = filter_quality(snaps, min_universe_size=0)
        symbols = {s.symbol for s in result}
        assert symbols == {"A"}

    def test_excludes_missing_financials(self):
        snaps = [
            _snap("A", roe_ttm=None, ocf_ttm=1e8),
            _snap("B", roe_ttm=0.15, ocf_ttm=None),
            _snap("C", roe_ttm=0.15, ocf_ttm=1e8),
            _snap("D", roe_ttm=0.20, ocf_ttm=1e8),
        ]
        result = filter_quality(snaps, min_universe_size=0)
        assert len(result) == 1
        assert result[0].symbol == "D"

    def test_small_universe_returns_all_valid(self):
        snaps = [
            _snap("A", roe_ttm=0.15, ocf_ttm=1e8),
            _snap("B", roe_ttm=0.10, ocf_ttm=1e8),
        ]
        result = filter_quality(snaps, min_universe_size=30)
        assert len(result) == 2  # below min_universe_size, no filtering
