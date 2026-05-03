from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def filter_st(snapshots: list[StockSnapshot]) -> list[StockSnapshot]:
    """剔除 ST 或 *ST 等风险警示股。"""
    return [s for s in snapshots if not s.name.upper().startswith(("ST", "*ST", "SST", "S*ST"))]
