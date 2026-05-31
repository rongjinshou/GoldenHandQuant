"""事件仓储协议（domain 层接口，纯标准库）。"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.domain.common.domain_event import DomainEvent


class EventStore(ABC):
    """事件持久化协议。

    所有事件存储实现必须实现此接口。
    设计为 append-only，事件不可修改、不可删除。
    """

    @abstractmethod
    def append(self, event: DomainEvent) -> None:
        """追加一个领域事件到事件流。

        Args:
            event: 要持久化的领域事件。
        """
        ...

    @abstractmethod
    def append_batch(self, events: list[DomainEvent]) -> None:
        """批量追加领域事件（事务性）。

        Args:
            events: 要持久化的领域事件列表。
        """
        ...

    @abstractmethod
    def get_events(
        self,
        aggregate_id: str | None = None,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[DomainEvent]:
        """查询领域事件。

        Args:
            aggregate_id: 按聚合根 ID 过滤。
            event_type: 按事件类型过滤。
            start_time: 起始时间（含）。
            end_time: 结束时间（含）。
            limit: 最大返回数量。

        Returns:
            匹配的领域事件列表（按时间升序）。
        """
        ...

    @abstractmethod
    def get_events_by_aggregate(self, aggregate_id: str) -> list[DomainEvent]:
        """获取指定聚合根的全部事件（按时间升序）。

        Args:
            aggregate_id: 聚合根 ID。

        Returns:
            该聚合根的全部领域事件。
        """
        ...
