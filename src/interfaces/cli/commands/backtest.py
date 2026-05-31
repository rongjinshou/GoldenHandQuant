"""quant backtest 子命令实现。"""

import argparse
from datetime import datetime

from src.application.backtest_app import BacktestAppService
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.registry import create_strategy, get_strategy
from src.infrastructure.config.settings import load_backtest_config
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


def _print_report(report) -> None:
    """输出回测报告摘要。"""
    print("\n" + "=" * 40)
    print("       BACKTEST PERFORMANCE REPORT       ")
    print("=" * 40)
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
            dt_str = trade.execute_at.strftime("%Y-%m-%d")
            d = trade.direction.value
            print(f"[{dt_str}] {d} {trade.volume} @ {trade.price:.2f} (PnL: {trade.realized_pnl:.2f})")
    else:
        print("No trades executed.")
    print("=" * 40)


def run_backtest(args: argparse.Namespace) -> None:
    """执行回测。参数由 quant.py 统一解析后传入。"""
    strategy_name: str = args.strategy
    config_path: str = args.config
    start_date_override: str | None = args.start_date
    end_date_override: str | None = args.end_date
    plot: bool = args.plot

    print("=== Starting Backtest Simulation ===")

    # 加载配置
    try:
        settings = load_backtest_config(config_path)
        symbols = settings.backtest.symbols
        start_date = start_date_override or settings.backtest.start_date
        end_date = end_date_override or settings.backtest.end_date
        initial_capital = settings.backtest.initial_capital
        history_fetcher_type = settings.data.history_fetcher
        tushare_token = settings.data.tushare.token
        print(f"Loaded configuration from {config_path}")
    except FileNotFoundError:
        symbols = ["000021.SZ"]
        start_date = start_date_override or "2016-01-01"
        end_date = end_date_override or datetime.now().strftime("%Y-%m-%d")
        initial_capital = 1_000_000.0
        history_fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None
        settings = None
        print(f"Config file not found ({config_path}), using defaults.")

    tf = Timeframe.DAY_1
    print(f"Strategy: {strategy_name}")
    print(f"Target: {symbols}")
    print(f"Range: {start_date} to {end_date}")

    # 初始化基础设施
    if history_fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher

        fetcher = TushareHistoryDataFetcher(token=tushare_token)
    else:
        from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher

        fetcher = QmtHistoryDataFetcher()

    market_gateway = MockMarketGateway()
    trade_gateway = MockTradeGateway(market_gateway=market_gateway, initial_capital=initial_capital)

    # 初始化策略
    try:
        config = get_strategy(strategy_name)
    except KeyError:
        print(f"Unknown strategy: {strategy_name}, falling back to dual_ma")
        strategy_name = "dual_ma"
        config = get_strategy(strategy_name)

    strategy_params: dict = {}
    if settings and hasattr(settings, "strategy"):
        if hasattr(settings.strategy, "top_n"):
            strategy_params["top_n"] = settings.strategy.top_n
        if hasattr(settings.strategy, "weights") and settings.strategy.weights:
            strategy_params["weights"] = settings.strategy.weights

    strategy = create_strategy(strategy_name, strategy_params)
    print(f"Strategy desc: {config.description}")

    # 处理截面策略的 FundamentalRegistry
    fundamental_registry = None
    stock_universe: list[str] = []
    if config.strategy_type == "cross_section":
        from src.domain.market.services.fundamental_registry import FundamentalRegistry

        fundamental_registry = FundamentalRegistry()

        if history_fetcher_type == "TushareHistoryDataFetcher":
            from src.infrastructure.gateway.tushare_fundamental_fetcher import TushareFundamentalFetcher

            fund_fetcher = TushareFundamentalFetcher(token=tushare_token)
            snapshots = fund_fetcher.fetch_by_range(start_date, end_date)
            fundamental_registry.load_snapshots(snapshots)
        else:
            from src.infrastructure.gateway.qmt_fundamental_fetcher import QmtFundamentalFetcher

            fund_fetcher = QmtFundamentalFetcher()
            from src.infrastructure.gateway.xtquant_client import xtdata as _xt

            for sector in ["沪深A股"]:
                try:
                    stock_universe.extend(_xt.get_stock_list_in_sector(sector))
                except Exception:
                    pass
            stock_universe = sorted(set(stock_universe))
            max_stocks = 500
            if len(stock_universe) > max_stocks:
                import random

                random.seed(42)
                stock_universe = sorted(random.sample(stock_universe, max_stocks))
                print(f"Stock universe: limited to {max_stocks} stocks")
            else:
                print(f"Stock universe: {len(stock_universe)} stocks")
            snapshots = fund_fetcher.fetch_by_range(start_date, end_date, symbols=stock_universe)
            fundamental_registry.load_snapshots(snapshots)

        stock_universe = sorted({s.symbol for s in snapshots})
        print(f"Stocks with fundamental data: {len(stock_universe)}")

    evaluator = PerformanceEvaluator()
    app = BacktestAppService(
        market_gateway=market_gateway,
        trade_gateway=trade_gateway,
        strategy=strategy,
        evaluator=evaluator,
        history_fetcher=fetcher,
        fundamental_registry=fundamental_registry,
        risk_settings=settings.risk if settings else None,
    )

    # 准备数据
    index_symbols: list[str] = []
    if settings and hasattr(settings, "risk") and settings.risk:
        idx = settings.risk.system_gate.get("index_symbol")
        if idx:
            index_symbols.append(idx)

    combined = stock_universe + symbols + index_symbols if stock_universe else symbols + index_symbols
    data_symbols = list(set(combined))
    print(f"\n[Step 1] Preparing Data ({len(data_symbols)} symbols)...")
    try:
        app.prepare_data(data_symbols, tf, start_date, end_date)
        print("Data preparation completed.")
    except Exception as e:
        print(f"Error preparing data: {e}")
        return

    # 执行回测
    backtest_symbols = stock_universe if stock_universe else symbols
    print(f"\n[Step 2] Running Backtest ({len(backtest_symbols)} symbols)...")
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")

    reports = app.run_backtest(backtest_symbols, start_date=dt_start, end_date=dt_end, base_timeframe=tf, plot=plot)
    if not reports:
        print("No backtest reports generated.")
        return

    _print_report(reports[0])
