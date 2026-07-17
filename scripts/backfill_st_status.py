"""ST 状态全市场回填(设计 0711-st-honesty §3.5)。WSL 可跑(纯 HTTP)。

流程: 深市官方简称变更→区间; 沪市巨潮公告(按季度窗口)→事件→区间;
交叉验证(深市双源, 准入门 §3.4) → 终态自洽检查 → 入库 + 报告。
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.domain.market.value_objects.st_prefixes import is_st_name  # noqa: E402
from src.infrastructure.gateway.st_status_source import (  # noqa: E402
    classify_sh_notices,
    cross_validate,
    derive_periods_from_sz_feed,
    events_to_periods,
)
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402


def _quarter_windows(start: date, end: date):
    cur = date(start.year, ((start.month - 1) // 3) * 3 + 1, 1)
    while cur <= end:
        nxt_month = cur.month + 3
        nxt = date(cur.year + (nxt_month - 1) // 12, (nxt_month - 1) % 12 + 1, 1)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


def main() -> int:
    parser = argparse.ArgumentParser(description="ST 状态回填")
    parser.add_argument("--db", default="data/market.duckdb")
    parser.add_argument("--start", default="2020-01-01", help="沪市公告检索起点")
    parser.add_argument("--check-only", action="store_true", help="只跑交叉验证不入库")
    args = parser.parse_args()

    import akshare as ak

    print("① 深市官方简称变更 …")
    sz_feed = ak.stock_info_sz_change_name(symbol="简称变更")
    sz_rows = sz_feed.to_dict("records")
    sz_periods = derive_periods_from_sz_feed(sz_rows)
    print(f"   {len(sz_rows)} 行变更 → {len(sz_periods)} 个 ST 区间")

    store = MarketDataStore(args.db)
    td_sorted = sorted(store.trading_dates())

    def next_td(d: date) -> date:
        for t in td_sorted:
            if t > d:
                return t
        return d + timedelta(days=1)  # 超出已知区: 日历近似(仅影响最新事件 ±1 天)

    print(f"② 沪深公告检索(风险警示, {args.start}→today, 按季度) …")
    start = date.fromisoformat(args.start)
    notices: list[dict] = []
    for lo, hi in _quarter_windows(start, date.today()):
        try:
            df = ak.stock_zh_a_disclosure_report_cninfo(
                symbol="", market="沪深京", keyword="风险警示", category="",
                start_date=lo.strftime("%Y%m%d"), end_date=hi.strftime("%Y%m%d"))
            rows = df.to_dict("records") if df is not None and not df.empty else []
        except Exception as exc:
            print(f"   {lo}~{hi}: 检索失败 {exc!r}")
            rows = []
        notices.extend(rows)
        print(f"   {lo}~{hi}: {len(rows)} 条")

    sh_events = classify_sh_notices(notices, next_td)
    sh_periods = events_to_periods(sh_events)
    print(f"   沪市主板: {len(sh_events)} 决定性事件 → {len(sh_periods)} 区间")

    print("③ 交叉验证(公告法管道对深市官方流, 设计 §3.4) …")
    sz_inferred = events_to_periods(classify_sh_notices(
        notices, next_td, code_prefixes=("000", "001", "002", "003"), suffix=".SZ"))
    # 官方流限定在公告检索窗口内可比(公告只查了 args.start 起)
    official_window = [p for p in sz_periods
                       if (p.end or date.today()) >= start and p.start != date.min]
    validation = cross_validate(official_window, sz_inferred, td_sorted)
    print(f"   官方事件 {validation['total_official']} | 对齐 {validation['matched']}"
          f" | ≤2td {validation['within_2td']} | 均值带符号 {validation['mean_signed_td']}"
          f" | 准入 {'PASS' if validation['pass'] else 'FAIL'}")

    print("④ 终态对照(开区间 vs instruments 当前名; 差异=instruments 名称滞后观察, "
          "非推导错误——2026-04 戴帽潮实证: 交易所变更流比 instruments 快照新鲜) …")
    current_names = dict(store._conn.execute(
        "SELECT symbol, ANY_VALUE(name) FROM instruments GROUP BY symbol").fetchall())
    delisted = {r[0] for r in store._conn.execute(
        "SELECT DISTINCT symbol FROM instruments WHERE delist_date IS NOT NULL").fetchall()}
    open_periods = [p for p in (sz_periods + sh_periods) if p.end is None]
    stale_names = sorted(p.symbol for p in open_periods
                         if p.symbol not in delisted
                         and not is_st_name(str(current_names.get(p.symbol, ""))))
    exempt_delisted = sum(1 for p in open_periods if p.symbol in delisted)
    print(f"   开区间 {len(open_periods)} | 退市豁免 {exempt_delisted} | "
          f"instruments 名称滞后 {len(stale_names)} 只(样例 {stale_names[:6]})")
    suspects = stale_names  # 报告字段沿用, 语义=名称滞后观察清单

    report = {
        "generated_at": date.today().isoformat(),
        "sz_periods": len(sz_periods), "sh_periods": len(sh_periods),
        "sh_events": len(sh_events),
        "validation": {k: v for k, v in validation.items() if k != "details"},
        "validation_details_sample": validation.get("details", [])[:80],
        "suspects": suspects,
    }
    Path("data/st_backfill_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("   报告 → data/st_backfill_report.json")

    if args.check_only:
        return 0 if validation["pass"] else 1
    if not validation["pass"]:
        print("✗ 交叉验证未达准入门: 沪市公告法区间不入库(设计 §3.4 回炉条款), "
              "深市官方区间照常入库")
        n = store.save_st_periods(sz_periods)
    else:
        n = store.save_st_periods(sz_periods + sh_periods)
    print(f"⑤ 入库 st_status_periods: {n} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
