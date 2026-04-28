import asyncio
from datetime import datetime, timedelta
from src.domain.market.interfaces.gateways.history_fetcher import IHistoryDataFetcher
from src.domain.backtest.interfaces.gateways.backtest_broker import IBacktestBroker
from src.domain.backtest.interfaces.gateways.backtest_market_gateway import IBacktestMarketGateway
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.backtest.services.performance_evaluator import PerformanceEvaluator
from src.domain.backtest.entities.backtest_report import BacktestReport
from src.domain.backtest.value_objects.daily_snapshot import DailySnapshot
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.account.services.settlement_service import DailySettlementService
from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
from src.domain.portfolio.interfaces.position_sizer import IPositionSizer
from src.domain.market.value_objects.suspension import StockStatusRegistry
from src.domain.trade.exceptions import TradeError, OrderSubmitError
from src.domain.account.exceptions import InsufficientFundsError, PositionNotAvailableError

class BacktestAppService:
    """回测应用服务。"""

    def __init__(
        self,
        market_gateway: IBacktestMarketGateway,
        trade_gateway: IBacktestBroker,
        strategy: BaseStrategy,
        evaluator: PerformanceEvaluator,
        history_fetcher: IHistoryDataFetcher | None = None,
        sizer: IPositionSizer | None = None,
        status_registry: StockStatusRegistry | None = None,
    ) -> None:
        self.market_gateway = market_gateway
        self.trade_gateway = trade_gateway
        self.strategy = strategy
        self.evaluator = evaluator
        self.history_fetcher = history_fetcher
        self.sizer = sizer or FixedRatioSizer(ratio=0.2)
        self.status_registry = status_registry
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
            report = self._run_single_strategy(
                symbols, start_date, end_date, base_timeframe,
                strategy, sub_account_id, initial_capital,
                plot=(plot and is_last),
            )
            reports.append(report)

        return reports

    def _run_single_strategy(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        base_timeframe: Timeframe,
        strategy: BaseStrategy,
        account_id: str,
        initial_capital: float,
        plot: bool = False,
    ) -> BacktestReport:
        """执行单个策略的回测循环。"""
        self.trade_gateway.activate_account(account_id)
        self.snapshots: list[DailySnapshot] = []

        # 1. 获取所有时间戳
        all_timestamps = self.market_gateway.get_all_timestamps(base_timeframe)
        valid_timestamps = [
            ts for ts in all_timestamps
            if start_date <= ts <= end_date
        ]

        from src.infrastructure.logging.backtest_logger import BacktestProgress, logger
        progress = BacktestProgress(len(valid_timestamps))

        if not valid_timestamps:
            print("Warning: No valid timestamps found for backtest range.")
            return self.evaluator.evaluate(
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                snapshots=[],
                trades=[]
            )

        for current_time in valid_timestamps:
            progress.update(current_time)
            market_time = current_time
            self.market_gateway.set_current_time(market_time)

            strategy_market_data: dict[str, list[Bar]] = {}
            execution_prices: dict[str, float] = {}
            current_prices: dict[str, float] = {}

            for symbol in symbols:
                all_bars = self.market_gateway.get_recent_bars(symbol, base_timeframe, 101)
                if not all_bars:
                    continue
                if len(all_bars) >= 2:
                    strategy_market_data[symbol] = all_bars[:-1]
                current_bar = all_bars[-1]
                execution_prices[symbol] = current_bar.open
                current_prices[symbol] = current_bar.close

            current_positions = self.trade_gateway.get_positions()
            signals = strategy.generate_signals(strategy_market_data, current_positions)

            position_map = {p.ticker: p for p in current_positions}

            for signal in signals:
                if self.status_registry and not self.status_registry.is_tradable(signal.symbol, market_time):
                    continue
                price = execution_prices.get(signal.symbol)
                if not price or price <= 0:
                    continue
                asset = self.trade_gateway.get_asset()
                if asset is None:
                    raise ValueError("Asset not available from trade gateway.")

                position = position_map.get(signal.symbol)
                volume = self.sizer.calculate_target(
                    signal, price, asset, position
                )

                if volume <= 0:
                    continue

                direction = OrderDirection(signal.direction.value)

                order = Order(
                    order_id=f"ORD_{market_time.strftime('%Y%m%d%H%M%S')}_{signal.symbol}",
                    account_id=asset.account_id,
                    ticker=signal.symbol,
                    direction=direction,
                    price=price,
                    volume=volume,
                    type=OrderType.LIMIT,
                    status=OrderStatus.CREATED,
                    created_at=market_time,
                )

                try:
                    self.trade_gateway.place_order(order)
                except OrderSubmitError as e:
                    print(f"[{market_time}] Order rejected for {signal.symbol}: {e}")
                except (InsufficientFundsError, PositionNotAvailableError) as e:
                    print(f"[{market_time}] Cannot execute for {signal.symbol}: {e}")
                except TradeError as e:
                    print(f"[{market_time}] Trade error for {signal.symbol}: {e}")

            all_orders = self.trade_gateway.list_orders()
            all_positions = self.trade_gateway.get_positions()
            asset = self.trade_gateway.get_asset()
            if asset is None:
                raise ValueError("Asset not available from trade gateway.")

            self.settlement_service.process_daily_settlement(all_orders, all_positions, asset)
            self._record_snapshot(market_time, current_prices)

        report = self.evaluator.evaluate(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            snapshots=self.snapshots,
            trades=self.trade_gateway.list_trade_records()
        )

        if plot:
            try:
                from src.infrastructure.visualization.plotter import BacktestPlotter
                plotter = BacktestPlotter()
                plotter.plot(report)
            except ImportError:
                print("Warning: Visualization module not found or matplotlib not installed.")
            except Exception as e:
                print(f"Error plotting backtest results: {e}")

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
        """使用 EventBus 异步驱动回测循环。

        保留原有同步循环作为 fallback，通过 use_event_bus=True 参数切换。
        """
        from src.infrastructure.event_bus import EventBus, MarketTickEvent, DailySettlementEvent

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
            valid_timestamps = [
                ts for ts in all_timestamps
                if start_date <= ts <= end_date
            ]

            if not valid_timestamps:
                reports.append(self.evaluator.evaluate(
                    start_date=start_date, end_date=end_date,
                    initial_capital=initial_capital, snapshots=[], trades=[],
                ))
                continue

            bus = EventBus()

            # 在 EventBus 驱动的循环中，按原同步逻辑逐步执行
            # 事件总线主要用于解耦各步骤，为后续完全异步迁移铺路
            from src.infrastructure.logging.backtest_logger import BacktestProgress
            progress = BacktestProgress(len(valid_timestamps))

            for current_time in valid_timestamps:
                progress.update(current_time)
                market_time = current_time
                self.market_gateway.set_current_time(market_time)

                strategy_market_data: dict[str, list[Bar]] = {}
                current_prices: dict[str, float] = {}
                bars_for_event: dict[str, Bar] = {}

                for symbol in symbols:
                    all_bars = self.market_gateway.get_recent_bars(symbol, base_timeframe, 101)
                    if not all_bars:
                        continue
                    if len(all_bars) >= 2:
                        strategy_market_data[symbol] = all_bars[:-1]
                    current_bar = all_bars[-1]
                    current_prices[symbol] = current_bar.close
                    bars_for_event[symbol] = current_bar

                # Publish MarketTickEvent (事件总线解耦第一步)
                await bus.publish(MarketTickEvent(
                    timestamp=market_time,
                    bars=bars_for_event,
                ))

                # 策略生成信号 + 执行 (保持同步逻辑，事件用于日志/审计)
                current_positions = self.trade_gateway.get_positions()
                signals = strategy.generate_signals(strategy_market_data, current_positions)

                execution_prices: dict[str, float] = {
                    symbol: bar.open for symbol, bar in bars_for_event.items()
                }
                position_map = {p.ticker: p for p in current_positions}

                for signal in signals:
                    if self.status_registry and not self.status_registry.is_tradable(signal.symbol, market_time):
                        continue
                    price = execution_prices.get(signal.symbol)
                    if not price or price <= 0:
                        continue
                    asset = self.trade_gateway.get_asset()
                    if asset is None:
                        raise ValueError("Asset not available from trade gateway.")

                    position = position_map.get(signal.symbol)
                    volume = self.sizer.calculate_target(signal, price, asset, position)
                    if volume <= 0:
                        continue

                    direction = OrderDirection(signal.direction.value)
                    order = Order(
                        order_id=f"ORD_{market_time.strftime('%Y%m%d%H%M%S')}_{signal.symbol}",
                        account_id=asset.account_id,
                        ticker=signal.symbol,
                        direction=direction,
                        price=price,
                        volume=volume,
                        type=OrderType.LIMIT,
                        status=OrderStatus.CREATED,
                        created_at=market_time,
                    )
                    try:
                        self.trade_gateway.place_order(order)
                    except OrderSubmitError as e:
                        print(f"[{market_time}] Order rejected for {signal.symbol}: {e}")
                    except (InsufficientFundsError, PositionNotAvailableError) as e:
                        print(f"[{market_time}] Cannot execute for {signal.symbol}: {e}")
                    except TradeError as e:
                        print(f"[{market_time}] Trade error for {signal.symbol}: {e}")

                # 日终结算
                all_orders = self.trade_gateway.list_orders()
                all_positions = self.trade_gateway.get_positions()
                asset = self.trade_gateway.get_asset()
                if asset is None:
                    raise ValueError("Asset not available from trade gateway.")
                self.settlement_service.process_daily_settlement(all_orders, all_positions, asset)
                self._record_snapshot(market_time, current_prices)

                # Publish DailySettlementEvent
                await bus.publish(DailySettlementEvent(
                    timestamp=market_time,
                    date=market_time,
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
                except ImportError:
                    print("Warning: Visualization module not found or matplotlib not installed.")
                except Exception as e:
                    print(f"Error plotting backtest results: {e}")
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
        
        # 更新 Asset 对象的 total_asset 以保持一致性
        asset.total_asset = total_asset

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
