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
    from src.domain.strategy.factors.low_volatility_factor import LowVolatilityFactor
    from src.domain.strategy.factors.quality_factor import ROEQualityFactor
    from src.domain.strategy.factors.reversal_factor import ReversalFactor
    from src.domain.strategy.factors.value_factor import PBValueFactor, PEValueFactor
    from src.domain.strategy.services.strategies.multi_factor_strategy import MultiFactorStrategy

    weights_dict = params.get("weights", {})
    factors = []
    weights = []

    factor_map = {
        "pb_value": PBValueFactor(),
        "pe_value": PEValueFactor(),
        "quality": ROEQualityFactor(),
        "reversal": ReversalFactor(),
        "low_volatility": LowVolatilityFactor(),
    }

    for name, weight in weights_dict.items():
        if name in factor_map:
            factors.append(factor_map[name])
            weights.append(weight)

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
    description="多因子选股策略 (价值+质量+反转+低波动)",
    default_params={
        "top_n": 10,
        "weights": {
            "pb_value": 0.25,
            "quality": 0.25,
            "reversal": 0.25,
            "low_volatility": 0.25,
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
