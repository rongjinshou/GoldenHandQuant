"""
回测运行入口脚本。

使用方式:
    python -m src.interfaces.cli.run_backtest
"""

import os
import sys
from datetime import datetime

# 确保项目根目录在 sys.path 中
sys.path.append(os.getcwd())

from src.application.backtest_app import BacktestAppService
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.registry import create_strategy, get_strategy
from src.infrastructure.config.settings import load_backtest_config
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.infrastructure.persistence.status_registry_loader import (
    build_status_registry_from_db,
)


def main():
    print("=== Starting Backtest Simulation (with QMT History Data) ===")

    # 加载配置（保留硬编码回退）
    try:
        settings = load_backtest_config()
        symbols = settings.backtest.symbols
        start_date = settings.backtest.start_date
        end_date = settings.backtest.end_date
        initial_capital = settings.backtest.initial_capital
        plot = settings.backtest.plot
        history_fetcher_type = settings.data.history_fetcher
        tushare_token = settings.data.tushare.token
        strategy_name = settings.strategy.name
        print("Loaded configuration from resources/backtest.yaml")
    except FileNotFoundError:
        symbols = ["000021.SZ"]
        start_date = "2016-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        initial_capital = 1_000_000.0
        plot = True
        history_fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None
        strategy_name = "DualMaStrategy"
        print("Config file not found, using default parameters.")

    tf = Timeframe.DAY_1

    print(f"Target: {symbols}")
    print(f"Timeframe: {tf.value}")
    print(f"Range: {start_date} to {end_date}")
    print(f"History Fetcher: {history_fetcher_type}")

    # 2. 初始化基础设施
    print("\nInitializing infrastructure...")
    fetcher = build_history_fetcher(history_fetcher_type, tushare_token)

    market_gateway = MockMarketGateway()

    # MockTradeGateway 需要 market_gateway 来查询价格 (假设构造函数如此设计)
    # 如果 MockTradeGateway 不需要 market_gateway，则只需传入 initial_capital
    # 检查之前的 run_backtest.py: trade_gateway = MockTradeGateway(market_gateway, initial_capital=1_000_000.0)
    # 0711-st-honesty: as-of ST 状态 → 撮合 ±5%/涨停破板/选股过滤(表空自动回退旧口径)
    status_registry = build_status_registry_from_db(start=start_date, end=end_date)
    trade_gateway = MockTradeGateway(market_gateway=market_gateway, initial_capital=initial_capital,
                                     stock_status_registry=status_registry)

    # 3. 初始化策略与应用
    print("Initializing strategy and app service...")

    # Map config names to registry names
    strategy_name_map = {
        "DualMaStrategy": "dual_ma",
        "MicroValueStrategy": "micro_value",
    }
    registry_name = strategy_name_map.get(strategy_name, strategy_name.lower())

    try:
        config = get_strategy(registry_name)
    except KeyError:
        print(f"Unknown strategy: {strategy_name}, falling back to dual_ma")
        registry_name = "dual_ma"
        config = get_strategy(registry_name)

    strategy_params = {}
    if hasattr(settings, 'strategy') and hasattr(settings.strategy, 'top_n'):
        strategy_params["top_n"] = settings.strategy.top_n
    if hasattr(settings, 'strategy') and hasattr(settings.strategy, 'weights') and settings.strategy.weights:
        strategy_params["weights"] = settings.strategy.weights

    strategy = create_strategy(registry_name, strategy_params)
    print(f"Strategy: {config.description}")

    fundamental_registry = None
    stock_universe: list[str] = []
    if config.strategy_type == "cross_section":
        from src.interfaces.cli._backtest_wiring import build_backtest_cross_section
        fundamental_registry, stock_universe = build_backtest_cross_section(
            history_fetcher_type, start_date, end_date,
            tushare_token=tushare_token, config_symbols=symbols,
        )

    evaluator = PerformanceEvaluator()

    app = BacktestAppService(
        market_gateway=market_gateway,
        trade_gateway=trade_gateway,
        strategy=strategy,
        evaluator=evaluator,
        history_fetcher=fetcher,
        fundamental_registry=fundamental_registry,
        status_registry=status_registry,
        risk_settings=settings.risk if 'settings' in locals() else None
    )

    # 4. 自动拉取/读取指定周期数据
    # 使用 stock_universe (有基本面数据的股票) + 指数 + 风控指数作为数据准备范围
    index_symbols: list[str] = []
    if 'settings' in locals() and hasattr(settings, 'risk') and settings.risk:
        idx = settings.risk.system_gate.index_symbol
        if idx:
            index_symbols.append(idx)
            print(f"Index symbol for SystemRiskGate: {idx}")

    combined = stock_universe + symbols + index_symbols if stock_universe else symbols + index_symbols
    data_symbols = list(set(combined))
    print(f"\n[Step 1] Preparing Data ({len(data_symbols)} symbols)...")
    try:
        app.prepare_data(data_symbols, tf, start_date, end_date)
        print("Data preparation completed.")
    except Exception as e:
        print(f"Error preparing data: {e}")
        print("Please ensure 'xtquant' is installed or data is cached in 'data/' directory.")
        return
    finally:
        # bars 已装入内存网关; 释放数据源连接(DuckDB 同进程 read_only 与
        # 之后入库的写连接配置冲突, 不释放会导致 backtest_runs 写入失败)
        if hasattr(fetcher, "close"):
            fetcher.close()

    # 5. 执行回测循环
    # 回测标的 = stock_universe (策略从中选股)
    backtest_symbols = stock_universe if stock_universe else symbols
    print(f"\n[Step 2] Running Backtest ({len(backtest_symbols)} symbols)...")
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")

    reports = app.run_backtest(backtest_symbols, start_date=dt_start, end_date=dt_end, base_timeframe=tf, plot=plot)
    if not reports:
        print("No backtest reports generated.")
        return
    report = reports[0]

    # 6. 输出报告
    print("\n" + "="*40)
    print("       BACKTEST PERFORMANCE REPORT       ")
    print("="*40)
    print(f"Date Range: {report.start_date.strftime('%Y-%m-%d')} to {report.end_date.strftime('%Y-%m-%d')}")
    print(f"Initial Capital:   {report.initial_capital:,.2f}")
    print(f"Final Capital:     {report.final_capital:,.2f}")
    print(f"Total Return:      {report.total_return:.2%}")
    print(f"Annualized Return: {report.annualized_return:.2%}")
    print(f"Max Drawdown:      {report.max_drawdown:.2%}")
    print(f"Win Rate:          {report.win_rate:.2%}")
    print(f"Total Trades:      {report.trade_count}")
    print("-" * 40)
    if report.trades:
        for trade in report.trades:
            dt_str = trade.execute_at.strftime('%Y-%m-%d')
            d = trade.direction.value
            print(f"[{dt_str}] {d} {trade.volume} @ {trade.price:.2f} (PnL: {trade.realized_pnl:.2f})")
    else:
        print("No trades executed.")
    print("="*40)

    # 7. 结果入库 (驾驶舱回测页消费; GHQ_NO_STORE=1 可关)
    store_backtest_reports(reports, params={
        "symbols": symbols, "timeframe": tf.value, "source": "run_backtest",
        "strategy": registry_name,
    })


