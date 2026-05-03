from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def filter_penny_stock(
    snapshots: list[StockSnapshot],
    min_price: float = 1.5,
) -> list[StockSnapshot]:
    """剔除收盘价低于 min_price 的仙股，规避面值退市风险。"""
    return [s for s in snapshots if s.close >= min_price]
