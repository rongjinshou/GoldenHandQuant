# 影子盘过程受控化 + 过闸判据 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把影子盘周二采样从人肉四命令变成受控过程：过程仪表 `quant shadow status`（台账+过闸判据）+ 周二编排器（QMT 看护/提醒/告警）+ Windows 任务计划模板 + 文档收编。

**Architecture:** 纯逻辑进 application（`shadow_audit.py` 台账/判据、`shadow_ops.py` 编排状态机，全部依赖注入可测）；装配进 interfaces（`shadow_cmd.py` 接 stores）与 scripts（`shadow_tuesday.py` 薄壳，subprocess 调既有 CLI）。规格：`2026-07-11-shadow-control-design.md`（SC-1..SC-6）。

**Tech Stack:** Python 3.13（`list[X]`、`@dataclass(slots=True, kw_only=True)`、StrEnum、match/case）、pytest AAA、既有 TradingStore/MarketDataStore/notification factory。

## Global Constraints

- application 顶层禁 import infrastructure（`tests/architecture/test_layer_purity.py` 门禁在跑；用注入 callables）
- 编排器安全律：`auto_trade.mode != dry_run` 拒绝运行；子命令永不带 `--live`
- 不碰 `frontend/`（另一路在途）；不碰既有决策核心
- 测试命令用 WSL python：`/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest`
- **本轮不 commit**：工作树上有 1-3 轮 153 个未提交文件且共享文件（quant.py/CLAUDE.md/runbook/台账）改动交错，无法干净分批；提交由用户统一裁量（延续既定状态）。计划里的"提交"步骤全部以"标记任务完成"替代
- 常量即规格：`GATE_START=2026-07-07`、`REQUIRED_VALID_SAMPLES=6`、`MAX_MISSED=1`（改值=改设计文档）

---

### Task 1: ShadowAuditService（台账七状态 + 过闸判据 G1-G5）

**Files:**
- Create: `src/application/shadow_audit.py`
- Test: `tests/application/test_shadow_audit.py`

**Interfaces:**
- Consumes: 无（纯逻辑，四个注入 callables）
- Produces: `ShadowAuditService(snapshot_health_by_day, is_trading_day, load_check, paper_run_count).report(today=date) -> ShadowReport`；`TuesdayStatus`（VALID/UNCHECKED/DIVERGED/MISSED/EXEMPT/UNKNOWN/PENDING）；`ShadowReport(ledger, valid_count, missed_count, diverged_count, unknown_count, next_due, process_ok, gate, gate_passed, manual_items)`；`GateCriterion(key, description, passed, actual)`；`TuesdayRecord(day, status, detail)`；常量 `GATE_START/REQUIRED_VALID_SAMPLES/MAX_MISSED/MANUAL_GATE_ITEMS`

- [ ] **Step 1: 写失败测试**

```python
"""ShadowAuditService: 周二台账七状态 + 过闸判据(设计 0711-shadow-control SC-1/SC-2)。"""
from datetime import date

from src.application.shadow_audit import (
    ShadowAuditService,
    TuesdayStatus,
)

# 2026-07 周二: 07-07 / 07-14 / 07-21 / 07-28


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

    def test_next_due_moves_a_week_after_today_sampled(self):
        today = date(2026, 7, 14)
        svc = _service(health={today: "ok"}, checks={today: True},
                       known_max=date(2026, 7, 14))
        rep = svc.report(today=today)
        assert rep.next_due == date(2026, 7, 21)


class TestProcessOkExitSemantics:
    def test_latest_due_missed_means_not_ok(self):
        svc = _service()
        rep = svc.report(today=date(2026, 7, 11))
        assert rep.process_ok is False

    def test_single_historical_miss_recovered_is_ok(self):
        d14 = date(2026, 7, 14)
        svc = _service(health={d14: "ok"}, checks={d14: True},
                       known_max=date(2026, 7, 17))
        rep = svc.report(today=date(2026, 7, 17))  # 07-07 MISSED, 07-14 VALID
        assert rep.missed_count == 1
        assert rep.process_ok is True

    def test_two_misses_not_ok_even_if_latest_valid(self):
        d21 = date(2026, 7, 21)
        svc = _service(health={d21: "ok"}, checks={d21: True},
                       known_max=date(2026, 7, 24))
        rep = svc.report(today=date(2026, 7, 24))  # 07-07/07-14 MISSED, 07-21 VALID
        assert rep.missed_count == 2
        assert rep.process_ok is False

    def test_diverged_or_past_unknown_not_ok(self):
        d14 = date(2026, 7, 14)
        diverged = _service(health={d14: "ok"}, checks={d14: False},
                            known_max=date(2026, 7, 17))
        assert diverged.report(today=date(2026, 7, 17)).process_ok is False
        unknown = _service(known_max=date(2026, 7, 6))
        assert unknown.report(today=date(2026, 7, 11)).process_ok is False


class TestGate:
    def _six_valid(self, *, missed_first: bool = True, paper: int = 6):
        # 07-07 MISSED(可选), 07-14 起连续 6 个 VALID
        valid_days = [date(2026, 7, 14), date(2026, 7, 21), date(2026, 7, 28),
                      date(2026, 8, 4), date(2026, 8, 11), date(2026, 8, 18)]
        health = {d: "ok" for d in valid_days}
        checks = {d: True for d in valid_days}
        trading = {} if missed_first else {date(2026, 7, 7): False}
        return _service(health=health, checks=checks, trading=trading,
                        known_max=date(2026, 8, 21), paper_count=paper)

    def test_gate_passes_with_six_valid_and_one_miss(self):
        rep = self._six_valid().report(today=date(2026, 8, 21))
        assert rep.valid_count == 6
        assert rep.gate_passed is True
        assert {c.key for c in rep.gate} == {"G1", "G2", "G3", "G4", "G5"}

    def test_gate_fails_below_six_valid(self):
        rep = self._six_valid().report(today=date(2026, 8, 14))  # 只攒到 5 个
        assert rep.valid_count == 5
        assert next(c for c in rep.gate if c.key == "G1").passed is False
        assert rep.gate_passed is False

    def test_gate_fails_on_fault_health(self):
        d14 = date(2026, 7, 14)
        svc = _service(health={d14: "fault"}, checks={d14: True},
                       known_max=date(2026, 7, 17), paper_count=1)
        rep = svc.report(today=date(2026, 7, 17))
        assert next(c for c in rep.gate if c.key == "G3").passed is False

    def test_gate_fails_on_paper_gap(self):
        rep = self._six_valid(paper=4).report(today=date(2026, 8, 21))
        assert next(c for c in rep.gate if c.key == "G4").passed is False

    def test_manual_items_listed(self):
        rep = self._six_valid().report(today=date(2026, 8, 21))
        assert any("M4" in item for item in rep.manual_items)
        assert any("DD-6" in item for item in rep.manual_items)
```

