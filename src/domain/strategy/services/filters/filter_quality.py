from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def filter_quality(
    snapshots: list[StockSnapshot],
    min_universe_size: int = 30,
) -> list[StockSnapshot]:
    """保留 ROE > 全市场中位数且 OCF > 0 的标的。"""
    valid = [s for s in snapshots if s.roe_ttm is not None and s.ocf_ttm is not None]
    if not valid:
        return []
    if len(valid) <= min_universe_size:
        return valid
    sorted_roe = sorted(s.roe_ttm for s in valid)  # type: ignore[arg-type]
    n = len(sorted_roe)
    if n % 2 == 0:
        median_roe = (sorted_roe[n // 2 - 1] + sorted_roe[n // 2]) / 2.0
    else:
        median_roe = sorted_roe[n // 2]

    return [
        s for s in valid
        if s.roe_ttm is not None and s.roe_ttm > median_roe
        and s.ocf_ttm is not None and s.ocf_ttm > 0
    ]
