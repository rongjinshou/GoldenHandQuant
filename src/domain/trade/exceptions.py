class TradeError(Exception):
    """交易领域基础异常。"""


class OrderSubmitError(TradeError):
    """订单提交失败异常。"""


class OrderCancelError(TradeError):
    """订单撤销失败异常。"""


class MarketClosedError(TradeError):
    """市场已关闭异常——尝试在非交易时间下单。"""

    def __init__(self, ticker: str = "", detail: str = "") -> None:
        self.ticker = ticker
        msg = f"Market is closed"
        if ticker:
            msg += f" for {ticker}"
        if detail:
            msg += f": {detail}"
        super().__init__(msg)


class OrderValidationError(TradeError):
    """订单参数校验失败异常。"""

    def __init__(self, reason: str, order_id: str = "") -> None:
        self.reason = reason
        self.order_id = order_id
        msg = f"Order validation failed: {reason}"
        if order_id:
            msg += f" (order: {order_id})"
        super().__init__(msg)
