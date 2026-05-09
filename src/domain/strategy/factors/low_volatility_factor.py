from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class LowVolatilityFactor:
    """20 日低波动因子 -- 波动率越低，分数越高。"""

    name = "low_volatility_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.volatility_20d
            for s in snapshots
            if s.volatility_20d is not None
        }
