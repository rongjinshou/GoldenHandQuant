"""因子衰减分析：计算不同持有期的 IC 衰减曲线。"""

from src.domain.market.value_objects.stock_snapshot import StockSnapshot
from src.domain.strategy.factor_test.expressions import Expr
from src.domain.strategy.factor_test.ic_calculator import ICCalculator


class DecayAnalyzer:
    """因子衰减分析器。"""

    def __init__(self) -> None:
        self._ic_calculator = ICCalculator()

    def analyze(
        self,
        expression: Expr,
        snapshots_by_date: dict[str, list[StockSnapshot]],
        prices_by_date: dict[str, dict[str, float]],
        holding_periods: list[int] | None = None,
    ) -> tuple[list[int], list[float]]:
        """计算不同持有期的 IC 衰减曲线。

        Args:
            expression: 因子表达式 AST
            snapshots_by_date: {date_str: [StockSnapshot, ...]}
            prices_by_date: {date_str: {symbol: close_price}}
            holding_periods: 持有期列表，默认 [1, 5, 10, 20, 60]

        Returns:
            (periods, decay_ics) — 各持有期对应的平均 IC
        """
        if holding_periods is None:
            holding_periods = [1, 5, 10, 20, 60]

        periods: list[int] = []
        decay_ics: list[float] = []
        sorted_dates = sorted(prices_by_date.keys())
        date_to_idx = {d: i for i, d in enumerate(sorted_dates)}

        for period in holding_periods:
            # 计算该持有期的收益率
            returns_by_date: dict[str, dict[str, float]] = {}
            for date_str in sorted_dates:
                idx = date_to_idx[date_str]
                future_idx = idx + period
                if future_idx >= len(sorted_dates):
                    continue
                future_date = sorted_dates[future_idx]
                current_prices = prices_by_date[date_str]
                future_prices = prices_by_date[future_date]
                period_returns: dict[str, float] = {}
                for symbol in current_prices:
                    if symbol in future_prices and current_prices[symbol] > 0:
                        period_returns[symbol] = future_prices[symbol] / current_prices[symbol] - 1
                if period_returns:
                    returns_by_date[date_str] = period_returns

            ic_series = self._ic_calculator.calculate_ic_series(
                expression, snapshots_by_date, returns_by_date
            )
            ic_values = [ic for _, ic in ic_series]
            if ic_values:
                avg_ic = sum(ic_values) / len(ic_values)
            else:
                avg_ic = 0.0

            periods.append(period)
            decay_ics.append(avg_ic)

        return periods, decay_ics
