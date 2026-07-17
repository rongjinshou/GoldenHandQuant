"""ShadowAuditService: 采样台账七状态 + 过闸判据(设计 0711-shadow-control SC-1/SC-2)。

采样口径双时代: 2026-07-14 前=周二(史料), 07-14 起=每个工作日(用户指令日频半个月)。
"""
from datetime import date, timedelta

from src.application.shadow_audit import (
    ShadowAuditService,
    TuesdayStatus,
)

# 2026-07 周二: 07-07 / 07-14 / 07-21 / 07-28; 日频时代起点 = 07-14


def _weekdays(start: date, n: int) -> list[date]:
    out, cur = [], start
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def _service(
    *,
    health: dict[date, str] | None = None,
    trading: dict[date, bool] | None = None,
    known_max: date = date(2026, 7, 10),
    checks: dict[date, bool] | None = None,
    paper_count: int = 0,
) -> ShadowAuditService:
    health = health or {}
    trading = trading or {}
    checks = checks or {}

    def is_trading_day(d: date) -> bool | None:
        if d > known_max:
            return None
        return trading.get(d, True)

    return ShadowAuditService(
        snapshot_health_by_day=lambda: dict(health),
        is_trading_day=is_trading_day,
        load_check=lambda d: checks.get(d),
        paper_run_count=lambda: paper_count,
    )


class TestTuesdayLedger:
    def test_missed_when_trading_tuesday_has_no_snapshot(self):
        svc = _service()
        rep = svc.report(today=date(2026, 7, 11))
        assert [r.day for r in rep.ledger] == [date(2026, 7, 7)]
        assert rep.ledger[0].status is TuesdayStatus.MISSED
        assert rep.missed_count == 1

    def test_exempt_when_holiday_tuesday(self):
        svc = _service(trading={date(2026, 7, 7): False})
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.ledger[0].status is TuesdayStatus.EXEMPT
        assert rep.missed_count == 0

    def test_unknown_when_bars_not_refreshed_past_that_day(self):
        svc = _service(known_max=date(2026, 7, 6))
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.ledger[0].status is TuesdayStatus.UNKNOWN
        assert rep.unknown_count == 1

    def test_valid_when_sampled_and_check_consistent(self):
        d = date(2026, 7, 7)
        svc = _service(health={d: "ok"}, checks={d: True})
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.ledger[0].status is TuesdayStatus.VALID
        assert rep.valid_count == 1

    def test_unchecked_when_sampled_without_check_file(self):
        d = date(2026, 7, 7)
        svc = _service(health={d: "ok"})
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.ledger[0].status is TuesdayStatus.UNCHECKED
        assert rep.valid_count == 0

    def test_diverged_when_check_inconsistent(self):
        d = date(2026, 7, 7)
        svc = _service(health={d: "ok"}, checks={d: False})
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.ledger[0].status is TuesdayStatus.DIVERGED
        assert rep.diverged_count == 1

    def test_today_tuesday_without_snapshot_is_pending_not_missed(self):
        today = date(2026, 7, 14)
        svc = _service(known_max=date(2026, 7, 13))
        rep = svc.report(today=today)
        by_day = {r.day: r.status for r in rep.ledger}
        assert by_day[today] is TuesdayStatus.PENDING
        assert rep.next_due == today


class TestNextDue:
    def test_next_due_is_next_tuesday_when_today_not_tuesday(self):
        svc = _service()
        rep = svc.report(today=date(2026, 7, 11))  # 周六
        assert rep.next_due == date(2026, 7, 14)

    def test_next_due_skips_weekend_after_friday_sampled(self):
        today = date(2026, 7, 17)  # 周五(日频时代)
        days = _weekdays(date(2026, 7, 14), 4)
        svc = _service(health={d: "ok" for d in days}, checks={d: True for d in days},
                       known_max=today)
        rep = svc.report(today=today)
        assert rep.next_due == date(2026, 7, 20)  # 下一工作日=周一


class TestProcessOkExitSemantics:
    def test_latest_due_missed_means_not_ok(self):
        svc = _service()
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.process_ok is False

    def test_single_historical_miss_recovered_is_ok(self):
        # 07-07 豁免, 07-14 VALID, 07-15 MISSED, 07-16 VALID(今日)
        sampled = [date(2026, 7, 14), date(2026, 7, 16)]
        svc = _service(health={d: "ok" for d in sampled},
                       checks={d: True for d in sampled},
                       trading={date(2026, 7, 7): False},
                       known_max=date(2026, 7, 16))
        rep = svc.report(today=date(2026, 7, 16))
        assert rep.missed_count == 1
        assert rep.process_ok is True

    def test_two_misses_within_tolerance_still_ok(self):
        # 07-15/07-16 MISSED(=MAX_MISSED), 最新已恢复 → 仍受控
        sampled = [date(2026, 7, 14), date(2026, 7, 17)]
        svc = _service(health={d: "ok" for d in sampled},
                       checks={d: True for d in sampled},
                       trading={date(2026, 7, 7): False},
                       known_max=date(2026, 7, 17))
        rep = svc.report(today=date(2026, 7, 17))
        assert rep.missed_count == 2
        assert rep.process_ok is True

    def test_three_misses_not_ok_even_if_latest_valid(self):
        # 07-15/16/17 MISSED(>MAX_MISSED=2), 07-20 VALID → 过程失控
        sampled = [date(2026, 7, 14), date(2026, 7, 20)]
        svc = _service(health={d: "ok" for d in sampled},
                       checks={d: True for d in sampled},
                       trading={date(2026, 7, 7): False},
                       known_max=date(2026, 7, 20))
        rep = svc.report(today=date(2026, 7, 20))
        assert rep.missed_count == 3
        assert rep.process_ok is False

    def test_diverged_or_past_unknown_not_ok(self):
        d14 = date(2026, 7, 14)
        diverged = _service(health={d14: "ok"}, checks={d14: False},
                            known_max=date(2026, 7, 17))
        assert diverged.report(today=date(2026, 7, 17)).process_ok is False
        unknown = _service(known_max=date(2026, 7, 6))
        assert unknown.report(today=date(2026, 7, 11)).process_ok is False


