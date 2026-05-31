"""端到端集成测试：使用真实 MockTradeGateway + MockMarketGateway 测试回测流程。"""

from datetime import datetime, timedelta

from src.application.backtest_app import BacktestAppService
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway


def _generate_trending_up_bars(symbol: str, n_days: int, start_price: float) -> list[Bar]:
    """生成连续上涨的 K 线数据，用于触发 DualMa 金叉。"""
    bars = []
    base_date = datetime(2025, 1, 2)
    price = start_price
    for i in range(n_days):
        # 前 10 天平稳，之后每天涨 1%，确保 MA5 上穿 MA10
        if i >= 10:
            price *= 1.01
        bar = Bar(
            symbol=symbol,
            timeframe=Timeframe.DAY_1,
            timestamp=base_date + timedelta(days=i),
            open=price * 0.99,
            high=price * 1.02,
            low=price * 0.98,
            close=price,
            volume=1_000_000,
            unadjusted_close=price,
        )
        bars.append(bar)
    return bars


def _generate_volatile_bars(symbol: str, n_days: int, start_price: float) -> list[Bar]:
    """生成震荡 K 线数据，可能触发多次金叉/死叉。"""
    bars = []
    base_date = datetime(2025, 1, 2)
    for i in range(n_days):
        # 锯齿形价格
        if i % 4 < 2:
            price = start_price * (1 + 0.02 * (i % 4))
        else:
            price = start_price * (1 - 0.01 * (i % 4))
        bar = Bar(
            symbol=symbol,
            timeframe=Timeframe.DAY_1,
            timestamp=base_date + timedelta(days=i),
            open=price * 0.99,
            high=price * 1.02,
            low=price * 0.98,
            close=price,
            volume=1_000_000,
            unadjusted_close=price,
        )
        bars.append(bar)
    return bars


class TestBacktestIntegration:
    """端到端回测集成测试。"""

    def test_basic_backtest_runs_to_completion(self):
        """基本回测流程能跑完并生成报告。"""
        # Arrange
        symbol = "600000.SH"
        bars = _generate_trending_up_bars(symbol, n_days=30, start_price=10.0)

        market_gw = MockMarketGateway()
        market_gw.load_bars(bars)

        trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=1_000_000.0)
        strategy = DualMaStrategy()
        evaluator = PerformanceEvaluator()

        app = BacktestAppService(
            market_gateway=market_gw,
            trade_gateway=trade_gw,
            strategy=strategy,
            evaluator=evaluator,
        )

        start_date = bars[0].timestamp
        end_date = bars[-1].timestamp

        # Act
        reports = app.run_backtest(
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date,
            base_timeframe=Timeframe.DAY_1,
        )

        # Assert
        assert len(reports) == 1
        report = reports[0]
        assert report.initial_capital == 1_000_000.0
        assert report.final_capital > 0
        assert report.trade_count >= 0
        assert report.start_date == start_date
        assert report.end_date == end_date
        assert report.strategy_name == "DualMaStrategy"

    def test_backtest_generates_trades_on_trending_data(self):
        """趋势数据应产生交易。"""
        # Arrange
        symbol = "600000.SH"
        # 使用更多天数确保产生金叉信号
        bars = _generate_trending_up_bars(symbol, n_days=50, start_price=10.0)

        market_gw = MockMarketGateway()
        market_gw.load_bars(bars)

        trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=1_000_000.0)
        strategy = DualMaStrategy()
        evaluator = PerformanceEvaluator()

        app = BacktestAppService(
            market_gateway=market_gw,
            trade_gateway=trade_gw,
            strategy=strategy,
            evaluator=evaluator,
        )

        start_date = bars[0].timestamp
        end_date = bars[-1].timestamp

        # Act
        reports = app.run_backtest(
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date,
        )

        # Assert
        report = reports[0]
        # 连续上涨应触发金叉 -> 产生交易
        assert report.trade_count > 0, "Trending data should generate trades"

    def test_backtest_snapshots_recorded(self):
        """回测应记录每日快照。"""
        symbol = "600000.SH"
        bars = _generate_trending_up_bars(symbol, n_days=30, start_price=10.0)

        market_gw = MockMarketGateway()
        market_gw.load_bars(bars)

        trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=1_000_000.0)
        strategy = DualMaStrategy()
        evaluator = PerformanceEvaluator()

        app = BacktestAppService(
            market_gateway=market_gw,
            trade_gateway=trade_gw,
            strategy=strategy,
            evaluator=evaluator,
        )

        reports = app.run_backtest(
            symbols=[symbol],
            start_date=bars[0].timestamp,
            end_date=bars[-1].timestamp,
        )

        report = reports[0]
        # 应有每日快照
        assert len(report.snapshots) > 0
        # 每个快照的总资产应为正
        for snap in report.snapshots:
            assert snap.total_asset > 0

    def test_backtest_sharpe_ratio_is_finite(self):
        """夏普比率应为有限数值。"""
        symbol = "600000.SH"
        bars = _generate_trending_up_bars(symbol, n_days=50, start_price=10.0)

        market_gw = MockMarketGateway()
        market_gw.load_bars(bars)

        trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=1_000_000.0)
        strategy = DualMaStrategy()
        evaluator = PerformanceEvaluator()

        app = BacktestAppService(
            market_gateway=market_gw,
            trade_gateway=trade_gw,
            strategy=strategy,
            evaluator=evaluator,
        )

        reports = app.run_backtest(
            symbols=[symbol],
            start_date=bars[0].timestamp,
            end_date=bars[-1].timestamp,
        )

        report = reports[0]
        import math
        assert math.isfinite(report.sharpe_ratio)

    def test_backtest_with_no_data_returns_empty_report(self):
        """无数据时应返回空报告。"""
        market_gw = MockMarketGateway()
        trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=1_000_000.0)
        strategy = DualMaStrategy()
        evaluator = PerformanceEvaluator()

        app = BacktestAppService(
            market_gateway=market_gw,
            trade_gateway=trade_gw,
            strategy=strategy,
            evaluator=evaluator,
        )

        start_date = datetime(2025, 1, 1)
        end_date = datetime(2025, 12, 31)

        reports = app.run_backtest(
            symbols=["NONEXIST.SZ"],
            start_date=start_date,
            end_date=end_date,
        )

        report = reports[0]
        assert report.initial_capital == 1_000_000.0
        assert report.final_capital == 1_000_000.0
        assert report.trade_count == 0
        assert report.total_return == 0.0

    def test_backtest_with_volatile_data(self):
        """震荡数据回测应正常完成。"""
        symbol = "000001.SZ"
        bars = _generate_volatile_bars(symbol, n_days=40, start_price=10.0)

        market_gw = MockMarketGateway()
        market_gw.load_bars(bars)

        trade_gw = MockTradeGateway(market_gateway=market_gw, initial_capital=500_000.0)
        strategy = DualMaStrategy()
        evaluator = PerformanceEvaluator()

        app = BacktestAppService(
            market_gateway=market_gw,
            trade_gateway=trade_gw,
            strategy=strategy,
            evaluator=evaluator,
        )

        reports = app.run_backtest(
            symbols=[symbol],
            start_date=bars[0].timestamp,
            end_date=bars[-1].timestamp,
        )

        report = reports[0]
        assert report.initial_capital == 500_000.0
        assert report.final_capital > 0
        # 震荡数据可能有交易
        assert report.trade_count >= 0
