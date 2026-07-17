"""影子盘过程审计: 采样台账 + 过闸判据。

设计: docs/feat/0711-shadow-control/2026-07-11-shadow-control-design.md SC-1/SC-2;
2026-07-14 用户指令改日频("跑半个月, 防御信号日频才抓得全"): 07-14 起每个交易日
都是采样日, 此前(07-07/07-13)按周二史料口径保留。
分层: 数据访问全部经构造注入的 callables, 顶层不 import infrastructure。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

GATE_START = date(2026, 7, 7)          # 阶段 1 计划首采日(0626 phase1 report)
DAILY_ERA_START = date(2026, 7, 14)    # 日频采样时代起点(用户指令)
REQUIRED_VALID_SAMPLES = 10            # G1: "跑半个月"≈10 个交易日
REQUIRED_DECISION_TUESDAYS = 2         # G1: 其中至少 2 个调仓周二(独立决策样本)
MAX_MISSED = 2                         # G5: 日频容错, >2 = 采样过程失控

MANUAL_GATE_ITEMS: tuple[str, ...] = (
    "G6 M4 成交回报回填+断线重连 QMT 实环境联测完成(以台账 M3 遗留项核销为准)",
    "G7 DD-6 ST 诚实债重验后 F01 gate 仍 PASS(以台账 DD-6 核销为准)",
)


class TuesdayStatus(StrEnum):
    VALID = "VALID"          # 已采样且比对一致
    UNCHECKED = "UNCHECKED"  # 已采样, 比对未跑(离线可补)
    DIVERGED = "DIVERGED"    # 已采样, 比对不一致(立案)
    MISSED = "MISSED"        # 交易日未采样(live 快照不可重建, 如实保留)
    EXEMPT = "EXEMPT"        # 节假日采样日(白名单)
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


def _sampling_days(start: date, end: date) -> list[date]:
    """采样日全集: 日频时代前=周二(史料口径), 日频时代起=每个工作日。"""
    out: list[date] = []
    d = start + timedelta(days=(1 - start.weekday()) % 7)  # 首个周二
    while d <= end and d < DAILY_ERA_START:
        out.append(d)
        d += timedelta(days=7)
    d = max(DAILY_ERA_START, start)
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _is_sampling_day(d: date) -> bool:
    if d >= DAILY_ERA_START:
        return d.weekday() < 5
    return d.weekday() == 1


def _next_sampling_day_after(d: date) -> date:
    nxt = d + timedelta(days=1)
    while not _is_sampling_day(nxt):
        nxt += timedelta(days=1)
    return nxt


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
        ledger = [self._classify(d, today, health) for d in _sampling_days(GATE_START, today)]

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

        if _is_sampling_day(today) and today not in health:
            next_due = today
        else:
            next_due = _next_sampling_day_after(today)

        sampled_health = [health[r.day] for r in ledger if r.day in health]
        paper = self._paper_run_count()
        # 日频样本量大但相关性高(相邻日截面近似), 独立决策样本仍以调仓周二计数
        tuesdays_valid = sum(
            1 for r in ledger if r.status is TuesdayStatus.VALID and r.day.weekday() == 1
        )
        gate = [
            GateCriterion(
                key="G1",
                description=(
                    f"有效样本 ≥ {REQUIRED_VALID_SAMPLES} 交易日"
                    f"(含 ≥{REQUIRED_DECISION_TUESDAYS} 调仓周二)"
                ),
                passed=(
                    valid >= REQUIRED_VALID_SAMPLES
                    and tuesdays_valid >= REQUIRED_DECISION_TUESDAYS
                ),
                actual=(
                    f"{valid}/{REQUIRED_VALID_SAMPLES} "
                    f"(周二 {tuesdays_valid}/{REQUIRED_DECISION_TUESDAYS})"
                ),
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
                description="纸面净值随采样入库无断档(入库数 ≥ 有效样本数)",
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
                        detail=(
                            "快照已落库, 比对未跑"
                            f"(可补: scripts/shadow_consistency_check.py --date {day})"
                        ),
                    )
                case True:
                    detail = "" if health[day] == "ok" else f"data_health={health[day]}"
                    return TuesdayRecord(day=day, status=TuesdayStatus.VALID, detail=detail)
                case _:
                    return TuesdayRecord(
                        day=day, status=TuesdayStatus.DIVERGED, detail="比对不一致, 立案"
                    )
        if day == today:
            return TuesdayRecord(
                day=day, status=TuesdayStatus.PENDING, detail="今日采样窗口进行中"
            )
        match self._is_trading_day(day):
            case None:
                return TuesdayRecord(
                    day=day, status=TuesdayStatus.UNKNOWN, detail="bars 未刷至该日, 先 data refresh"
                )
            case True:
                return TuesdayRecord(
                    day=day, status=TuesdayStatus.MISSED, detail="live 快照不可重建, 如实保留"
                )
            case _:
                return TuesdayRecord(day=day, status=TuesdayStatus.EXEMPT, detail="非交易日")
