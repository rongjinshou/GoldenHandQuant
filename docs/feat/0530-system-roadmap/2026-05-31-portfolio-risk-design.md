# 组合风险管理 -- 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**所属阶段**: Phase 3 -- 多策略组合 (子项目 3.3)
**状态**: 草案

---

## 一、需求概述

### 1.1 背景

当前系统的风控体系（`src/domain/risk/`）聚焦于**单策略、单账户**层面：回撤熔断（`DrawdownPolicy`）、仓位上限（`PositionLimitPolicy`）、绝对止损（`HardStopLossPolicy`）、涨停破板（`LimitUpBreakPolicy`）、系统级门禁（`SystemRiskGate`）。这些策略在单策略运行时足够有效。

但在多策略组合场景下，存在以下盲区：

- 两个策略各自回撤 15%，但因为高度相关，组合回撤可能达到 28%（而非预期的分散效果）
- 组合层面的 VaR 无法从单一策略风控中推导
- 极端行情下策略间相关性会急剧上升（"危机时所有资产同跌"）
- ML 模型过拟合或特征漂移可能导致策略突然失效

### 1.2 核心目标

**组合最大回撤 < 单一策略最大回撤的 70%**。

### 1.3 核心能力

| # | 能力 | 优先级 | 依赖 |
|---|------|--------|------|
| 1 | 相关性分析（策略收益的皮尔逊相关 + 滚动相关） | P0 | ComparisonReport (策略对比) |
| 2 | 分散度评估（分散比率、有效策略数） | P0 | 相关性分析 |
| 3 | 组合 VaR（历史模拟法 + 参数法） | P0 | 相关性分析、CapitalAllocationEngine |
| 4 | 压力测试（历史场景 + 假设场景） | P1 | VaR、BacktestReport |
| 5 | ML 模型风险监控（过拟合检测 + 特征漂移） | P1 | StrategyPoolEntry |

### 1.4 与现有系统的关系

```
现有: ComparisonReport      -- 提供策略间相关性矩阵（一次性计算）
新增: PortfolioRiskService  -- 持续监控组合风险（滚动窗口 + 实时告警）
关联: CapitalAllocationEngine -- 提供策略权重，用于组合收益计算
关联: StrategyPoolEntry     -- 提供 ML 模型版本信息
关联: BacktestReport        -- 提供各策略日收益率序列
```

---

## 二、现有架构分析

### 2.1 已有风控组件

| 组件 | 文件 | 职责 | 组合层面缺口 |
|------|------|------|-------------|
| `BaseRiskPolicy` | `src/domain/risk/services/base_risk_policy.py` | 订单级风控接口 | 仅检查单个订单 |
| `RiskChain` | `src/domain/risk/services/risk_chain.py` | 责任链模式串联多个策略 | 仅串联，不感知组合 |
| `DrawdownPolicy` | `src/domain/risk/services/risk_policies/drawdown_policy.py` | 单账户回撤熔断 | 不感知其他策略的回撤 |
| `PositionLimitPolicy` | `src/domain/risk/services/risk_policies/position_limit_policy.py` | 单标的仓位上限 | 不感知跨策略的标的重叠 |
| `HardStopLossPolicy` | `src/domain/risk/services/risk_policies/hard_stop_loss_policy.py` | 单持仓绝对止损 | 无组合级止损 |
| `SystemRiskGate` | `src/domain/risk/services/system_risk_gate.py` | 基于大盘 MA20 的系统门禁 | 功能完整，可复用 |
| `RiskSignalGenerator` | `src/domain/risk/services/risk_signal_generator.py` | 盘后风控信号聚合 | 仅聚合信号，不分析组合 |
| `BaseRiskSignalPolicy` | `src/domain/risk/services/base_risk_signal_policy.py` | 盘后风控信号策略接口 | 仅单策略持仓评估 |

### 2.2 相关组件

