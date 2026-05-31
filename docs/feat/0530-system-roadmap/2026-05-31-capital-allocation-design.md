# 资金分配引擎设计文档

> 日期: 2026-05-31
> 状态: Draft
> 作者: Architect Agent

## 1. 背景与目标

当前系统中，`IPositionSizer` 接口及其实现（`EqualWeightSizer`、`KellySizer`、`FixedRatioSizer`）负责**单策略内**的个股仓位计算。但系统缺乏一个更高层次的**策略间资金分配引擎**——当多个策略并行运行时，如何将总资金合理分配给各策略，并根据策略表现动态调整。

### 核心问题

- 新策略上线时，分配多少资金？
- 策略表现好/差时，如何增减资金？
- 如何避免单一策略占用过多资金？
- 不同分配算法如何切换？

## 2. 现有架构分析

### 2.1 关键已有组件

| 组件 | 位置 | 职责 |
|------|------|------|
| `Asset` | `src/domain/account/entities/asset.py` | 账户总资产、可用/冻结现金 |
| `AccountRepository` | `src/domain/account/entities/account_repository.py` | 多账户资金与持仓管理 |
| `BacktestReport` | `src/domain/backtest/entities/backtest_report.py` | 策略绩效报告（sharpe、sortino、calmar、胜率、盈亏比、回撤） |
| `PerformanceEvaluator` | `src/domain/backtest/services/performance_evaluator.py` | 聚合快照 -> 报告 |
| `IPositionSizer` | `src/domain/portfolio/interfaces/position_sizer.py` | 单策略内个股仓位计算接口 |
| `Signal` | `src/domain/strategy/value_objects/signal.py` | 交易信号（含 confidence_score） |
| `BaseStrategy` | `src/domain/strategy/services/base_strategy.py` | 策略抽象基类 |

### 2.2 缺口分析

现有架构在**策略间**资金分配上存在以下缺口：

1. **无策略级资金预算概念**：`Asset` 只有账户级总额，没有策略级资金划分。
2. **无策略绩效追踪**：`BacktestReport` 是回测产物，运行时没有持续的策略绩效记录。
3. **无再平衡触发机制**：没有定期检查各策略资金偏离度并触发再平衡的机制。
4. **无分配算法抽象**：等权、风险平价、凯利、夏普加权等算法没有统一接口。

## 3. 领域模型设计

### 3.1 新增值对象

#### `StrategyAllocation` — 策略资金分配结果

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyAllocation:
    """单个策略的资金分配结果。"""
    strategy_name: str
    allocated_capital: float       # 分配的资金总额
    weight: float                  # 权重 (0.0 - 1.0)
    allocated_at: datetime
    reason: str = ""               # 分配原因说明
```

#### `AllocationResult` — 完整分配结果

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class AllocationResult:
    """一次完整的资金分配结果。"""
    total_capital: float
    allocations: list[StrategyAllocation]
    algorithm: str                 # 使用的分配算法名称
    created_at: datetime
```

#### `StrategyPerformance` — 策略绩效快照

```python
@dataclass(slots=True, kw_only=True)
class StrategyPerformance:
    """策略绩效快照，用于分配决策。"""
    strategy_name: str
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    volatility: float              # 日收益率标准差 (年化)
    lookback_days: int             # 回看窗口天数
    updated_at: datetime
```

#### `RebalanceFrequency` — 再平衡频率枚举

```python
class RebalanceFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
```

### 3.2 分配算法接口

```python
class IAllocationAlgorithm(ABC):
    """资金分配算法接口。"""

    @abstractmethod
    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]:
        """计算各策略的资金分配。

        Args:
            total_capital: 可分配总资金。
            performances: 各策略绩效数据。
            current_allocations: 当前分配（用于增量调整，初始分配时为 None）。

        Returns:
            各策略的分配结果列表。权重之和必须为 1.0。
        """
        ...
```

### 3.3 分配算法实现

#### 算法 1：等权分配 (EqualWeight)

最简单的基准算法。

```
weight_i = 1 / N
allocated_i = total_capital * weight_i
```

- 优点：简单、无参数
- 缺点：不考虑策略表现差异

#### 算法 2：夏普比率加权 (SharpeWeight)

按各策略夏普比率正向加权。

```
raw_weight_i = max(sharpe_i, 0) + epsilon   # epsilon=0.01 防止全零
weight_i = raw_weight_i / sum(raw_weight_j)
```

- 优点：表现好的策略获得更多资金
- 缺点：夏普比率估计不稳定时分配会震荡

#### 算法 3：风险平价 (RiskParity)

各策略对组合风险的贡献相等。

```
risk_budget_i = 1 / N
vol_inv_i = 1 / volatility_i
weight_i = vol_inv_i / sum(vol_inv_j)
```

- 优点：天然分散风险，低波动策略获得更多资金
- 缺点：可能给低收益的低波动策略过多资金

#### 算法 4：凯利公式 (KellyAllocation)

基于凯利公式计算最优资金比例。

```
kelly_i = (win_rate_i * profit_loss_ratio_i - (1 - win_rate_i)) / profit_loss_ratio_i
kelly_i = max(kelly_i, 0) * 0.5   # 半凯利
weight_i = kelly_i / sum(kelly_j)
```

- 优点：理论最优的长期增长率
- 缺点：对输入参数敏感，需要半凯利约束

### 3.4 再平衡触发机制

