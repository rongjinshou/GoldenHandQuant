import pytest
from datetime import datetime, timedelta
from src.application.backtest_app import BacktestAppService
from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway
from src.domain.portfolio.services.equal_weight_sizer import EqualWeightSizer
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.services.fundamental_registry import FundamentalRegistry

def _make_bar(symbol, dt, close, volume=1e6, prev_close=None):
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1, timestamp=dt,
        open=close * 0.99, high=close * 1.02, low=close * 0.98, close=close,
        volume=volume, prev_close=prev_close or close * 0.99,
    )

class TestMicroValueIntegration:
    @pytest.mark.parametrize("use_event_bus", [False, True])
    def test_basic_backtest_run_with_mock_data(self, use_event_bus):
        # Arrange: 10 stocks, 30 trading days
        symbols = [f"00000{i}.SZ" for i in range(1, 10)]
        start = datetime(2024, 6, 1)
        dates = [start + timedelta(days=i) for i in range(30)]

        market = MockMarketGateway()
        trade = MockTradeGateway(market_gateway=market, initial_capital=1_000_000)
        strategy = MicroValueStrategy(top_n=3)
        evaluator = PerformanceEvaluator()
        sizer = EqualWeightSizer(n_symbols=3)

        # Load mock bars
        for sym in symbols:
            bars = [_make_bar(sym, d, 10.0 + 0.1 * i + hash(sym) % 3) for i, d in enumerate(dates)]
            market.load_bars(bars)

        # Build FundamentalRegistry with mock data
        registry = FundamentalRegistry()
        for sym in symbols:
            for d in dates:
                registry.add(FundamentalSnapshot(
                    symbol=sym, date=d, name=f"Stock {sym}",
                    list_date=datetime(2000, 1, 1), market_cap=1e9 + hash(sym) % 10 * 1e8,
                    roe_ttm=0.10 + hash(sym) % 10 * 0.02,
                    ocf_ttm=1e8 + hash(sym) % 10 * 1e7,
                ))

        app = BacktestAppService(
            market_gateway=market, trade_gateway=trade,
            strategy=strategy, evaluator=evaluator, sizer=sizer,
        )
        app.fundamental_registry = registry

        # Act
        reports = app.run_backtest(
            symbols=symbols, start_date=dates[0], end_date=dates[-1],
            base_timeframe=Timeframe.DAY_1, plot=False, use_event_bus=use_event_bus
        )

        # Assert
        assert len(reports) == 1
        report = reports[0]
        assert report.initial_capital == 1_000_000
        assert report.trade_count >= 0
        assert report.max_drawdown >= 0.0
        assert len(report.snapshots) > 0
        print(f"Total Return: {report.total_return:.2%}")
        print(f"Sharpe: {report.sharpe_ratio:.2f}")
        print(f"Trades: {report.trade_count}")
