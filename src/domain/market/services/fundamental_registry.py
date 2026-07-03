from dataclasses import replace
from datetime import datetime

from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot


class FundamentalRegistry:
    """基本面数据内存注册表。

    双索引结构:
    - _by_symbol: dict[symbol, dict[date, FundamentalSnapshot]] — 按标的查询 O(1)
    - _by_date: dict[date, list[FundamentalSnapshot]] — 按日期批量获取 O(1)

    索引键使用 ann_date（公告日期），不使用 end_date（报告期），杜绝未来函数。
    """

    def __init__(self) -> None:
        self._by_symbol: dict[str, dict[datetime, FundamentalSnapshot]] = {}
        self._by_date: dict[datetime, list[FundamentalSnapshot]] = {}

    def add(self, snapshot: FundamentalSnapshot) -> None:
        date_key = snapshot.date.replace(hour=0, minute=0, second=0, microsecond=0)

        self._by_symbol.setdefault(snapshot.symbol, {})[date_key] = snapshot
        self._by_date.setdefault(date_key, []).append(snapshot)

    def get(self, symbol: str, date: datetime) -> FundamentalSnapshot | None:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._by_symbol.get(symbol, {}).get(date_key)

    def load_snapshots(self, snapshots: list[FundamentalSnapshot]) -> None:
        for snapshot in snapshots:
            self.add(snapshot)

    def get_all_at_date(self, date: datetime) -> list[FundamentalSnapshot]:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._by_date.get(date_key, [])

    def latest_date_at_or_before(self, date: datetime) -> datetime | None:
        """<= date 的最近快照日; 无则 None。live 装配 as-of 别名用(0626 阶段1 DD-5)。"""
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = [d for d in self._by_date if d <= date_key]
        return max(candidates) if candidates else None

    def alias_date(self, src: datetime, dst: datetime) -> int:
        """把 src 日快照以 dst 日期别名注册(live as-of 回退, 不动既有数据); 返回行数。"""
        # 复制一份: get_all_at_date 返回内部列表, src==dst 时边迭代边 add 会死循环
        rows = list(self.get_all_at_date(src))
        for snap in rows:
            self.add(replace(snap, date=dst))
        return len(rows)
