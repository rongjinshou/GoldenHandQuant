from typing import Protocol

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


class IAccountGateway(Protocol):
    """账户网关协议（参数化支持多账户）。"""

    def get_asset(self, account_id: str | None = None) -> Asset | None:
        """获取指定账户资产。若未指定 account_id 则返回默认账户。"""
        ...

    def get_positions(self, account_id: str | None = None) -> list[Position]:
        """获取指定账户持仓列表。"""
        ...
