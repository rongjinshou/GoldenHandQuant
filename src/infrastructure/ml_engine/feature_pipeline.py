from datetime import datetime

import numpy as np

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.bar import Bar


class FeaturePipeline:
    """从 Bar 序列提取 ML 特征。

    职责: OHLCV -> 技术指标特征向量。
    不依赖任何 ML 框架，仅使用 Python 标准库 + numpy。
    """

    @staticmethod
    def extract_features(bars: list[Bar]) -> np.ndarray:
        """从 Bar 序列提取特征向量。

        Returns:
            shape (n_bars, n_features) 的特征矩阵。
            特征包括: returns_1d, returns_5d, volatility_5d, volume_ratio, ma_divergence 等。
        """
        if len(bars) < 10:
            return np.array([])

        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])

        features = []
        for i in range(5, len(closes)):
            ret_1d = (closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] > 0 else 0
            ret_5d = (closes[i] - closes[i - 5]) / closes[i - 5] if closes[i - 5] > 0 else 0
            vol_5d = np.std(closes[i - 5:i + 1]) / closes[i] if closes[i] > 0 else 0
            avg_vol = np.mean(volumes[i - 5:i])
            vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1.0
            ma_5 = np.mean(closes[i - 5:i + 1])
            ma_div = (closes[i] - ma_5) / ma_5 if ma_5 > 0 else 0

            features.append([ret_1d, ret_5d, vol_5d, vol_ratio, ma_div])

        return np.array(features)

    @staticmethod
    def build_cross_section(
        date: datetime,
        bars: dict[str, Bar],
        registry: FundamentalRegistry,
    ) -> list:
        from src.domain.market.value_objects.stock_snapshot import StockSnapshot

        fundamentals = {s.symbol: s for s in registry.get_all_at_date(date)}
        snapshots: list[StockSnapshot] = []

        for symbol, bar in bars.items():
            fund = fundamentals.get(symbol)
            if fund is None:
                continue
            snapshots.append(StockSnapshot(
                symbol=symbol,
                date=date,
                open=bar.open, high=bar.high, low=bar.low,
                close=bar.close, volume=bar.volume,
                name=fund.name, list_date=fund.list_date,
                market_cap=fund.market_cap,
                roe_ttm=fund.roe_ttm, ocf_ttm=fund.ocf_ttm,
            ))

        return snapshots
