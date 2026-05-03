from datetime import datetime

from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def filter_new_listing(
    snapshots: list[StockSnapshot],
    current_date: datetime,
    min_days: int = 365,
) -> list[StockSnapshot]:
    """剔除上市天数不足 min_days 的次新股。"""
    return [s for s in snapshots if (current_date - s.list_date).days >= min_days]
