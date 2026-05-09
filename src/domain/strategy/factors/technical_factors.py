from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class MA5CrossFactor:
    """5 日均线交叉因子 — close / ma_5，价格在均线上方得分高。"""

    name = "ma5_cross"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.close / s.ma_5
            for s in snapshots
            if s.ma_5 is not None and s.ma_5 != 0
        }


class MA20CrossFactor:
    """20 日均线交叉因子 — close / ma_20，价格在均线上方得分高。"""

    name = "ma20_cross"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.close / s.ma_20
            for s in snapshots
            if s.ma_20 is not None and s.ma_20 != 0
        }


class MA60CrossFactor:
    """60 日均线交叉因子 — close / ma_60，价格在均线上方得分高。"""

    name = "ma60_cross"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.close / s.ma_60
            for s in snapshots
            if s.ma_60 is not None and s.ma_60 != 0
        }


class High20dProximityFactor:
    """20 日高点距离因子 — (close - low_20d) / (high_20d - low_20d)，接近低点得分高。"""

    name = "high_20d_proximity"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        result: dict[str, float] = {}
        for s in snapshots:
            if (
                s.high_20d is not None
                and s.low_20d is not None
                and s.high_20d != s.low_20d
            ):
                result[s.symbol] = (s.close - s.low_20d) / (s.high_20d - s.low_20d)
        return result


class Low20dProximityFactor:
    """20 日低点距离因子 — 1 - (close - low_20d) / (high_20d - low_20d)，接近低点得分高。"""

    name = "low_20d_proximity"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        result: dict[str, float] = {}
        for s in snapshots:
            if (
                s.high_20d is not None
                and s.low_20d is not None
                and s.high_20d != s.low_20d
            ):
                result[s.symbol] = 1.0 - (s.close - s.low_20d) / (s.high_20d - s.low_20d)
        return result


class OBVSlope20dFactor:
    """20 日 OBV 斜率因子 — 正斜率得分高。"""

    name = "obv_slope_20d"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.obv_slope_20d
            for s in snapshots
            if s.obv_slope_20d is not None
        }


class PriceRangeFactor:
    """价格振幅因子 — (high - low) / close，窄幅得分高。"""

    name = "price_range"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: (s.high - s.low) / s.close
            for s in snapshots
            if s.close is not None and s.close != 0
        }


class ClosePositionFactor:
    """收盘位置因子 — (close - low) / (high - low)，收盘在高位得分高。"""

    name = "close_position"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        result: dict[str, float] = {}
        for s in snapshots:
            if s.high != s.low:
                result[s.symbol] = (s.close - s.low) / (s.high - s.low)
        return result


class GapFactor:
    """跳空因子 — (open - prev_close) / prev_close，正跳空得分高。"""

    name = "gap"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: (s.open - s.prev_close) / s.prev_close
            for s in snapshots
            if s.prev_close is not None and s.prev_close != 0
        }


class MACDCrossFactor:
    """MACD 交叉因子 — macd - macd_signal，柱状图为正得分高。"""

    name = "macd_cross"

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        return {
            s.symbol: s.macd - s.macd_signal
            for s in snapshots
            if s.macd is not None and s.macd_signal is not None
        }
