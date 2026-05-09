from typing import Protocol

from src.domain.market.value_objects.stock_snapshot import StockSnapshot


class Factor(Protocol):
    """因子接口。"""

    name: str

    def compute(self, snapshots: list[StockSnapshot]) -> dict[str, float]:
        """计算每只股票的因子原始值。"""
        ...


class FactorScorer:
    """因子打分器：百分位排名 + 加权合成。"""

    @staticmethod
    def percentile_rank(
        raw_values: dict[str, float],
        invert: bool = False,
    ) -> dict[str, float]:
        if not raw_values:
            return {}

        items = sorted(raw_values.items(), key=lambda x: x[1])
        n = len(items)

        if n == 1:
            return {items[0][0]: 0.5}

        # All values identical — no differentiation, return 0.5 for all
        if items[0][1] == items[-1][1]:
            return {symbol: 0.5 for symbol, _ in items}

        scores: dict[str, float] = {}
        for rank, (symbol, _) in enumerate(items):
            score = rank / (n - 1)
            scores[symbol] = (1.0 - score) if invert else score

        return scores

    @staticmethod
    def weighted_combine(
        factor_scores: list[dict[str, float]],
        weights: list[float],
    ) -> dict[str, float]:
        if not factor_scores:
            return {}

        common = set(factor_scores[0].keys())
        for scores in factor_scores[1:]:
            common &= set(scores.keys())

        combined: dict[str, float] = {}
        for symbol in common:
            total = sum(
                scores[symbol] * w
                for scores, w in zip(factor_scores, weights)
            )
            combined[symbol] = total

        return combined

    @staticmethod
    def rank_top_n(scores: dict[str, float], n: int) -> list[str]:
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [symbol for symbol, _ in sorted_items[:n]]