| 组件 | 文件 | 与组合风控的关系 |
|------|------|-----------------|
| `BacktestReport` | `src/domain/backtest/entities/backtest_report.py` | 提供 `daily_returns`、`equity_curve`、`snapshots` |
| `ComparisonReport` | (待实现) 策略对比面板 | 提供 `correlation_matrix`、`aligned_equity_curves` |
| `CapitalAllocationEngine` | (待实现) 资金分配引擎 | 提供各策略权重 `AllocationResult` |
| `StrategyPoolEntry` | (待实现) 策略池管理 | 提供 ML 模型版本元数据 |
| `PerformanceEvaluator` | `src/domain/backtest/services/performance_evaluator.py` | 聚合快照到报告 |

### 2.3 关键约束

1. **Domain 红线**：`src/domain/` 禁止 import numpy/scipy/pandas。相关性、VaR 计算必须用纯 Python。
2. **数据类型**：Python 3.13+，`@dataclass(slots=True, kw_only=True)`，`list[X]` / `dict[K,V]` / `X | None`。
3. **不可变值对象**：计算结果采用 `frozen=True`，保证快照可信度。
4. **与策略对比的关系**：`ComparisonReport` 提供一次性相关性矩阵，`PortfolioRiskService` 提供滚动监控，两者互补。

---

## 三、领域模型设计

### 3.1 整体结构

```
src/domain/risk/
  services/
    portfolio/
      __init__.py
      correlation_analyzer.py        # 相关性分析器
      diversification_evaluator.py   # 分散度评估器
      portfolio_var_calculator.py    # 组合 VaR 计算器
      stress_test_runner.py          # 压力测试运行器
      ml_model_risk_monitor.py       # ML 模型风险监控器
      portfolio_risk_service.py      # 组合风控服务（聚合入口）
      stress_scenarios/
        __init__.py
        historical_scenarios.py      # 历史极端行情场景
        hypothetical_scenarios.py    # 假设场景
  value_objects/
    correlation_matrix.py            # 相关性矩阵值对象
    diversification_result.py        # 分散度评估结果
    var_result.py                    # VaR 计算结果
    stress_test_result.py            # 压力测试结果
    ml_risk_alert.py                 # ML 风险告警值对象
    portfolio_risk_report.py         # 组合风控报告（聚合）
```

### 3.2 核心值对象

#### `CorrelationMatrix` -- 相关性矩阵

```python
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
    computed_at: datetime
    sample_count: int

    @property
    def average_correlation(self) -> float:
        """所有策略对的平均相关系数（不含对角线）。"""
        ...

    @property
    def max_correlation_pair(self) -> tuple[str, str, float]:
        """相关系数最高的策略对。"""
        ...

    @property
    def min_correlation_pair(self) -> tuple[str, str, float]:
        """相关系数最低的策略对。"""
        ...
```

#### `DiversificationResult` -- 分散度评估结果

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class DiversificationResult:
    """组合分散度评估结果。

    Attributes:
        diversification_ratio: 分散比率 = 组合波动率 / 加权平均波动率。值越大分散效果越好。
        effective_strategies: 有效策略数（基于权重集中度的 Herfindahl 指数）。
        concentration_index: 权重集中度（HHI，0-1，越低越分散）。
        max_pairwise_correlation: 最高策略对相关系数。
        is_well_diversified: 是否充分分散（分散比率 > 1.2 且 HHI < 0.25）。
    """
    diversification_ratio: float
    effective_strategies: float
    concentration_index: float
    max_pairwise_correlation: float
    is_well_diversified: bool
```

#### `VaRResult` -- VaR 计算结果

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class VaRResult:
    """组合风险价值（VaR）计算结果。

    Attributes:
        confidence_level: 置信水平（如 0.95、0.99）。
        method: 计算方法（"historical" 或 "parametric"）。
        var_absolute: 绝对 VaR（损失金额）。
        var_percentage: 百分比 VaR（损失比例）。
        cvar: 条件 VaR（Expected Shortfall，尾部平均损失）。
        holding_period: 持有期（天数）。
        portfolio_value: 组合总价值。
        computed_at: 计算时间。
    """
    confidence_level: float
    method: str
    var_absolute: float
    var_percentage: float
    cvar: float
    holding_period: int
    portfolio_value: float
    computed_at: datetime
```

