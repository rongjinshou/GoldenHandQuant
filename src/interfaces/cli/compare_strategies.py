"""
策略对比面板 CLI 入口。

使用方式:
    python -m src.interfaces.cli.compare_strategies \
        --strategies dual_ma,micro_value \
        --start-date 2020-01-01 \
        --end-date 2025-12-31 \
        --symbols 000021.SZ \
        --plot
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.append(os.getcwd())

from src.application.backtest_app import BacktestAppService
from src.application.strategy_comparison_app import StrategyComparisonAppService
from src.domain.backtest.services.comparison_report_service import ComparisonReportService
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.registry import create_strategy, get_strategy
from src.infrastructure.config.settings import load_backtest_config
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.infrastructure.visualization.comparison_plotter import ComparisonPlotter
from src.infrastructure.visualization.comparison_printer import ComparisonRichPrinter


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError(f"必须为正数: {value}")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strategy Comparison Tool")
    parser.add_argument("--strategies", type=str, required=True,
                        help="Comma-separated strategy names")
    parser.add_argument("--start-date", type=str, default=None,
                        help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None,
                        help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbols")
    parser.add_argument("--plot", action="store_true",
                        help="Show matplotlib comparison charts")
    parser.add_argument("--config", type=str, default=None,
                        help="YAML config file path")
    parser.add_argument("--params", type=str, default=None,
                        help="Strategy params override (key=value format)")
    parser.add_argument("--initial-capital", type=_positive_float, default=None,
                        help="初始资金覆盖（正数; 默认用配置文件值）")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    # 加载配置（显式传入的 --config 路径不存在时响亮报错, 不许静默回落默认值）
    if args.config and not os.path.exists(args.config):
        sys.exit(f"配置文件不存在: {args.config}")
    try:
        settings = (load_backtest_config(args.config) if args.config
                    else load_backtest_config())
        default_symbols = settings.backtest.symbols
        default_start = settings.backtest.start_date
        default_end = settings.backtest.end_date
        initial_capital = settings.backtest.initial_capital
        history_fetcher_type = settings.data.history_fetcher
        tushare_token = settings.data.tushare.token
    except FileNotFoundError:
        default_symbols = ["000021.SZ"]
        default_start = "2020-01-01"
        default_end = datetime.now().strftime("%Y-%m-%d")
        initial_capital = 1_000_000.0
        history_fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None

    if args.initial_capital is not None:
        initial_capital = args.initial_capital

    strategy_names = [s.strip() for s in args.strategies.split(",")]
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else default_symbols
    start_date = args.start_date or default_start
    end_date = args.end_date or default_end
    tf = Timeframe.DAY_1

    # 解析策略参数
    strategy_params: dict[str, dict[str, str]] = {}
    if args.params:
        for pair in args.params.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                # 支持 strategy.param_name=value 格式
                if "." in key:
                    sname, param = key.split(".", 1)
                    strategy_params.setdefault(sname, {})[param] = value

    print("=== Strategy Comparison ===")
    print(f"Strategies: {strategy_names}")
    print(f"Symbols: {symbols}")
    print(f"Range: {start_date} to {end_date}")

    # 初始化基础设施 (fetcher 构建逻辑与 run_backtest 共用)
    from src.interfaces.cli.run_backtest import build_history_fetcher
    fetcher = build_history_fetcher(history_fetcher_type, tushare_token)

    market_gateway = MockMarketGateway()
    trade_gateway = MockTradeGateway(market_gateway=market_gateway, initial_capital=initial_capital)
    evaluator = PerformanceEvaluator()

    # 确定是否需要 fundamental_registry（任一策略为 cross_section 即需要）
    need_fundamental = False
    for name in strategy_names:
        try:
            cfg = get_strategy(name)
            if cfg.strategy_type == "cross_section":
                need_fundamental = True
                break
        except KeyError:
            pass

    fundamental_registry = None
    stock_universe: list[str] = []
    if need_fundamental:
        from src.interfaces.cli._backtest_wiring import build_backtest_cross_section
        fundamental_registry, stock_universe = build_backtest_cross_section(
            history_fetcher_type, start_date, end_date,
            tushare_token=tushare_token, config_symbols=symbols,
        )

    # 构建 BacktestAppService（注入默认策略，实际回测用 strategies 参数覆盖）
    default_strategy = create_strategy(strategy_names[0])
    app = BacktestAppService(
        market_gateway=market_gateway,
        trade_gateway=trade_gateway,
        strategy=default_strategy,
        evaluator=evaluator,
        history_fetcher=fetcher,
        fundamental_registry=fundamental_registry,
    )

    # 准备数据
    combined = stock_universe + symbols if stock_universe else symbols
    data_symbols = list(set(combined))
    print(f"\nPreparing data ({len(data_symbols)} symbols)...")
    try:
        app.prepare_data(data_symbols, tf, start_date, end_date)
    except Exception as e:
        print(f"Error preparing data: {e}")
        return
    finally:
        # 释放数据源连接 (DuckDB read_only 与之后入库写连接同进程互斥)
        if hasattr(fetcher, "close"):
            fetcher.close()

    # 执行对比
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")
    backtest_symbols = stock_universe if stock_universe else symbols

    comparison_service = ComparisonReportService()
    comparison_app = StrategyComparisonAppService(app, comparison_service)

    print("\nRunning comparison...")
    report = comparison_app.run_comparison(
        strategy_names=strategy_names,
        symbols=backtest_symbols,
        start_date=dt_start,
        end_date=dt_end,
        base_timeframe=tf,
        strategy_params=strategy_params if strategy_params else None,
    )

    # 输出报告
    ComparisonRichPrinter().print(report)

    # 结果入库 (驾驶舱回测页消费; GHQ_NO_STORE=1 可关)
    from src.interfaces.cli.run_backtest import store_backtest_reports
    store_backtest_reports(report.reports, params={
        "symbols": symbols, "timeframe": tf.value, "source": "compare_strategies",
        "strategies": strategy_names,
    })

    if args.plot:
        ComparisonPlotter().plot(report, show=True)


if __name__ == "__main__":
    main()