- [ ] **Step 2: 跑测试确认红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/application/test_shadow_audit.py -q`
Expected: FAIL（`ModuleNotFoundError: src.application.shadow_audit`）

- [ ] **Step 3: 最小实现**

```python
"""影子盘过程审计: 周二采样台账 + 过闸判据。

设计: docs/feat/0711-shadow-control/2026-07-11-shadow-control-design.md SC-1/SC-2。
分层: 数据访问全部经构造注入的 callables, 顶层不 import infrastructure。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

GATE_START = date(2026, 7, 7)  # 阶段 1 计划首采日(0626 phase1 report)
REQUIRED_VALID_SAMPLES = 6     # G1: "攒 4-8 周"取中偏保守
MAX_MISSED = 1                 # G5: ≥2 = 采样过程失控

MANUAL_GATE_ITEMS: tuple[str, ...] = (
    "G6 M4 成交回报回填+断线重连 QMT 实环境联测完成(以台账 M3 遗留项核销为准)",
    "G7 DD-6 ST 诚实债重验后 F01 gate 仍 PASS(以台账 DD-6 核销为准)",
)


class TuesdayStatus(StrEnum):
    VALID = "VALID"          # 已采样且比对一致
    UNCHECKED = "UNCHECKED"  # 已采样, 比对未跑(离线可补)
    DIVERGED = "DIVERGED"    # 已采样, 比对不一致(立案)
    MISSED = "MISSED"        # 交易日未采样(live 快照不可重建, 如实保留)
    EXEMPT = "EXEMPT"        # 节假日周二(白名单)
    UNKNOWN = "UNKNOWN"      # bars 未刷至该日, 无法判交易日(三值诚实)
    PENDING = "PENDING"      # 今日采样窗口进行中


@dataclass(slots=True, kw_only=True)
class TuesdayRecord:
    day: date
    status: TuesdayStatus
    detail: str = ""


@dataclass(slots=True, kw_only=True)
class GateCriterion:
    key: str
    description: str
    passed: bool
    actual: str


@dataclass(slots=True, kw_only=True)
class ShadowReport:
    ledger: list[TuesdayRecord]
    valid_count: int
    missed_count: int
    diverged_count: int
    unknown_count: int
    next_due: date
    process_ok: bool
    gate: list[GateCriterion]
    gate_passed: bool
    manual_items: tuple[str, ...] = MANUAL_GATE_ITEMS


def _tuesdays(start: date, end: date) -> list[date]:
    d = start + timedelta(days=(1 - start.weekday()) % 7)
    out: list[date] = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


def _next_tuesday_after(d: date) -> date:
    return d + timedelta(days=(1 - d.weekday()) % 7 or 7)


class ShadowAuditService:
    """把注入的原始事实折成台账与过闸报告(纯逻辑, 可完全离线测试)。"""

    def __init__(
        self,
        *,
        snapshot_health_by_day: Callable[[], dict[date, str]],
        is_trading_day: Callable[[date], bool | None],
        load_check: Callable[[date], bool | None],
        paper_run_count: Callable[[], int],
    ) -> None:
        self._snapshot_health_by_day = snapshot_health_by_day
        self._is_trading_day = is_trading_day
        self._load_check = load_check
        self._paper_run_count = paper_run_count

    def report(self, *, today: date) -> ShadowReport:
        health = self._snapshot_health_by_day()
        ledger = [self._classify(d, today, health) for d in _tuesdays(GATE_START, today)]

        def count(status: TuesdayStatus) -> int:
            return sum(1 for r in ledger if r.status is status)

        valid = count(TuesdayStatus.VALID)
        missed = count(TuesdayStatus.MISSED)
        diverged = count(TuesdayStatus.DIVERGED)
        unknown = count(TuesdayStatus.UNKNOWN)

        past_due = [r for r in ledger if r.status is not TuesdayStatus.PENDING]
        latest_missed = bool(past_due) and past_due[-1].status is TuesdayStatus.MISSED
        # 退出码对准"当前失控"而非历史记录(SC-1): 历史性单次 MISSED 恢复采样后不再报警
        process_ok = not (latest_missed or missed > MAX_MISSED or diverged > 0 or unknown > 0)

        if today.weekday() == 1 and today not in health:
            next_due = today
        else:
            next_due = _next_tuesday_after(today)

        sampled_health = [health[r.day] for r in ledger if r.day in health]
        paper = self._paper_run_count()
        gate = [
            GateCriterion(
                key="G1",
                description=f"有效样本 ≥ {REQUIRED_VALID_SAMPLES} 个调仓周二",
                passed=valid >= REQUIRED_VALID_SAMPLES,
                actual=f"{valid}/{REQUIRED_VALID_SAMPLES}",
            ),
            GateCriterion(
                key="G2",
                description="无未解释分歧(DIVERGED=0)",
                passed=diverged == 0,
                actual=str(diverged),
            ),
            GateCriterion(
                key="G3",
                description="采样期 data_health 全 ok",
                passed=all(h == "ok" for h in sampled_health),
                actual=",".join(sorted(set(sampled_health))) or "无采样",
            ),
            GateCriterion(
                key="G4",
                description="纸面净值周度入库无断档(入库数 ≥ 有效样本数)",
                passed=paper >= valid,
                actual=f"{paper}/{valid}",
            ),
            GateCriterion(
                key="G5",
                description=f"MISSED 累计 ≤ {MAX_MISSED}",
                passed=missed <= MAX_MISSED,
                actual=str(missed),
            ),
        ]
        return ShadowReport(
            ledger=ledger,
            valid_count=valid,
            missed_count=missed,
            diverged_count=diverged,
            unknown_count=unknown,
            next_due=next_due,
            process_ok=process_ok,
            gate=gate,
            gate_passed=all(c.passed for c in gate),
        )

    def _classify(self, day: date, today: date, health: dict[date, str]) -> TuesdayRecord:
        if day in health:
            match self._load_check(day):
                case None:
                    return TuesdayRecord(
                        day=day,
                        status=TuesdayStatus.UNCHECKED,
                        detail=f"快照已落库, 比对未跑(可补: scripts/shadow_consistency_check.py --date {day})",
                    )
                case True:
                    detail = "" if health[day] == "ok" else f"data_health={health[day]}"
                    return TuesdayRecord(day=day, status=TuesdayStatus.VALID, detail=detail)
                case _:
                    return TuesdayRecord(day=day, status=TuesdayStatus.DIVERGED, detail="比对不一致, 立案")
        if day == today:
            return TuesdayRecord(day=day, status=TuesdayStatus.PENDING, detail="今日采样窗口进行中")
        match self._is_trading_day(day):
            case None:
                return TuesdayRecord(day=day, status=TuesdayStatus.UNKNOWN, detail="bars 未刷至该日, 先 data refresh")
            case True:
                return TuesdayRecord(day=day, status=TuesdayStatus.MISSED, detail="live 快照不可重建, 如实保留")
            case _:
                return TuesdayRecord(day=day, status=TuesdayStatus.EXEMPT, detail="非交易日")
```

- [ ] **Step 4: 跑测试确认绿**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/application/test_shadow_audit.py -q`
Expected: 全 PASS

- [ ] **Step 5: 标记任务完成（不 commit，见 Global Constraints）**

---

### Task 2: `quant shadow status` CLI（装配 + 呈现 + 退出码）

**Files:**
- Create: `src/interfaces/cli/commands/shadow_cmd.py`
- Modify: `src/interfaces/cli/quant.py`（monitor 子命令块后加 shadow 子命令；match 里加 case）
- Test: `tests/interfaces/cli/test_shadow_cmd.py`

**Interfaces:**
- Consumes: Task 1 全部导出；`TradingStore(db_path=...).load_signal_snapshots(limit=1000)`；`MarketDataStore(path, read_only=True).trading_dates()` / `.load_backtest_runs(limit=300)`
- Produces: `run_shadow(args) -> None`（sys.exit 承载退出码）；纯装配助手 `_snapshot_health(store) -> dict[date, str]`、`_trading_day_fn(market_store) -> Callable[[date], bool | None]`、`_check_loader(checks_dir: Path) -> Callable[[date], bool | None]`、`_paper_count(market_store) -> int`

- [ ] **Step 1: 写失败测试（覆盖四个装配闭包，鸭子类型假 store）**

```python
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
        (tmp_path / "2026-07-14.json").write_text(json.dumps({"consistent": True}), encoding="utf-8")
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
```

- [ ] **Step 2: 跑测试确认红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/interfaces/cli/test_shadow_cmd.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `shadow_cmd.py`**

```python
"""quant shadow — 影子盘过程仪表(设计 0711-shadow-control SC-1/SC-2)。