#### `StressTestResult` -- 压力测试结果

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class StressTestResult:
    """单个压力测试场景的结果。

    Attributes:
        scenario_name: 场景名称。
        scenario_type: 场景类型（"historical" 或 "hypothetical"）。
        description: 场景描述。
        portfolio_loss: 组合损失（百分比）。
        strategy_losses: 各策略的损失 {strategy_name: loss_percentage}。
        max_drawdown_under_stress: 压力期间最大回撤。
        recovery_days: 预计恢复天数（-1 表示无法恢复）。
        passed: 是否通过压力测试（组合损失 < 阈值）。
    """
    scenario_name: str
    scenario_type: str
    description: str
    portfolio_loss: float
    strategy_losses: dict[str, float]
    max_drawdown_under_stress: float
    recovery_days: int
    passed: bool
```

#### `MLRiskAlert` -- ML 风险告警

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class MLRiskAlert:
    """ML 模型风险告警。

    Attributes:
        strategy_name: 策略名称。
        alert_type: 告警类型（"overfitting"、"feature_drift"、"performance_degradation"）。
        severity: 严重程度（"warning"、"critical"）。
        metric_name: 触发告警的指标名称。
        metric_value: 指标当前值。
        threshold: 告警阈值。
        description: 告警描述。
        detected_at: 检测时间。
    """
    strategy_name: str
    alert_type: str
    severity: str
    metric_name: str
    metric_value: float
    threshold: float
    description: str
    detected_at: datetime
```

#### `PortfolioRiskReport` -- 组合风控报告

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PortfolioRiskReport:
    """组合风控综合报告。

    Attributes:
        computed_at: 计算时间。
        strategy_count: 参与组合的策略数。
        correlation: 相关性矩阵。
        diversification: 分散度评估。
        var_95: 95% 置信水平 VaR。
        var_99: 99% 置信水平 VaR。
        stress_tests: 压力测试结果列表。
        ml_alerts: ML 风险告警列表。
        overall_risk_level: 整体风险等级（"low"、"medium"、"high"、"critical"）。
        recommendations: 风险建议列表。
    """
    computed_at: datetime
    strategy_count: int
    correlation: CorrelationMatrix
    diversification: DiversificationResult
    var_95: VaRResult
    var_99: VaRResult
    stress_tests: list[StressTestResult]
    ml_alerts: list[MLRiskAlert]
    overall_risk_level: str
    recommendations: list[str]
```

---

## 四、相关性分析设计

### 4.1 约束

Domain 层禁止 numpy/scipy，相关性计算必须使用纯 Python。

### 4.2 皮尔逊相关系数

```
r = Σ[(xi - x̄)(yi - ȳ)] / sqrt[Σ(xi - x̄)² × Σ(yi - ȳ)²]
```

其中 xi、yi 是两个策略在第 i 个交易日的日收益率。

```python
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
        ...

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
        ...

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
```

### 4.3 时间对齐

多策略的日收益率序列可能长度不同。对齐逻辑：

1. 各策略的 `BacktestReport.dates` 取交集。
2. 仅在公共日期上计算相关性。
3. 若公共日期 < 30，输出警告 "样本不足，相关性不可靠"。
4. 对齐工作由 `CorrelationAnalyzer` 内部处理，调用方传入已对齐的收益率字典。

### 4.4 滚动相关性的意义

- **全样本相关性**：衡量策略之间的长期关系。
- **60 日滚动相关性**：捕捉相关性的时变特征。危机期间相关性会急剧上升（"相关性崩溃"），这是组合风控的关键信号。
- **告警规则**：任意两个策略的 60 日滚动相关系数 > 0.7 时，触发 "相关性过高" 告警。

---

## 五、分散度评估设计

### 5.1 分散比率 (Diversification Ratio)

```
DR = Σ(wi × σi) / σp
```

- wi：策略 i 的权重
- σi：策略 i 的波动率（日收益率标准差，年化）
- σp：组合波动率（考虑相关性）
- DR = 1 表示无分散效果（所有策略完全正相关）
- DR > 1.2 表示有效分散

### 5.2 有效策略数 (Effective Number of Strategies)

基于权重的 Herfindahl-Hirschman Index (HHI)：

```
HHI = Σ(wi²)
N_eff = 1 / HHI
```

- 等权 3 策略：HHI = 1/3, N_eff = 3.0
- 90%/5%/5% 分配：HHI = 0.815, N_eff = 1.23
- HHI < 0.25 表示权重分配足够分散

### 5.3 实现

```python
class DiversificationEvaluator:
    """分散度评估器。"""

    def evaluate(
        self,
        weights: dict[str, float],
        volatilities: dict[str, float],
        correlation: CorrelationMatrix,
    ) -> DiversificationResult:
        """评估组合的分散程度。

        Args:
            weights: {strategy_name: weight}，权重之和应为 1.0。
            volatilities: {strategy_name: annualized_volatility}。
            correlation: 策略间相关性矩阵。

        Returns:
            DiversificationResult: 分散度评估结果。
        """
        ...
