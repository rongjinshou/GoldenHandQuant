from datetime import datetime

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot


def _snap(symbol: str, date_str: str, name: str = "Test", mcap: float = 1e10) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol=symbol,
        date=datetime.strptime(date_str, "%Y-%m-%d"),
        name=name,
        list_date=datetime(2000, 1, 1),
        market_cap=mcap,
    )


class TestLatestDateAtOrBefore:
    def test_returns_most_recent_earlier_date(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-06-27"))
        registry.add(_snap("000001.SZ", "2026-06-30"))

        result = registry.latest_date_at_or_before(datetime(2026, 7, 3))

        assert result == datetime(2026, 6, 30)

    def test_returns_none_when_no_earlier_date(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-07-05"))

        assert registry.latest_date_at_or_before(datetime(2026, 7, 3)) is None

    def test_returns_none_on_empty_registry(self):
        registry = FundamentalRegistry()

        assert registry.latest_date_at_or_before(datetime(2026, 7, 3)) is None

    def test_exact_date_returns_that_date(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-06-30"))
        registry.add(_snap("000001.SZ", "2026-07-03"))

        result = registry.latest_date_at_or_before(datetime(2026, 7, 3))

        assert result == datetime(2026, 7, 3)

    def test_intraday_time_is_normalized_to_day(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-07-03"))

        result = registry.latest_date_at_or_before(datetime(2026, 7, 3, 14, 50))

        assert result == datetime(2026, 7, 3)


class TestAliasDate:
    def test_alias_copies_all_rows_to_dst_with_dst_date(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-06-30", "A"))
        registry.add(_snap("600000.SH", "2026-06-30", "B"))
        src = datetime(2026, 6, 30)
        dst = datetime(2026, 7, 3)

        count = registry.alias_date(src, dst)

        assert count == 2
        aliased = registry.get_all_at_date(dst)
        assert {s.symbol for s in aliased} == {"000001.SZ", "600000.SH"}
        assert all(s.date == dst for s in aliased)

    def test_alias_missing_src_is_noop(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-06-30"))

        count = registry.alias_date(datetime(2026, 6, 29), datetime(2026, 7, 3))

        assert count == 0
        assert registry.get_all_at_date(datetime(2026, 7, 3)) == []

    def test_alias_does_not_pollute_src_day_data(self):
        registry = FundamentalRegistry()
        original = _snap("000001.SZ", "2026-06-30")
        registry.add(original)
        src = datetime(2026, 6, 30)
        dst = datetime(2026, 7, 3)

        registry.alias_date(src, dst)

        src_rows = registry.get_all_at_date(src)
        assert len(src_rows) == 1
        assert src_rows[0] is original
        assert src_rows[0].date == src

    def test_alias_same_day_terminates(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-06-30"))
        day = datetime(2026, 6, 30)

        count = registry.alias_date(day, day)

        assert count == 1

    def test_aliased_snapshot_queryable_by_symbol_at_dst(self):
        registry = FundamentalRegistry()
        registry.add(_snap("000001.SZ", "2026-06-30", mcap=5e9))

        registry.alias_date(datetime(2026, 6, 30), datetime(2026, 7, 3))

        aliased = registry.get("000001.SZ", datetime(2026, 7, 3))
        assert aliased is not None
        assert aliased.market_cap == 5e9
        assert aliased.date == datetime(2026, 7, 3)
