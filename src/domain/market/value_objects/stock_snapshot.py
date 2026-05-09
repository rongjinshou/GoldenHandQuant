from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class StockSnapshot:
    """Bar + FundamentalSnapshot 合并视图，过滤器的标准输入。"""
    symbol: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    name: str
    list_date: datetime
    market_cap: float
    roe_ttm: float | None = None
    ocf_ttm: float | None = None
    prev_close: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None

    # 价量因子（由 FeaturePipeline 从 bar 历史计算）
    return_5d: float | None = None        # 5 日收益率
    return_20d: float | None = None       # 20 日收益率
    return_60d: float | None = None       # 60 日收益率
    volatility_20d: float | None = None   # 20 日波动率
    volatility_60d: float | None = None   # 60 日波动率
    turnover_rate: float | None = None    # 换手率
    avg_turnover_20d: float | None = None # 20 日平均换手率
    rsi_14: float | None = None           # 14 日 RSI
    macd: float | None = None             # MACD
    macd_signal: float | None = None      # MACD 信号线
    ma_5: float | None = None             # 5 日均线
    ma_20: float | None = None            # 20 日均线
    ma_60: float | None = None            # 60 日均线
    high_20d: float | None = None         # 20 日最高价
    low_20d: float | None = None          # 20 日最低价
    atr_14: float | None = None           # 14 日 ATR
    skewness_20d: float | None = None     # 20 日偏度
    illiquidity_20d: float | None = None  # 20 日非流动性 (Amihud)
    obv_slope_20d: float | None = None    # 20 日 OBV 斜率

    # 基本面因子（由 FeaturePipeline 从 FundamentalSnapshot 传递）
    roa_ttm: float | None = None
    gross_margin: float | None = None
    net_margin: float | None = None
    asset_turnover: float | None = None
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    pcf_ratio: float | None = None
    ps_ratio: float | None = None
    dividend_yield: float | None = None
    earnings_growth: float | None = None
    revenue_growth: float | None = None
