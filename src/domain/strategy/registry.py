import copy
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.domain.strategy.services.base_strategy import BaseStrategy


@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyConfig:
    """策略注册配置。"""
    name: str
    factory: Callable[[dict[str, Any]], BaseStrategy]
    strategy_type: str  # "bar" | "cross_section"
    description: str
    default_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        for field_name in self.__dataclass_fields__:
            val = getattr(self, field_name)
            if isinstance(val, (list, dict, set)):
                object.__setattr__(self, field_name, copy.deepcopy(val))


_REGISTRY: dict[str, StrategyConfig] = {}


def _register(config: StrategyConfig) -> None:
    _REGISTRY[config.name] = config


def get_strategy(name: str) -> StrategyConfig:
    """获取策略配置。不存在则抛 KeyError。"""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy: {name}")
    return _REGISTRY[name]


def list_strategies() -> list[StrategyConfig]:
    """列出所有已注册策略。"""
    return list(_REGISTRY.values())


def create_strategy(name: str, params: dict[str, Any] | None = None) -> BaseStrategy:
    """创建策略实例。"""
    config = get_strategy(name)
    merged = {**config.default_params, **(params or {})}
    return config.factory(merged)


# -- 内置策略注册 --


def _build_dual_ma(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.services.strategies.dual_ma_strategy import DualMaStrategy
    return DualMaStrategy()


def _build_micro_value(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.services.strategies.micro_value_strategy import MicroValueStrategy
    return MicroValueStrategy(top_n=params.get("top_n", 9))


def _build_multi_factor(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.factors.fundamental_factors import (
        AssetTurnoverFactor,
        CurrentRatioFactor,
        DebtToEquityFactor,
        DividendYieldFactor,
        EarningsGrowthFactor,
        GrossMarginFactor,
        NetMarginFactor,
        PCFRatioFactor,
        PSRatioFactor,
        ROAFactor,
    )
    from src.domain.strategy.factors.low_volatility_factor import LowVolatilityFactor
    from src.domain.strategy.factors.price_volume_factors import (
        ATR14Factor,
        AvgTurnover20dFactor,
        Illiquidity20dFactor,
        Return5dFactor,
        Return60dFactor,
        RSI14Factor,
        Skewness20dFactor,
        TurnoverFactor,
        Volatility60dFactor,
    )
    from src.domain.strategy.factors.price_volume_factors import (
        MACDFactor as MACDHistFactor,
    )
    from src.domain.strategy.factors.quality_factor import ROEQualityFactor
    from src.domain.strategy.factors.reversal_factor import ReversalFactor
    from src.domain.strategy.factors.technical_factors import (
        ClosePositionFactor,
        GapFactor,
        High20dProximityFactor,
        MA5CrossFactor,
        MA20CrossFactor,
        MA60CrossFactor,
        MACDCrossFactor,
        OBVSlope20dFactor,
        PriceRangeFactor,
    )
    from src.domain.strategy.factors.value_factor import PBValueFactor, PEValueFactor
    from src.domain.strategy.services.strategies.multi_factor_strategy import MultiFactorStrategy

    weights_dict = params.get("weights", {})
    factors = []
    weights = []

    factor_map = {
        # 价值因子
        "pb_value": PBValueFactor(),
        "pe_value": PEValueFactor(),
        # 质量因子
        "roe": ROEQualityFactor(),
        "roa": ROAFactor(),
        "gross_margin": GrossMarginFactor(),
        "net_margin": NetMarginFactor(),
        "asset_turnover": AssetTurnoverFactor(),
        "current_ratio": CurrentRatioFactor(),
        "debt_to_equity": DebtToEquityFactor(),
        # 估值因子
        "pcf_ratio": PCFRatioFactor(),
        "ps_ratio": PSRatioFactor(),
        "dividend_yield": DividendYieldFactor(),
        # 成长因子
        "earnings_growth": EarningsGrowthFactor(),
        # 动量/反转因子
        "return_5d": Return5dFactor(),
        "reversal": ReversalFactor(),
        "return_60d": Return60dFactor(),
        # 波动率因子
        "low_volatility": LowVolatilityFactor(),
        "volatility_60d": Volatility60dFactor(),
        "atr_14": ATR14Factor(),
        "skewness_20d": Skewness20dFactor(),
        # 流动性因子
        "turnover": TurnoverFactor(),
        "avg_turnover_20d": AvgTurnover20dFactor(),
        "illiquidity_20d": Illiquidity20dFactor(),
        # 技术因子
        "rsi_14": RSI14Factor(),
        "macd_hist": MACDHistFactor(),
        "macd_cross": MACDCrossFactor(),
        "ma5_cross": MA5CrossFactor(),
        "ma20_cross": MA20CrossFactor(),
        "ma60_cross": MA60CrossFactor(),
        "high_20d_proximity": High20dProximityFactor(),
        "obv_slope_20d": OBVSlope20dFactor(),
        "price_range": PriceRangeFactor(),
        "close_position": ClosePositionFactor(),
        "gap": GapFactor(),
    }

    for name, weight in weights_dict.items():
        if name in factor_map:
            factors.append(factor_map[name])
            weights.append(weight)

    # 加载挖掘因子
    try:
        from src.infrastructure.ml_engine.factor_repository import FactorRepository
        repo = FactorRepository()
        mined_factors = repo.list_factors(status="active", min_ir=0.5)
        for info in mined_factors:
            try:
                factor = repo.to_domain_factor(info["name"])
                factor_map[info["name"]] = factor
                default_weight = info.get("metrics", {}).get("ir", 1.0)
                weights_dict.setdefault(info["name"], default_weight)
            except Exception:
                pass
    except Exception:
        pass  # 仓库不存在时静默跳过

    if not factors:
        factors = [PBValueFactor(), ROEQualityFactor()]
        weights = [0.5, 0.5]

    return MultiFactorStrategy(
        factors=factors,
        weights=weights,
        top_n=params.get("top_n", 10),
    )


_register(StrategyConfig(
    name="multi_factor",
    factory=_build_multi_factor,
    strategy_type="cross_section",
    description="多因子选股策略 (30 因子: 价值+质量+动量+波动+技术+流动性)",
    default_params={
        "top_n": 10,
        "weights": {
            # 价值因子 (2)
            "pb_value": 1, "pe_value": 1,
            # 质量因子 (6)
            "roe": 1, "roa": 1, "gross_margin": 1, "net_margin": 1,
            "asset_turnover": 1, "current_ratio": 1,
            # 杠杆因子 (1)
            "debt_to_equity": 1,
            # 估值因子 (2)
            "pcf_ratio": 1, "ps_ratio": 1,
            # 收益/分红因子 (2)
            "dividend_yield": 1, "earnings_growth": 1,
            # 动量/反转因子 (3)
            "return_5d": 1, "reversal": 1, "return_60d": 1,
            # 波动率因子 (4)
            "low_volatility": 1, "volatility_60d": 1, "atr_14": 1, "skewness_20d": 1,
            # 流动性因子 (3)
            "turnover": 1, "avg_turnover_20d": 1, "illiquidity_20d": 1,
            # 技术因子 (7)
            "rsi_14": 1, "macd_hist": 1, "macd_cross": 1,
            "ma5_cross": 1, "ma20_cross": 1, "ma60_cross": 1,
            "high_20d_proximity": 1, "obv_slope_20d": 1,
            "price_range": 1, "close_position": 1, "gap": 1,
        },
    },
))

_register(StrategyConfig(
    name="dual_ma",
    factory=_build_dual_ma,
    strategy_type="bar",
    description="DualMa 双均线策略 (MA5/MA10 金叉死叉)",
))

_register(StrategyConfig(
    name="micro_value",
    factory=_build_micro_value,
    strategy_type="cross_section",
    description="微盘价值质量增强策略",
    default_params={"top_n": 9},
))


def _build_ml_return_prediction(params: dict[str, Any]) -> BaseStrategy:
    from src.domain.strategy.services.strategies.ml_return_prediction_strategy import (
        MLReturnPredictionStrategy,
    )
    from src.infrastructure.ml_engine.inference import InferenceEngine
    from src.infrastructure.ml_engine.model_loader import ModelLoader

    model_name = params.get("model_name", "lgbm_return_5d")
    top_n = params.get("top_n", 10)
    model_dir = params.get("model_dir", "models/")
    feature_columns = params.get("feature_columns", None)

    strategy = MLReturnPredictionStrategy(
        model_name=model_name,
        top_n=top_n,
        model_dir=model_dir,
        feature_columns=feature_columns,
    )
    loader = ModelLoader(model_dir=model_dir)
    engine = InferenceEngine(loader, model_type="lightgbm")
    strategy.set_inference_engine(engine)
    return strategy


_register(StrategyConfig(
    name="ml_return_prediction",
    factory=_build_ml_return_prediction,
    strategy_type="cross_section",
    description="ML 收益预测选股策略 (LightGBM)",
    default_params={
        "model_name": "lgbm_return_5d",
        "top_n": 10,
        "model_dir": "models/",
    },
))
