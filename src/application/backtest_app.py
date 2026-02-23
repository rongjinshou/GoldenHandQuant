from datetime import datetime, timedelta
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
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
from src.infrastructure.mock.mock_trade import MockTradeGateway  # 需要访问 mock 特有的属性

class BacktestAppService:
    """回测应用服务。"""

    def __init__(
        self,
        market_gateway: IMarketGateway,
        trade_gateway: MockTradeGateway,  # 使用具体类型以便访问 mock 方法
        strategy: BaseStrategy,
        evaluator: PerformanceEvaluator,
    ) -> None:
        self.market_gateway = market_gateway
        self.trade_gateway = trade_gateway
        self.strategy = strategy
        self.evaluator = evaluator
        self.snapshots: list[DailySnapshot] = []

    def run_backtest(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestReport:
        """执行回测。

        Args:
            symbols: 回测标的列表。
            start_date: 开始日期。
            end_date: 结束日期。

        Returns:
            BacktestReport: 回测报告。
        """
        current_date = start_date
        initial_capital = self.trade_gateway.get_asset().total_asset

        while current_date <= end_date:
            # 1. 推进时间
            # 假设每日回测，时间设为当日收盘 15:00
            market_time = current_date.replace(hour=15, minute=0, second=0)
            self.market_gateway.set_current_time(market_time)
            
            # 2. 日终结算 (T+1 可用持仓更新)
            # 在每日交易前还是后调用？通常是盘后结算，次日生效。
            # 这里简化：每日开始前先结算昨日持仓
            self.trade_gateway.daily_settlement()

            # 3. 获取行情数据
            market_data: dict[str, list[Bar]] = {}
            current_prices: dict[str, float] = {}
            
            for symbol in symbols:
                bars = self.market_gateway.get_recent_bars(symbol, "1d", 100)
                if bars:
                    market_data[symbol] = bars
                    current_prices[symbol] = bars[-1].close

            # 4. 获取当前持仓
            current_positions = self.trade_gateway.get_positions()

            # 5. 生成策略信号
            signals = self.strategy.generate_signals(market_data, current_positions)

            # 6. 执行信号 (模拟撮合)
            for signal in signals:
                price = current_prices.get(signal.symbol)
                if not price:
                    continue

                # 创建订单
                # 假设 SignalDirection.value 与 OrderDirection.value 兼容 ("BUY"/"SELL")
                direction = OrderDirection(signal.direction.value)
                
                # 检查: 买入必须 100 整数倍 (规则 4.1)
                volume = signal.target_volume
                if direction == OrderDirection.BUY:
                    volume = (volume // 100) * 100
                    if volume < 100:
                        continue
                
                order = Order(
                    order_id=f"ORD_{market_time.strftime('%Y%m%d%H%M%S')}_{signal.symbol}",
                    account_id=self.trade_gateway.asset.account_id,
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
                except Exception as e:
                    # 简单记录日志，不中断回测
                    print(f"[{market_time}] Order failed for {signal.symbol}: {e}")

            # 7. 收盘清算: 撤销未成交订单 (规则 4.4)
            self.trade_gateway.cancel_all_open_orders()

            # 8. 记录每日快照
            self._record_snapshot(market_time, current_prices)

            # 推进到下一天
            current_date += timedelta(days=1)
            
        # 8. 生成报告
        return self.evaluator.evaluate(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            snapshots=self.snapshots,
            trades=self.trade_gateway.trade_records
        )

    def _record_snapshot(self, date: datetime, current_prices: dict[str, float]) -> None:
        """记录每日资产快照。"""
        asset = self.trade_gateway.get_asset()
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
