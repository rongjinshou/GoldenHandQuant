from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class ROEQualityFactor:
    """ROE 质量因子 — 高 ROE 得高分。"""

    name = "roe_quality"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.roe_ttm
            for s in snapshots
            if s.roe_ttm is not None and s.roe_ttm > 0
        }
