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

