from typing import Protocol

from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot


class IFundamentalFetcher(Protocol):
    """基本面数据获取接口（Domain 层定义，Infrastructure 层实现）。"""

    def fetch_by_range(
        self, start_date: str, end_date: str
    ) -> list[FundamentalSnapshot]:
        """批量预加载指定区间的基本面数据。

        以 ann_date（公告日期）为时间轴，杜绝未来函数。
        """
        ...

    def fetch_index_daily(
        self, index_symbol: str, start_date: str, end_date: str
    ) -> list[dict]:
        """获取指数日线数据（用于风控门禁和基准比较）。

        Returns:
            list[dict]: 每项含 trade_date, open, high, low, close, volume 等字段。
        """
        ...