def build_history_fetcher(fetcher_type: str, tushare_token: str | None = None):
    """按配置构建历史数据源 (run_backtest/compare 共用)。

    DuckDBHistoryDataFetcher: 与研究共库, QMT 不在线也能跑;
    缺失标的(如指数)优先回退 QMT, QMT 不可用则无回退。
    """
    if fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher
        return TushareHistoryDataFetcher(token=tushare_token)
    if fetcher_type == "DuckDBHistoryDataFetcher":
        from src.infrastructure.gateway.duckdb_history_data import DuckDBHistoryDataFetcher
        fallback = None
        try:
            from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
            fallback = QmtHistoryDataFetcher()
        except Exception as e:
            print(f"QMT 回退不可用 (库内缺失标的将跳过): {e}")
        return DuckDBHistoryDataFetcher(
            os.environ.get("GHQ_MARKET_DB", "data/market.duckdb"), fallback=fallback)
    from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
    return QmtHistoryDataFetcher()


def _reproducibility_metadata() -> dict:
    """代码版本指纹（C2 可复现审计）: 取不到 git 时降级为 unknown, 不阻断入库。"""
    import subprocess
    from pathlib import Path

    from src.domain.market.services.feature_engine import FEATURE_VERSION

    meta: dict = {"feature_version": FEATURE_VERSION,
                  "git_sha": "unknown", "git_dirty": None}
    repo_root = Path(__file__).resolve().parents[3]
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10,
                             cwd=repo_root)
        if sha.returncode == 0:
            meta["git_sha"] = sha.stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10,
                               cwd=repo_root)
        if dirty.returncode == 0:
            meta["git_dirty"] = bool(dirty.stdout.strip())
    except Exception:
        pass
    return meta


def _data_fingerprint(store) -> dict:
    """数据版本指纹: bars 行数+最新日, 区分「同参不同数据版本」的两次跑。"""
    try:
        rows, max_date = store._conn.execute(  # noqa: SLF001 — 同为持久层协作
            "SELECT COUNT(*), MAX(date) FROM bars").fetchone()
        return {"bars_rows": rows, "bars_max_date": str(max_date)}
    except Exception:
        return {"bars_rows": None, "bars_max_date": None}


def store_backtest_reports(reports, *, params: dict) -> None:
    """回测结果写入 market.duckdb backtest_runs (闭环 v1 DD-5)。失败不影响回测。

    C2 可复现审计: 统一注入 repro 块(git_sha/数据指纹/特征版本)与 survivorship
    宇宙口径(调用方未标注时显式记 unspecified, 让「没标」本身可见)。
    """
    if os.environ.get("GHQ_NO_STORE") == "1":
        return
    try:
        from src.infrastructure.persistence.backtest_run_mapper import build_backtest_run_row
        from src.infrastructure.persistence.market_data_store import MarketDataStore

        run_id = f"{datetime.now():%Y%m%d-%H%M%S}"
        store = MarketDataStore(os.environ.get("GHQ_MARKET_DB", "data/market.duckdb"))
        try:
            full_params = {
                "survivorship": "unspecified",
                **params,
                "repro": {**_reproducibility_metadata(), **_data_fingerprint(store)},
            }
            rows = [build_backtest_run_row(r, run_id=run_id, params=full_params)
                    for r in reports]
            store.insert_backtest_runs(rows)
        finally:
            store.close()
        print(f"结果已入库: backtest_runs run_id={run_id} ({len(rows)} 策略)")
    except Exception as e:
        print(f"⚠ 回测结果入库失败 (不影响回测本身): {e}")


if __name__ == "__main__":
    main()
