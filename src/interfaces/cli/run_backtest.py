import math
from datetime import datetime, timedelta
from src.domain.market.value_objects.bar import Bar
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.application.backtest_app import BacktestAppService
from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy

def generate_mock_data(symbol: str, start_date: datetime, days: int) -> list[Bar]:
    """生成模拟 K 线数据 (正弦波形态以便触发均线交叉)。"""
    bars = []
    base_price = 100.0
    
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        
        # 跳过周末
        if current_date.weekday() >= 5:
            continue
            
        # 构造正弦波趋势 + 随机扰动
        # 周期约 20 天
        trend = 10 * math.sin(i / 10.0)
        noise = (i % 3 - 1) * 0.5  # -0.5, 0, 0.5
        
        close_price = base_price + trend + noise
        open_price = close_price - noise
        high_price = max(open_price, close_price) + 0.5
        low_price = min(open_price, close_price) - 0.5
        
        bar = Bar(
            symbol=symbol,
            timestamp=current_date,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=10000 + i * 100
        )
        bars.append(bar)
        
    return bars

def main():
    print("=== Starting Backtest Simulation ===")
    
    # 1. 准备数据
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 6, 1)
    symbol = "600000.SH"
    
    print(f"Generating mock data for {symbol}...")
    # 生成足够长的数据以覆盖回测区间 + 预热期
    mock_bars = generate_mock_data(symbol, start_date - timedelta(days=60), 200)
    
    # 2. 初始化基础设施
    market_gateway = MockMarketGateway(initial_data={symbol: mock_bars})
    trade_gateway = MockTradeGateway(market_gateway=market_gateway, initial_capital=1_000_000.0)
    
    # 3. 初始化策略与评估器
    strategy = DualMaStrategy()
    evaluator = PerformanceEvaluator()
    
    # 4. 初始化应用服务
    app = BacktestAppService(
        market_gateway=market_gateway,
        trade_gateway=trade_gateway,
        strategy=strategy,
        evaluator=evaluator
    )
    
    # 5. 运行回测
    print(f"Running backtest from {start_date.date()} to {end_date.date()}...")
    report = app.run_backtest([symbol], start_date, end_date)
    
    # 6. 输出报告
    print("\n=== Backtest Report ===")
    print(f"Initial Capital:   {report.initial_capital:,.2f}")
    print(f"Final Capital:     {report.final_capital:,.2f}")
    print(f"Total Return:      {report.total_return * 100:.2f}%")
    print(f"Annualized Return: {report.annualized_return * 100:.2f}%")
    print(f"Max Drawdown:      {report.max_drawdown * 100:.2f}%")
    print(f"Win Rate:          {report.win_rate * 100:.2f}%")
    print(f"Total Trades:      {report.trade_count}")
    
    print("\n--- Trade History (First 10) ---")
    for trade in report.trades[:10]:
        pnl_str = f", PnL: {trade.realized_pnl:.2f}" if trade.realized_pnl != 0 else ""
        print(f"[{trade.execute_at.strftime('%Y-%m-%d')}] {trade.direction.name} {trade.symbol} "
              f"@ {trade.price:.2f} x {trade.volume}{pnl_str}")

if __name__ == "__main__":
    main()
