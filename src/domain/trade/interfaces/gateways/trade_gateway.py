from typing import Protocol

from src.domain.trade.entities.order import Order


class ITradeGateway(Protocol):
    """交易网关接口。

    负责向外部交易系统下单 / 查单 / 撤单。
    `is_dry_run` 标识该网关是否「不触达真实券商」（dry-run 包装、Mock 撮合 = True；
    QMT 实盘 = False），供 AutoTradeAppService 装配一致性校验用。
    """

    is_dry_run: bool

    def place_order(self, order: Order) -> str:
        """提交订单，返回委托编号；失败抛 OrderSubmitError。"""
        ...

    def query_order_status(self, order_id: str) -> str | None:
        """查询订单状态字符串（FILLED/CANCELED/REJECTED/...）；查不到返回 None。"""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """撤销委托，受理返回 True，否则 False。"""
        ...
