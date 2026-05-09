from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class ReversalFactor:
    """20 日反转因子 -- 涨幅越小/负，分数越高（A 股反转效应）。"""

    name = "reversal_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.return_20d
            for s in snapshots
            if s.return_20d is not None
        }