```

### 5.4 组合波动率计算

```
σp = sqrt(w^T × Σ × w)
```

其中 Σ 是协方差矩阵，Σ[i][j] = ρ[i][j] × σi × σj。

纯 Python 实现：双重循环计算二次型。

---

## 六、组合 VaR 设计

### 6.1 两种方法

#### 方法 1：历史模拟法 (Historical Simulation)

不假设收益分布，直接使用历史收益率的分位数。

```
VaR_α = -percentile(portfolio_returns, α)
```

- 优点：不需要分布假设，捕捉尾部风险
- 缺点：依赖历史数据的代表性

#### 方法 2：参数法 (Parametric / Variance-Covariance)

假设收益服从正态分布。

```
VaR_α = -(μ_p - z_α × σ_p) × portfolio_value
```

- μ_p：组合日均收益率
- σ_p：组合日波动率
- z_α：标准正态分布的 α 分位数（95% → 1.645，99% → 2.326）

### 6.2 条件 VaR (CVaR / Expected Shortfall)

CVaR = 超过 VaR 阈值后的平均损失。

```
CVaR_α = -mean(portfolio_returns[portfolio_returns <= -VaR_α])
```

CVaR 比 VaR 更好地衡量尾部风险。

### 6.3 持有期调整

日 VaR 调整为 N 日 VaR：

```
VaR_N = VaR_1 × sqrt(N)
```

这是标准的 "平方根时间" 规则（假设收益独立同分布）。

### 6.4 实现

```python
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
        ...

    def calculate_parametric_var(
        self,
        portfolio_returns: list[float],
        portfolio_value: float,
        confidence_level: float = 0.95,
        holding_period: int = 1,
    ) -> VaRResult:
        """参数法计算 VaR（假设正态分布）。"""
        ...

    def calculate_portfolio_returns(
        self,
        strategy_returns: dict[str, list[float]],
        weights: dict[str, float],
    ) -> list[float]:
        """从各策略日收益率和权重计算组合日收益率。

        portfolio_return_i = Σ(wj × rj_i)

        Args:
            strategy_returns: {strategy_name: daily_returns}。
            weights: {strategy_name: weight}。

        Returns:
            组合日收益率序列。
        """
        ...

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
```

### 6.5 与资金分配引擎的集成

`PortfolioVaRCalculator.calculate_portfolio_returns` 需要各策略权重，这些权重来自 `CapitalAllocationEngine` 的 `AllocationResult`。两者通过 `weights` 字典解耦，无需直接依赖。

---

## 七、压力测试设计

### 7.1 历史场景

基于 A 股历史极端行情设计场景，每个场景定义一个时间区间和对应的基准跌幅：

| 场景 | 时间区间 | 基准跌幅 | 特征 |
|------|---------|---------|------|
| 2015 股灾 | 2015-06-12 ~ 2015-07-09 | -43% | 杠杆崩盘、流动性枯竭、千股跌停 |
| 2018 熊市 | 2018-01-29 ~ 2018-12-28 | -30% | 贸易摩擦、去杠杆、持续阴跌 |
| 2020 新冠 | 2020-01-20 ~ 2020-03-23 | -16% | 外部冲击、全球联动、快速下跌后 V 型反弹 |
| 2022 调整 | 2022-01-04 ~ 2022-10-31 | -27% | 俄乌冲突、疫情反复、地产风险 |

**实现方式**：每个历史场景是一个值对象，包含场景元数据和基准收益率序列。压力测试运行器将各策略在场景期间的实际表现（从 BacktestReport 中提取）作为压力结果。

### 7.2 假设场景

不依赖历史数据，通过参数化方式构造假设冲击：

| 场景 | 冲击方式 | 参数 |
|------|---------|------|
| 市场暴跌 | 所有策略收益率同时乘以一个冲击系数 | shock_factor = -0.10 |
| 相关性崩溃 | 将相关性矩阵中所有非对角元素设为 0.9 | crisis_correlation = 0.9 |
| 流动性危机 | 高换手策略额外承受 2x 滑点惩罚 | liquidity_penalty = 2.0 |
| 策略失效 | 某个策略突然收益率降为 -5%/天 |失效天数 = 5 |
| ML 模型失效 | ML 策略预测完全随机，收益率为 0 | duration = 20 天 |

### 7.3 实现

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class StressScenario:
    """压力测试场景定义。

    Attributes:
        name: 场景名称。
        scenario_type: "historical" 或 "hypothetical"。
        description: 场景描述。
        date_range: 历史场景的时间区间（假设场景为空）。
        shock_params: 假设场景的冲击参数（历史场景为空）。
    """
    name: str
    scenario_type: str
    description: str
    date_range: tuple[datetime, datetime] | None = None
    shock_params: dict[str, float] = field(default_factory=dict)


class StressTestRunner:
    """压力测试运行器。"""

    def __init__(
        self,
        historical_scenarios: list[StressScenario] | None = None,
        hypothetical_scenarios: list[StressScenario] | None = None,
        loss_threshold: float = 0.15,  # 组合损失 > 15% 则不通过
    ) -> None:
        self._historical = historical_scenarios or []
        self._hypothetical = hypothetical_scenarios or []
        self._loss_threshold = loss_threshold

    def run_historical(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
    ) -> list[StressTestResult]:
        """运行历史场景压力测试。

        从各策略的 BacktestReport 中提取场景期间的收益率，
        按权重加权得到组合在该场景下的表现。

        Args:
            strategy_reports: {strategy_name: BacktestReport}。
            weights: {strategy_name: weight}。

        Returns:
            各历史场景的测试结果。
        """
        ...

    def run_hypothetical(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
        correlation: CorrelationMatrix,
    ) -> list[StressTestResult]:
        """运行假设场景压力测试。

        根据场景参数构造假设冲击，评估组合表现。

        Args:
            strategy_reports: {strategy_name: BacktestReport}。
            weights: {strategy_name: weight}。
            correlation: 当前相关性矩阵。

        Returns:
            各假设场景的测试结果。
        """
        ...

    def run_all(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
        correlation: CorrelationMatrix,
    ) -> list[StressTestResult]:
        """运行全部压力测试场景。"""
        historical = self.run_historical(strategy_reports, weights)
        hypothetical = self.run_hypothetical(strategy_reports, weights, correlation)
        return historical + hypothetical
```

