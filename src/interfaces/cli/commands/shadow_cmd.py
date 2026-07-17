"""quant shadow — 影子盘过程仪表(设计 0711-shadow-control SC-1/SC-2)。

装配层: 接 TradingStore/MarketDataStore/shadow_checks 文件, 喂 ShadowAuditService;
呈现台账/过闸判据; 退出码 = report.process_ok(供编排器/巡检消费)。
"""
import json
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from src.application.shadow_audit import (
    MAX_MISSED,
    REQUIRED_VALID_SAMPLES,
    ShadowAuditService,
    ShadowReport,
    TuesdayStatus,
)

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
        if day in out and out[day] != "ok":
            continue
        if health != "ok" or day not in out:
            out[day] = health
    return out


def _trading_day_fn(market_store) -> Callable[[date], bool | None]:
    # 兑现①: 交易所日历(trade_calendar 表, 含未来节假日)优先——未来周二可预判;
    # 表空/store 无此能力 → 回退 bars 推导(旧行为, 未来=UNKNOWN)
    calendar = getattr(market_store, "load_trade_calendar", lambda: None)()
    if calendar is not None:
        open_days, known_until = calendar

        def is_trading_day_cal(d: date) -> bool | None:
            if d > known_until:
                return None
            return d in open_days

        return is_trading_day_cal

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


_WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _print_report(rep: ShadowReport, *, show_gate: bool) -> None:
    print("影子盘采样台账(07-07 起周二史料, 07-14 起每交易日):")
    for r in rep.ledger:
        mark = _STATUS_MARK[r.status]
        detail = f"  {r.detail}" if r.detail else ""
        print(f"  {r.day} {_WEEKDAY_NAMES[r.day.weekday()]}  {mark} {r.status:<9}{detail}")
    print(f"\n有效样本 {rep.valid_count}/{REQUIRED_VALID_SAMPLES} | "
          f"MISSED {rep.missed_count} | "
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
        print(f"\n⚠ 过程异常: 最近到期采样 MISSED / MISSED>{MAX_MISSED} / 存在 DIVERGED / "
              "存在 UNKNOWN(先 data refresh)")


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