装配层: 接 TradingStore/MarketDataStore/shadow_checks 文件, 喂 ShadowAuditService;
呈现台账/过闸判据; 退出码 = report.process_ok(供编排器/巡检消费)。
"""
import json
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from src.application.shadow_audit import ShadowReport, ShadowAuditService, TuesdayStatus

_STATUS_MARK = {
    TuesdayStatus.VALID: "✅",
    TuesdayStatus.UNCHECKED: "🟡",
    TuesdayStatus.DIVERGED: "🔴",
    TuesdayStatus.MISSED: "🔴",
    TuesdayStatus.EXEMPT: "⚪",
    TuesdayStatus.UNKNOWN: "❔",
    TuesdayStatus.PENDING: "⏳",
}


def _snapshot_health(store) -> dict[date, str]:
    """dry_run 快照日 -> data_health; 同日多条取最坏(fault 优先, 宁严勿宽)。"""
    out: dict[date, str] = {}
    for row in store.load_signal_snapshots(limit=1000):
        if row.get("mode") != "dry_run":
            continue
        day = datetime.fromisoformat(str(row["snapshot_time"])).date()
        health = str(row.get("data_health") or "ok")
        if out.get(day) != "ok" and day in out:
            continue
        if health != "ok" or day not in out:
            out[day] = health
    return out


def _trading_day_fn(market_store) -> Callable[[date], bool | None]:
    days = market_store.trading_dates()
    known = set(days)
    known_max = max(days) if days else None

    def is_trading_day(d: date) -> bool | None:
        if known_max is None or d > known_max:
            return None
        return d in known

    return is_trading_day


def _check_loader(checks_dir: Path) -> Callable[[date], bool | None]:
    def load(d: date) -> bool | None:
        path = checks_dir / f"{d.isoformat()}.json"
        if not path.exists():
            return None
        try:
            return bool(json.loads(path.read_text(encoding="utf-8")).get("consistent"))
        except Exception:
            return False  # 比对文件损坏按分歧对待, 宁严勿宽
    return load


def _paper_count(market_store) -> int:
    runs = market_store.load_backtest_runs(limit=300)
    return len({r["run_id"] for r in runs if str(r.get("run_id", "")).startswith("SHADOW-PAPER-")})


def _print_report(rep: ShadowReport, *, show_gate: bool) -> None:
    print("影子盘采样台账(自 2026-07-07, 调仓周二):")
    for r in rep.ledger:
        mark = _STATUS_MARK[r.status]
        detail = f"  {r.detail}" if r.detail else ""
        print(f"  {r.day} 周二  {mark} {r.status:<9}{detail}")
    print(f"\n有效样本 {rep.valid_count}/6 | MISSED {rep.missed_count} | "
          f"DIVERGED {rep.diverged_count} | 下一到期采样日 {rep.next_due}")
    if show_gate:
        print("\n过闸判据(真单 Spec 开启条件, 设计 SC-2):")
        for c in rep.gate:
            print(f"  {'✅' if c.passed else '✗'} {c.key} {c.description}  [{c.actual}]")
        print("  人工判据(以债务台账核销为准):")
        for item in rep.manual_items:
            print(f"  ☐ {item}")
        if rep.gate_passed:
            print("\n🎉 机器判据 G1-G5 全过——核对人工判据后可开真单 Spec(演进点 E5)")
    if not rep.process_ok:
        print("\n⚠ 过程异常: 最近到期采样 MISSED / MISSED≥2 / 存在 DIVERGED / 存在 UNKNOWN(先 data refresh)")


def run_shadow(args) -> None:
    from src.infrastructure.persistence.market_data_store import MarketDataStore
    from src.infrastructure.persistence.trading_store import TradingStore

    trading_store = TradingStore(db_path=args.db)
    market_store = MarketDataStore(args.market_db, read_only=True)
    try:
        service = ShadowAuditService(
            snapshot_health_by_day=lambda: _snapshot_health(trading_store),
            is_trading_day=_trading_day_fn(market_store),
            load_check=_check_loader(Path(args.checks_dir)),
            paper_run_count=lambda: _paper_count(market_store),
        )
        report = service.report(today=date.today())
        _print_report(report, show_gate=args.gate)
        sys.exit(0 if report.process_ok else 1)
    finally:
        trading_store.close()
```

（若 `MarketDataStore` 无 `close()` 需求与既有 data_cmd.py 一致即可，不额外包装。）

- [ ] **Step 4: 注册进 `quant.py`**

在 `# --- monitor ---` 块之后、`return parser` 之前加：

```python
    # --- shadow ---
    p_sh = subparsers.add_parser("shadow", help="影子盘过程仪表 (采样台账/过闸判据)")
    p_sh.add_argument("shadow_command", choices=["status"], help="子命令")
    p_sh.add_argument("--gate", action="store_true", help="显示过闸判据 G1-G5 + 人工项")
    p_sh.add_argument("--db", default="data/trading.db", help="交易留痕库")
    p_sh.add_argument("--market-db", default="data/market.duckdb", help="市场数据库")
    p_sh.add_argument("--checks-dir", default="data/shadow_checks", help="一致性比对结果目录")
```

在 `case "monitor":` 之前加：

```python
        case "shadow":
            from src.interfaces.cli.commands.shadow_cmd import run_shadow

            run_shadow(args)
```

- [ ] **Step 5: 跑测试确认绿 + 实跑验收**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/interfaces/cli/test_shadow_cmd.py -q`
Expected: 全 PASS

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m src.interfaces.cli.quant shadow status --gate; echo "exit=$?"`
Expected: 台账显示 `2026-07-07 周二 🔴 MISSED`、下一到期 `2026-07-14`、有效 `0/6`、`exit=1`

---

### Task 3: ShadowTuesdayOrchestrator（编排状态机）

**Files:**
- Create: `src/application/shadow_ops.py`
- Test: `tests/application/test_shadow_ops.py`

**Interfaces:**
- Consumes: 无（全注入）
- Produces: `StepResult(name, ok, output_tail)`；`ShadowTuesdayOrchestrator(run_step, probe_qmt, notify, now, sleep, python_exe, verify_snapshot_today, auto_trade_mode, force=False, deadline=time(14,30), market_open=time(9,35))`，方法 `run_morning() -> int`、`run_post_close() -> int`（0=成功/非调仓日；1=失败或 MISSED；2=mode 安全律拒绝）；`notify(title: str, body: str, level: str)` 其中 level ∈ {"info","warning","critical"}

- [ ] **Step 1: 写失败测试**

```python
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
        assert len(h.calls) == 3


class TestQmtWatch:
    def test_offline_then_online_reminds_once_and_proceeds(self):
        h = Harness(probe_results=(False, False, True))
        assert h.orch.run_morning() == 0
        reminders = [n for n in h.notices if "QMT" in n[0] or "QMT" in n[1]]
        assert len(reminders) == 1 and reminders[0][2] == "warning"
        assert len(h.calls) == 3

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
        assert names == ["data-refresh", "index-bars", "auto-trade-once"]
        refresh_argv = h.calls[0][1]
        assert refresh_argv[:4] == ["PY", "-m", "src.interfaces.cli.quant", "data"]
        assert "--end-date" in refresh_argv and "2026-07-14" in refresh_argv
        at_argv = h.calls[2][1]
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
```

- [ ] **Step 2: 跑测试确认红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/application/test_shadow_ops.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `shadow_ops.py`**

```python
"""影子盘周二编排器(设计 0711-shadow-control SC-3)。

