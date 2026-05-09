from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class PBValueFactor:
    """市净率价值因子 — 低 PB 得高分。"""

    name = "pb_value"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.pb_ratio
            for s in snapshots
            if s.pb_ratio is not None and s.pb_ratio > 0
        }


class PEValueFactor:
    """市盈率价值因子 — 低 PE 得高分。"""

    name = "pe_value"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.pe_ratio
            for s in snapshots
            if s.pe_ratio is not None and s.pe_ratio > 0
        }