```python
class IRebalanceTrigger(ABC):
    """再平衡触发器接口。"""

    @abstractmethod
    def should_rebalance(self, current_date: datetime, last_rebalance: datetime | None) -> bool:
        """判断是否应触发再平衡。"""
        ...

    @abstractmethod
    def record_rebalance(self, rebalance_date: datetime) -> None:
        """记录再平衡时间。"""
        ...
```

实现类：
- `DailyRebalanceTrigger`：每个交易日触发
- `WeeklyRebalanceTrigger`：每周一（或指定日）触发
- `MonthlyRebalanceTrigger`：每月第一个交易日触发

### 3.5 资金分配引擎

```python
class CapitalAllocationEngine:
    """资金分配引擎，协调分配算法和再平衡触发。"""

    def __init__(
        self,
        algorithm: IAllocationAlgorithm,
        trigger: IRebalanceTrigger,
        max_single_weight: float = 0.40,   # 单策略最大权重
        min_single_weight: float = 0.05,   # 单策略最小权重
    ) -> None: ...

    def initial_allocate(
        self,
        total_capital: float,
        strategy_names: list[str],
    ) -> AllocationResult:
        """新策略上线时的初始分配（等权）。"""
        ...

    def rebalance(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation],
        current_date: datetime,
    ) -> AllocationResult | None:
        """检查并执行再平衡。返回 None 表示不需要再平衡。"""
        ...

    def adjust_for_new_strategy(
        self,
        total_capital: float,
        new_strategy: str,
        current_allocations: list[StrategyAllocation],
    ) -> AllocationResult:
        """新策略加入时，从现有策略中按比例抽调资金。"""
        ...
```

## 4. 领域边界与分层

### 4.1 放置位置

```
src/domain/portfolio/
    entities/
        strategy_allocation.py      # StrategyAllocation, AllocationResult
        strategy_performance.py     # StrategyPerformance
    interfaces/
        allocation_algorithm.py     # IAllocationAlgorithm
        rebalance_trigger.py        # IRebalanceTrigger
    services/
        capital_allocation_engine.py  # CapitalAllocationEngine
        allocation_algorithms/
            equal_weight.py
            sharpe_weight.py
            risk_parity.py
            kelly_allocation.py
        rebalance_triggers/
            daily_trigger.py
            weekly_trigger.py
            monthly_trigger.py
```

### 4.2 与现有组件的关系

```
                   ┌─────────────────────────┐
                   │  CapitalAllocationEngine │
                   │  (策略间资金分配)          │
                   └────────┬────────────────┘
                            │ 输出 AllocationResult
                            ▼
                   ┌─────────────────────────┐
                   │    IPositionSizer        │
                   │  (策略内个股仓位)          │
                   └────────┬────────────────┘
                            │ 输出 OrderTarget
                            ▼
                   ┌─────────────────────────┐
                   │    OrderService          │
                   │  (下单执行)               │
                   └─────────────────────────┘
```

- **资金分配引擎**决定每个策略的预算（策略间）
- **PositionSizer**在策略预算内决定个股仓位（策略内）
- 两者解耦，可独立测试和替换

### 4.3 与 BacktestReport 的关系

`StrategyPerformance` 是 `BacktestReport` 的运行时精简版：

| BacktestReport (回测) | StrategyPerformance (运行时) |
|---|---|
| total_return | total_return |
| annualized_return | annualized_return |
| sharpe_ratio | sharpe_ratio |
| max_drawdown | max_drawdown |
| win_rate | win_rate |
| (无) | volatility |
| trades, snapshots, equity_curve | (不需要) |

`PerformanceEvaluator` 可扩展为同时输出 `StrategyPerformance`，或新建轻量级的 `PerformanceTracker` 持续追踪。

## 5. 约束与安全规则

### 5.1 权重约束

- 所有策略权重之和 = 1.0（归一化）
- 单策略最大权重：40%（可配置，防止过度集中）
- 单策略最小权重：5%（可配置，过低无意义）
- 新策略默认权重上限：20%（冷启动保护）

### 5.2 Domain 红线

所有新增代码在 `src/domain/portfolio/` 下，严格遵守 domain 层规则：
- 仅使用 Python 标准库
- 纯业务逻辑，无 I/O
- `@dataclass(slots=True, kw_only=True)` 模式
- `match/case` 用于状态分发

### 5.3 再平衡保护

- 最小再平衡间隔：至少 1 个交易日（防止频繁交易）
- 单次再平衡最大调整幅度：权重变化不超过 10%（可配置，渐进式调整）
- 策略绩效数据不足时（lookback < 20 个交易日），回退到等权分配

## 6. 与 Application 层的集成

### 6.1 回测集成

`BacktestAppService` 中增加可选的 `CapitalAllocationEngine` 参数：

```python
class BacktestAppService:
    def __init__(
        self,
        # ... 现有参数 ...
        allocation_engine: CapitalAllocationEngine | None = None,
    ): ...
```

当配置了 allocation_engine 时：
1. 回测开始时调用 `initial_allocate` 分配资金
2. 每日检查 `should_rebalance`
3. 触发时调用 `rebalance` 更新分配
4. PositionSizer 使用分配到的策略预算而非总资金

### 6.2 实盘集成

`LiveSignalService` / `TradingApp` 中类似集成。

## 7. 不在范围内

- **不实现**：策略收益归因（Attribution）
- **不实现**：交易成本对分配的影响（成本感知分配）
- **不实现**：跨资产类别分配（仅 A 股）
- **不实现**：机器学习驱动的分配权重预测