class TestGate:
    """日频时代判据: G1 有效样本 ≥10 交易日(含 ≥2 调仓周二); G5 MISSED ≤ 2。"""

    def _svc(self, sampled: list[date], *, paper: int | None = None):
        # 07-07 史料周二统一豁免, 聚焦日频样本
        return _service(health={d: "ok" for d in sampled},
                        checks={d: True for d in sampled},
                        trading={date(2026, 7, 7): False},
                        known_max=sampled[-1],
                        paper_count=len(sampled) if paper is None else paper)

    def test_gate_passes_with_ten_valid_days(self):
        days = _weekdays(date(2026, 7, 14), 10)  # 含 07-14/07-21 两个周二
        rep = self._svc(days).report(today=days[-1])
        assert rep.valid_count == 10
        assert rep.gate_passed is True
        assert {c.key for c in rep.gate} == {"G1", "G2", "G3", "G4", "G5"}

    def test_gate_fails_below_ten_valid(self):
        days = _weekdays(date(2026, 7, 14), 9)
        rep = self._svc(days).report(today=days[-1])
        assert rep.valid_count == 9
        assert next(c for c in rep.gate if c.key == "G1").passed is False
        assert rep.gate_passed is False

    def test_gate_fails_with_ten_valid_but_one_tuesday(self):
        # 两个周二缺采(07-21/07-28 MISSED=2 仍在 G5 容忍内) → 有效日凑满 10
        # 但独立决策样本只有 07-14 一个周二 → G1 必须不过
        skipped = {date(2026, 7, 21), date(2026, 7, 28)}
        days = [d for d in _weekdays(date(2026, 7, 14), 12) if d not in skipped]
        rep = self._svc(days).report(today=days[-1])
        assert rep.valid_count == 10
        assert rep.missed_count == 2
        g1 = next(c for c in rep.gate if c.key == "G1")
        assert g1.passed is False, g1.actual
        assert next(c for c in rep.gate if c.key == "G5").passed is True

    def test_gate_fails_on_fault_health(self):
        d14 = date(2026, 7, 14)
        svc = _service(health={d14: "fault"}, checks={d14: True},
                       trading={date(2026, 7, 7): False},
                       known_max=d14, paper_count=1)
        rep = svc.report(today=d14)
        assert next(c for c in rep.gate if c.key == "G3").passed is False

    def test_gate_fails_on_paper_gap(self):
        days = _weekdays(date(2026, 7, 14), 10)
        rep = self._svc(days, paper=8).report(today=days[-1])
        assert next(c for c in rep.gate if c.key == "G4").passed is False

    def test_manual_items_listed(self):
        days = _weekdays(date(2026, 7, 14), 10)
        rep = self._svc(days).report(today=days[-1])
        assert any("M4" in item for item in rep.manual_items)
        assert any("DD-6" in item for item in rep.manual_items)


class TestDailyEra:
    """日频采样时代(2026-07-14 用户指令): 07-14 起每个交易日都是采样日;
    此前(07-07/07-13)仍按周二史料口径。"""

    def _svc(self, health=None, checks=None, known_max=None):
        return _service(health=health or {}, checks=checks or {},
                        trading={}, known_max=known_max or date(2026, 7, 31))

    def test_weekdays_after_0714_are_sampling_days(self):
        rep = self._svc().report(today=date(2026, 7, 16))  # 周四
        days = [r.day for r in rep.ledger]
        assert date(2026, 7, 14) in days
        assert date(2026, 7, 15) in days
        assert date(2026, 7, 16) in days
        assert date(2026, 7, 10) not in days            # 日频时代前的周五不算
        assert date(2026, 7, 7) in days                 # 史料周二保留

    def test_gate_needs_10_days_including_2_tuesdays(self):
        # 07-14(周二)起连续 10 个工作日 VALID: 含 07-14/07-21 两个周二
        days = _weekdays(date(2026, 7, 14), 10)
        svc = self._svc(health={x: "ok" for x in days}, checks={x: True for x in days})
        rep = svc.report(today=days[-1])
        g1 = next(c for c in rep.gate if c.key == "G1")
        assert rep.valid_count == 10 and g1.passed, g1.actual

    def test_next_due_is_next_trading_day_in_daily_era(self):
        d14 = date(2026, 7, 14)
        rep = self._svc(health={d14: "ok"},
                        checks={d14: True}).report(today=d14)
        assert rep.next_due == date(2026, 7, 15)        # 周三, 不再是下周二
