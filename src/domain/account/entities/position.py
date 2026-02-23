from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class Position:
    """账户持仓实体。

    遵循 A 股 T+1 结算规则:
    1. available_volume (可用持仓) <= total_volume (总持仓)
    2. 当日买入: total_volume 增加，available_volume 不变
    3. 当日卖出: available_volume 减少，total_volume 减少

    Attributes:
        account_id: 账户 ID。
        ticker: 证券代码 (如 "600000.SH")。
        total_volume: 总持仓数量。
        available_volume: 可用持仓数量 (T+0 可卖)。
        average_cost: 持仓均价 (移动加权平均)。
        updated_at: 最后更新时间。
    """

    account_id: str
    ticker: str
    total_volume: int = 0
    available_volume: int = 0
    average_cost: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)

    def on_buy_filled(self, volume: int, price: float) -> None:
        """买入成交: 增加 total_volume, available_volume 不变 (T+1)。

        Args:
            volume: 成交数量。
            price: 成交价格。

        Raises:
            ValueError: 如果数量 <= 0 或价格 < 0。
        """
        if volume <= 0:
            raise ValueError("Buy volume must be positive")
        if price < 0:
            raise ValueError("Price cannot be negative")

        # 计算新成本: (旧总持仓 * 旧成本 + 新量 * 新价) / 新总持仓
        current_total_cost = self.total_volume * self.average_cost
        new_cost_basis = volume * price

        self.total_volume += volume
        # available_volume 不变 (T+1)

        if self.total_volume > 0:
            self.average_cost = (current_total_cost + new_cost_basis) / self.total_volume
        else:
            self.average_cost = 0.0

        self.updated_at = datetime.now()

    def on_sell_filled(self, volume: int, price: float) -> None:
        """卖出成交: 减少 total_volume, 减少 available_volume。

        Args:
            volume: 成交数量。
            price: 成交价格。

        Raises:
            ValueError: 如果数量 <= 0 或超过可用持仓。
        """
        if volume <= 0:
            raise ValueError("Sell volume must be positive")
        if volume > self.available_volume:
            raise ValueError(f"Insufficient available volume: {self.available_volume} < {volume}")

        # 卖出通常不改变平均持仓成本（移动加权平均法），除非清仓
        # 盈亏 = (price - average_cost) * volume

        self.total_volume -= volume
        self.available_volume -= volume

        if self.total_volume == 0:
            self.average_cost = 0.0

        self.updated_at = datetime.now()

    def settle_t_plus_1(self) -> None:
        """T+1 结算: 当日买入变成可用。

        通常在日终清算或次日开盘前调用。
        """
        self.available_volume = self.total_volume
        self.updated_at = datetime.now()
