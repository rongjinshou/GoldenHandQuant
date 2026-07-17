"""shadow_cmd 装配闭包: 三值交易日/最坏 health 合并/比对文件加载/纸面净值计数。"""
import json
from datetime import date
from pathlib import Path

from src.interfaces.cli.commands.shadow_cmd import (
    _check_loader,
    _paper_count,
    _snapshot_health,
    _trading_day_fn,
)


class FakeTradingStore:
    def __init__(self, rows):
        self._rows = rows

    def load_signal_snapshots(self, limit=20):
        return self._rows


class FakeMarketStore:
    def __init__(self, days, runs=()):
        self._days = days
        self._runs = list(runs)

    def trading_dates(self, source="qmt"):
        return self._days

    def load_backtest_runs(self, limit=100):
        return self._runs


class TestSnapshotHealth:
    def test_filters_mode_and_keeps_worst_health(self):
        rows = [
            {"snapshot_time": "2026-07-07T09:35:00", "mode": "dry_run", "data_health": "ok"},
            {"snapshot_time": "2026-07-07T14:50:00", "mode": "dry_run", "data_health": "fault"},
            {"snapshot_time": "2026-07-08T09:35:00", "mode": "live", "data_health": "ok"},
        ]
        health = _snapshot_health(FakeTradingStore(rows))
        assert health == {date(2026, 7, 7): "fault"}

    def test_fault_not_overwritten_by_later_ok(self):
        rows = [
            {"snapshot_time": "2026-07-07T09:35:00", "mode": "dry_run", "data_health": "fault"},
            {"snapshot_time": "2026-07-07T14:50:00", "mode": "dry_run", "data_health": "ok"},
        ]
        assert _snapshot_health(FakeTradingStore(rows)) == {date(2026, 7, 7): "fault"}


class TestTradingDayTriState:
    def test_known_true_false_and_unknown(self):
        fn = _trading_day_fn(FakeMarketStore([date(2026, 7, 9), date(2026, 7, 10)]))
        assert fn(date(2026, 7, 10)) is True
        assert fn(date(2026, 7, 5)) is False      # 已知区内的非交易日
        assert fn(date(2026, 7, 14)) is None       # 超出已知最大日

    def test_empty_store_is_all_unknown(self):
        fn = _trading_day_fn(FakeMarketStore([]))
        assert fn(date(2026, 7, 10)) is None


class TestCheckLoader:
    def test_missing_file_none_and_consistent_roundtrip(self, tmp_path: Path):
        load = _check_loader(tmp_path)
        assert load(date(2026, 7, 7)) is None
        (tmp_path / "2026-07-14.json").write_text(
            json.dumps({"consistent": True}), encoding="utf-8"
        )
        assert load(date(2026, 7, 14)) is True

    def test_corrupt_file_counts_as_diverged(self, tmp_path: Path):
        (tmp_path / "2026-07-14.json").write_text("{not-json", encoding="utf-8")
        assert _check_loader(tmp_path)(date(2026, 7, 14)) is False


class TestPaperCount:
    def test_counts_distinct_shadow_paper_runs_only(self):
        runs = [
            {"run_id": "SHADOW-PAPER-20260704"},
            {"run_id": "SHADOW-PAPER-20260704"},
            {"run_id": "SHADOW-PAPER-20260714"},
            {"run_id": "20260710-233436"},
        ]
        assert _paper_count(FakeMarketStore([], runs)) == 2


class TestTradingDayFnWithExchangeCalendar:
    """兑现①: 交易所日历(含未来)优先于 bars 推导——未来周二可预判 EXEMPT/交易日。"""

    class CalStore(FakeMarketStore):
        def __init__(self, days, cal):
            super().__init__(days)
            self._cal = cal

        def load_trade_calendar(self):
            return self._cal

    def test_future_dates_resolved_by_exchange_calendar(self):
        cal = (frozenset({date(2026, 7, 14), date(2026, 12, 31)}), date(2026, 12, 31))
        fn = _trading_day_fn(self.CalStore([date(2026, 7, 10)], cal))
        assert fn(date(2026, 7, 14)) is True      # 未来交易日: bars 推导下本是 None
        assert fn(date(2026, 10, 6)) is False     # 未来节假日周二 → 可预判 EXEMPT
        assert fn(date(2027, 1, 5)) is None       # 超出日历末端仍诚实 UNKNOWN

    def test_fallback_to_bars_when_calendar_absent(self):
        class NoCal(FakeMarketStore):
            def load_trade_calendar(self):
                return None
        fn = _trading_day_fn(NoCal([date(2026, 7, 9), date(2026, 7, 10)]))
        assert fn(date(2026, 7, 10)) is True
        assert fn(date(2026, 7, 14)) is None      # 回退旧行为
