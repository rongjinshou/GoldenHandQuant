from datetime import datetime

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class CrossSectionBuilder:
    """从 Bar + 基本面构建截面 StockSnapshot 列表(领域逻辑)。

    截面策略的输入构建:OHLCV + 基本面 -> StockSnapshot。纯 Python、无第三方依赖。
    原属 infrastructure/ml_engine/feature_pipeline,Spec 2 架构治理归位 domain。
    """

    @staticmethod
    def build_cross_section(
        date: datetime,
        bars: dict[str, Bar],
        registry: FundamentalRegistry,
        bar_history: dict[str, list[Bar]] | None = None,
        precomputed_features: dict[str, dict[str, float]] | None = None,
    ) -> list[StockSnapshot]:
        """构建截面 StockSnapshot。

        技术指标来源(B7): 优先 `precomputed_features`(由 feature_engine 算好的统一口径,
        见 [SnapshotFeatureSource]); 否则回退 `bar_history` + 手写 `_compute_bar_metrics`
        (旧路径, return_20d 口径有偏, 仅遗留调用方用)。给了 precomputed_features 即不再手写重算。
        """
        fundamentals = {s.symbol: s for s in registry.get_all_at_date(date)}
        snapshots: list[StockSnapshot] = []

        for symbol, bar in bars.items():
            fund = fundamentals.get(symbol)
            if fund is None:
                continue

            # 价量指标: precomputed_features(feature_engine 统一口径) 优先于手写重算
            kw: dict = {}
            if precomputed_features is not None:
                if symbol in precomputed_features:
                    kw.update(precomputed_features[symbol])
            elif bar_history and symbol in bar_history:
                hist = bar_history[symbol]
                CrossSectionBuilder._compute_bar_metrics(hist, kw)

            # 传递基本面指标
            CrossSectionBuilder._compute_fundamental_metrics(fund, kw)

            snapshots.append(StockSnapshot(
                symbol=symbol,
                date=date,
                open=bar.open, high=bar.high, low=bar.low,
                close=bar.close, volume=bar.volume,
                name=fund.name, list_date=fund.list_date,
                market_cap=fund.market_cap,
                roe_ttm=fund.roe_ttm, ocf_ttm=fund.ocf_ttm,
                prev_close=bar.prev_close if bar.prev_close > 0 else None,
                **kw,
            ))

        return snapshots

    @staticmethod
    def _compute_bar_metrics(hist: list[Bar], kw: dict) -> None:
        """从 bar 历史计算所有价量指标，写入 kw 字典。"""
        n = len(hist)
        closes = [b.close for b in hist]
        highs = [b.high for b in hist]
        lows = [b.low for b in hist]
        volumes = [b.volume for b in hist]

        # 收益率
        if n >= 6 and closes[0] > 0:
            kw["return_5d"] = (closes[-1] - closes[-6]) / closes[-6]
        if n >= 21 and closes[0] > 0:
            kw["return_20d"] = (closes[-1] - closes[0]) / closes[0]
        if n >= 61 and closes[0] > 0:
            kw["return_60d"] = (closes[-1] - closes[-61]) / closes[-61]

        # 波动率
        daily_rets = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(1, n) if closes[i - 1] > 0
        ]
        if len(daily_rets) >= 20:
            kw["volatility_20d"] = _std(daily_rets[-20:])
        if len(daily_rets) >= 60:
            kw["volatility_60d"] = _std(daily_rets[-60:])

        # 换手率 & 平均换手率
        if volumes[-1] > 0 and n >= 1:
            avg_vol_20 = sum(volumes[max(0, n - 20):n]) / min(20, n)
            if avg_vol_20 > 0:
                kw["turnover_rate"] = volumes[-1] / avg_vol_20
                kw["avg_turnover_20d"] = avg_vol_20

        # RSI (14)
        if len(daily_rets) >= 14:
            gains = [r for r in daily_rets[-14:] if r > 0]
            losses = [-r for r in daily_rets[-14:] if r < 0]
            avg_gain = sum(gains) / 14 if gains else 0
            avg_loss = sum(losses) / 14 if losses else 0
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                kw["rsi_14"] = 100 - 100 / (1 + rs)
            else:
                kw["rsi_14"] = 100.0

        # MACD (12, 26, 9)
        if n >= 35:
            ema12 = _ema(closes, 12)
            ema26 = _ema(closes, 26)
            macd_line = ema12 - ema26
            # signal = EMA9 of MACD (近似: 用最后 9 个 MACD 值)
            if n >= 35:
                macd_vals = []
                for i in range(26, n):
                    e12 = _ema(closes[:i + 1], 12)
                    e26 = _ema(closes[:i + 1], 26)
                    macd_vals.append(e12 - e26)
                if len(macd_vals) >= 9:
                    signal = _ema(macd_vals, 9)
                    kw["macd"] = macd_line
                    kw["macd_signal"] = signal

        # 均线
        if n >= 5:
            kw["ma_5"] = sum(closes[-5:]) / 5
        if n >= 20:
            kw["ma_20"] = sum(closes[-20:]) / 20
        if n >= 60:
            kw["ma_60"] = sum(closes[-60:]) / 60

        # 20 日最高/最低
        if n >= 20:
            kw["high_20d"] = max(highs[-20:])
            kw["low_20d"] = min(lows[-20:])

        # ATR (14)
        if n >= 15:
            true_ranges = []
            for i in range(1, n):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
                true_ranges.append(tr)
            if len(true_ranges) >= 14:
                kw["atr_14"] = sum(true_ranges[-14:]) / 14

        # 偏度 (20 日)
        if len(daily_rets) >= 20:
            r20 = daily_rets[-20:]
            m = sum(r20) / len(r20)
            s = _std(r20)
            if s > 0:
                kw["skewness_20d"] = sum(((x - m) / s) ** 3 for x in r20) / len(r20)

        # 非流动性 (Amihud: |return| / volume)
        if len(daily_rets) >= 20:
            illiq_vals = []
            for i in range(max(1, n - 20), n):
                ret = abs((closes[i] - closes[i - 1]) / closes[i - 1]) if closes[i - 1] > 0 else 0
                vol = volumes[i]
                if vol > 0:
                    illiq_vals.append(ret / vol)
            if illiq_vals:
                kw["illiquidity_20d"] = sum(illiq_vals) / len(illiq_vals)

        # OBV 斜率 (20 日)
        if n >= 21:
            obv = [0.0]
            for i in range(1, n):
                if closes[i] > closes[i - 1]:
                    obv.append(obv[-1] + volumes[i])
                elif closes[i] < closes[i - 1]:
                    obv.append(obv[-1] - volumes[i])
                else:
                    obv.append(obv[-1])
            if len(obv) >= 20:
                obv_20 = obv[-20:]
                x_mean = 9.5  # mean of 0..19
                y_mean = sum(obv_20) / 20
                num = sum((i - x_mean) * (obv_20[i] - y_mean) for i in range(20))
                den = sum((i - x_mean) ** 2 for i in range(20))
                if den > 0:
                    kw["obv_slope_20d"] = num / den

    @staticmethod
    def _compute_fundamental_metrics(fund, kw: dict) -> None:
        """从 FundamentalSnapshot 传递基本面指标。"""
        kw["pe_ratio"] = fund.pe_ratio
        kw["pb_ratio"] = fund.pb_ratio
        kw["earnings_growth"] = fund.earnings_growth
        kw["revenue_growth"] = fund.revenue_growth


def _std(values: list[float]) -> float:
    """计算样本标准差。"""
    n = len(values)
    if n < 2:
        return 0.0
    m = sum(values) / n
    return (sum((x - m) ** 2 for x in values) / (n - 1)) ** 0.5


def _ema(values: list[float], period: int) -> float:
    """计算指数移动平均。"""
    if len(values) < period:
        return sum(values) / len(values) if values else 0.0
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * multiplier + ema * (1 - multiplier)
    return ema
