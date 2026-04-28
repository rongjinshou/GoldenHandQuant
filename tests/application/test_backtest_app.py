"""BacktestAppService 回归测试 — Lookahead Bias 验证。"""
from unittest.mock import MagicMock
from datetime import datetime
from src.application.backtest_app import BacktestAppService
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe


def test_run_backtest_strategy_should_not_see_current_bar_close():
    """策略生成信号时不应看到当前 Bar 的收盘价。"""
    mock_market = MagicMock()
    mock_trade = MagicMock()
    mock_strategy = MagicMock()
    mock_evaluator = MagicMock()

    # 构造 3 根日线 Bar: T-2, T-1, T
    t1 = datetime(2024, 1, 3)
    t2 = datetime(2024, 1, 4)
    t3 = datetime(2024, 1, 5)
    bar_t1 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t1,
                 open=9.5, high=10.5, low=9.5, close=10.0, volume=10000)
    bar_t2 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t2,
                 open=10.0, high=11.0, low=10.0, close=11.0, volume=10000)
    bar_t3 = Bar(symbol="000001.SZ", timeframe=Timeframe.DAY_1, timestamp=t3,
                 open=11.0, high=20.0, low=11.0, close=20.0, volume=10000)

    # 设置 Mock 返回值
    mock_trade.get_asset.return_value = MagicMock(total_asset=100000, available_cash=100000,
                                                  frozen_cash=0, account_id="TEST")
    mock_trade.get_positions.return_value = []
    mock_trade.list_orders.return_value = []
    mock_trade.list_trade_records.return_value = []
    mock_market.get_all_timestamps.return_value = [t1, t2, t3]

    # get_recent_bars 返回全部3根bar; 应用层应只将前2根传给策略
    mock_market.get_recent_bars.return_value = [bar_t1, bar_t2, bar_t3]
    mock_strategy.generate_signals.return_value = []
    mock_evaluator.evaluate.return_value = MagicMock()

    app = BacktestAppService(
        market_gateway=mock_market,
        trade_gateway=mock_trade,
        strategy=mock_strategy,
        evaluator=mock_evaluator,
    )
    app.run_backtest(
        symbols=["000001.SZ"],
        start_date=t1,
        end_date=t3,
        base_timeframe=Timeframe.DAY_1,
    )

    # 验证: 传给策略的 bars 不包含 T3 (最后一根)
    bars_passed_to_strategy = mock_strategy.generate_signals.call_args[0][0]
    for symbol, bars in bars_passed_to_strategy.items():
        bar_timestamps = [b.timestamp for b in bars]
        assert t3 not in bar_timestamps, (
            f"Lookahead bias detected! Strategy received bar at {t3} which is the current time"
        )
