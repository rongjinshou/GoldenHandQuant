"""自动特征组合器 — 从 StockSnapshot 字段生成组合特征。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class FeatureOperator(Enum):
    """特征组合算子。"""
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    RANK = "rank"
    ZSCORE = "zscore"


@dataclass(slots=True, kw_only=True)
class CombinationRule:
    """组合规则定义。"""
    name: str
    operator: FeatureOperator
    feature_a: str
    feature_b: str | None = None
    category: str  # "same_domain" | "cross_domain" | "transform"


# 基础特征池定义
FUNDAMENTAL_FEATURES: list[str] = [
    "pe_ratio", "pb_ratio", "market_cap", "roe_ttm", "ocf_ttm",
    "roa_ttm", "gross_margin", "net_margin", "asset_turnover",
    "current_ratio", "debt_to_equity", "pcf_ratio", "ps_ratio",
    "dividend_yield", "earnings_growth", "revenue_growth",
]

PRICE_FEATURES: list[str] = [
    "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volatility_60d", "turnover_rate",
    "avg_turnover_20d", "rsi_14", "macd", "macd_signal",
    "atr_14", "skewness_20d", "illiquidity_20d", "obv_slope_20d",
]

DERIVED_FEATURES: list[str] = [
    "high_low_range", "close_position", "gap",
    "high_20d", "low_20d",
]

# 同域组合对（语义相近，组合意义大）
_SAME_DOMAIN_PAIRS: list[tuple[str, str, FeatureOperator]] = [
    # 基本面 x 基本面
    ("roe_ttm", "earnings_growth", FeatureOperator.MUL),
    ("pe_ratio", "pb_ratio", FeatureOperator.DIV),
    ("roa_ttm", "gross_margin", FeatureOperator.MUL),
    ("net_margin", "asset_turnover", FeatureOperator.MUL),
    ("earnings_growth", "revenue_growth", FeatureOperator.DIV),
    ("pe_ratio", "earnings_growth", FeatureOperator.DIV),
    ("market_cap", "roe_ttm", FeatureOperator.DIV),
    ("dividend_yield", "pe_ratio", FeatureOperator.DIV),
    # 技术 x 技术
    ("return_5d", "volatility_20d", FeatureOperator.DIV),
    ("return_20d", "volatility_20d", FeatureOperator.DIV),
    ("rsi_14", "volatility_20d", FeatureOperator.MUL),
    ("turnover_rate", "volatility_20d", FeatureOperator.DIV),
    ("return_5d", "return_20d", FeatureOperator.DIV),
    ("macd", "macd_signal", FeatureOperator.SUB),
    ("return_60d", "volatility_60d", FeatureOperator.DIV),
    ("atr_14", "volatility_20d", FeatureOperator.DIV),
    ("skewness_20d", "volatility_20d", FeatureOperator.DIV),
    ("illiquidity_20d", "turnover_rate", FeatureOperator.MUL),
    ("obv_slope_20d", "return_5d", FeatureOperator.MUL),
]

# 跨域组合对（基本面 x 技术）
_CROSS_DOMAIN_PAIRS: list[tuple[str, str, FeatureOperator]] = [
    ("return_5d", "pe_ratio", FeatureOperator.DIV),
    ("rsi_14", "pe_ratio", FeatureOperator.DIV),
    ("return_60d", "debt_to_equity", FeatureOperator.DIV),
    ("volatility_20d", "market_cap", FeatureOperator.DIV),
    ("return_5d", "roe_ttm", FeatureOperator.MUL),
    ("turnover_rate", "market_cap", FeatureOperator.DIV),
    ("return_20d", "pb_ratio", FeatureOperator.DIV),
    ("macd", "pe_ratio", FeatureOperator.DIV),
    ("return_5d", "dividend_yield", FeatureOperator.MUL),
    ("volatility_20d", "current_ratio", FeatureOperator.DIV),
]


def _extract_numeric_features(snapshots: list[StockSnapshot]) -> tuple[list[str], np.ndarray]:
    """从快照列表提取所有数值特征矩阵。"""
    all_features = FUNDAMENTAL_FEATURES + PRICE_FEATURES + DERIVED_FEATURES
    n = len(snapshots)
    matrix = np.full((n, len(all_features)), np.nan, dtype=np.float32)

    for i, snap in enumerate(snapshots):
        for j, fname in enumerate(all_features):
            val = getattr(snap, fname, None)
            if val is not None:
                matrix[i, j] = float(val)

    return all_features, matrix


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """安全除法，分母为 0 时返回 NaN。"""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(np.abs(b) > 1e-10, a / b, np.nan)
    return result.astype(np.float32)


class AutoFeatureCombiner:
    """自动特征组合器。"""

    def __init__(self) -> None:
        self._feature_names: list[str] = []
        self._rules: list[CombinationRule] = []

    def generate_combinations(
        self,
        snapshots: list[StockSnapshot],
        strategy: str = "standard",
    ) -> pd.DataFrame:
        """生成组合特征矩阵。

        Args:
            snapshots: 某一日的全市场快照。
            strategy: 组合策略 ("standard" | "aggressive" | "conservative")。

        Returns:
            DataFrame, index=symbol, columns=feature_name。
        """
        if not snapshots:
            return pd.DataFrame()

        symbols = [s.symbol for s in snapshots]
        all_feature_names, raw_matrix = _extract_numeric_features(snapshots)

        # 生成组合规则
        rules = self._generate_rules(all_feature_names, strategy)
        self._rules = rules

        # 构建特征名到列索引的映射
        feat_idx = {name: i for i, name in enumerate(all_feature_names)}

        # 应用组合规则
        combined_cols: list[np.ndarray] = []
        combined_names: list[str] = []

        # 基础特征直接加入
        for i, name in enumerate(all_feature_names):
            combined_cols.append(raw_matrix[:, i])
            combined_names.append(name)

        for rule in rules:
            idx_a = feat_idx.get(rule.feature_a)
            if idx_a is None:
                continue
            col_a = raw_matrix[:, idx_a]

            if rule.operator in (FeatureOperator.RANK, FeatureOperator.ZSCORE):
                result = self._apply_unary(col_a, rule.operator)
            else:
                idx_b = feat_idx.get(rule.feature_b) if rule.feature_b else None
                if idx_b is None:
                    continue
                col_b = raw_matrix[:, idx_b]
                result = self._apply_binary(col_a, col_b, rule.operator)

            combined_cols.append(result)
            combined_names.append(rule.name)

        self._feature_names = combined_names

        # 组装 DataFrame
        matrix = np.column_stack(combined_cols)
        return pd.DataFrame(matrix, index=symbols, columns=combined_names)

    def get_feature_names(self) -> list[str]:
        """返回所有生成的特征名称。"""
        return self._feature_names

    def get_expression(self, feature_name: str) -> str:
        """返回特征的表达式描述。"""
        for rule in self._rules:
            if rule.name == feature_name:
                if rule.feature_b:
                    return f"{rule.feature_a} {rule.operator.value} {rule.feature_b}"
                return f"{rule.operator.value}({rule.feature_a})"
        return feature_name

    def _generate_rules(
        self,
        feature_names: list[str],
        strategy: str,
    ) -> list[CombinationRule]:
        """根据策略生成组合规则。"""
        available = set(feature_names)
        rules: list[CombinationRule] = []

        # 确定组合数量限制
        if strategy == "conservative":
            max_same, max_cross, max_transform = 8, 5, 10
        elif strategy == "aggressive":
            max_same, max_cross, max_transform = 30, 20, 30
        else:  # standard
            max_same, max_cross, max_transform = 19, 10, 20

        # 同域组合
        count = 0
        for a, b, op in _SAME_DOMAIN_PAIRS:
            if count >= max_same:
                break
            if a in available and b in available:
                rules.append(CombinationRule(
                    name=f"{a}_{op.value}_{b}",
                    operator=op,
                    feature_a=a,
                    feature_b=b,
                    category="same_domain",
                ))
                count += 1

        # 跨域组合
        count = 0
        for a, b, op in _CROSS_DOMAIN_PAIRS:
            if count >= max_cross:
                break
            if a in available and b in available:
                rules.append(CombinationRule(
                    name=f"{a}_{op.value}_{b}",
                    operator=op,
                    feature_a=a,
                    feature_b=b,
                    category="cross_domain",
                ))
                count += 1

        # 变换（排名、标准化）
        transform_features = [
            f for f in feature_names
            if f in available and f not in ("high_20d", "low_20d")
        ]
        count = 0
        for fname in transform_features:
            if count >= max_transform:
                break
            rules.append(CombinationRule(
                name=f"rank_{fname}",
                operator=FeatureOperator.RANK,
                feature_a=fname,
                category="transform",
            ))
            count += 1
            if count >= max_transform:
                break
            rules.append(CombinationRule(
                name=f"zscore_{fname}",
                operator=FeatureOperator.ZSCORE,
                feature_a=fname,
                category="transform",
            ))
            count += 1

        return rules

    @staticmethod
    def _apply_binary(
        a: np.ndarray,
        b: np.ndarray,
        operator: FeatureOperator,
    ) -> np.ndarray:
        """应用二元算子。"""
        if operator == FeatureOperator.ADD:
            return (a + b).astype(np.float32)
        elif operator == FeatureOperator.SUB:
            return (a - b).astype(np.float32)
        elif operator == FeatureOperator.MUL:
            return (a * b).astype(np.float32)
        elif operator == FeatureOperator.DIV:
            return _safe_div(a, b)
        else:
            raise ValueError(f"Unsupported binary operator: {operator}")

    @staticmethod
    def _apply_unary(values: np.ndarray, operator: FeatureOperator) -> np.ndarray:
        """应用一元算子（排名或标准化）。"""
        valid_mask = ~np.isnan(values)
        result = np.full_like(values, np.nan, dtype=np.float32)

        if not np.any(valid_mask):
            return result

        valid_vals = values[valid_mask]
        n = len(valid_vals)

        if operator == FeatureOperator.RANK:
            # 百分位排名 [0, 1]
            order = valid_vals.argsort().argsort().astype(np.float32)
            if n > 1:
                order /= (n - 1)
            result[valid_mask] = order
        elif operator == FeatureOperator.ZSCORE:
            mean = np.mean(valid_vals)
            std = np.std(valid_vals)
            if std > 1e-10:
                result[valid_mask] = ((valid_vals - mean) / std).astype(np.float32)
            else:
                result[valid_mask] = 0.0
        else:
            raise ValueError(f"Unsupported unary operator: {operator}")

        return result
