from logging import getLogger
from datetime import datetime
from uuid import uuid4

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.strategy.services.base_strategy import BaseStrategy
from src.domain.market.value_objects.bar import Bar
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.domain.trade.value_objects.order_status import OrderStatus
from src.domain.strategy.value_objects.signal_direction import SignalDirection

logger = getLogger(__name__)


class TradingAppService:
    """交易应用服务。
    
    负责编排领域对象与基础设施，执行核心交易流程。
    """

    def __init__(
        self,
        market_gateway: IMarketGateway,
        account_gateway: IAccountGateway,
        trade_gateway: ITradeGateway,
        strategy: BaseStrategy,
    ):
        self.market_gateway = market_gateway
        self.account_gateway = account_gateway
        self.trade_gateway = trade_gateway
        self.strategy = strategy

    def run_cycle(self, symbols: list[str]) -> None:
        """执行一次完整的交易循环。

        Args:
            symbols: 需要关注的标的列表。
        """
        logger.info(f"Starting trading cycle for {len(symbols)} symbols...")

        # a. 获取最新行情
        market_data: dict[str, list[Bar]] = {}
        for symbol in symbols:
            # 默认获取日线，100根用于计算
            bars = self.market_gateway.get_recent_bars(symbol, timeframe="1d", limit=100)
            if bars:
                market_data[symbol] = bars
            else:
                logger.warning(f"No bars found for {symbol}")

        if not market_data:
            logger.warning("No market data available, skipping cycle.")
            return

        # b. 获取账户持仓与资金
        positions = self.account_gateway.get_positions()
        asset = self.account_gateway.get_asset()
        
        if asset is None:
            logger.error("Failed to retrieve asset information, aborting cycle.")
            return

        # c. 调用策略生成信号
        signals = self.strategy.generate_signals(market_data, positions)
        logger.info(f"Generated {len(signals)} signals.")

        # d. 遍历信号并构造订单
        for signal in signals:
            # 获取当前参考价格 (使用最新 Bar 的收盘价)
            bars = market_data.get(signal.symbol)
            if not bars:
                logger.warning(f"Missing market data for signal {signal.symbol}, skipping.")
                continue
            
            current_price = bars[-1].close
            
            # 转换方向
            order_direction = (
                OrderDirection.BUY 
                if signal.direction == SignalDirection.BUY 
                else OrderDirection.SELL
            )

            # 极简应用层校验 (资金/持仓)
            if order_direction == OrderDirection.BUY:
                estimated_cost = current_price * signal.target_volume
                if asset.available_cash < estimated_cost:
                    logger.warning(
                        f"Insufficient funds for {signal.symbol}: "
                        f"Need {estimated_cost}, Have {asset.available_cash}"
                    )
                    continue
            
            # e. 构造并发送订单
            try:
                order = Order(
                    order_id=str(uuid4()),
                    account_id=asset.account_id,
                    ticker=signal.symbol,
                    direction=order_direction,
                    price=current_price,
                    volume=signal.target_volume,
                    type=OrderType.LIMIT,  # 默认限价单
                    status=OrderStatus.CREATED
                )
                
                # 提交订单
                order_id = self.trade_gateway.place_order(order)
                logger.info(f"Order submitted: {order_id} for {signal.symbol} {signal.direction} {signal.target_volume}")
                
            except Exception as e:
                logger.error(f"Failed to submit order for {signal.symbol}: {e}")