人只负责开 QMT 极简端; 其余步骤机器编排: 看护提醒→refresh→采样→(收盘)比对→净值→台账。
全部依赖注入(subprocess/时钟/探针/通知), application 层可完全离线测试。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta

_QUANT = ("-m", "src.interfaces.cli.quant")
_PROBE_RETRY_SECONDS = 60.0
_OPEN_WAIT_SECONDS = 30.0


@dataclass(slots=True, kw_only=True)
class StepResult:
    name: str
    ok: bool
    output_tail: str = ""


class ShadowTuesdayOrchestrator:
    def __init__(
        self,
        *,
        run_step: Callable[[str, list[str]], StepResult],
        probe_qmt: Callable[[], bool],
        notify: Callable[[str, str, str], None],
        now: Callable[[], datetime],
        sleep: Callable[[float], None],
        python_exe: str,
        verify_snapshot_today: Callable[[], bool],
        auto_trade_mode: Callable[[], str],
        force: bool = False,
        deadline: time = time(14, 30),
        market_open: time = time(9, 35),
    ) -> None:
        self._run_step = run_step
        self._probe_qmt = probe_qmt
        self._notify = notify
        self._now = now
        self._sleep = sleep
        self._python = python_exe
        self._verify_snapshot_today = verify_snapshot_today
        self._auto_trade_mode = auto_trade_mode
        self._force = force
        self._deadline = deadline
        self._market_open = market_open

    # ---- 公共入口 ----

    def run_morning(self) -> int:
        guarded = self._guards()
        if guarded is not None:
            return guarded
        if not self._await_qmt():
            return 1
        self._await_market_open()
        today = self._now().date()
        if not self._run_chain(self._refresh_steps(today) + [self._auto_trade_step()]):
            return 1
        if not self._verify_snapshot_today():
            self._notify(
                "影子盘采样失败",
                "auto-trade 已执行但当日 signal_snapshot 未落库, 请查 trading_cycles.note",
                "critical",
            )
            return 1
        self._notify(
            "影子盘采样完成",
            f"{today} 决策快照已落库; 收盘后跑 --post-close(或任务计划自动)",
            "info",
        )
        return 0

    def run_post_close(self) -> int:
        guarded = self._guards()
        if guarded is not None:
            return guarded
        today = self._now().date()
        steps = self._refresh_steps(today) + [
            ("consistency-check",
             [self._python, "scripts/shadow_consistency_check.py", "--date", today.isoformat()]),
            ("paper-equity", [self._python, "scripts/shadow_paper_equity.py"]),
        ]
        if not self._run_chain(steps):
            return 1
        status = self._run_step(
            "shadow-status",
            [self._python, *_QUANT, "shadow", "status", "--gate"],
        )
        # shadow status 的退出码承载"过程健康"(含历史 MISSED), 不作为收盘链失败;
        # 其输出并入通知摘要供人复核。
        self._notify(
            "影子盘收盘链完成",
            f"{today} 比对一致, 纸面净值已入库。台账摘要:\n{status.output_tail}",
            "info",
        )
        return 0

    # ---- 内部 ----

    def _guards(self) -> int | None:
        mode = self._auto_trade_mode()
        if mode != "dry_run":
            self._notify(
                "影子盘编排器拒绝运行",
                f"auto_trade.mode={mode}, 本工具只服务 dry_run 影子盘(安全律)",
                "critical",
            )
            return 2
        if self._now().date().weekday() != 1 and not self._force:
            self._notify("非调仓日", "今天不是周二, 影子盘无采样任务(--force 可越过)", "info")
            return 0
        return None

    def _await_qmt(self) -> bool:
        reminded = False
        while not self._probe_qmt():
            if not reminded:
                self._notify(
                    "请打开 QMT 极简端",
                    "影子盘采样等待中: 请登录 QMT 极简模式并确认行情面板有跳动数据",
                    "warning",
                )
                reminded = True
            if self._now().time() >= self._deadline:
                self._notify(
                    "影子盘 MISSED",
                    f"QMT 截至 {self._deadline:%H:%M} 未上线, 今日采样脱靶(live 快照不可补), "
                    "台账将如实记录",
                    "critical",
                )
                return False
            self._sleep(_PROBE_RETRY_SECONDS)
        return True

    def _await_market_open(self) -> None:
        # 任务计划 09:20 拉起提醒, 采样动作等 09:35 开盘价定型(阶段 1 比对口径)
        while self._now().time() < self._market_open:
            self._sleep(_OPEN_WAIT_SECONDS)

    def _refresh_steps(self, today) -> list[tuple[str, list[str]]]:
        return [
            ("data-refresh",
             [self._python, *_QUANT, "data", "refresh",
              "--start-date", (today - timedelta(days=14)).isoformat(),
              "--end-date", today.isoformat()]),
            ("index-bars", [self._python, "scripts/fetch_index_bars.py"]),
        ]

    def _auto_trade_step(self) -> tuple[str, list[str]]:
        return ("auto-trade-once",
                [self._python, *_QUANT, "auto-trade", "--once", "--enable"])

    def _run_chain(self, steps: list[tuple[str, list[str]]]) -> bool:
        for name, argv in steps:
            result = self._run_step(name, argv)
            if not result.ok:
                self._notify(
                    f"影子盘步骤失败: {name}",
                    f"命令: {' '.join(argv)}\n输出尾部:\n{result.output_tail}",
                    "critical",
                )
                return False
        return True
