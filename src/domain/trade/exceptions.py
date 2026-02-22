class TradeError(Exception):
    """交易领域基础异常。"""


class OrderSubmitError(TradeError):
    """订单提交失败异常。"""


class OrderCancelError(TradeError):
    """订单撤销失败异常。"""
