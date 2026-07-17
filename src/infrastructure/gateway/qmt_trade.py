import logging
import os
import time

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


def derive_session_id(base: int, *, stamp: float | None = None, pid: int | None = None) -> int:
    """派生进程唯一 session: 固定 session 会被 QMT 中上一进程的残留注册占用致
    connect != 0(0713 watch / 0714 auto-trade 两日实证)。+300_000 频段与
    sync_live_account 的 +500_000 频段错开; 时间×31+pid 使同秒双进程亦不撞。"""
    t = int(stamp if stamp is not None else time.time())
    p = pid if pid is not None else os.getpid()
    return base + 300_000 + (t * 31 + p) % 100_000


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


class GhqTraderCallback(XtQuantTraderCallback):
    """交易回报回调（M3 保守版, 2026-07-10）。

    断线: 置网关不可用标志(place_order 拒单)+高声告警; 不自动重连——
    重连时序未经真实环境验证前, 显性失败优于隐性带病运行。
    委托错误/回报: 只留日志(成交量回填 execution_records 属 M4 另立)。
    """

    def __init__(self, gateway: "QmtTradeGateway") -> None:
        super().__init__()
        self._gateway = gateway

    def on_disconnected(self) -> None:
        logger.error("QMT 交易连接断开(on_disconnected)! 网关已置不可用, "
                     "新订单将被拒绝 — 请检查 QMT 客户端后重启进程")
        self._gateway._connected = False

    def on_order_error(self, order_error) -> None:
        logger.error("QMT 委托错误回报: order_id=%s error_id=%s msg=%s",
                     getattr(order_error, "order_id", "?"),
                     getattr(order_error, "error_id", "?"),
                     getattr(order_error, "error_msg", "?"))

    def on_stock_order(self, order) -> None:
        logger.info("QMT 委托状态回报: order_id=%s status=%s",
                    getattr(order, "order_id", "?"),
                    getattr(order, "order_status", "?"))


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
        self.session_id = derive_session_id(session_id)
        self.account_id = account_id
        self.account_type = account_type

        self._initialized = False
        self._connected = False
        try:
            self.xt_trader = XtQuantTrader(path, self.session_id)
            self.account = StockAccount(account_id, account_type)
            self.callback = GhqTraderCallback(self)
            self.xt_trader.register_callback(self.callback)
            self.xt_trader.start()

            connect_result = self.xt_trader.connect()
            if connect_result != 0:
                raise RuntimeError(
                    f"QMT 交易连接失败(connect={connect_result}), "
                    "检查 QMT 客户端是否已「极简模式」登录"
                )
            logger.info(
                f"Connected to QMT trading gateway (session: {self.session_id}, base: {session_id})"
            )

            subscribe_result = self.xt_trader.subscribe(self.account)
            if subscribe_result != 0:
                raise RuntimeError(
                    f"QMT 账户订阅失败(subscribe={subscribe_result}), account={account_id}"
                )
            logger.info(f"Subscribed to account {account_id}")

            self._initialized = True
            self._connected = True
        except Exception as e:
            # 半初始化的网关绝不能进入下单路径: get_asset 返 None 会触发下游
            # 日亏闸 fail-open, 故 fail-fast 而非吞异常继续
            logger.error("QmtTradeGateway 初始化失败: %s", e, exc_info=True)
            raise

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
        """按 QMT 委托号撤单。返回是否受理(异步撤单, 受理≠已撤)。

        真单前置注意事项(2026-07-05 债务台账):
        本方法自 R1(0628) 补入协议后，从未经过真实盘中撤单验证。
        首次真单撤单时需人工确认: 1) QMT 返回码含义 2) 撤单后状态轮询验证。
        """
        if not self._check_initialized():
            logger.warning("撤单失败: QMT 网关未初始化 (order_id=%s)", order_id)
            return False
        try:
            result = self.xt_trader.cancel_order_stock(
                self.account, int(order_id)
            )
            if result == 0:
                logger.info("撤单已受理: order_id=%s (异步, 需轮询确认)", order_id)
                return True
            logger.warning("撤单被拒: order_id=%s QMT返回码=%s", order_id, result)
            return False
        except ValueError:
            logger.error("撤单失败: order_id=%s 非有效委托号", order_id)
            return False
        except Exception as e:
            logger.error("撤单异常: order_id=%s error=%s", order_id, e, exc_info=True)
            return False

    def place_order(self, order: Order) -> str:
        """提交订单。"""
        if not self._check_initialized():
            raise OrderSubmitError("QmtTradeGateway 未成功初始化")
        if not self._connected:
            raise OrderSubmitError(
                "QMT 交易连接已断开(on_disconnected), 拒绝下单 — 检查客户端后重启进程")
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
