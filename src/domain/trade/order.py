from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIAL_FILLED = "PARTIAL_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    PARTIAL_CANCELED = "PARTIAL_CANCELED"


class OrderDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


@dataclass(slots=True, kw_only=True)
class Order:
    """订单实体。

    遵循 A 股交易规则与状态机流转。

    Attributes:
        order_id: 订单 ID。
        account_id: 账户 ID。
        ticker: 证券代码。
        direction: 买卖方向 (BUY/SELL)。
        price: 委托价格。
        volume: 委托数量。
        type: 订单类型 (LIMIT/MARKET)。
        status: 订单状态。
        traded_volume: 已成交数量。
        traded_price: 平均成交价格。
        created_at: 创建时间。
        updated_at: 最后更新时间。
        remark: 备注/拒单原因。
    """

    order_id: str
    account_id: str
    ticker: str
    direction: OrderDirection
    price: float
    volume: int
    type: OrderType = OrderType.LIMIT

    # 状态与成交信息
    status: OrderStatus = OrderStatus.CREATED
    traded_volume: int = 0
    traded_price: float = 0.0  # 平均成交价

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 备注/错误信息
    remark: str = ""

    def __post_init__(self) -> None:
        """初始化验证。

        Raises:
            ValueError: 如果数量/价格无效。
        """
        if self.volume <= 0:
            raise ValueError("Order volume must be positive")
        if self.price < 0:
            raise ValueError("Order price cannot be negative")

        # A 股买入必须是 100 的整数倍
        if self.direction == OrderDirection.BUY:
            if self.volume % 100 != 0:
                raise ValueError(f"Buy volume must be a multiple of 100, got {self.volume}")

    def submit(self) -> None:
        """提交订单。

        状态流转: CREATED -> SUBMITTED

        Raises:
            RuntimeError: 如果当前状态不可提交。
        """
        if self.status != OrderStatus.CREATED:
            raise RuntimeError(f"Cannot submit order in status {self.status}")
        self.status = OrderStatus.SUBMITTED
        self.updated_at = datetime.now()

    def on_fill(self, fill_volume: int, fill_price: float) -> None:
        """订单成交回报处理。

        状态流转: SUBMITTED / PARTIAL_FILLED -> PARTIAL_FILLED / FILLED

        Args:
            fill_volume: 本次成交数量。
            fill_price: 本次成交价格。

        Raises:
            RuntimeError: 如果当前状态不可成交，或成交量超出委托量。
        """
        if self.status not in [OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]:
            raise RuntimeError(f"Cannot fill order in status {self.status}")

        if fill_volume <= 0:
            return

        # 更新成交信息
        new_traded_volume = self.traded_volume + fill_volume
        if new_traded_volume > self.volume:
            # 防止超额成交 (虽然实盘极少发生，但需防御)
            raise RuntimeError(f"Fill volume exceeds order volume: {new_traded_volume} > {self.volume}")

        # 更新平均成交价
        current_value = self.traded_volume * self.traded_price
        new_fill_value = fill_volume * fill_price
        self.traded_price = (current_value + new_fill_value) / new_traded_volume
        self.traded_volume = new_traded_volume

        # 状态流转
        if self.traded_volume == self.volume:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIAL_FILLED

        self.updated_at = datetime.now()

    def cancel(self) -> None:
        """撤单成功。

        状态流转:
        - SUBMITTED -> CANCELED
        - PARTIAL_FILLED -> PARTIAL_CANCELED

        Raises:
            RuntimeError: 如果当前状态不可撤单。
        """
        match self.status:
            case OrderStatus.SUBMITTED:
                self.status = OrderStatus.CANCELED
            case OrderStatus.PARTIAL_FILLED:
                self.status = OrderStatus.PARTIAL_CANCELED
            case _:
                raise RuntimeError(f"Cannot cancel order in status {self.status}")

        self.updated_at = datetime.now()

    def reject(self, reason: str) -> None:
        """拒单。

        状态流转: SUBMITTED -> REJECTED

        Args:
            reason: 拒单原因。

        Raises:
            RuntimeError: 如果当前状态不可拒单。
        """
        if self.status != OrderStatus.SUBMITTED:
            # 部分成交后通常不会变拒单，而是部成撤，这里仅允许 SUBMITTED -> REJECTED
            raise RuntimeError(f"Cannot reject order in status {self.status}")

        self.status = OrderStatus.REJECTED
        self.remark = reason
        self.updated_at = datetime.now()
