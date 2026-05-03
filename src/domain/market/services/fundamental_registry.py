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

    def get_all_at_date(self, date: datetime) -> list[FundamentalSnapshot]:
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        return self._by_date.get(date_key, [])
