from typing import Protocol
from src.domain.account.asset import Asset
from src.domain.account.position import Position

class IAccountGateway(Protocol):
    """账户网关接口。
    
    负责查询账户资金与持仓。
    """

    def get_asset(self) -> Asset | None:
        """获取账户资金信息。

        Returns:
            Asset | None: 资金实体，若查询失败返回 None。
        """
        ...

    def get_positions(self) -> list[Position]:
        """获取账户持仓列表。

        Returns:
            list[Position]: 持仓实体列表。
        """
        ...
