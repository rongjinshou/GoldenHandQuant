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
    ) -> BacktestReport:
        """执行回测。

        Args:
            symbols: 回测标的列表。
            start_date: 开始日期。
            end_date: 结束日期。
            base_timeframe: 回测基准周期。
            plot: 是否绘制回测结果图表。

        Returns:
            BacktestReport: 回测报告。
        """
        initial_asset = self.trade_gateway.get_asset()
        if initial_asset is None:
            raise ValueError("Asset not available from trade gateway.")
        initial_capital = initial_asset.total_asset

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
            # 1. 推进时间
            market_time = current_time
            self.market_gateway.set_current_time(market_time)
            
            # 2. 获取行情数据
            # 关键修复: 分离策略可见数据(T-1以前) 与 当前执行价格(T日)
            # 设计决策: 执行价格使用 T 日 open 价
            #   - 当前方案: T 日 open 价 → 等价于"T日开盘交易"（适用于日内策略）
            #   - 更严格方案: T+1 日 open 价 → 等价于"T日收盘分析，次日开盘交易"（适用于日线策略）
            #   - 当前实现采用 T 日 open 方案
            strategy_market_data: dict[str, list[Bar]] = {}
            execution_prices: dict[str, float] = {}
            current_prices: dict[str, float] = {}

            for symbol in symbols:
                all_bars = self.market_gateway.get_recent_bars(symbol, base_timeframe, 101)
                if not all_bars:
                    continue
                # 策略只能看到 T-1 及以前的数据 (排除最后一根 T 日 Bar)
                if len(all_bars) >= 2:
                    strategy_market_data[symbol] = all_bars[:-1]
                # 执行价格: 使用 T 日开盘价; 市值估算: 使用收盘价
                current_bar = all_bars[-1]
                execution_prices[symbol] = current_bar.open
                current_prices[symbol] = current_bar.close

            # 3. 获取当前持仓
            current_positions = self.trade_gateway.get_positions()

            # 4. 生成策略信号 (基于 T-1 数据)
            signals = self.strategy.generate_signals(strategy_market_data, current_positions)

            # 5. 执行信号 (使用 T 日开盘价撮合)
            position_map = {p.ticker: p for p in current_positions}

            for signal in signals:
                # 停牌/*ST 过滤
                if self.status_registry and not self.status_registry.is_tradable(signal.symbol, market_time):
                    continue
                price = execution_prices.get(signal.symbol)
                if not price or price <= 0:
                    continue
                asset = self.trade_gateway.get_asset()
                if asset is None:
                    raise ValueError("Asset not available from trade gateway.")

                # 计算目标数量
                position = position_map.get(signal.symbol)
                volume = self.sizer.calculate_target(
                    signal, price, asset, position
                )

                if volume <= 0:
                    continue

                # 创建订单
                # 假设 SignalDirection.value 与 OrderDirection.value 兼容 ("BUY"/"SELL")
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
                    created_at=market_time  # 使用回测时间
                )
                
                try:
                    self.trade_gateway.place_order(order)
                except OrderSubmitError as e:
                    print(f"[{market_time}] Order rejected for {signal.symbol}: {e}")
                except (InsufficientFundsError, PositionNotAvailableError) as e:
                    print(f"[{market_time}] Cannot execute for {signal.symbol}: {e}")
                except TradeError as e:
                    print(f"[{market_time}] Trade error for {signal.symbol}: {e}")

            # 6. 日终结算 (收盘清算 + T+1)
            # 获取最新的 orders (包括刚刚生成的)
            all_orders = self.trade_gateway.list_orders()
            all_positions = self.trade_gateway.get_positions()
            asset = self.trade_gateway.get_asset()
            if asset is None:
                raise ValueError("Asset not available from trade gateway.")
            
            self.settlement_service.process_daily_settlement(all_orders, all_positions, asset)

            # 7. 记录每日快照 (结算后记录，反映真实的净值)
            self._record_snapshot(market_time, current_prices)

        # 8. 生成报告
        report = self.evaluator.evaluate(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            snapshots=self.snapshots,
            trades=self.trade_gateway.list_trade_records()
        )

        if plot:
            try:
                # 动态导入以避免在应用层引入硬依赖
                from src.infrastructure.visualization.plotter import BacktestPlotter
                plotter = BacktestPlotter()
                plotter.plot(report)
            except ImportError:
                print("Warning: Visualization module not found or matplotlib not installed.")
            except Exception as e:
                print(f"Error plotting backtest results: {e}")

        return report

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
