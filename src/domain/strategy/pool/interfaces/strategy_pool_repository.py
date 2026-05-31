from typing import Protocol

from src.domain.strategy.pool.entities.strategy_pool_entry import StrategyPoolEntry
from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus


class IStrategyPoolRepository(Protocol):
    """策略池持久化接口。"""

    def save(self, entry: StrategyPoolEntry) -> None: ...

    def find_by_name(self, name: str) -> StrategyPoolEntry | None: ...

    def find_all(self) -> list[StrategyPoolEntry]: ...

    def find_by_status(self, status: StrategyStatus) -> list[StrategyPoolEntry]: ...

    def find_active(self) -> list[StrategyPoolEntry]: ...

    def delete(self, name: str) -> None: ...
