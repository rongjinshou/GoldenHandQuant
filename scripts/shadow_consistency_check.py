"""影子盘一致性比对 — dry-run 决策快照 vs DuckDB 离线同输入决策(0626 阶段1 DD-8)。

用法: $WIN_PYTHON scripts/shadow_consistency_check.py [--date 2026-07-08] [--db data/trading.db]
前提: 该日 auto-trade 已落 signal_snapshots 快照(data_health=ok);
     market.duckdb 已 refresh 覆盖快照日(bars 到该日, 收盘后跑)。

口径(design DD-8): 比对在决策快照级, 不在执行流水级。复用 build_live_signal_service
走同一条装配+scan 路径(零重复实现), fundamental/宇宙/持仓/资金/时钟均按快照重放,
唯一自由变量 = bars 源(QMT 实时 vs DuckDB 存量)。

diff 判定: selection 对称差 / targets 逐位 (symbol, direction, volume) / gate_passed 布尔。
price 不比 — 前复权基准日漂移属预期白名单; 其余白名单差异(报告标注, 人工复核非误报):
盘中末根 bar 形态、fundamental 别名滞后、节假日周二。

exit 0 = 全一致; 1 = 有 diff(打印白名单提示); 2 = 无快照或数据缺失。
报告: 打印 + json 存 data/shadow_checks/{date}.json。
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.getcwd())

import duckdb  # noqa: E402

from src.application.data_health import DataHealthError  # noqa: E402
from src.domain.account.entities.asset import Asset  # noqa: E402
from src.domain.account.entities.position import Position  # noqa: E402
from src.domain.market.value_objects.timeframe import Timeframe  # noqa: E402
from src.infrastructure.config.settings import load_trading_config  # noqa: E402
from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher  # noqa: E402
from src.infrastructure.mock.mock_market import MockMarketGateway  # noqa: E402
from src.infrastructure.persistence.trading_store import TradingStore  # noqa: E402
from src.interfaces.cli._auto_trade_wiring import build_live_signal_service  # noqa: E402

EXIT_OK, EXIT_DIFF, EXIT_NO_DATA = 0, 1, 2

# 120 根决策窗口 + 节假日/停牌余量, 与 mainboard_f01_gate 离线装载套路同源
_BARS_LOOKBACK_DAYS = 365

_WHITELIST_HINT = (
    "白名单差异(design DD-8, 人工复核而非误报): 前复权基准日漂移(故不比 price)、"
    "盘中末根 bar 形态(09:35 开盘价已定型, 应收敛)、fundamental 别名滞后 ≤1 交易日、"
    "节假日周二(实盘无交易日历判断)"
)


class _StubAccountTradeGateway:
    """快照重放用最小网关 stub — 持仓/资产来自 signal_snapshots, 绝不触达券商。

    同一实例同时充当 IAccountGateway 与 ITradeGateway: scan 与 runner 内部各取一次
    持仓/资产, 必须同源(与 live dry-run 透传真账户的语义对齐)。
    """

    is_dry_run = True

    def __init__(self, positions: list[Position], asset: Asset) -> None:
        self._positions = positions
        self._asset = asset

    def get_asset(self, account_id: str | None = None) -> Asset | None:
        return self._asset

    def get_positions(self, account_id: str | None = None) -> list[Position]:
        return self._positions

    def place_order(self, order) -> str:
        raise NotImplementedError("重放比对绝不下单")

    def query_order_status(self, order_id: str) -> str | None:
        raise NotImplementedError("重放比对不查单")

    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("重放比对不撤单")


def _rebuild_positions(positions_json: str) -> list[Position]:
    """positions_json(序列化约定见 auto_trade_app) → domain Position 列表。"""
    return [
        Position(
            account_id="shadow_replay",
            ticker=row["symbol"],
            total_volume=int(row["total_volume"]),
            available_volume=int(row["available_volume"]),
            average_cost=float(row["average_cost"]),
        )
        for row in json.loads(positions_json or "[]")
    ]


def _target_tuples(targets: list[dict]) -> list[tuple[str, str, int]]:
    """targets → 逐位比对键 (symbol, direction, volume); price 刻意剔除(白名单)。"""
    return [(t["symbol"], t["direction"], int(t["volume"])) for t in targets]


def _counter_only(a: list[tuple[str, str, int]], b: list[tuple[str, str, int]]) -> list[dict]:
    """多重集差 a - b, 转 JSON 可序列化行。"""
    only = Counter(a) - Counter(b)
    return [
        {"symbol": s, "direction": d, "volume": v, "count": c}
        for (s, d, v), c in sorted(only.items())
    ]


def _load_snapshot(db_path: str, date_str: str) -> dict | None:
    store = TradingStore(db_path)
    try:
        return store.load_signal_snapshot_by_date(date_str)
    finally:
        store.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="影子盘一致性比对: dry-run 决策快照 vs DuckDB 离线同输入重放 (design DD-8)",
    )
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="快照日 YYYY-MM-DD (默认今天)")
    parser.add_argument("--db", default="data/trading.db",
                        help="交易留痕库路径 (默认 data/trading.db)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        date.fromisoformat(args.date)
    except ValueError:
        print(f"[exit 2] --date 非法: {args.date!r}, 需 YYYY-MM-DD")
        return EXIT_NO_DATA

    # 1. 读快照(先于一切 DuckDB 访问: 无快照日不碰 market.duckdb)
    snap = _load_snapshot(args.db, args.date)
    if snap is None:
        print(f"[exit 2] {args.date} 无决策快照: 该日 auto-trade 未跑或未落库 "
              f"(库 {args.db}, 表 signal_snapshots)")
        return EXIT_NO_DATA
    if snap.get("data_health") != "ok":
        print(f"[exit 2] {args.date} 快照 data_health={snap.get('data_health')!r} "
              f"(note: {snap.get('note')}): 数据故障周期无决策可比, 跳过")
        return EXIT_NO_DATA

    snap_time = datetime.fromisoformat(snap["snapshot_time"])
    snap_day = snap_time.date()

    # 2. 同一配置重演装配口径
    settings = load_trading_config()
    at = settings.auto_trade
    if at.strategy != snap["strategy"]:
        print(f"[warn] 当前配置 strategy={at.strategy} != 快照 strategy={snap['strategy']}, "
              f"以当前配置重放 — 若快照后改过配置, 比对口径可能失真")

    # 3. 快照持仓/资产注入 stub(sizer 只消费 total_asset; 其余字段合理填充)
    stub = _StubAccountTradeGateway(
        positions=_rebuild_positions(snap.get("positions_json") or "[]"),
        asset=Asset(
            account_id="shadow_replay",
            total_asset=float(snap.get("total_asset") or 0.0),
            available_cash=float(snap.get("total_asset") or 0.0),
            frozen_cash=0.0,
        ),
    )

    # 4. 离线装配: 同一条 build_live_signal_service 路径, today=快照日(as-of 别名基准)
    mkt = MockMarketGateway()
    try:
        fetcher = DuckDBHistoryDataFetcher()
        service, symbols = build_live_signal_service(
            at, market_gateway=mkt, account_gateway=stub, trade_gateway=stub,
            today=snap_day,
        )
    except DataHealthError as e:
        print(f"[exit 2] 离线装配数据故障: {e}")
        return EXIT_NO_DATA
    except duckdb.Error as e:
        print(f"[exit 2] market.duckdb 打不开(data refresh/factor-test 写进程占用?): {e}")
        return EXIT_NO_DATA

    # 5. DuckDB bars 装 MockMarketGateway(套路同 mainboard_f01_gate; 指数必装)
    bars_start = (snap_day - timedelta(days=_BARS_LOOKBACK_DAYS)).isoformat()
    bars_end = snap_day.isoformat()
    index_bars = fetcher.fetch_history_bars(
        service.index_symbol, Timeframe.DAY_1, bars_start, bars_end)
    if not index_bars:
        print(f"[exit 2] market.duckdb 无指数 {service.index_symbol} bars: 先 data refresh")
        fetcher.close()
        return EXIT_NO_DATA
    index_latest = index_bars[-1].timestamp.date()
    if (snap_day - index_latest).days > 7:
        print(f"[exit 2] market.duckdb 指数 bars 最新 {index_latest} 落后快照日 "
              f"{bars_end} 超 7 天: 先 data refresh 再比对")
        fetcher.close()
        return EXIT_NO_DATA
    if index_latest < snap_day:
        # 非交易日/未收盘的快照: QMT 实时侧末根同为最近交易日, 两侧窗口天然对齐
        print(f"[warn] 指数 bars 末根 {index_latest} < 快照日 {bars_end}"
              f"(非交易日/未 refresh 到当日?): 两侧均截至最近交易日, 继续比对")
    mkt.load_bars(index_bars)
    print(f"装载 bars {bars_start}..{bars_end}: 宇宙 {len(symbols)} 只 + 指数 {service.index_symbol}")
    equity_symbols = [s for s in symbols if s != service.index_symbol]
    for i, sym in enumerate(equity_symbols, start=1):
        mkt.load_bars(fetcher.fetch_history_bars(sym, Timeframe.DAY_1, bars_start, bars_end))
        if i % 300 == 0:
            print(f"  ... {i}/{len(equity_symbols)}")
    fetcher.close()

    # 6. 时钟/行情时间对齐快照时刻 → 同输入重放决策核心
    mkt.set_current_time(snap_time)
    service.clock = lambda: snap_time
    try:
        service.scan(at.strategy, symbols)
    except DataHealthError as e:
        print(f"[exit 2] 离线重放被 scan 数据健康守卫拒绝: {e}")
        return EXIT_NO_DATA
    offline = service.last_snapshot
    if offline is None:
        print(f"[exit 2] 离线 scan 未产生决策快照(strategy={at.strategy} 非截面?), 无可比对")
        return EXIT_NO_DATA

    # 7. diff: selection 对称差 / targets 逐位 / gate 布尔
    live_sel = sorted(json.loads(snap.get("selection_json") or "[]"))
    off_sel = sorted(offline.selection)
    sel_only_live = sorted(set(live_sel) - set(off_sel))
    sel_only_off = sorted(set(off_sel) - set(live_sel))
    sel_match = not sel_only_live and not sel_only_off

    live_tgt = _target_tuples(json.loads(snap.get("targets_json") or "[]"))
    off_tgt = _target_tuples(offline.targets)
    tgt_match = live_tgt == off_tgt
    tgt_only_live = _counter_only(live_tgt, off_tgt)
    tgt_only_off = _counter_only(off_tgt, live_tgt)
    order_only_mismatch = not tgt_match and not tgt_only_live and not tgt_only_off

    gate_live, gate_off = bool(snap.get("gate_passed")), bool(offline.gate_passed)
    gate_match = gate_live == gate_off
    consistent = sel_match and tgt_match and gate_match

    report = {
        "date": args.date,
        "cycle_id": snap.get("cycle_id"),
        "snapshot_time": snap["snapshot_time"],
        "mode": snap.get("mode"),
        "strategy": snap["strategy"],
        "consistent": consistent,
        "gate": {"live": gate_live, "offline": gate_off, "match": gate_match},
        "selection": {
            "live": live_sel, "offline": off_sel,
            "only_in_live": sel_only_live, "only_in_offline": sel_only_off,
            "match": sel_match,
        },
        "targets": {
            "live_count": len(live_tgt), "offline_count": len(off_tgt),
            "only_in_live": tgt_only_live, "only_in_offline": tgt_only_off,
            "order_only_mismatch": order_only_mismatch,
            "match": tgt_match,
        },
        "meta": {  # informative, 不进入判定
            "universe_size": {"live": snap.get("universe_size"), "offline": offline.universe_size},
            "filtered_size": {"live": snap.get("filtered_size"), "offline": offline.filtered_size},
            "fundamental_date": {
                "live": snap.get("fundamental_date"),
                "offline": offline.fundamental_date.isoformat() if offline.fundamental_date else None,
            },
            "fundamental_rows": {"live": snap.get("fundamental_rows"),
                                 "offline": offline.fundamental_rows},
            "staleness_days": {"live": snap.get("staleness_days"), "offline": offline.staleness_days},
            "index_bars_count": {"live": snap.get("index_bars_count"),
                                 "offline": offline.index_bars_count},
        },
        "whitelist_note": _WHITELIST_HINT,
    }
    out_dir = Path("data/shadow_checks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.date}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def mark(ok: bool) -> str:
        return "一致" if ok else "DIFF"

    print(f"\n=== 影子盘一致性比对 {args.date} (cycle {snap.get('cycle_id')}) ===")
    print(f"快照: {snap['snapshot_time']} mode={snap.get('mode')} strategy={snap['strategy']}")
    print(f"gate_passed: live={gate_live} offline={gate_off} -> {mark(gate_match)}")
    print(f"selection  : live {len(live_sel)} / offline {len(off_sel)} 只 -> {mark(sel_match)}")
    if sel_only_live:
        print(f"  仅 live   : {sel_only_live}")
    if sel_only_off:
        print(f"  仅 offline: {sel_only_off}")
    print(f"targets    : live {len(live_tgt)} / offline {len(off_tgt)} 单, "
          f"逐位(symbol,direction,volume) -> {mark(tgt_match)}")
    if tgt_only_live:
        print(f"  仅 live   : {tgt_only_live}")
    if tgt_only_off:
        print(f"  仅 offline: {tgt_only_off}")
    if order_only_mismatch:
        print("  (成员与股数全同, 仅顺序不同)")
    meta = report["meta"]
    print("meta 对照(informative): " + "; ".join(
        f"{k} live={v['live']} off={v['offline']}" for k, v in meta.items()))
    print(f"报告已存: {out_path}")

    if consistent:
        print("结论: 全一致 (exit 0)")
        return EXIT_OK
    print("结论: 有 diff (exit 1) — 先对照白名单再定性:")
    print(f"  {_WHITELIST_HINT}")
    return EXIT_DIFF


if __name__ == "__main__":
    sys.exit(main())
