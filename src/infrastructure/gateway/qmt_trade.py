import logging

from src.infrastructure.libs.xtquant import xtconstant
from src.infrastructure.libs.xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from src.infrastructure.libs.xtquant.xttype import StockAccount

from src.domain.account.asset import Asset
from src.domain.account.gateways import IAccountGateway
from src.domain.account.position import Position
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.gateways import ITradeGateway
from src.domain.trade.order import Order, OrderDirection, OrderType

logger = logging.getLogger(__name__)


class QmtTradeGateway(ITradeGateway, IAccountGateway):
    """QMT 交易网关实现。"""

    def __init__(self, path: str, session_id: int, account_id: str, account_type: str = "STOCK") -> None:
        """
        Args:
            path: MiniQMT userdata_mini 路径
            session_id: 会话 ID
            account_id: 资金账号
            account_type: 账号类型，默认 'STOCK' (股票)
        """
        self.path = path
        self.session_id = session_id
        self.account_id = account_id
        self.account_type = account_type

        try:
            # 创建交易对象
            self.xt_trader = XtQuantTrader(path, session_id)

            # 创建账号对象
            self.account = StockAccount(account_id, account_type)

            # 注册回调 (即使不使用异步功能，注册回调也是个好习惯，用于接收断线等通知)
            self.callback = XtQuantTraderCallback()
            self.xt_trader.register_callback(self.callback)

            # 启动交易线程
            self.xt_trader.start()

            # 建立连接
            connect_result = self.xt_trader.connect()
            if connect_result == 0:
                logger.info(f"Connected to QMT trading gateway (session: {session_id})")
            else:
                logger.error(f"Failed to connect to QMT trading gateway: {connect_result}")

            # 订阅账号
            subscribe_result = self.xt_trader.subscribe(self.account)
            if subscribe_result == 0:
                logger.info(f"Subscribed to account {account_id}")
            else:
                logger.error(f"Failed to subscribe to account {account_id}: {subscribe_result}")

        except Exception as e:
            logger.error(f"Failed to initialize QmtTradeGateway: {e}", exc_info=True)

    def get_asset(self) -> Asset | None:
        """获取账户资金信息。"""
        try:
            xt_asset = self.xt_trader.query_stock_asset(self.account)
            if not xt_asset:
                logger.warning(f"Failed to query asset for account {self.account_id}")
                return None

            # 转换 XtAsset 到 Asset
            return Asset(
                account_id=self.account_id,
                total_asset=xt_asset.total_asset,
                available_cash=xt_asset.cash,
                frozen_cash=xt_asset.frozen_cash,
            )
        except Exception as e:
            logger.error(f"Error querying asset: {e}", exc_info=True)
            return None

    def get_positions(self) -> list[Position]:
        """获取账户持仓列表。"""
        try:
            xt_positions = self.xt_trader.query_stock_positions(self.account)
            if xt_positions is None:
                logger.warning(f"Failed to query positions for account {self.account_id}")
                return []

            positions = []
            for xt_pos in xt_positions:
                # 转换 XtPosition 到 Position
                # 兼容不同版本的 XtPosition，优先使用 avg_price
                avg_cost = getattr(xt_pos, "avg_price", getattr(xt_pos, "open_price", 0.0))

                pos = Position(
                    account_id=self.account_id,
                    ticker=xt_pos.stock_code,
                    total_volume=xt_pos.volume,
                    available_volume=xt_pos.can_use_volume,
                    average_cost=avg_cost,
                )
                positions.append(pos)

            return positions
        except Exception as e:
            logger.error(f"Error querying positions: {e}", exc_info=True)
            return []

    def place_order(self, order: Order) -> str:
        """提交订单。

        Args:
            order: 订单实体

        Returns:
            str: 订单 ID (QMT 返回的是 int，这里转为 str)

        Raises:
            OrderSubmitError: 如果提交失败
        """
        try:
            # 映射委托类型
            order_type = -1
            match order.direction:
                case OrderDirection.BUY:
                    order_type = xtconstant.STOCK_BUY
                case OrderDirection.SELL:
                    order_type = xtconstant.STOCK_SELL
                case _:
                    raise OrderSubmitError(f"Unsupported order direction: {order.direction}")

            # 映射报价类型
            price_type = xtconstant.FIX_PRICE
            price = order.price

            match order.type:
                case OrderType.LIMIT:
                    price_type = xtconstant.FIX_PRICE
                case OrderType.MARKET:
                    # 使用五档即成剩撤作为市价单默认行为
                    # 根据市场区分
                    if order.ticker.endswith(".SH"):
                        price_type = xtconstant.MARKET_SH_CONVERT_5_CANCEL
                    elif order.ticker.endswith(".SZ"):
                        price_type = xtconstant.MARKET_SZ_CONVERT_5_CANCEL
                    else:
                        # 其他市场默认使用对手方最优，或者降级为限价单
                        logger.warning(
                            f"Unknown market for ticker {order.ticker} for market order, defaulting to FIX_PRICE with limit price"
                        )
                        price_type = xtconstant.FIX_PRICE

                    # 市价单价格通常传 0，但在 FIX_PRICE 降级时保持原价
                    if price_type != xtconstant.FIX_PRICE:
                        price = 0
                case _:
                    raise OrderSubmitError(f"Unsupported order type: {order.type}")

            # 下单
            # order_stock(account, stock_code, order_type, order_volume, price_type, price, strategy_name, order_remark)
            order_id = self.xt_trader.order_stock(
                self.account,
                order.ticker,
                order_type,
                int(order.volume),
                price_type,
                price,
                "strategy",  # 策略名称
                order.remark,
            )

            if order_id == -1:
                raise OrderSubmitError("QMT returned -1")

            logger.info(f"Order placed successfully: {order_id}")
            return str(order_id)

        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            if isinstance(e, OrderSubmitError):
                raise
            raise OrderSubmitError(f"Error placing order: {e}") from e