### 7.4 历史场景数据来源

历史场景的基准收益率序列需要预置数据。两种方案：

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| A: 硬编码 | 将 4 个历史场景的关键日期和跌幅直接写在代码中 | 简单，但不灵活 |
| B: 外部配置 | 从 YAML/JSON 文件加载场景定义 | 灵活，但增加 I/O 依赖 |

**选定方案 A**：场景数量有限（4 个），硬编码在 `historical_scenarios.py` 中。场景的基准跌幅用于判断 "通过/不通过"，实际组合表现从 BacktestReport 中提取。

---

## 八、ML 模型风险监控设计

### 8.1 过拟合检测

过拟合的核心信号：训练集表现远好于测试集。

**检测指标**：

| 指标 | 计算方式 | 告警阈值 |
|------|---------|---------|
| IC 衰减率 | (train_IC - test_IC) / train_IC | > 50% |
| 夏普衰减率 | (train_sharpe - test_sharpe) / train_sharpe | > 40% |
| 胜率衰减 | train_win_rate - test_win_rate | > 15% |

```python
class MLModelRiskMonitor:
    """ML 模型风险监控器。"""

    def check_overfitting(
        self,
        strategy_name: str,
        train_metrics: dict[str, float],
        test_metrics: dict[str, float],
    ) -> list[MLRiskAlert]:
        """检测过拟合风险。

        比较训练集和测试集的关键指标（IC、夏普、胜率），
        若衰减超过阈值则生成告警。

        Args:
            strategy_name: 策略名称。
            train_metrics: 训练集指标 {"ic": 0.08, "sharpe": 2.0, "win_rate": 0.65}。
            test_metrics: 测试集指标 {"ic": 0.03, "sharpe": 0.8, "win_rate": 0.48}。

        Returns:
            过拟合告警列表（可能为空）。
        """
        ...
```

