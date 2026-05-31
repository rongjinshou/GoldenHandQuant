from src.domain.strategy.pool.entities.strategy_pool_entry import StrategyPoolEntry
from src.domain.strategy.pool.value_objects.strategy_status import StrategyStatus


class MemoryStrategyPoolRepository:
    """内存版策略池仓储（用于测试和回测）。"""

    def __init__(self) -> None:
        self._store: dict[str, StrategyPoolEntry] = {}

    def save(self, entry: StrategyPoolEntry) -> None:
        self._store[entry.strategy_name] = entry

    def find_by_name(self, name: str) -> StrategyPoolEntry | None:
        return self._store.get(name)

    def find_all(self) -> list[StrategyPoolEntry]:
        return list(self._store.values())

    def find_by_status(self, status: StrategyStatus) -> list[StrategyPoolEntry]:
        return [e for e in self._store.values() if e.status == status]

    def find_active(self) -> list[StrategyPoolEntry]:
        return self.find_by_status(StrategyStatus.ACTIVE)

    def delete(self, name: str) -> None:
        self._store.pop(name, None)
