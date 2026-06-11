"""DuckDBHistoryDataFetcher 测试 — tmp DuckDB 造数, 覆盖读取/窗口/回退。"""
from datetime import datetime

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher
from src.infrastructure.persistence.market_data_store import MarketDataStore


def _bar(symbol: str, date: str, close: float) -> Bar:
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1,
        timestamp=datetime.strptime(date, "%Y-%m-%d"),
        open=close - 0.5, high=close + 1.0, low=close - 1.0, close=close,
        volume=1000.0, prev_close=close - 0.2,
    )


class _FakeFallback:
    def __init__(self, bars=None):
        self.calls: list[tuple] = []
        self._bars = bars or []

    def fetch_history_bars(self, symbol, timeframe, start_date, end_date):
        self.calls.append((symbol, timeframe, start_date, end_date))
        return self._bars


def _seeded_db(tmp_path) -> str:
    db = str(tmp_path / "m.duckdb")
    s = MarketDataStore(db)
    s.upsert_bars(
        [_bar("600000.SH", f"2024-01-{d:02d}", 10.0 + d) for d in range(2, 12)],
        "qmt",
    )
    s.close()
    return db


class TestFetch:
    def test_reads_bars_sorted_with_fields(self, tmp_path):
        f = DuckDBHistoryDataFetcher(_seeded_db(tmp_path))

        bars = f.fetch_history_bars("600000.SH", Timeframe.DAY_1,
                                    "2024-01-01", "2024-12-31")

        assert len(bars) == 10
        assert bars[0].timestamp == datetime(2024, 1, 2)
        assert bars[-1].timestamp == datetime(2024, 1, 11)
        assert bars[0].close == 12.0 and bars[0].open == 11.5
        assert bars[0].prev_close == 11.8
        assert bars[0].timeframe == Timeframe.DAY_1

    def test_date_window_clipped(self, tmp_path):
        f = DuckDBHistoryDataFetcher(_seeded_db(tmp_path))

        bars = f.fetch_history_bars("600000.SH", Timeframe.DAY_1,
                                    "2024-01-05", "2024-01-08")

        assert [b.timestamp.day for b in bars] == [5, 6, 7, 8]


class TestFallback:
    def test_missing_symbol_uses_fallback(self, tmp_path):
        fb = _FakeFallback(bars=[_bar("000852.SH", "2024-01-02", 5000.0)])
        f = DuckDBHistoryDataFetcher(_seeded_db(tmp_path), fallback=fb)

        bars = f.fetch_history_bars("000852.SH", Timeframe.DAY_1,
                                    "2024-01-01", "2024-12-31")

        assert len(bars) == 1 and fb.calls
        assert fb.calls[0][0] == "000852.SH"

    def test_missing_symbol_without_fallback_returns_empty(self, tmp_path):
        f = DuckDBHistoryDataFetcher(_seeded_db(tmp_path))
        assert f.fetch_history_bars("000852.SH", Timeframe.DAY_1,
                                    "2024-01-01", "2024-12-31") == []

    def test_non_daily_timeframe_goes_to_fallback(self, tmp_path):
        fb = _FakeFallback()
        f = DuckDBHistoryDataFetcher(_seeded_db(tmp_path), fallback=fb)

        f.fetch_history_bars("600000.SH", Timeframe.MIN_5,
                             "2024-01-01", "2024-12-31")

        assert fb.calls and fb.calls[0][1] == Timeframe.MIN_5