### 8.2 特征漂移监控

特征漂移：线上数据的特征分布与训练时不同。

**纯 Python 实现**（不依赖 scipy 的 KS 检验）：

采用均值偏移 + 方差比方法：

```
mean_shift = |mean_online - mean_train| / std_train
variance_ratio = std_online / std_train
```

| 指标 | 告警阈值 | 严重阈值 |
|------|---------|---------|
| mean_shift | > 1.0 | > 2.0 |
| variance_ratio | < 0.5 或 > 2.0 | < 0.3 或 > 3.0 |

```python
    def check_feature_drift(
        self,
        strategy_name: str,
        feature_name: str,
        train_mean: float,
        train_std: float,
        online_mean: float,
        online_std: float,
    ) -> MLRiskAlert | None:
        """检测单个特征的分布漂移。

        Args:
            strategy_name: 策略名称。
            feature_name: 特征名称。
            train_mean: 训练集均值。
            train_std: 训练集标准差。
            online_mean: 线上数据均值。
            online_std: 线上数据标准差。

        Returns:
            若触发告警返回 MLRiskAlert，否则返回 None。
        """
        ...
```

### 8.3 策略表现退化检测

持续监控策略的滚动表现指标，检测突然退化：

| 指标 | 检测方式 | 告警阈值 |
|------|---------|---------|
| 滚动夏普（60 日） | 当前值 < 历史均值 - 2σ | z-score < -2 |
| 滚动胜率（20 日） | 当前值 < 历史均值 - 2σ | z-score < -2 |
| 连续亏损天数 | 连续亏损的交易日数 | >= 5 天 |

```python
    def check_performance_degradation(
        self,
        strategy_name: str,
        rolling_sharpe: list[float],
        rolling_win_rate: list[float],
        consecutive_loss_days: int,
    ) -> list[MLRiskAlert]:
        """检测策略表现退化。

        Args:
            strategy_name: 策略名称。
            rolling_sharpe: 60 日滚动夏普比率序列。
            rolling_win_rate: 20 日滚动胜率序列。
            consecutive_loss_days: 连续亏损天数。

        Returns:
            表现退化告警列表。
        """
        ...
```

### 8.4 与 StrategyPoolEntry 的关系

`MLModelRiskMonitor` 的检测结果（告警列表）可以反馈给 `StrategyPoolEntry`：

- `critical` 级别的过拟合告警 → 触发策略 SUSPENDED 状态
- 连续 `warning` 级别的特征漂移 → 触发模型重训练建议
- 表现退化告警 → 影响策略评级

两者通过 `MLRiskAlert` 值对象解耦，`PoolManager` 负责根据告警调整策略状态。

---

## 九、组合风控服务（聚合入口）

### 9.1 PortfolioRiskService

聚合所有组合风控能力的统一入口：

