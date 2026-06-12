"""SingleStrategyRunner — 资金买不起一手时的显式留痕（高价股+小资金零成交可诊断）。"""
from datetime import datetime
from unittest.mock import MagicMock

from src.application.strategy_runner import SingleStrategyRunner
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.value_objects.signal_direction import SignalDirection


def _make_runner():
    strategy = MagicMock()
    sizer = MagicMock()
    market = MagicMock()
    trade = MagicMock()
    runner = SingleStrategyRunner(
        strategy=strategy, sizer=sizer,
        market_gateway=market, trade_gateway=trade,
    )
    return runner, strategy, sizer, market, trade


def _wire_one_buy_signal(strategy, market, trade, *, open_price: float,
                         available_cash: float):
    bar_t1 = Bar(symbol="001309.SZ", timeframe=Timeframe.DAY_1,
                 timestamp=datetime(2026, 6, 10),
                 open=open_price, high=open_price, low=open_price,
                 close=open_price, volume=10000)
    bar_t = Bar(symbol="001309.SZ", timeframe=Timeframe.DAY_1,
                timestamp=datetime(2026, 6, 11),
                open=open_price, high=open_price, low=open_price,
                close=open_price, volume=10000)
    market.get_recent_bars.return_value = [bar_t1, bar_t]

    signal = MagicMock()
    signal.symbol = "001309.SZ"
    signal.direction = SignalDirection.BUY
    signal.strategy_name = "test"
    strategy.generate_signals.return_value = [signal]

    trade.get_positions.return_value = []
    trade.get_asset.return_value = MagicMock(
        total_asset=available_cash, available_cash=available_cash)

    context = MagicMock()
    context.symbols = ["001309.SZ"]
    context.current_time = datetime(2026, 6, 11)
    return context


class TestUnaffordableLot:
    def test_buy_signal_smaller_than_one_lot_is_counted(self):
        """632 元股 + 3 万资金: 一手 6.3 万买不起 → 计数器+1, 示例含标的与金额。"""
        runner, strategy, sizer, market, trade = _make_runner()
        context = _wire_one_buy_signal(strategy, market, trade,
                                       open_price=632.0, available_cash=30_000)
        sizer.calculate_target.return_value = 0  # 47 股 → 取整手 → 0

        targets, _ = runner.evaluate(context)

        assert targets == []
        assert runner.unaffordable_buys == 1
        assert "001309.SZ" in runner.unaffordable_example

    def test_zero_volume_with_enough_cash_not_counted(self):
        """偏离阈值内归零（资金充足）不是"买不起", 不应误报。"""
        runner, strategy, sizer, market, trade = _make_runner()
        context = _wire_one_buy_signal(strategy, market, trade,
                                       open_price=10.0, available_cash=1_000_000)
        sizer.calculate_target.return_value = 0

        runner.evaluate(context)

        assert runner.unaffordable_buys == 0

    def test_affordable_buy_not_counted(self):
        runner, strategy, sizer, market, trade = _make_runner()
        context = _wire_one_buy_signal(strategy, market, trade,
                                       open_price=10.0, available_cash=100_000)
        sizer.calculate_target.return_value = 100

        targets, _ = runner.evaluate(context)

        assert len(targets) == 1
        assert runner.unaffordable_buys == 0
