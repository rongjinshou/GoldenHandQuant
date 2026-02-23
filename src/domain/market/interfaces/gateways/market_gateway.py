from typing import Protocol
from datetime import datetime
from src.domain.market.value_objects.bar import Bar

class IMarketGateway(Protocol):
    """行情网关接口。
    
    负责从外部数据源获取行情数据。
    """
    
    def get_recent_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        """获取最近的 K 线数据。

        Args:
            symbol: 标的代码。
            timeframe: K 线周期 (如 "1d", "1m")。
            limit: 获取数量。

        Returns:
            list[Bar]: K 线列表，按时间升序排列。
        """
        ...