```

- [ ] **Step 4: 跑测试确认绿**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/application/test_shadow_ops.py -q`
Expected: 全 PASS

---

### Task 4: `scripts/shadow_tuesday.py` 薄壳（真实装配）

**Files:**
- Create: `scripts/shadow_tuesday.py`

**Interfaces:**
- Consumes: Task 3 的 `ShadowTuesdayOrchestrator/StepResult`；`load_trading_config(path).auto_trade.mode` 与 `.risk.notification`；`create_notification_gateway`；`NotificationMessage/NotificationLevel`；`TradingStore.load_signal_snapshot_by_date(date_str)`
- Produces: 命令行入口（`--post-close/--force/--config/--deadline HH:MM`），退出码同编排器

- [ ] **Step 1: 写脚本（装配壳无单测，逻辑已在 Task 3 覆盖；WSL 冒烟验证）**

```python
"""影子盘周二编排器入口(Windows python 运行; 设计 0711-shadow-control SC-3/SC-4)。

用法:
  $WIN_PYTHON scripts/shadow_tuesday.py                # 上午段: QMT 看护→refresh→采样
  $WIN_PYTHON scripts/shadow_tuesday.py --post-close   # 收盘段: refresh→比对→净值→台账
  任务计划注册(周二 09:20/15:10 自动): scripts/windows/register_shadow_tasks.ps1
"""
import argparse
import subprocess
import sys
import time as time_mod
from datetime import datetime, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.application.shadow_ops import (  # noqa: E402
    ShadowTuesdayOrchestrator,
    StepResult,
)


def _probe_qmt() -> bool:
    try:
        from xtquant import xtdata  # Windows 侧才可用; WSL 下 ImportError -> False
        return bool(xtdata.get_instrument_detail("000001.SZ"))
    except Exception:
        return False


def _run_step(name: str, argv: list[str]) -> StepResult:
    print(f"[shadow-tuesday] ▶ {name}: {' '.join(argv)}", flush=True)
    proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().splitlines()[-15:])
    print(tail, flush=True)
    return StepResult(name=name, ok=proc.returncode == 0, output_tail=tail)


def _build_notify(config_path: str):
    gateway = None
    try:
        from src.infrastructure.config.settings import load_trading_config
        from src.infrastructure.notification.factory import create_notification_gateway
        gateway = create_notification_gateway(load_trading_config(config_path).risk.notification)
    except Exception as exc:
        print(f"[shadow-tuesday] 通知网关装配失败(仅控制台): {exc}", flush=True)

    def notify(title: str, body: str, level: str) -> None:
        print(f"[shadow-tuesday][{level.upper()}] {title}\n{body}", flush=True)
        if gateway is None:
            return
        try:
            from src.domain.notification.value_objects.notification_message import (
                NotificationLevel,
                NotificationMessage,
            )
            gateway.send(NotificationMessage(
                title=title, body=body,
                level=NotificationLevel(level), category="system",
            ))
        except Exception as exc:  # 通知失败不阻断(SC-4)
            print(f"[shadow-tuesday] 通知发送失败: {exc}", flush=True)

    return notify


def _verify_snapshot_today() -> bool:
    from src.infrastructure.persistence.trading_store import TradingStore
    store = TradingStore(db_path="data/trading.db")
    try:
        row = store.load_signal_snapshot_by_date(datetime.now().date().isoformat())
        return bool(row and row.get("mode") == "dry_run")
    finally:
        store.close()


def _auto_trade_mode(config_path: str) -> str:
    try:
        from src.infrastructure.config.settings import load_trading_config
        return str(load_trading_config(config_path).auto_trade.mode)
    except Exception as exc:
        print(f"[shadow-tuesday] 配置读取失败: {exc}", flush=True)
        return f"unreadable({exc.__class__.__name__})"  # 非 dry_run -> 安全律拒绝


def main() -> int:
    parser = argparse.ArgumentParser(description="影子盘周二编排器")
    parser.add_argument("--post-close", action="store_true", help="收盘段: 比对+净值+台账")
    parser.add_argument("--morning", action="store_true", help="上午段(默认)")
    parser.add_argument("--force", action="store_true", help="非周二也执行(冒烟用)")
    parser.add_argument("--config", default="resources/trading.yaml")
    parser.add_argument("--deadline", default="14:30", help="QMT 看护截止(HH:MM)")
    args = parser.parse_args()

    hh, mm = args.deadline.split(":")
    orch = ShadowTuesdayOrchestrator(
        run_step=_run_step,
        probe_qmt=_probe_qmt,
        notify=_build_notify(args.config),
        now=datetime.now,
        sleep=time_mod.sleep,
        python_exe=sys.executable,
        verify_snapshot_today=_verify_snapshot_today,
        auto_trade_mode=lambda: _auto_trade_mode(args.config),
        force=args.force,
        deadline=time(int(hh), int(mm)),
    )
    return orch.run_post_close() if args.post_close else orch.run_morning()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: WSL 冒烟（非周二守卫路径，不触达 QMT）**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python scripts/shadow_tuesday.py; echo "exit=$?"`
