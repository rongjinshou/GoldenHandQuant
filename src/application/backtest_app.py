import asyncio
from datetime import datetime

from src.application.strategy_runner import (
    CrossSectionalStrategyRunner,
    DayContext,
    SingleStrategyRunner,
    StrategyRunner,
)
from src.domain.account.exceptions import InsufficientFundsError, PositionNotAvailableError
from src.domain.account.services.settlement_service import DailySettlementService
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.interfaces.gateways.backtest_broker import IBacktestBroker
from src.domain.backtest.interfaces.gateways.backtest_market_gateway import IBacktestMarketGateway
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.market.value_objects.suspension import StockStatusRegistry
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.portfolio.entities.order_target import OrderTarget
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError, TradeError
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.trade.value_objects.order_type import OrderType


class BacktestAppService:
    """回测应用服务。"""

    # 策略行情回溯窗口: DualMa 需要 ~10 根 Bar 计算 MA10 + 1 根当前 Bar + 容余
    LOOKBACK_WINDOW = 101

    def __init__(
        self,
        market_gateway: IBacktestMarketGateway,
        trade_gateway: IBacktestBroker,
        strategy: BaseStrategy,
        evaluator: PerformanceEvaluator,
        history_fetcher: IHistoryDataFetcher | None = None,
        sizer: IPositionSizer | None = None,
        status_registry: StockStatusRegistry | None = None,
        fundamental_registry=None,
        risk_settings=None,
    ) -> None:
        self.market_gateway = market_gateway
        self.trade_gateway = trade_gateway
        self.strategy = strategy
        self.evaluator = evaluator
        self.history_fetcher = history_fetcher
        self.sizer = sizer or FixedRatioSizer(ratio=0.2)
        self.status_registry = status_registry
        self.fundamental_registry = fundamental_registry
        self.risk_settings = risk_settings
        self.snapshots: list[DailySnapshot] = []
        self.settlement_service = DailySettlementService()

    def prepare_data(
        self,
        symbols: list[str],
        timeframe: Timeframe,
        start_date: str,
        end_date: str
    ) -> None:
        """准备回测数据。

        通过历史数据获取器拉取数据，并加载到行情网关中。
        """
        if not self.history_fetcher:
            raise ValueError("History fetcher not configured.")

        for symbol in symbols:
            # 1. 拉取数据
            bars = self.history_fetcher.fetch_history_bars(symbol, timeframe, start_date, end_date)

            # 2. 加载到行情网关
            self.market_gateway.load_bars(bars)

    def run_backtest(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        base_timeframe: Timeframe = Timeframe.DAY_1,
        plot: bool = False,
        strategies: list[BaseStrategy] | None = None,
        use_event_bus: bool = False,
    ) -> list[BacktestReport]:
        """执行回测，支持多策略并行评估。

        Args:
            symbols: 回测标的列表。
            start_date: 开始日期。
            end_date: 结束日期。
            base_timeframe: 回测基准周期。
            plot: 是否绘制回测结果图表（多策略时仅绘制最后一个）。
            strategies: 策略列表，None 时使用构造时注入的默认策略。
            use_event_bus: 是否使用事件总线驱动回测循环（异步 pub/sub 模式）。

        Returns:
            list[BacktestReport]: 每个策略对应一份回测报告。
        """
        if use_event_bus:
            return asyncio.run(self._run_with_event_bus(
                symbols, start_date, end_date, base_timeframe,
                strategies, plot,
            ))

        if strategies is None:
            strategies = [self.strategy]

        initial_asset = self.trade_gateway.get_asset()
        if initial_asset is None:
            raise ValueError("Asset not available from trade gateway.")
        initial_capital = initial_asset.total_asset

        reports: list[BacktestReport] = []
        for i, strategy in enumerate(strategies):
            sub_account_id = f"BT_{strategy.name}_{start_date.strftime('%Y%m%d')}"
            self.trade_gateway.create_sub_account(sub_account_id, initial_capital)
            is_last = (i == len(strategies) - 1)

            report = self._run_unified_loop(
                symbols, start_date, end_date, base_timeframe,
                strategy, sub_account_id, initial_capital,
                plot=(plot and is_last),
            )
            reports.append(report)

        return reports

    def _build_runner(self, strategy: BaseStrategy) -> StrategyRunner:
        if isinstance(strategy, CrossSectionalStrategy):
            if self.fundamental_registry is None:
                raise ValueError("CrossSectionalStrategy requires fundamental_registry.")
            return CrossSectionalStrategyRunner(
                strategy=strategy,
                sizer=self.sizer,
                market_gateway=self.market_gateway,
                trade_gateway=self.trade_gateway,
                fundamental_registry=self.fundamental_registry,
                risk_settings=self.risk_settings
            )
        else:
            return SingleStrategyRunner(
                strategy=strategy,
                sizer=self.sizer,
                market_gateway=self.market_gateway,
                trade_gateway=self.trade_gateway,
                status_registry=self.status_registry
            )

    def _execute_targets(self, targets: list[OrderTarget], current_time: datetime, account_id: str) -> None:
        for target in targets:
            order = Order(
                order_id=f"ORD_{current_time.strftime('%Y%m%d%H%M%S')}_{target.symbol}",
                account_id=account_id,
                ticker=target.symbol,
                direction=target.direction,
                price=target.price,
                volume=target.volume,
                type=OrderType.LIMIT,
                status=OrderStatus.CREATED,
                created_at=current_time,
            )
            try:
                self.trade_gateway.place_order(order)
            except OrderSubmitError as e:
                print(f"[{current_time}] Order rejected for {target.symbol}: {e}")
            except (InsufficientFundsError, PositionNotAvailableError) as e:
                print(f"[{current_time}] Cannot execute for {target.symbol}: {e}")
            except TradeError as e:
                print(f"[{current_time}] Trade error for {target.symbol}: {e}")

    def _settle_and_snapshot(self, current_time: datetime, current_prices: dict[str, float]) -> None:
        all_orders = self.trade_gateway.list_orders()
        all_positions = self.trade_gateway.get_positions()
        asset = self.trade_gateway.get_asset()
        if asset is None:
            raise ValueError("Asset not available from trade gateway.")

        self.settlement_service.process_daily_settlement(all_orders, all_positions, asset)
        self._record_snapshot(current_time, current_prices)

    def _run_unified_loop(
        self, symbols: list[str], start_date: datetime, end_date: datetime, base_timeframe: Timeframe,
        strategy: BaseStrategy, account_id: str, initial_capital: float, plot: bool = False,
    ) -> BacktestReport:
        """执行统一的回测循环。"""
        from src.infrastructure.logging.backtest_logger import BacktestProgress

        self.trade_gateway.activate_account(account_id)
        self.snapshots: list[DailySnapshot] = []

        all_timestamps = self.market_gateway.get_all_timestamps(base_timeframe)
        valid_timestamps = [ts for ts in all_timestamps if start_date <= ts <= end_date]

        if not valid_timestamps:
            print("Warning: No valid timestamps found for backtest range.")
            return self.evaluator.evaluate(
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital, snapshots=[], trades=[],
            )

        progress = BacktestProgress(len(valid_timestamps))
        runner = self._build_runner(strategy)

        for current_time in valid_timestamps:
            progress.update(current_time)
            self.market_gateway.set_current_time(current_time)

            context = DayContext(
                current_time=current_time,
                symbols=symbols,
                base_timeframe=base_timeframe
            )

            targets, close_prices = runner.evaluate(context)

            self._execute_targets(targets, current_time, account_id)
            self._settle_and_snapshot(current_time, close_prices)

        report = self.evaluator.evaluate(
            start_date=start_date, end_date=end_date,
            initial_capital=initial_capital,
            snapshots=self.snapshots,
            trades=self.trade_gateway.list_trade_records(),
        )

        if plot:
            try:
                from src.infrastructure.visualization.plotter import BacktestPlotter
                BacktestPlotter().plot(report)
            except Exception as e:
                print(f"Error plotting: {e}")

        return report

    async def _run_with_event_bus(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        base_timeframe: Timeframe,
        strategies: list[BaseStrategy] | None,
        plot: bool,
    ) -> list[BacktestReport]:
        """使用 EventBus 异步驱动回测循环。"""
        from src.infrastructure.event_bus import DailySettlementEvent, EventBus, MarketTickEvent
        from src.infrastructure.logging.backtest_logger import BacktestProgress

        if strategies is None:
            strategies = [self.strategy]

        initial_asset = self.trade_gateway.get_asset()
        if initial_asset is None:
            raise ValueError("Asset not available from trade gateway.")
        initial_capital = initial_asset.total_asset

        reports: list[BacktestReport] = []
        for i, strategy in enumerate(strategies):
            sub_account_id = f"BT_{strategy.name}_{start_date.strftime('%Y%m%d')}"
            self.trade_gateway.create_sub_account(sub_account_id, initial_capital)
            self.trade_gateway.activate_account(sub_account_id)
            self.snapshots: list[DailySnapshot] = []

            all_timestamps = self.market_gateway.get_all_timestamps(base_timeframe)
            valid_timestamps = [ts for ts in all_timestamps if start_date <= ts <= end_date]

            if not valid_timestamps:
                reports.append(self.evaluator.evaluate(
                    start_date=start_date, end_date=end_date,
                    initial_capital=initial_capital, snapshots=[], trades=[],
                ))
                continue

            bus = EventBus()
            progress = BacktestProgress(len(valid_timestamps))
            runner = self._build_runner(strategy)

            for current_time in valid_timestamps:
                progress.update(current_time)
                self.market_gateway.set_current_time(current_time)

                context = DayContext(
                    current_time=current_time,
                    symbols=symbols,
                    base_timeframe=base_timeframe
                )

                bars_for_event = {}
                for sym in symbols:
                    recent = self.market_gateway.get_recent_bars(sym, base_timeframe, 1)
                    if recent:
                        bars_for_event[sym] = recent[-1]

                await bus.publish(MarketTickEvent(
                    timestamp=current_time,
                    bars=bars_for_event,
                ))

                targets, close_prices = runner.evaluate(context)
                self._execute_targets(targets, current_time, sub_account_id)
                self._settle_and_snapshot(current_time, close_prices)

                await bus.publish(DailySettlementEvent(
                    timestamp=current_time,
                    date=current_time,
                ))

            is_last = (i == len(strategies) - 1)
            report = self.evaluator.evaluate(
                start_date=start_date, end_date=end_date,
                initial_capital=initial_capital,
                snapshots=self.snapshots,
                trades=self.trade_gateway.list_trade_records(),
            )

            if plot and is_last:
                try:
                    from src.infrastructure.visualization.plotter import BacktestPlotter
                    BacktestPlotter().plot(report)
                except Exception as e:
                    print(f"Error plotting: {e}")
            reports.append(report)

        return reports

    def _record_snapshot(self, date: datetime, current_prices: dict[str, float]) -> None:
        """记录每日资产快照。"""
        asset = self.trade_gateway.get_asset()
        if asset is None:
            raise ValueError("Asset not available from trade gateway.")
        positions = self.trade_gateway.get_positions()

        market_value = 0.0
        for pos in positions:
            # 如果当日无行情，尝试用最后一次已知价格，或成本价估算
            price = current_prices.get(pos.ticker, pos.average_cost)
            market_value += pos.total_volume * price

        total_asset = asset.available_cash + asset.frozen_cash + market_value

        asset.update_total_asset(total_asset)

        last_snapshot = self.snapshots[-1] if self.snapshots else None
        last_total = last_snapshot.total_asset if last_snapshot else total_asset # 第一天若无变动则 PnL 为 0

        # 修正: 第一天 PnL = total_asset - initial_capital (但 initial_capital 不在参数里，用 last_total)
        # 如果是第一天，last_total = total_asset，pnl = 0。合理。
        pnl = total_asset - last_total
        return_rate = pnl / last_total if last_total > 0 else 0.0

        snapshot = DailySnapshot(
            date=date,
            total_asset=total_asset,
            available_cash=asset.available_cash,
            market_value=market_value,
            pnl=pnl,
            return_rate=return_rate
        )
        self.snapshots.append(snapshot)
