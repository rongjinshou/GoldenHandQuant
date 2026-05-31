from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class OptimizationResult:
    """组合优化结果值对象。

    封装优化器输出的权重分配、预期收益、风险和夏普比率。

    Attributes:
        weights: 各资产/策略的权重字典，key 为名称，value 为权重。
        expected_return: 组合预期收益率（年化）。
        expected_risk: 组合预期风险（年化波动率）。
        sharpe_ratio: 组合夏普比率。
        optimizer_name: 使用的优化器名称。
    """

    weights: dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    optimizer_name: str = ""

    @property
    def weight_sum(self) -> float:
        """权重之和。"""
        return sum(self.weights.values())

    @property
    def asset_count(self) -> int:
        """非零权重的资产数量。"""
        return sum(1 for w in self.weights.values() if abs(w) > 1e-10)

    def get_weight(self, name: str) -> float:
        """获取指定资产的权重，不存在则返回 0。"""
        return self.weights.get(name, 0.0)
