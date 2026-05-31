from datetime import datetime

from src.domain.risk.value_objects.correlation_matrix import CorrelationMatrix


class CorrelationAnalyzer:
    """相关性分析器（纯 Python 实现）。"""

    def compute_correlation_matrix(
        self,
        strategy_returns: dict[str, list[float]],
    ) -> CorrelationMatrix:
        """计算所有策略对的相关性矩阵。

        Args:
            strategy_returns: {strategy_name: daily_returns}。
                各序列必须已对齐（同一天的收益在同一下标）。

        Returns:
            CorrelationMatrix: NxN 相关性矩阵。
        """
        names = list(strategy_returns.keys())
        n = len(names)
        returns = [strategy_returns[name] for name in names]
        sample_count = len(returns[0]) if n > 0 else 0

        matrix: list[list[float]] = []
        for i in range(n):
            row: list[float] = []
            for j in range(n):
                if i == j:
                    row.append(1.0)
                elif j < i:
                    row.append(matrix[j][i])
                else:
                    row.append(self._pearson(returns[i], returns[j]))
            matrix.append(row)

        return CorrelationMatrix(
            strategy_names=names,
            matrix=matrix,
            window_size=0,
            computed_at=datetime.now(),
            sample_count=sample_count,
        )

    def compute_rolling_correlation(
        self,
        returns_a: list[float],
        returns_b: list[float],
        window: int = 60,
    ) -> list[float]:
        """计算两个策略的滚动相关系数。

        Args:
            returns_a: 策略 A 的日收益率序列。
            returns_b: 策略 B 的日收益率序列。
            window: 滚动窗口大小（交易日数）。

        Returns:
            滚动相关系数序列（长度 = len(returns_a) - window + 1）。
        """
        n = len(returns_a)
        if n < window or len(returns_b) < window:
            return []
        result: list[float] = []
        for i in range(n - window + 1):
            chunk_a = returns_a[i : i + window]
            chunk_b = returns_b[i : i + window]
            result.append(self._pearson(chunk_a, chunk_b))
        return result

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """纯 Python 实现的皮尔逊相关系数。"""
        n = len(x)
        if n < 2:
            return 0.0
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)
        denom = (var_x * var_y) ** 0.5
        if denom == 0:
            return 0.0
        return cov / denom
