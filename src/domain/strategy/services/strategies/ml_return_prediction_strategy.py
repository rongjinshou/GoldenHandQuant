"""ML 收益预测选股策略。"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection

logger = logging.getLogger(__name__)


class _InferenceEngine(Protocol):
    """推理引擎协议（Domain 层不直接依赖 infrastructure）。"""

    def predict_batch(
        self, model_name: str, feature_dict: dict[str, list[float]]
    ) -> dict[str, float]: ...


# StockSnapshot 基础特征字段列表（仅直接属性）
_SNAPSHOT_FIELDS: list[str] = [
    "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volatility_60d",
    "turnover_rate", "avg_turnover_20d",
    "rsi_14", "macd", "macd_signal",
    "ma_5", "ma_20", "ma_60",
    "high_20d", "low_20d",
    "atr_14", "skewness_20d", "illiquidity_20d", "obv_slope_20d",
    "pe_ratio", "pb_ratio", "roe_ttm", "market_cap",
]


def _load_feature_columns_from_metadata(model_dir: str, model_name: str) -> list[str] | None:
    """从模型元数据文件中加载 feature_columns。"""
    meta_path = Path(model_dir) / model_name / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        return meta.get("feature_columns")
    except (json.JSONDecodeError, OSError):
        return None


def _compute_derived_features(snap: StockSnapshot) -> dict[str, float | None]:
    """从 StockSnapshot 计算衍生特征，与 feature_transforms.compute_derived_features 逻辑一致。"""
    close = snap.close
    ma_5 = snap.ma_5
    ma_20 = snap.ma_20
    ma_60 = snap.ma_60
    high_20d = snap.high_20d
    low_20d = snap.low_20d
    macd = snap.macd
    macd_signal = snap.macd_signal
    pb_ratio = snap.pb_ratio
    market_cap = snap.market_cap
    turnover_rate = snap.turnover_rate
    avg_turnover_20d = snap.avg_turnover_20d

    def _ratio(a: float | None, b: float | None) -> float | None:
        if a is not None and b is not None and b > 0:
            return a / b - 1.0
        return None

    derived: dict[str, float | None] = {}
    derived["close"] = close

    # 均线偏离度
    derived["close_to_ma5"] = _ratio(close, ma_5)
    derived["close_to_ma20"] = _ratio(close, ma_20)
    derived["close_to_ma60"] = _ratio(close, ma_60)

    # 均线交叉
    derived["ma5_to_ma20"] = _ratio(ma_5, ma_20)
    derived["ma20_to_ma60"] = _ratio(ma_20, ma_60)

    # 价格区间
    if high_20d is not None and low_20d is not None and close and close > 0:
        derived["high_low_range"] = (high_20d - low_20d) / close
        denom = high_20d - low_20d
        derived["close_position"] = (close - low_20d) / denom if denom > 0 else None
    else:
        derived["high_low_range"] = None
        derived["close_position"] = None

    # MACD 柱
    if macd is not None and macd_signal is not None:
        derived["macd_hist"] = macd - macd_signal
    else:
        derived["macd_hist"] = None

    # 对数市值
    if market_cap is not None and market_cap > 0:
        derived["log_market_cap"] = math.log(market_cap)
    else:
        derived["log_market_cap"] = None

    # 账面市值比
    if pb_ratio is not None and pb_ratio > 0:
        derived["bp_ratio"] = 1.0 / pb_ratio
    else:
        derived["bp_ratio"] = None

    # 波动变化率
    derived["vol_ratio_5_20"] = None

    # 异常换手率相对偏差
    if turnover_rate is not None and avg_turnover_20d is not None and avg_turnover_20d > 0:
        derived["turnover_relative_deviation"] = (turnover_rate - avg_turnover_20d) / avg_turnover_20d
    else:
        derived["turnover_relative_deviation"] = None

    return derived


class MLReturnPredictionStrategy(CrossSectionalStrategy):
    """ML 收益预测选股策略。"""

    def __init__(
        self,
        model_name: str,
        top_n: int = 10,
        min_score: float = 0.0,
        model_dir: str = "models/",
        feature_columns: list[str] | None = None,
    ) -> None:
        self._model_name = model_name
        self._top_n = top_n
        self._min_score = min_score
        self._model_dir = model_dir
        self._feature_columns = feature_columns
        self._inference: _InferenceEngine | None = None

    @property
    def name(self) -> str:
        return f"MLReturnPrediction_{self._model_name}"

    def set_inference_engine(self, engine: Any) -> None:
        """注入推理引擎（依赖注入）。"""
        self._inference = engine

    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        """ML 预测 -> 排序 -> Top N 买入 + 跌出持仓卖出。"""
        if not self._inference or not universe:
            return []

        # 1. 提取特征矩阵
        feature_dict, symbols = self._extract_features(universe)
        if not feature_dict:
            return []

        # 2. ML 推理
        scores = self._inference.predict_batch(self._model_name, feature_dict)

        # 3. 排序选取 Top N
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_symbols = [s for s, score in ranked[:self._top_n] if score >= self._min_score]
        top_set = set(top_symbols)

        # 4. 生成信号
        signals: list[Signal] = []
        for i, (symbol, score) in enumerate(ranked[:self._top_n]):
            if score < self._min_score:
                continue
            # 将回归分数映射到 [0, 1] 区间作为置信度
            confidence = min(max(score, 0.0), 1.0) if score <= 1.0 else 1.0
            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence_score=confidence,
                strategy_name=self.name,
                reason=f"ML prediction rank #{i + 1}, score={score:.4f}",
            ))

        for pos in current_positions:
            if pos.ticker not in top_set:
                signals.append(Signal(
                    symbol=pos.ticker,
                    direction=SignalDirection.SELL,
                    confidence_score=0.0,
                    strategy_name=self.name,
                    reason="Dropped from ML top_n",
                ))

        return signals

    def _extract_features(
        self, universe: list[StockSnapshot]
    ) -> tuple[dict[str, list[float]], list[str]]:
        """从 StockSnapshot 提取特征矩阵。

        优先从模型 metadata 加载 feature_columns，确保训练/推理特征一致。
        同时计算衍生特征（与 feature_transforms.compute_derived_features 逻辑一致）。
        """
        # 从 metadata 加载 feature_columns
        feature_columns = self._feature_columns
        if feature_columns is None:
            feature_columns = _load_feature_columns_from_metadata(self._model_dir, self._model_name)
        fields = feature_columns or _SNAPSHOT_FIELDS

        feature_dict: dict[str, list[float]] = {}
        for snap in universe:
            # 获取基础属性值
            base_vals: dict[str, float | None] = {}
            for f in _SNAPSHOT_FIELDS:
                base_vals[f] = getattr(snap, f, None)

            # 计算衍生特征
            derived = _compute_derived_features(snap)
            all_vals = {**base_vals, **derived}

            # 按 fields 顺序提取特征
            # 用 0 填充缺失特征，与训练时的 NaN 处理保持一致，
            # 而非直接跳过整只股票（跳过会导致推理时丢弃有效标的）。
            vals: list[float] = []
            for f in fields:
                v = all_vals.get(f)
                vals.append(float(v) if v is not None else 0.0)
            feature_dict[snap.symbol] = vals

        symbols = list(feature_dict.keys())
        return feature_dict, symbols