Expected: 今日(周六)输出 `非调仓日` 提示且 `exit=0`（mode 守卫读 trading.yaml `dry_run` 放行，周二守卫拦下）

---

### Task 5: Windows 任务计划模板

**Files:**
- Create: `scripts/windows/register_shadow_tasks.ps1`

**Interfaces:**
- Consumes: Task 4 的脚本路径与参数
- Produces: 计划任务 `GHQ-Shadow-Morning`（周二 09:20）/ `GHQ-Shadow-PostClose`（周二 15:10）

- [ ] **Step 1: 写 ps1（顶部注释即使用说明；interop 恢复前无法代跑，静态审查 + 留给 07-14 前注册）**

```powershell
<#
影子盘周二任务计划注册(设计 0711-shadow-control SC-5)。

Windows PowerShell 执行一次:
  powershell -ExecutionPolicy Bypass -File scripts\windows\register_shadow_tasks.ps1
卸载:
  powershell -ExecutionPolicy Bypass -File scripts\windows\register_shadow_tasks.ps1 -Unregister
验证:
  Get-ScheduledTask -TaskName "GHQ-Shadow-*"

注意: 任务在当前用户会话运行, 周二须已登录 Windows; QMT 仍须人工打开——
编排器负责"提醒+等待+超时告警", 不做自动登录(设计裁定, 乙案否决)。
#>
param(
    [string]$PythonExe = "C:\Users\11492\.conda\envs\goldenhandquant\python.exe",
    [string]$RepoDir   = "C:\Codes\GoldenHandQuant",
    [switch]$Unregister
)
$ErrorActionPreference = "Stop"
$names = @("GHQ-Shadow-Morning", "GHQ-Shadow-PostClose")

if ($Unregister) {
    foreach ($n in $names) {
        Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host "已卸载: $($names -join ', ')"
    exit 0
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 6)

$morningAction  = New-ScheduledTaskAction -Execute $PythonExe -Argument "scripts\shadow_tuesday.py" -WorkingDirectory $RepoDir
$morningTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 09:20
Register-ScheduledTask -TaskName $names[0] -Action $morningAction -Trigger $morningTrigger `
    -Settings $settings -Description "GoldenHandQuant 影子盘周二上午采样(dry-run)" -Force | Out-Null

