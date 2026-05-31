from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class PriceVolumeData:
    """价量数据子对象。"""
    close: float
    open: float
    high: float
    low: float
    volume: float
    prev_close: float | None = None
    turnover_rate: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FundamentalData:
    """基本面数据子对象。"""
    market_cap: float
    roe_ttm: float | None = None
    ocf_ttm: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
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


@dataclass(frozen=True, slots=True, kw_only=True)
class TechnicalIndicators:
    """技术指标子对象。"""
    return_5d: float | None = None
    return_20d: float | None = None
    return_60d: float | None = None
    volatility_20d: float | None = None
    volatility_60d: float | None = None
    avg_turnover_20d: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    ma_5: float | None = None
    ma_20: float | None = None
    ma_60: float | None = None
    high_20d: float | None = None
    low_20d: float | None = None
    atr_14: float | None = None
    skewness_20d: float | None = None
    illiquidity_20d: float | None = None
    obv_slope_20d: float | None = None


# 字段名 → 所属子对象分组
_PRICE_VOLUME_FIELDS = {f.name for f in PriceVolumeData.__dataclass_fields__.values()}
_FUNDAMENTAL_FIELDS = {f.name for f in FundamentalData.__dataclass_fields__.values()}
_TECHNICAL_FIELDS = {f.name for f in TechnicalIndicators.__dataclass_fields__.values()}
_SUB_OBJECT_FIELDS = _PRICE_VOLUME_FIELDS | _FUNDAMENTAL_FIELDS | _TECHNICAL_FIELDS


class StockSnapshot:
    """Bar + FundamentalSnapshot 合并视图，过滤器的标准输入。

    内部拆分为 3 个子对象: PriceVolumeData, FundamentalData, TechnicalIndicators。
    通过 __getattr__/__setattr__ 保持向后兼容的 flat 访问。
    """

    __slots__ = ("symbol", "date", "name", "list_date",
                 "price_volume", "fundamental", "technical")

    def __init__(
        self,
        *,
        symbol: str,
        date: datetime,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        name: str,
        list_date: datetime,
        market_cap: float,
        # 以下为可选字段，按分组传入子对象
        roe_ttm: float | None = None,
        ocf_ttm: float | None = None,
        prev_close: float | None = None,
        pe_ratio: float | None = None,
        pb_ratio: float | None = None,
        return_5d: float | None = None,
        return_20d: float | None = None,
        return_60d: float | None = None,
        volatility_20d: float | None = None,
        volatility_60d: float | None = None,
        turnover_rate: float | None = None,
        avg_turnover_20d: float | None = None,
        rsi_14: float | None = None,
        macd: float | None = None,
        macd_signal: float | None = None,
        ma_5: float | None = None,
        ma_20: float | None = None,
        ma_60: float | None = None,
        high_20d: float | None = None,
        low_20d: float | None = None,
        atr_14: float | None = None,
        skewness_20d: float | None = None,
        illiquidity_20d: float | None = None,
        obv_slope_20d: float | None = None,
        roa_ttm: float | None = None,
        gross_margin: float | None = None,
        net_margin: float | None = None,
        asset_turnover: float | None = None,
        current_ratio: float | None = None,
        debt_to_equity: float | None = None,
        pcf_ratio: float | None = None,
        ps_ratio: float | None = None,
        dividend_yield: float | None = None,
        earnings_growth: float | None = None,
        revenue_growth: float | None = None,
        **_extra: object,
    ) -> None:
        # 核心字段直接存储
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "date", date)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "list_date", list_date)

        # 构建子对象
        object.__setattr__(self, "price_volume", PriceVolumeData(
            close=close, open=open, high=high, low=low, volume=volume,
            prev_close=prev_close, turnover_rate=turnover_rate,
        ))
        object.__setattr__(self, "fundamental", FundamentalData(
            market_cap=market_cap, roe_ttm=roe_ttm, ocf_ttm=ocf_ttm,
            pe_ratio=pe_ratio, pb_ratio=pb_ratio, roa_ttm=roa_ttm,
            gross_margin=gross_margin, net_margin=net_margin,
            asset_turnover=asset_turnover, current_ratio=current_ratio,
            debt_to_equity=debt_to_equity, pcf_ratio=pcf_ratio,
            ps_ratio=ps_ratio, dividend_yield=dividend_yield,
            earnings_growth=earnings_growth, revenue_growth=revenue_growth,
        ))
        object.__setattr__(self, "technical", TechnicalIndicators(
            return_5d=return_5d, return_20d=return_20d, return_60d=return_60d,
            volatility_20d=volatility_20d, volatility_60d=volatility_60d,
            avg_turnover_20d=avg_turnover_20d, rsi_14=rsi_14,
            macd=macd, macd_signal=macd_signal, ma_5=ma_5, ma_20=ma_20,
            ma_60=ma_60, high_20d=high_20d, low_20d=low_20d,
            atr_14=atr_14, skewness_20d=skewness_20d,
            illiquidity_20d=illiquidity_20d, obv_slope_20d=obv_slope_20d,
        ))

    def __getattr__(self, name: str) -> object:
        """向后兼容: flat 访问代理到对应子对象。"""
        if name in _PRICE_VOLUME_FIELDS:
            return getattr(self.price_volume, name)
        if name in _FUNDAMENTAL_FIELDS:
            return getattr(self.fundamental, name)
        if name in _TECHNICAL_FIELDS:
            return getattr(self.technical, name)
        raise AttributeError(f"'StockSnapshot' object has no attribute {name!r}")

    def __setattr__(self, name: str, value: object) -> None:
        """向后兼容: flat 赋值代理到对应子对象（重建 frozen 子对象）。"""
        if name in _PRICE_VOLUME_FIELDS:
            from dataclasses import replace
            object.__setattr__(
                self, "price_volume",
                replace(self.price_volume, **{name: value}),
            )
        elif name in _FUNDAMENTAL_FIELDS:
            from dataclasses import replace
            object.__setattr__(
                self, "fundamental",
                replace(self.fundamental, **{name: value}),
            )
        elif name in _TECHNICAL_FIELDS:
            from dataclasses import replace
            object.__setattr__(
                self, "technical",
                replace(self.technical, **{name: value}),
            )
        else:
            object.__setattr__(self, name, value)
