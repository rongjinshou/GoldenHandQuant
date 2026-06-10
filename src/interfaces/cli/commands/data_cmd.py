"""quant data 子命令 — 市场数据库维护（refresh / status）。"""

import argparse


def run_data(args: argparse.Namespace) -> None:
    match args.data_action:
        case "status":
            _run_status(args)
        case "refresh":
            _run_refresh(args)


def _run_status(args: argparse.Namespace) -> None:
    from src.infrastructure.persistence.market_data_store import MarketDataStore

    store = MarketDataStore(args.db)
    try:
        stats = store.table_stats()
    finally:
        store.close()

    print(f"=== Market Data Store: {args.db} ===")
    print(f"{'table':<24} {'rows':>12} {'symbols':>8}  date range")
    for table, s in stats.items():
        rng = f"{s['min_date']} ~ {s['max_date']}" if s["min_date"] else "-"
        print(f"{table:<24} {s['rows']:>12,} {s['symbols']:>8}  {rng}")


def _run_refresh(args: argparse.Namespace) -> None:
    from src.interfaces.cli.commands._data_wiring import build_data_wiring, resolve_universe

    wiring = build_data_wiring(args.config, args.db)
    try:
        symbols = resolve_universe(wiring)
        print(f"[refresh] {len(symbols)} symbols, {args.start_date} → {args.end_date}")

        refreshed = wiring.market_data.ensure_bars(symbols, args.start_date, args.end_date)
        print(f"  bars: 刷新 {len(refreshed)} 只 (缺口拉取)")
        wiring.market_data.ensure_fundamentals(args.start_date, args.end_date)
        print("  fundamentals: 缺口已补")
        recomputed = wiring.market_data.ensure_features(
            symbols, args.start_date, args.end_date, refreshed
        )
        print(f"  features: 重算 {recomputed} 只 (v{_feature_version()})")

        for table, s in wiring.store.table_stats().items():
            print(f"  {table:<24} rows={s['rows']:,}")
    finally:
        wiring.store.close()


def _feature_version() -> int:
    from src.domain.market.services.feature_engine import FEATURE_VERSION
    return FEATURE_VERSION
