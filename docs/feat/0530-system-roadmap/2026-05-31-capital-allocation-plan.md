# 资金分配引擎实现计划

> 日期: 2026-05-31
> 设计文档: `2026-05-31-capital-allocation-design.md`
> 预估工作量: 3-4 天

## 任务总览

| # | 任务 | 文件 | 依赖 | 验收标准 |
|---|------|------|------|----------|
| T1 | 值对象定义 | `entities/strategy_allocation.py`, `entities/strategy_performance.py` | 无 | dataclass 可实例化，字段验证通过 |
| T2 | 分配算法接口 | `interfaces/allocation_algorithm.py` | T1 | ABC 定义完整 |
| T3 | 等权分配 | `allocation_algorithms/equal_weight.py` | T2 | 单元测试通过 |
| T4 | 夏普加权分配 | `allocation_algorithms/sharpe_weight.py` | T2 | 单元测试通过 |
| T5 | 风险平价分配 | `allocation_algorithms/risk_parity.py` | T2 | 单元测试通过 |
| T6 | 凯利公式分配 | `allocation_algorithms/kelly_allocation.py` | T2 | 单元测试通过 |
| T7 | 再平衡触发器接口 | `interfaces/rebalance_trigger.py` | 无 | ABC 定义完整 |
| T8 | 三种触发器实现 | `rebalance_triggers/daily_trigger.py`, `weekly_trigger.py`, `monthly_trigger.py` | T7 | 单元测试通过 |
| T9 | 资金分配引擎 | `services/capital_allocation_engine.py` | T1-T8 | 集成测试通过 |
| T10 | 回测集成 | `src/application/backtest_app.py` | T9 | 回测可配置分配引擎 |
| T11 | 性能追踪器 | `src/domain/backtest/services/performance_tracker.py` | T1 | 持续追踪策略绩效 |

## 详细步骤

### Phase 1: 基础模型 (T1-T2)

#### T1.1 值对象 — `StrategyAllocation`

文件: `src/domain/portfolio/entities/strategy_allocation.py`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyAllocation:
    strategy_name: str
    allocated_capital: float
    weight: float
    allocated_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        if self.allocated_capital < 0:
            raise ValueError(...)
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(...)
```

#### T1.2 值对象 — `AllocationResult`

同一文件或单独文件:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class AllocationResult:
    total_capital: float
    allocations: list[StrategyAllocation]
    algorithm: str
    created_at: datetime

    @property
    def weight_sum(self) -> float:
        return sum(a.weight for a in self.allocations)
```

#### T1.3 值对象 — `StrategyPerformance`

文件: `src/domain/portfolio/entities/strategy_performance.py`

```python
@dataclass(slots=True, kw_only=True)
class StrategyPerformance:
    strategy_name: str
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    volatility: float
    lookback_days: int
    updated_at: datetime
```

#### T1.4 枚举 — `RebalanceFrequency`

文件: `src/domain/portfolio/value_objects/rebalance_frequency.py`

```python
class RebalanceFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
```

#### T2 分配算法接口

文件: `src/domain/portfolio/interfaces/allocation_algorithm.py`

```python
class IAllocationAlgorithm(ABC):
    @abstractmethod
    def calculate(
        self,
        total_capital: float,
        performances: list[StrategyPerformance],
        current_allocations: list[StrategyAllocation] | None = None,
    ) -> list[StrategyAllocation]: ...
```

**验证**: `python -m pytest tests/domain/portfolio/ -v`

### Phase 2: 分配算法 (T3-T6)

每个算法一个文件，均实现 `IAllocationAlgorithm`。

#### T3 等权分配

文件: `src/domain/portfolio/services/allocation_algorithms/equal_weight.py`

逻辑:
```
weight_i = 1 / len(performances)
```

#### T4 夏普加权分配

文件: `src/domain/portfolio/services/allocation_algorithms/sharpe_weight.py`

