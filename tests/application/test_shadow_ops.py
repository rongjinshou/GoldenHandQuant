"""ShadowTuesdayOrchestrator: 安全律/看护重试/开盘等待/链式步骤/收盘链(设计 SC-3)。"""
from datetime import datetime, time, timedelta

from src.application.shadow_ops import ShadowTuesdayOrchestrator, StepResult

TUESDAY_0920 = datetime(2026, 7, 14, 9, 20)


class FakeClock:
    def __init__(self, start: datetime):
        self.t = start
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.t

    def sleep(self, secs: float) -> None:
        self.sleeps.append(secs)
        self.t += timedelta(seconds=secs)


class Harness:
    def __init__(self, *, start=TUESDAY_0920, probe_results=(True,), steps_ok=True,
                 mode="dry_run", verify=True, force=False):
        self.clock = FakeClock(start)
        self.calls: list[tuple[str, list[str], datetime]] = []
        self.notices: list[tuple[str, str, str]] = []
        probes = list(probe_results)

        def probe() -> bool:
            return probes.pop(0) if len(probes) > 1 else probes[0]

        def run_step(name: str, argv: list[str]) -> StepResult:
            self.calls.append((name, argv, self.clock.now()))
            return StepResult(name=name, ok=steps_ok, output_tail=f"tail-{name}")

        self.orch = ShadowTuesdayOrchestrator(
            run_step=run_step,
            probe_qmt=probe,
            notify=lambda t, b, lv: self.notices.append((t, b, lv)),
            now=self.clock.now,
            sleep=self.clock.sleep,
            python_exe="PY",
            verify_snapshot_today=lambda: verify,
            auto_trade_mode=lambda: mode,
            force=force,
        )


class TestGuards:
    def test_refuses_when_mode_not_dry_run(self):
        h = Harness(mode="live")
        assert h.orch.run_morning() == 2
        assert h.calls == []
        assert any(lv == "critical" for _, _, lv in h.notices)

    def test_non_tuesday_exits_zero_without_steps(self):
        h = Harness(start=datetime(2026, 7, 15, 9, 20))  # 周三
        assert h.orch.run_morning() == 0
        assert h.calls == []

    def test_force_overrides_non_tuesday(self):
        h = Harness(start=datetime(2026, 7, 15, 9, 40), force=True)
        assert h.orch.run_morning() == 0
        assert len(h.calls) == 4


class TestQmtWatch:
    def test_offline_then_online_reminds_once_and_proceeds(self):
        h = Harness(probe_results=(False, False, True))
        assert h.orch.run_morning() == 0
        reminders = [n for n in h.notices if "QMT" in n[0] or "QMT" in n[1]]
        assert len(reminders) == 1 and reminders[0][2] == "warning"
        assert len(h.calls) == 4

    def test_offline_past_deadline_is_missed_alert(self):
        h = Harness(start=datetime(2026, 7, 14, 14, 29), probe_results=(False,))
        assert h.orch.run_morning() == 1
        assert any("MISSED" in t or "MISSED" in b for t, b, lv in h.notices if lv == "critical")
        assert h.calls == []


class TestMorningChain:
    def test_waits_until_market_open_before_steps(self):
        h = Harness()
        assert h.orch.run_morning() == 0
        assert all(ts.time() >= time(9, 35) for _, _, ts in h.calls)

    def test_step_order_and_argv(self):
        h = Harness(start=datetime(2026, 7, 14, 9, 40))
        assert h.orch.run_morning() == 0
        names = [c[0] for c in h.calls]
        assert names == ["data-refresh", "index-bars", "sync-market-cap", "auto-trade-once"]
        refresh_argv = h.calls[0][1]
        assert refresh_argv[:4] == ["PY", "-m", "src.interfaces.cli.quant", "data"]
        assert "--end-date" in refresh_argv and "2026-07-14" in refresh_argv
        assert h.calls[2][1][1].endswith("sync_market_cap.py")  # MC-1: 决策前市值同步
        at_argv = h.calls[3][1]
        assert at_argv[-2:] == ["--once", "--enable"]
        assert "--live" not in at_argv

    def test_step_failure_stops_chain_with_critical(self):
        h = Harness(start=datetime(2026, 7, 14, 9, 40), steps_ok=False)
        assert h.orch.run_morning() == 1
        assert len(h.calls) == 1
        assert h.notices[-1][2] == "critical"

    def test_missing_snapshot_after_run_is_failure(self):
        h = Harness(start=datetime(2026, 7, 14, 9, 40), verify=False)
        assert h.orch.run_morning() == 1
        assert h.notices[-1][2] == "critical"


class TestPostCloseChain:
    def test_chain_and_digest(self):
        h = Harness(start=datetime(2026, 7, 14, 15, 10))
        assert h.orch.run_post_close() == 0
        names = [c[0] for c in h.calls]
        assert names == ["data-refresh", "index-bars", "consistency-check",
                         "paper-equity", "shadow-status"]
        check_argv = h.calls[2][1]
        assert check_argv[1].endswith("shadow_consistency_check.py")
        assert check_argv[-1] == "2026-07-14"
        assert h.notices[-1][2] == "info"

    def test_consistency_failure_alerts(self):
        h = Harness(start=datetime(2026, 7, 14, 15, 10), steps_ok=False)
        assert h.orch.run_post_close() == 1
        assert h.notices[-1][2] == "critical"
