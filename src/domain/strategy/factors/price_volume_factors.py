from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class Return5dFactor:
    """5 日收益率因子 -- 跌多得分高（反转效应）。"""

    name = "return_5d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.return_5d
            for s in snapshots
            if s.return_5d is not None
        }


class Return60dFactor:
    """60 日收益率因子 -- 涨多得分高（动量效应）。"""

    name = "return_60d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.return_60d
            for s in snapshots
            if s.return_60d is not None
        }


class Volatility60dFactor:
    """60 日波动率因子 -- 低波得分高。"""

    name = "volatility_60d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.volatility_60d
            for s in snapshots
            if s.volatility_60d is not None
        }


class TurnoverFactor:
    """换手率因子 -- 低换手得分高。"""

    name = "turnover"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.turnover_rate
            for s in snapshots
            if s.turnover_rate is not None
        }


class AvgTurnover20dFactor:
    """20 日平均换手率因子 -- 低换手得分高。"""

    name = "avg_turnover_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.avg_turnover_20d
            for s in snapshots
            if s.avg_turnover_20d is not None
        }


class RSI14Factor:
    """14 日 RSI 因子 -- 低 RSI 得分高（超卖信号）。"""

    name = "rsi_14"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.rsi_14
            for s in snapshots
            if s.rsi_14 is not None
        }


class MACDFactor:
    """MACD 柱状图因子（macd - macd_signal），正值得分高。"""

    name = "macd_hist"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.macd - s.macd_signal
            for s in snapshots
            if s.macd is not None and s.macd_signal is not None
        }


class ATR14Factor:
    """14 日 ATR 因子 -- 低波动得分高。"""

    name = "atr_14"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.atr_14
            for s in snapshots
            if s.atr_14 is not None
        }


class Skewness20dFactor:
    """20 日偏度因子 -- 负偏得分高。"""

    name = "skewness_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.skewness_20d
            for s in snapshots
            if s.skewness_20d is not None
        }


class Illiquidity20dFactor:
    """20 日 Amihud 非流动性因子 -- 低非流动性得分高。"""

    name = "illiquidity_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.illiquidity_20d
            for s in snapshots
            if s.illiquidity_20d is not None
        }
