import logging

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType

from .xtquant_client import StockAccount, XtQuantTrader, XtQuantTraderCallback, xtconstant

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
            self.xt_trader = XtQuantTrader(path, session_id)
            self.account = StockAccount(account_id, account_type)
            self.callback = XtQuantTraderCallback()
            self.xt_trader.register_callback(self.callback)
            self.xt_trader.start()

            connect_result = self.xt_trader.connect()
            if connect_result == 0:
                logger.info(f"Connected to QMT trading gateway (session: {session_id})")
            else:
                logger.error(f"Failed to connect to QMT trading gateway: {connect_result}")

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
        """提交订单。"""
        try:
            order_type = -1
            match order.direction:
                case OrderDirection.BUY:
                    order_type = xtconstant.STOCK_BUY
                case OrderDirection.SELL:
                    order_type = xtconstant.STOCK_SELL
                case _:
                    raise OrderSubmitError(f"Unsupported order direction: {order.direction}")

            price_type = xtconstant.FIX_PRICE
            price = order.price

            match order.type:
                case OrderType.LIMIT:
                    price_type = xtconstant.FIX_PRICE
                case OrderType.MARKET:
                    if order.ticker.endswith(".SH"):
                        price_type = xtconstant.MARKET_SH_CONVERT_5_CANCEL
                    elif order.ticker.endswith(".SZ"):
                        price_type = xtconstant.MARKET_SZ_CONVERT_5_CANCEL
                    else:
                        logger.warning(
                            f"Unknown market for ticker {order.ticker} for market order, "
                            f"defaulting to FIX_PRICE with limit price"
                        )
                        price_type = xtconstant.FIX_PRICE

                    if price_type != xtconstant.FIX_PRICE:
                        price = 0
                case _:
                    raise OrderSubmitError(f"Unsupported order type: {order.type}")

            order_id = self.xt_trader.order_stock(
                self.account,
                order.ticker,
                order_type,
                int(order.volume),
                price_type,
                price,
                "strategy",
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
