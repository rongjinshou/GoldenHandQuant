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


def _map_xt_order_status(status: int) -> str:
    """xtconstant 委托状态 → 引擎通用状态。"""
    if status == xtconstant.ORDER_SUCCEEDED:
        return "FILLED"
    if status == xtconstant.ORDER_PART_SUCC:
        return "PARTIAL"
    if status in (xtconstant.ORDER_CANCELED, xtconstant.ORDER_PART_CANCEL):
        return "CANCELED"
    if status == xtconstant.ORDER_JUNK:
        return "REJECTED"
    return "ALIVE"  # 未报/待报/已报/待撤等中间态


class QmtTradeGateway(ITradeGateway, IAccountGateway):
    """QMT 交易网关实现。"""

    is_dry_run = False  # QMT 实盘网关, 触达真实券商

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

        self._initialized = False
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

            self._initialized = True
        except Exception as e:
            logger.error("QmtTradeGateway 初始化失败: %s", e, exc_info=True)

    def _check_initialized(self) -> bool:
        """检查是否初始化成功。"""
        if not self._initialized:
            logger.error("QmtTradeGateway 未成功初始化，无法执行操作")
            return False
        return True

    def get_asset(self, account_id: str | None = None) -> Asset | None:
        """获取账户资金信息。"""
        if not self._check_initialized():
            return None
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

    def get_positions(self, account_id: str | None = None) -> list[Position]:
        """获取账户持仓列表。"""
        if not self._check_initialized():
            return []
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

    def query_order_status(self, order_id: str) -> str | None:
        """按 QMT 委托号查询订单状态（映射为引擎通用状态字符串）。

        Returns:
            FILLED/PARTIAL/CANCELED/REJECTED/ALIVE，查不到返回 None。
        """
        if not self._check_initialized():
            return None
        try:
            orders = self.xt_trader.query_stock_orders(self.account) or []
            for xt_order in orders:
                if str(xt_order.order_id) != str(order_id):
                    continue
                return _map_xt_order_status(xt_order.order_status)
            return None
        except Exception as e:
            logger.error(f"Error querying order status: {e}", exc_info=True)
            return None

    def cancel_order(self, order_id: str) -> bool:
        """按 QMT 委托号撤单。返回是否受理(异步撤单, 受理≠已撤)。"""
        if not self._check_initialized():
            return False
        try:
            result = self.xt_trader.cancel_order_stock(
                self.account, int(order_id)
            )
            if result == 0:
                logger.info(f"Cancel accepted for order {order_id}")
                return True
            logger.warning(f"Cancel rejected for order {order_id}: {result}")
            return False
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}", exc_info=True)
            return False

    def place_order(self, order: Order) -> str:
        """提交订单。"""
        if not self._check_initialized():
            raise OrderSubmitError("QmtTradeGateway 未成功初始化")
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