```python
class PortfolioRiskService:
    """组合风控服务 -- 聚合入口。

    协调相关性分析、分散度评估、VaR 计算、压力测试、ML 风险监控，
    生成综合的 PortfolioRiskReport。
    """

    def __init__(
        self,
        correlation_analyzer: CorrelationAnalyzer | None = None,
        diversification_evaluator: DiversificationEvaluator | None = None,
        var_calculator: PortfolioVaRCalculator | None = None,
        stress_test_runner: StressTestRunner | None = None,
        ml_risk_monitor: MLModelRiskMonitor | None = None,
        var_confidence_levels: list[float] | None = None,
    ) -> None:
        self._correlation = correlation_analyzer or CorrelationAnalyzer()
        self._diversification = diversification_evaluator or DiversificationEvaluator()
        self._var = var_calculator or PortfolioVaRCalculator()
        self._stress = stress_test_runner or StressTestRunner()
        self._ml_risk = ml_risk_monitor or MLModelRiskMonitor()
        self._confidence_levels = var_confidence_levels or [0.95, 0.99]

    def generate_report(
        self,
        strategy_reports: dict[str, BacktestReport],
        weights: dict[str, float],
    ) -> PortfolioRiskReport:
        """生成组合风控综合报告。

        流程：
        1. 计算相关性矩阵
        2. 评估分散度
        3. 计算 VaR（95% 和 99%）
        4. 运行压力测试
        5. 检查 ML 风险（若有 ML 策略数据）
        6. 综合评定风险等级
        7. 生成风险建议

        Args:
            strategy_reports: {strategy_name: BacktestReport}。
            weights: {strategy_name: weight}。

        Returns:
            PortfolioRiskReport: 组合风控综合报告。
        """
        ...

    def assess_risk_level(
        self,
        diversification: DiversificationResult,
        var_95: VaRResult,
        stress_tests: list[StressTestResult],
        ml_alerts: list[MLRiskAlert],
    ) -> str:
        """综合评定风险等级。

        规则：
        - critical: 任一压力测试不通过 OR 有 critical 级 ML 告警
        - high: VaR_95 > 5% OR 分散度不足 (HHI > 0.4)
        - medium: VaR_95 > 3% OR 有 warning 级 ML 告警
        - low: 其他情况
        """
        ...

    def generate_recommendations(
        self,
        correlation: CorrelationMatrix,
        diversification: DiversificationResult,
        var_95: VaRResult,
        stress_tests: list[StressTestResult],
        ml_alerts: list[MLRiskAlert],
    ) -> list[str]:
        """生成风险建议。

        根据各维度的评估结果，生成可操作的建议文本。
        """
        ...
```

### 9.2 风险等级评定规则

| 等级 | 条件 | 建议动作 |
|------|------|---------|
| `low` | 所有指标正常 | 维持现状 |
| `medium` | VaR_95 > 3% 或有 warning 告警 | 关注监控，考虑调整权重 |
| `high` | VaR_95 > 5% 或分散度不足 | 降低高相关策略权重，增加对冲 |
| `critical` | 压力测试不通过或 critical 告警 | 暂停表现最差的策略，人工干预 |

### 9.3 风险建议生成规则

| 触发条件 | 建议 |
|---------|------|
| 任意策略对相关系数 > 0.7 | "策略 {A} 与 {B} 相关性过高({r:.2f})，建议替换其中一个或降低权重" |
| 分散比率 < 1.1 | "组合分散效果不足，建议增加低相关策略" |
| HHI > 0.35 | "资金过度集中在 {策略名}，建议重新分配" |
| 压力测试不通过 | "{场景名} 场景下组合损失 {loss:.1%}，超过阈值，建议降低仓位" |
| 过拟合告警 | "{策略名} 存在过拟合风险（IC 衰减 {rate:.0%}），建议重新训练" |
| 特征漂移告警 | "{策略名} 的特征 {feature} 发生漂移，建议检查数据源" |
| 表现退化告警 | "{策略名} 表现持续退化，建议暂停并评估" |

---

## 十、层职责划分

| 层 | 组件 | 职责 |
|----|------|------|
| **Domain** | `CorrelationAnalyzer` | 纯 Python 相关性计算 |
| **Domain** | `DiversificationEvaluator` | 分散度评估 |
| **Domain** | `PortfolioVaRCalculator` | VaR / CVaR 计算 |
| **Domain** | `StressTestRunner` | 压力测试编排 |
| **Domain** | `MLModelRiskMonitor` | ML 模型风险检测 |
| **Domain** | `PortfolioRiskService` | 聚合入口，生成综合报告 |
| **Domain** | 值对象 (6 个) | 不可变数据容器 |
| **Domain** | `StressScenario` + 历史场景数据 | 压力测试场景定义 |
| **Infrastructure** | `PortfolioRiskRichPrinter` | rich 终端输出 |
| **Infrastructure** | `PortfolioRiskPlotter` | matplotlib 图表 |
| **Application** | `PortfolioRiskAppService` | 编排：收集数据 → 调用 Domain 服务 → 输出报告 |
| **Interfaces** | `portfolio_risk.py` CLI | 命令行入口 |

