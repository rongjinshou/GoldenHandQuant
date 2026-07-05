"""因子名 → StockSnapshot 字段名映射。

已注册因子名可直接在表达式中使用，系统自动映射到对应字段。
"""

from src.domain.market.value_objects.stock_snapshot import KNOWN_FIELDS


class UnknownFactorFieldError(ValueError):
    """因子表达式引用的字段名无法解析为任何已知 StockSnapshot 字段。

    F10(毛利率)教训: 未校验时，无法解析的字段被求值器静默跳过/置空，
    因子在全部日期上拿不到任何真实数据，最终以近乎全 0/NaN 的记分牌数字
    误判为"FAIL"，而非报出"这个字段根本不存在"的真实原因。
    """


FACTOR_FIELD_MAP: dict[str, str] = {
    # 价值因子
    "pb_value": "pb_ratio",
    "pe_value": "pe_ratio",
    # 质量因子
    "roe": "roe_ttm",
    "roa": "roa_ttm",
    "gross_margin": "gross_margin",
    "net_margin": "net_margin",
    "asset_turnover": "asset_turnover",
    "current_ratio": "current_ratio",
    "debt_to_equity": "debt_to_equity",
    # 估值因子
    "pcf_ratio": "pcf_ratio",
    "ps_ratio": "ps_ratio",
    "dividend_yield": "dividend_yield",
    # 成长因子
    "earnings_growth": "earnings_growth",
    "revenue_growth": "revenue_growth",
    # 动量/反转因子
    "return_5d": "return_5d",
    "reversal": "return_5d",
    "return_60d": "return_60d",
    # 波动率因子
    "low_volatility": "volatility_60d",
    "volatility_60d": "volatility_60d",
    "volatility_20d": "volatility_20d",
    "atr_14": "atr_14",
    "skewness_20d": "skewness_20d",
    # 流动性因子
    "turnover": "turnover_rate",
    "avg_turnover_20d": "avg_turnover_20d",
    "illiquidity_20d": "illiquidity_20d",
    # 技术因子
    "rsi_14": "rsi_14",
    "macd_hist": "macd",
    "macd_cross": "macd",
    "ma5_cross": "ma_5",
    "ma20_cross": "ma_20",
    "ma60_cross": "ma_60",
    "high_20d_proximity": "high_20d",
    "obv_slope_20d": "obv_slope_20d",
    "return_20d": "return_20d",
}


def resolve_field_name(name: str) -> str:
    """将因子名或字段名解析为 StockSnapshot 字段名。

    如果 name 已经是 StockSnapshot 字段名，直接返回；
    如果 name 是已注册因子名，映射到对应字段名；
    否则原样返回（由求值器处理报错）。
    """
    if name in FACTOR_FIELD_MAP:
        return FACTOR_FIELD_MAP[name]
    return name


def resolve_and_validate_field_name(name: str) -> str:
    """解析字段名，并校验解析结果确为已知 StockSnapshot 字段。

    未知字段名(拼写错误/映射表遗漏/字段从未在 StockSnapshot 声明)会在此
    立即抛出 UnknownFactorFieldError，而不是被求值器悄悄产出空结果(F10 教训)。
    """
    resolved = resolve_field_name(name)
    if resolved not in KNOWN_FIELDS:
        raise UnknownFactorFieldError(
            f"因子字段 {name!r}(解析为 {resolved!r}) 不是任何已知 StockSnapshot 字段 —— "
            f"检查因子表达式拼写，或 FACTOR_FIELD_MAP 是否需要补充映射。"
        )
    return resolved
