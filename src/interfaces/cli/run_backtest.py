"""
回测运行入口脚本。

使用方式:
    python -m src.interfaces.cli.run_backtest
"""

import sys
import os
from datetime import datetime

# 确保项目根目录在 sys.path 中
sys.path.append(os.getcwd())

from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.application.backtest_app import BacktestAppService
from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.timeframe import Timeframe
from src.infrastructure.config.settings import load_backtest_config

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
        print("Loaded configuration from resources/backtest.yaml")
    except FileNotFoundError:
        symbols = ["000021.SZ"]
        start_date = "2016-01-01"
        end_date = datetime.now().strftime("%Y-%m-%d")
        initial_capital = 1_000_000.0
        plot = True
        history_fetcher_type = "TushareHistoryDataFetcher"
        tushare_token = None
        print("Config file not found, using default parameters.")

    tf = Timeframe.DAY_1

    print(f"Target: {symbols}")
    print(f"Timeframe: {tf.value}")
    print(f"Range: {start_date} to {end_date}")
    print(f"History Fetcher: {history_fetcher_type}")

    # 2. 初始化基础设施
    print("\nInitializing infrastructure...")
    if history_fetcher_type == "TushareHistoryDataFetcher":
        from src.infrastructure.gateway.tushare_history_data import TushareHistoryDataFetcher
        fetcher = TushareHistoryDataFetcher(token=tushare_token)
    else:
        from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
        fetcher = QmtHistoryDataFetcher()
    
    market_gateway = MockMarketGateway()
    
    # MockTradeGateway 需要 market_gateway 来查询价格 (假设构造函数如此设计)
    # 如果 MockTradeGateway 不需要 market_gateway，则只需传入 initial_capital
    # 检查之前的 run_backtest.py: trade_gateway = MockTradeGateway(market_gateway, initial_capital=1_000_000.0)
    trade_gateway = MockTradeGateway(market_gateway=market_gateway, initial_capital=initial_capital)
    
    # 3. 初始化策略与应用
    print("Initializing strategy and app service...")
    strategy = DualMaStrategy()
    evaluator = PerformanceEvaluator()
    
    app = BacktestAppService(
        market_gateway=market_gateway,
        trade_gateway=trade_gateway,
        strategy=strategy,
        evaluator=evaluator,
        history_fetcher=fetcher
    )
    
    # 4. 自动拉取/读取指定周期数据
    print("\n[Step 1] Preparing Data...")
    try:
        app.prepare_data(symbols, tf, start_date, end_date)
        print("Data preparation completed.")
    except Exception as e:
        print(f"Error preparing data: {e}")
        print("Please ensure 'xtquant' is installed or data is cached in 'data/' directory.")
        return

    # 5. 执行回测循环
    print("\n[Step 2] Running Backtest...")
    # 转换日期字符串为 datetime 对象用于 run_backtest
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")
    
    reports = app.run_backtest(symbols, start_date=dt_start, end_date=dt_end, base_timeframe=tf, plot=plot)
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
            print(f"[{trade.execute_at.strftime('%Y-%m-%d')}] {trade.direction.value} {trade.volume} @ {trade.price:.2f} (PnL: {trade.realized_pnl:.2f})")
    else:
        print("No trades executed.")
    print("="*40)

if __name__ == "__main__":
    main()