### 依赖方向

```
Interfaces (CLI)
    ↓
Application (PortfolioRiskAppService)
    ↓
Domain (PortfolioRiskService → 各子服务)
    ↑
Infrastructure (PortfolioRiskRichPrinter, PortfolioRiskPlotter)
```

注意：所有 Domain 层组件严格使用纯 Python，不依赖任何第三方库。rich 和 matplotlib 仅在 Infrastructure 层使用。

---

## 十一、设计决策记录

### 决策 1: 相关性计算放在 Domain 层而非 Infrastructure 层

**选项**:
- A) Domain 层纯 Python 实现
- B) Infrastructure 层使用 numpy

**选择**: A (Domain 层纯 Python)

**理由**: 相关性计算是核心业务逻辑（判断策略是否适合组合），不是 I/O 或外部依赖。日频数据量小（年化 252 个点），纯 Python 性能完全够用。遵守 Domain 红线。

### 决策 2: VaR 仅支持两种简单方法

**选项**:
- A) 历史模拟法 + 参数法（正态假设）
- B) 增加蒙特卡洛模拟
- C) 增加 Copula 方法

**选择**: A (两种简单方法)

**理由**: 蒙特卡洛和 Copula 方法复杂度高，对个人投资者场景过度工程化。历史模拟法已经足够好（不依赖分布假设），参数法作为补充（计算快）。后续可按需扩展。

### 决策 3: 压力测试场景硬编码

**选项**:
- A) 硬编码在 Python 文件中
- B) 外部 YAML/JSON 配置

**选择**: A (硬编码)

**理由**: A 股历史极端场景数量有限（4 个），硬编码简单直接，避免 Domain 层的 I/O 依赖。假设场景通过参数化实现，灵活性足够。

### 决策 4: ML 风险监控不使用 KS 检验

**选项**:
- A) 使用 scipy.stats.ks_2samp
- B) 使用均值偏移 + 方差比的简化方法

**选择**: B (简化方法)

**理由**: Domain 层禁止使用 scipy。均值偏移 + 方差比方法在实践中对特征漂移检测已经足够有效，且计算简单、可解释性强。

### 决策 5: PortfolioRiskService 不直接依赖 CapitalAllocationEngine

**选项**:
- A) PortfolioRiskService 注入 CapitalAllocationEngine
- B) 通过 weights 字典解耦

**选择**: B (weights 字典解耦)

**理由**: PortfolioRiskService 只需要权重数据，不需要控制分配逻辑。通过字典传入权重，两个服务完全解耦，可独立测试和演进。

---

## 十二、与 Phase 3 其他子项目的关系

```
子项目 3.1: 策略池管理 (StrategyPoolEntry)
    ├── 提供策略生命周期状态
    ├── 提供 ML 模型版本元数据
    └── 接收 MLRiskAlert → 触发 SUSPENDED

子项目 3.2: 资金分配引擎 (CapitalAllocationEngine)
    ├── 提供策略权重 → PortfolioRiskService
    └── 接收风险建议 → 调整权重

子项目 3.3: 组合风险管理 (PortfolioRiskService) ← 本文档
    ├── 依赖策略对比面板的 correlation_matrix（可选）
    ├── 输出 PortfolioRiskReport
    └── 输出 MLRiskAlert → 策略池管理
```

---

## 十三、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 纯 Python 相关性计算性能 | 大策略数时可能慢 | 日频数据量小（252 点/年），10 个策略的 10x10 矩阵计算 < 1ms |
| 历史场景数据不准确 | 压力测试结果不可靠 | 使用公开可查的指数数据，场景定义经过验证 |
| VaR 正态假设不成立 | 参数法低估尾部风险 | 历史模拟法作为主方法，参数法仅作参考 |
| 特征漂移检测灵敏度不足 | 漏报漂移 | 均值 + 方差双维度检测，阈值设保守 |
| 相关性在危机时突变 | 平时低估组合风险 | 滚动相关性监控 + "相关性崩溃" 假设场景 |
| 与策略对比面板重复计算 | 浪费资源 | PortfolioRiskService 可接收已有的 CorrelationMatrix，避免重复计算 |

---

**文档结束**
