from abc import ABC, abstractmethod
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.market.value_objects.bar import Bar

class IHistoryDataFetcher(ABC):
    """历史数据获取接口。"""

    @abstractmethod
    def fetch_history_bars(
        self, 
        symbol: str, 
        timeframe: Timeframe, 
        start_date: str, 
        end_date: str
    ) -> list[Bar]:
        """获取历史 K 线数据。

        Args:
            symbol: 标的代码 (如 '600000.SH').
            timeframe: K 线周期.
            start_date: 开始日期 (YYYY-MM-DD).
            end_date: 结束日期 (YYYY-MM-DD).

        Returns:
            list[Bar]: K 线列表.
        """
        ...