逻辑:
```
raw_i = max(sharpe_i, 0) + 0.01
weight_i = raw_i / sum(raw_j)
```

#### T5 风险平价分配

文件: `src/domain/portfolio/services/allocation_algorithms/risk_parity.py`

逻辑:
```
vol_inv_i = 1 / max(volatility_i, 0.001)
weight_i = vol_inv_i / sum(vol_inv_j)
```

#### T6 凯利公式分配

文件: `src/domain/portfolio/services/allocation_algorithms/kelly_allocation.py`

逻辑:
```
kelly_i = (win_rate_i * pl_ratio_i - (1 - win_rate_i)) / pl_ratio_i
kelly_i = max(kelly_i, 0) * 0.5   # 半凯利
weight_i = kelly_i / sum(kelly_j)
```

需要从 `StrategyPerformance` 推导盈亏比，或在 `StrategyPerformance` 中增加 `profit_loss_ratio` 字段。

**验证**: 每个算法的单元测试覆盖:
- 2 个策略的权重分配
- 权重之和 = 1.0
- 边界情况（全零夏普、零波动率等）
- 权重约束（max/min）校验

### Phase 3: 再平衡触发器 (T7-T8)

#### T7 触发器接口

文件: `src/domain/portfolio/interfaces/rebalance_trigger.py`

```python
class IRebalanceTrigger(ABC):
    @abstractmethod
    def should_rebalance(self, current_date: datetime, last_rebalance: datetime | None) -> bool: ...

    @abstractmethod
    def record_rebalance(self, rebalance_date: datetime) -> None: ...
```

#### T8 三种触发器

文件:
- `src/domain/portfolio/services/rebalance_triggers/daily_trigger.py`
- `src/domain/portfolio/services/rebalance_triggers/weekly_trigger.py`
- `src/domain/portfolio/services/rebalance_triggers/monthly_trigger.py`

| 触发器 | 规则 |
|--------|------|
| Daily | 每个交易日（`last_rebalance` 为空或 < current_date） |
| Weekly | 当前日期为周一 且 距上次 >= 5 天 |
| Monthly | 当前日期为月初第一个交易日 且 距上次 >= 20 天 |

**验证**: 单元测试覆盖跨日/跨周/跨月边界。

### Phase 4: 引擎核心 (T9)

文件: `src/domain/portfolio/services/capital_allocation_engine.py`

```python
class CapitalAllocationEngine:
    def __init__(
        self,
        algorithm: IAllocationAlgorithm,
        trigger: IRebalanceTrigger,
        max_single_weight: float = 0.40,
        min_single_weight: float = 0.05,
        max_weight_change: float = 0.10,
        min_lookback_days: int = 20,
    ) -> None: ...

    def initial_allocate(self, total_capital, strategy_names) -> AllocationResult:
        """等权初始分配，应用权重约束。"""

    def rebalance(self, total_capital, performances, current_allocations, current_date) -> AllocationResult | None:
        """检查触发条件 -> 执行算法 -> 应用约束 -> 渐进式调整。"""

    def adjust_for_new_strategy(self, total_capital, new_strategy, current_allocations) -> AllocationResult:
        """新策略加入，从现有策略按比例抽调。"""

    def _apply_constraints(self, allocations) -> list[StrategyAllocation]:
        """应用 max/min 权重约束并重新归一化。"""

    def _apply_gradual_adjustment(self, new_allocs, current_allocs) -> list[StrategyAllocation]:
        """限制单次权重变化幅度（max_weight_change）。"""
```

**验证**: 集成测试覆盖:
- 初始分配：3 个策略，权重均分
- 再平衡：策略 A 夏普 2.0，策略 B 夏普 0.5 → A 权重增加
- 权重约束：单策略不超过 40%
- 渐进调整：单次变化不超过 10%
- 绩效不足：回退等权

### Phase 5: 集成 (T10-T11)