$postAction  = New-ScheduledTaskAction -Execute $PythonExe -Argument "scripts\shadow_tuesday.py --post-close" -WorkingDirectory $RepoDir
$postTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 15:10
Register-ScheduledTask -TaskName $names[1] -Action $postAction -Trigger $postTrigger `
    -Settings $settings -Description "GoldenHandQuant 影子盘周二收盘比对+净值" -Force | Out-Null

Write-Host "已注册: $($names -join ', ') (周二 09:20 / 15:10)"
```

---

### Task 6: 文档收编（runbook §5 / CLAUDE.md / debt-ledger）

**Files:**
- Modify: `docs/feat/0611-closed-loop/2026-06-12-morning-runbook.md`（§5 四命令块 → 编排器两条 + 仪表自查）
- Modify: `CLAUDE.md`（影子盘命令两条，加在 `sync_live_account` 命令块之前）
- Modify: `docs/rules/debt-ledger.md`（§五"未动工"追加演进点清单指针行）

- [ ] **Step 1: runbook §5 的 bash 块替换为**

```bash
# 周二全链一条命令(推荐注册任务计划后全自动: scripts/windows/register_shadow_tasks.ps1)
$WIN_PYTHON scripts/shadow_tuesday.py                # 上午段: QMT 看护提醒→refresh→采样
$WIN_PYTHON scripts/shadow_tuesday.py --post-close   # 收盘段: refresh→比对→净值→台账摘要
# 过程仪表: 采样台账(07-07 起逐周二)/有效样本 n/6/过闸判据; MISSED/分歧/UNKNOWN 时退出码 1
$WIN_PYTHON -m src.interfaces.cli.quant shadow status --gate
```

