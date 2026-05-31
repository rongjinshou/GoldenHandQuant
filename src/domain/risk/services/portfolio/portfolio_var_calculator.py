from datetime import datetime

from src.domain.risk.value_objects.var_result import VaRResult


class PortfolioVaRCalculator:
    """组合 VaR 计算器。"""

    def calculate_historical_var(
        self,
        portfolio_returns: list[float],
        portfolio_value: float,
        confidence_level: float = 0.95,
        holding_period: int = 1,
    ) -> VaRResult:
        """历史模拟法计算 VaR。

        Args:
            portfolio_returns: 组合日收益率序列。
            portfolio_value: 组合当前总价值。
            confidence_level: 置信水平（默认 95%）。
            holding_period: 持有期天数（默认 1 天）。

        Returns:
            VaRResult: VaR 计算结果。
        """
        if not portfolio_returns:
            return VaRResult(
                confidence_level=confidence_level,
                method="historical",
                var_absolute=0.0,
                var_percentage=0.0,
                cvar=0.0,
                holding_period=holding_period,
                portfolio_value=portfolio_value,
                computed_at=datetime.now(),
            )

        alpha = 1.0 - confidence_level
        var_pct = -self._percentile(portfolio_returns, alpha)

        # 持有期调整: sqrt(N)
        if holding_period > 1:
            var_pct *= holding_period**0.5

        var_abs = var_pct * portfolio_value

        # CVaR: 均值 of returns <= -var_pct
        threshold = -var_pct
        tail = [r for r in portfolio_returns if r <= threshold]
        cvar_pct = -sum(tail) / len(tail) if tail else var_pct
        if holding_period > 1:
            cvar_pct *= holding_period**0.5

        return VaRResult(
            confidence_level=confidence_level,
            method="historical",
            var_absolute=var_abs,
            var_percentage=var_pct,
            cvar=cvar_pct,
            holding_period=holding_period,
            portfolio_value=portfolio_value,
            computed_at=datetime.now(),
        )

    def calculate_parametric_var(
        self,
        portfolio_returns: list[float],
        portfolio_value: float,
        confidence_level: float = 0.95,
        holding_period: int = 1,
    ) -> VaRResult:
        """参数法计算 VaR（假设正态分布）。"""
        if not portfolio_returns:
            return VaRResult(
                confidence_level=confidence_level,
                method="parametric",
                var_absolute=0.0,
                var_percentage=0.0,
                cvar=0.0,
                holding_period=holding_period,
                portfolio_value=portfolio_value,
                computed_at=datetime.now(),
            )

        n = len(portfolio_returns)
        mu = sum(portfolio_returns) / n
        variance = sum((r - mu) ** 2 for r in portfolio_returns) / (n - 1) if n > 1 else 0.0
        sigma = variance**0.5

        z = self._z_score(confidence_level)
        var_pct = -(mu - z * sigma)

        if holding_period > 1:
            var_pct *= holding_period**0.5

        var_abs = var_pct * portfolio_value

        # 参数法 CVaR (正态分布): E[X | X < -VaR] = mu - sigma * phi(z) / (1-confidence)
        # 简化近似: CVaR ≈ VaR * 1.1 (正态分布下)
        cvar_pct = var_pct * 1.1

        return VaRResult(
            confidence_level=confidence_level,
            method="parametric",
            var_absolute=var_abs,
            var_percentage=var_pct,
            cvar=cvar_pct,
            holding_period=holding_period,
            portfolio_value=portfolio_value,
            computed_at=datetime.now(),
        )

    def calculate_portfolio_returns(
        self,
        strategy_returns: dict[str, list[float]],
        weights: dict[str, float],
    ) -> list[float]:
        """从各策略日收益率和权重计算组合日收益率。

        portfolio_return_i = sum(wj * rj_i)

        Args:
            strategy_returns: {strategy_name: daily_returns}。
            weights: {strategy_name: weight}。

        Returns:
            组合日收益率序列。
        """
        names = list(strategy_returns.keys())
        if not names:
            return []
        length = len(strategy_returns[names[0]])
        result: list[float] = []
        for i in range(length):
            total = 0.0
            for name in names:
                total += weights.get(name, 0.0) * strategy_returns[name][i]
            result.append(total)
        return result

    @staticmethod
    def _percentile(data: list[float], p: float) -> float:
        """纯 Python 实现的百分位数计算。"""
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])

    @staticmethod
    def _z_score(confidence_level: float) -> float:
        """常用置信水平对应的 z 分位数（查表法）。

        仅支持 0.90, 0.95, 0.99 三个常用值，避免复杂的逆误差函数计算。
        """
        table = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
        return table.get(confidence_level, 1.645)
