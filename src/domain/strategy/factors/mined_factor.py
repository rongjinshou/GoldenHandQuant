"""挖掘因子适配器 — 从预计算的 parquet 加载因子值，适配 Factor Protocol。"""

from __future__ import annotations

from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class MinedFactor:
    """挖掘因子适配器 — 适配 Factor Protocol。

    不依赖 pandas/numpy，仅使用标准字典操作。
    """

    def __init__(
        self,
        name: str,
        values_by_date: dict[str, dict[str, float]],
        inverted: bool = False,
    ) -> None:
        self.name = name
        self._values_by_date = values_by_date
        self.inverted = inverted

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """从预计算值中查找当日因子值。"""
        if not snapshots:
            return {}
        date_key = snapshots[0].date.strftime("%Y-%m-%d")
        day_values = self._values_by_date.get(date_key, {})
        return {
            s.symbol: day_values[s.symbol]
            for s in snapshots
            if s.symbol in day_values
        }