并在该 bash 块后追加一行说明：

```markdown
> 2026-07-11 起流程收敛为编排器（设计 `docs/feat/0711-shadow-control/`）：QMT 未上线会
> 通知提醒并每分钟重试至 14:30，超时按 MISSED 高声告警——人唯一的职责是周二开 QMT。
> 原四步手动命令仍可用（编排器内部即按该顺序 subprocess 执行）。
```

- [ ] **Step 2: CLAUDE.md 在"实盘页·真实账户快照"命令块之前插入**

```markdown
# 影子盘周二编排（QMT 看护提醒→refresh→采样→收盘比对+净值; 任务计划模板
# scripts/windows/register_shadow_tasks.ps1 注册周二 09:20/15:10 自动跑）
$WIN_PYTHON scripts/shadow_tuesday.py                 # 上午段
$WIN_PYTHON scripts/shadow_tuesday.py --post-close    # 收盘段
# 影子盘过程仪表（采样台账/有效样本 n/6/过闸判据; 过程异常退出码 1; WSL 可跑）
$WIN_PYTHON -m src.interfaces.cli.quant shadow status --gate
```

- [ ] **Step 3: debt-ledger §五"未动工"表追加一行**

```markdown
| 演进点清单 E3-E9（DD-6 ST/M4 联测/真单 Spec/C1-b/驾驶舱影子证据/全自动/ML 长线） | 0710 §11 第四轮识别, 用户裁定主攻"通往小资金实盘"; E1/E2 已落地为 `quant shadow status --gate` 过闸判据(G1-G5 机器判 + G6/G7 人工判) | `docs/feat/0710-six-sigma-evolution/` §11 + `docs/feat/0711-shadow-control/` | 2026-07-11 |
```

---

### Task 7: 全量验证

- [ ] **Step 1: ruff**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m ruff check src/ tests/ scripts/`
Expected: `All checks passed!`

- [ ] **Step 2: 全量 pytest（含架构守卫——application 顶层纯度必须仍为零违规）**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/ -q`
Expected: 全 PASS（1350 + 新增用例）

- [ ] **Step 3: 仪表实跑验收（设计验收 §四.3）**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m src.interfaces.cli.quant shadow status --gate; echo "exit=$?"`
Expected: `2026-07-07 周二 🔴 MISSED`、下一到期 `2026-07-14`、有效样本 `0/6`、`exit=1`

- [ ] **Step 4: verify_all（WSL 部分）**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python scripts/verify_all.py`
Expected: ruff/pytest/data-quality ✓；frontend-fresh ✗ 为另一路在途前端改动的正确拦截（非本轮问题）

---

## Self-Review 记录

1. **Spec coverage**: SC-1→Task 1+2；SC-2→Task 1(G1-G5)+Task 2(--gate 呈现+人工项)；SC-3→Task 3+4；SC-4→Task 4 `_build_notify`；SC-5→Task 5；SC-6→Task 6；设计 §三(07-07 记 MISSED)→Task 2 Step 5 实跑断言；设计 §四验收 1-4→Task 7，验收 5(Windows 真跑/注册)与验收 6(文档)分别在 Task 5 说明与 Task 6。无缺口。
2. **Placeholder scan**: 无 TBD/TODO/"适当处理"；所有代码/命令/预期输出完整。
3. **Type consistency**: `StepResult(name, ok, output_tail)`、`notify(title, body, level)`、`TuesdayStatus` 七值、`report(today=...)` 关键字调用、`ShadowReport` 字段名在 Task 1/2/3/4 间交叉核对一致；`auto_trade_mode` 返回 str 且守卫比较 `!= "dry_run"` 一致。