#### T10 回测集成

修改 `src/application/backtest_app.py`:

1. 构造函数增加 `allocation_engine: CapitalAllocationEngine | None = None`
2. 回测循环中，每日检查 `should_rebalance`
3. 触发时调用 `rebalance`，将结果传递给 PositionSizer

#### T11 性能追踪器

文件: `src/domain/backtest/services/performance_tracker.py`

轻量级服务，持续记录每个策略的滚动绩效，输出 `StrategyPerformance`:

```python
class PerformanceTracker:
    def __init__(self, lookback_days: int = 60) -> None: ...

    def record_daily_return(self, strategy_name: str, daily_return: float, date: datetime) -> None: ...

    def get_performance(self, strategy_name: str) -> StrategyPerformance | None: ...

    def get_all_performances(self) -> list[StrategyPerformance]: ...
```

**验证**: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v`

## 文件清单

### 新增文件

```
src/domain/portfolio/entities/strategy_allocation.py
src/domain/portfolio/entities/strategy_performance.py
src/domain/portfolio/value_objects/rebalance_frequency.py
src/domain/portfolio/interfaces/allocation_algorithm.py
src/domain/portfolio/interfaces/rebalance_trigger.py
src/domain/portfolio/services/allocation_algorithms/__init__.py
src/domain/portfolio/services/allocation_algorithms/equal_weight.py
src/domain/portfolio/services/allocation_algorithms/sharpe_weight.py
src/domain/portfolio/services/allocation_algorithms/risk_parity.py
src/domain/portfolio/services/allocation_algorithms/kelly_allocation.py
src/domain/portfolio/services/rebalance_triggers/__init__.py
src/domain/portfolio/services/rebalance_triggers/daily_trigger.py
src/domain/portfolio/services/rebalance_triggers/weekly_trigger.py
src/domain/portfolio/services/rebalance_triggers/monthly_trigger.py
src/domain/portfolio/services/capital_allocation_engine.py
src/domain/backtest/services/performance_tracker.py
tests/domain/portfolio/entities/test_strategy_allocation.py
tests/domain/portfolio/services/allocation_algorithms/test_equal_weight.py
tests/domain/portfolio/services/allocation_algorithms/test_sharpe_weight.py
tests/domain/portfolio/services/allocation_algorithms/test_risk_parity.py
tests/domain/portfolio/services/allocation_algorithms/test_kelly_allocation.py
tests/domain/portfolio/services/rebalance_triggers/test_daily_trigger.py
tests/domain/portfolio/services/rebalance_triggers/test_weekly_trigger.py
tests/domain/portfolio/services/rebalance_triggers/test_monthly_trigger.py
tests/domain/portfolio/services/test_capital_allocation_engine.py
tests/domain/backtest/services/test_performance_tracker.py
```

### 修改文件

```
src/domain/portfolio/entities/__init__.py        # 导出新实体
src/domain/portfolio/interfaces/__init__.py       # 导出新接口
src/domain/portfolio/services/__init__.py         # 导出新服务
src/application/backtest_app.py                   # 集成分配引擎（T10）
```

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 凯利公式参数不稳定 | 分配剧烈波动 | 半凯利 + 渐进调整 + max_weight_change 约束 |
| 绩效数据不足 | 算法输出不合理 | min_lookback_days 回退等权 |
| 权重归一化精度 | 浮点误差 | 使用 `round(weight, 6)` 并在最后调整最大权重补齐误差 |
| 再平衡过于频繁 | 交易成本侵蚀收益 | trigger + min_weight_change 阈值双重保护 |

## 里程碑

- **M1** (Day 1): T1-T2 完成，基础模型和接口就绪
- **M2** (Day 2): T3-T6 完成，四种算法全部实现并通过测试
- **M3** (Day 3): T7-T9 完成，引擎核心功能就绪
- **M4** (Day 4): T10-T11 完成，集成到回测流程
