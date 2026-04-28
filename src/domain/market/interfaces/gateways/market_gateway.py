from typing import Protocol
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe

class IMarketGateway(Protocol):
    """行情网关接口 (实盘 + 回测通用)。

    负责从外部数据源获取行情数据。
    """

    def get_recent_bars(self, symbol: str, timeframe: Timeframe, limit: int) -> list[Bar]:
        """获取最近的 K 线数据。

        Args:
            symbol: 标的代码。
            timeframe: K 线周期。
            limit: 获取数量。

        Returns:
            list[Bar]: K 线列表，按时间升序排列。
        """
        ...
