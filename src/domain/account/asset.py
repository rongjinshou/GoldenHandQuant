from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class Asset:
    """账户资产实体。

    遵循 A 股资金冻结规则:
    1. total_asset = available_cash + frozen_cash + market_value (持仓市值)
    2. 下单冻结: available_cash -> frozen_cash
    3. 成交扣款: frozen_cash -> 减少

    Attributes:
        account_id: 账户 ID。
        total_asset: 总资产 (现金 + 持仓市值)。
        available_cash: 可用资金 (可用于下单)。
        frozen_cash: 冻结资金 (挂单中)。
        updated_at: 最后更新时间。
    """

    account_id: str
    total_asset: float = 0.0
    available_cash: float = 0.0
    frozen_cash: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)

    def freeze_cash(self, amount: float) -> None:
        """冻结资金 (下单前)。

        Args:
            amount: 冻结金额。

        Raises:
            ValueError: 如果金额 <= 0 或可用资金不足。
        """
        if amount <= 0:
            raise ValueError("Freeze amount must be positive")
        if amount > self.available_cash:
            raise ValueError(f"Insufficient available cash: {self.available_cash} < {amount}")

        self.available_cash -= amount
        self.frozen_cash += amount
        self.updated_at = datetime.now()

    def unfreeze_cash(self, amount: float) -> None:
        """解冻资金 (撤单/拒单)。

        Args:
            amount: 解冻金额。

        Raises:
            ValueError: 如果金额 <= 0 或超过已冻结资金。
        """
        if amount <= 0:
            raise ValueError("Unfreeze amount must be positive")
        if amount > self.frozen_cash:
            raise ValueError(f"Cannot unfreeze more than frozen cash: {self.frozen_cash} < {amount}")

        self.frozen_cash -= amount
        self.available_cash += amount
        self.updated_at = datetime.now()

    def deduct_frozen_cash(self, amount: float) -> None:
        """扣除冻结资金 (成交)。

        注意: 此操作只减少现金，不自动扣减 total_asset (因为资金可能转换为持仓)。
        若用于扣除手续费，需额外手动调整 total_asset。

        Args:
            amount: 扣除金额。

        Raises:
            ValueError: 如果金额 <= 0 或超过已冻结资金。
        """
        if amount <= 0:
            raise ValueError("Deduct amount must be positive")
        if amount > self.frozen_cash:
            raise ValueError(f"Cannot deduct more than frozen cash: {self.frozen_cash} < {amount}")

        self.frozen_cash -= amount
        # self.total_asset 不自动减少，保持总资产守恒 (Cash -> Position)
        self.updated_at = datetime.now()

    def deposit(self, amount: float) -> None:
        """入金。

        Args:
            amount: 入金金额。

        Raises:
            ValueError: 如果金额 <= 0。
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.available_cash += amount
        self.total_asset += amount
        self.updated_at = datetime.now()
