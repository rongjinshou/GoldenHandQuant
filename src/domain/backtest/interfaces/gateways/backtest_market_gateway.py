from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe


class IBacktestMarketGateway(IMarketGateway, Protocol):
    """回测专用行情网关接口。

    在通用行情接口基础上扩展回测特有方法。
    """

    def load_bars(self, bars: list[Bar]) -> None:
        """加载历史 Bar 到内存索引。"""
        ...

    def set_current_time(self, dt: datetime) -> None:
        """设置回测当前时间。"""
        ...

    def get_all_timestamps(self, timeframe: Timeframe) -> list[datetime]:
        """获取指定周期下的所有去重时间戳（回测专用）。

        Args:
            timeframe: K 线周期。

        Returns:
            list[datetime]: 时间戳列表，按时间升序排列。
        """
        ...

    def last_bar_timestamp(self, symbol: str, timeframe: Timeframe) -> datetime | None:
        """标的已加载数据的全局末根时间（不受回测当前时间截断）。

        退市强平判定用（B1 DD-9）：全局末根=当日且非回测末日 → 此后永无行情。
        停牌股复牌后仍有 bar，其全局末根在未来，不会被误判。
        """
        ...

