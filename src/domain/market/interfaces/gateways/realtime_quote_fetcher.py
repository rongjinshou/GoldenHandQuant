from typing import Protocol

from src.domain.market.value_objects.quote import Quote


class IRealtimeQuoteFetcher(Protocol):
    """实时行情获取接口。

    实现要求：get_quotes 为按需快照；subscribe_first_tick 走订阅推送拿首个
    tick（验证订阅链路），超时回退快照，拿不到返回 None。
    """

    def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """批量获取最新快照（拿不到的标的不在返回 dict 中）。"""
        ...

    def subscribe_first_tick(self, symbol: str, timeout: float = 3.0) -> Quote | None:
        """订阅 tick 推送并返回首个报价；超时回退快照；失败返回 None。"""
        ...
