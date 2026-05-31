from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class CorrelationMatrix:
    """策略收益相关性矩阵。

    Attributes:
        strategy_names: 策略名称列表（矩阵行列顺序）。
        matrix: NxN 对称矩阵，matrix[i][j] = 策略 i 与策略 j 的相关系数。
        window_size: 滚动窗口大小（0 表示全样本）。
        computed_at: 计算时间。
        sample_count: 用于计算的样本数。
    """

    strategy_names: list[str]
    matrix: list[list[float]]
    window_size: int = 0
    computed_at: datetime = datetime.now()
    sample_count: int = 0

    @property
    def average_correlation(self) -> float:
        """所有策略对的平均相关系数（不含对角线）。"""
        n = len(self.strategy_names)
        if n < 2:
            return 0.0
        total = 0.0
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                total += self.matrix[i][j]
                count += 1
        return total / count if count > 0 else 0.0

    @property
    def max_correlation_pair(self) -> tuple[str, str, float]:
        """相关系数最高的策略对。"""
        n = len(self.strategy_names)
        if n < 2:
            return ("", "", 0.0)
        max_val = -2.0
        max_i, max_j = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if self.matrix[i][j] > max_val:
                    max_val = self.matrix[i][j]
                    max_i, max_j = i, j
        return (self.strategy_names[max_i], self.strategy_names[max_j], max_val)

    @property
    def min_correlation_pair(self) -> tuple[str, str, float]:
        """相关系数最低的策略对。"""
        n = len(self.strategy_names)
        if n < 2:
            return ("", "", 0.0)
        min_val = 2.0
        min_i, min_j = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if self.matrix[i][j] < min_val:
                    min_val = self.matrix[i][j]
                    min_i, min_j = i, j
        return (self.strategy_names[min_i], self.strategy_names[min_j], min_val)
