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
from src.infrastructure.gateway.qmt_history_data import QmtHistoryDataFetcher
from src.application.backtest_app import BacktestAppService
from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.timeframe import Timeframe

def main():
    print("=== Starting Backtest Simulation (with QMT History Data) ===")
    
    # 1. 定义回测参数
    symbols = ["000001.SZ"]  # 使用平安银行作为示例
    tf = Timeframe.DAY_1     # 设定回测周期
    start_date = "2023-01-01" # 稍微往前一点，保证有足够数据
    end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"Target: {symbols}")
    print(f"Timeframe: {tf.value}")
    print(f"Range: {start_date} to {end_date}")

    # 2. 初始化基础设施
    print("\nInitializing infrastructure...")
    fetcher = QmtHistoryDataFetcher()
    market_gateway = MockMarketGateway()
    
    # MockTradeGateway 需要 market_gateway 来查询价格 (假设构造函数如此设计)
    # 如果 MockTradeGateway 不需要 market_gateway，则只需传入 initial_capital
    # 检查之前的 run_backtest.py: trade_gateway = MockTradeGateway(market_gateway, initial_capital=1_000_000.0)
    trade_gateway = MockTradeGateway(market_gateway=market_gateway, initial_capital=1_000_000.0)
    
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
    
    report = app.run_backtest(symbols, start_date=dt_start, end_date=dt_end, base_timeframe=tf)
    
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
    print("First 5 Trades:")
    if report.trades:
        for trade in report.trades[:5]:
            print(f"[{trade.execute_at.strftime('%Y-%m-%d')}] {trade.direction.value} {trade.volume} @ {trade.price:.2f} (PnL: {trade.realized_pnl:.2f})")
        if len(report.trades) > 5:
            print("...")
    else:
        print("No trades executed.")
    print("="*40)

if __name__ == "__main__":
    main()
