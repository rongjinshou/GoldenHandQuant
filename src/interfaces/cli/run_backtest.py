"""
回测运行入口脚本。

使用方式:
    python -m src.interfaces.cli.run_backtest
"""

import sys
import os
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# 确保项目根目录在 sys.path 中
sys.path.append(os.getcwd())

from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.application.backtest_app import BacktestAppService
from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.bar import Bar  # 虽然主要用 pandas 注入，但类型检查可能需要

def generate_mock_data(symbol: str, days: int = 250, start_price: float = 10.0) -> pd.DataFrame:
    """生成模拟日线数据 (随机漫步)。"""
    end_date = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days * 1.5) # 多生成一些以确保工作日足够
    
    # 生成日期序列 (仅工作日)
    dates = pd.bdate_range(start=start_date, end=end_date)[-days:]
    
    # 生成价格序列
    np.random.seed(42) # 固定种子以便复现
    returns = np.random.normal(loc=0.0005, scale=0.02, size=len(dates)) # 每日预期万5收益，2%波动
    
    prices = [start_price]
    data = []
    
    for i, date in enumerate(dates):
        prev_close = prices[-1]
        ret = returns[i]
        
        # 模拟 OHLC
        # 假设: Open = PrevClose * (1 + gap_noise)
        # Close = PrevClose * (1 + ret)
        # High = Max(Open, Close) * (1 + high_noise)
        # Low = Min(Open, Close) * (1 - low_noise)
        
        open_price = prev_close * (1 + np.random.normal(0, 0.005))
        close_price = prev_close * (1 + ret)
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, 0.01)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, 0.01)))
        
        volume = int(np.random.randint(10000, 100000) * 100) # 1万手到10万手
        
        data.append({
            "datetime": date.to_pydatetime(),
            "symbol": symbol,
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": volume
        })
        
        prices.append(close_price)
        
    return pd.DataFrame(data)

def main():
    print("=== Starting Backtest Simulation ===")
    
    # 1. 准备数据
    symbol = "600000.SH"
    print(f"Generating mock data for {symbol}...")
    df = generate_mock_data(symbol, days=250)
    print(f"Generated {len(df)} bars from {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")
    
    # 2. 初始化网关
    print("Initializing gateways...")
    market_gateway = MockMarketGateway()
    market_gateway.load_data(df)
    
    trade_gateway = MockTradeGateway(market_gateway, initial_capital=1_000_000.0)
    
    # 3. 初始化策略与应用
    print("Initializing strategy and app service...")
    strategy = DualMaStrategy()
    evaluator = PerformanceEvaluator()
    
    app_service = BacktestAppService(
        market_gateway=market_gateway,
        trade_gateway=trade_gateway,
        strategy=strategy,
        evaluator=evaluator
    )
    
    # 4. 执行回测
    print("Running backtest...")
    start_date = df['datetime'].iloc[0]
    end_date = df['datetime'].iloc[-1]
    
    report = app_service.run_backtest(
        symbols=[symbol],
        start_date=start_date,
        end_date=end_date
    )
    
    # 5. 输出报告
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
    for trade in report.trades[:5]:
        print(f"[{trade.execute_at.strftime('%Y-%m-%d')}] {trade.direction.value} {trade.volume} @ {trade.price:.2f} (PnL: {trade.realized_pnl:.2f})")
    print("..." if len(report.trades) > 5 else "")
    print("="*40)

if __name__ == "__main__":
    main()
