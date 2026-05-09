import logging
from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factors.base import Factor, FactorScorer
from src.domain.strategy.services.cross_sectional_strategy import CrossSectionalStrategy
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection

logger = logging.getLogger(__name__)

# 因子名称集合：低值高分（需要 invert）
INVERT_FACTORS = {
    # 价值/估值
    "pb_value", "pe_value", "pcf_ratio", "ps_ratio",
    # 反转/动量
    "reversal_20d", "return_5d",
    # 波动率/风险
    "low_volatility_20d", "volatility_60d", "atr_14", "skewness_20d",
    # 流动性
    "turnover", "avg_turnover_20d", "illiquidity_20d",
    # 技术
    "rsi_14", "high_20d_proximity", "price_range",
    # 杠杆
    "debt_to_equity",
}


class MultiFactorStrategy(CrossSectionalStrategy):
    """多因子选股策略。"""

    def __init__(
        self,
        factors: list[Factor],
        weights: list[float],
        top_n: int = 10,
    ) -> None:
        self._factors = factors
        self._weights = weights
        self._top_n = top_n

    @property
    def name(self) -> str:
        return "MultiFactorStrategy"

    def generate_cross_sectional_signals(
        self,
        universe: list[StockSnapshot],
        current_positions: list[Position],
        current_date: datetime,
    ) -> list[Signal]:
        if not universe or not self._factors:
            return []

        all_scores: list[dict[str, float]] = []
        for factor in self._factors:
            raw = factor.compute(universe)
            if not raw:
                logger.warning("因子 %s 无有效数据", factor.name)
                continue
            scores = FactorScorer.percentile_rank(
                raw,
                invert=(factor.name in INVERT_FACTORS),
            )
            all_scores.append(scores)

        if not all_scores:
            return []

        combined = FactorScorer.weighted_combine(all_scores, self._weights)
        if not combined:
            return []

        top_symbols = FactorScorer.rank_top_n(combined, self._top_n)
        top_set = set(top_symbols)

        signals: list[Signal] = []

        for i, symbol in enumerate(top_symbols):
            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.BUY,
                confidence_score=combined.get(symbol, 0.0),
                strategy_name=self.name,
                reason=f"MultiFactor rank #{i+1}, score={combined.get(symbol, 0):.3f}",
            ))

        for pos in current_positions:
            if pos.ticker not in top_set:
                signals.append(Signal(
                    symbol=pos.ticker,
                    direction=SignalDirection.SELL,
                    confidence_score=0.0,
                    strategy_name=self.name,
                    reason="Dropped from multi-factor top_n",
                ))

        return signals
