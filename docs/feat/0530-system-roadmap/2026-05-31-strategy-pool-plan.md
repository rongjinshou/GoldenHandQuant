# 策略池管理系统 -- 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划
**设计文档**: [2026-05-31-strategy-pool-design.md](./2026-05-31-strategy-pool-design.md)
**状态**: 草案

---

## 一、实现概览

### 1.1 总体策略

按"先骨架、再核心、后集成"的顺序实现，每个 Phase 独立可交付、可测试。

### 1.2 预估工作量

| Phase | 内容 | 预估代码量 | 预估工时 |
|-------|------|-----------|---------|
| Phase 1 | 数据模型 + 状态机 | ~200 行 | 2h |
| Phase 2 | 评级引擎 | ~120 行 | 1.5h |
| Phase 3 | 策略池管理器 | ~150 行 | 2h |
| Phase 4 | 持久化 + 集成 | ~100 行 | 1.5h |
| Phase 5 | ML 版本管理 | ~80 行 | 1h |
| Phase 6 | 测试 | ~400 行 | 3h |
| **合计** | | **~1,050 行** | **~11h** |

---

## 二、Phase 1: 数据模型 + 状态机

**目标**: 建立策略池的核心数据结构和状态转换逻辑。

### 任务清单

#### 1.1 创建目录结构

```
src/domain/strategy/pool/
  __init__.py
  entities/
    __init__.py
    strategy_pool_entry.py
  value_objects/
    __init__.py
    strategy_status.py
    strategy_rating.py
    performance_snapshot.py
    ml_model_version.py
  interfaces/
    __init__.py
    strategy_pool_repository.py
  services/
    __init__.py
    rating_engine.py
    pool_manager.py
```

**验证**: 目录结构正确，所有 `__init__.py` 存在。

#### 1.2 实现 StrategyStatus 枚举

**文件**: `src/domain/strategy/pool/value_objects/strategy_status.py`

```python
from enum import StrEnum

class StrategyStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"
```

**验证**: 枚举值可正常访问。

#### 1.3 实现 StrategyRating 枚举

**文件**: `src/domain/strategy/pool/value_objects/strategy_rating.py`

```python
from enum import StrEnum

class StrategyRating(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
```

**验证**: 枚举值可正常访问。

#### 1.4 实现 PerformanceSnapshot 值对象

**文件**: `src/domain/strategy/pool/value_objects/performance_snapshot.py`

```python
from dataclasses import dataclass
from datetime import datetime

from src.domain.strategy.pool.value_objects.strategy_rating import StrategyRating

@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceSnapshot:
    evaluated_at: datetime
    period_start: datetime
    period_end: datetime
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    composite_score: float
    rating: StrategyRating
    benchmark_return: float = 0.0
    underperform_weeks: int = 0
```

**验证**: 创建实例，确认不可变性（赋值抛 AttributeError）。

#### 1.5 实现 MLModelVersion 值对象

**文件**: `src/domain/strategy/pool/value_objects/ml_model_version.py`

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True, slots=True, kw_only=True)
class MLModelVersion:
    version_id: str
    model_type: str
    trained_at: datetime
    training_samples: int
    feature_count: int
    metrics: dict[str, float] = field(default_factory=dict)
    is_active: bool = False
    notes: str = ""
```

**验证**: 创建实例，确认不可变性。

#### 1.6 实现 StrategyPoolEntry 实体

**文件**: `src/domain/strategy/pool/entities/strategy_pool_entry.py`

核心逻辑:
- `__post_init__`: 验证 strategy_type 合法
- 状态转换方法: 使用 match/case 验证合法转换，非法转换抛 `ValueError`
- 查询属性: `latest_snapshot`、`is_tradeable`、`should_auto_retire`
- ML 版本管理: `add_model_version`、`activate_model_version`、`rollback_model_version`

**验证**:
- 创建 CANDIDATE 状态的条目
- 验证合法转换 (CANDIDATE → ACTIVE)
- 验证非法转换抛异常 (CANDIDATE → PAUSED)
- 验证 RETIRED 不可逆

---

## 三、Phase 2: 评级引擎

**目标**: 实现基于 BacktestReport 指标的评级算法。

### 任务清单

#### 2.1 实现 RatingEngine

**文件**: `src/domain/strategy/pool/services/rating_engine.py`

核心方法:
- `calculate_score(report, benchmark_return) -> float`: 计算综合得分
- `calculate_rating(score) -> StrategyRating`: 得分转评级
- `evaluate(report, benchmark_return) -> PerformanceSnapshot`: 生成评估快照

**评级公式**:

```python
def calculate_score(
    self,
    sharpe_ratio: float,
    max_drawdown: float,
    win_rate: float,
    underperform_weeks: int = 0,
) -> float:
    risk_adjusted = min(max(sharpe_ratio / 2.0 * 100, 0), 100)
    drawdown = min(max((1 - max_drawdown / 0.30) * 100, 0), 100)
    consistency = min(max(win_rate * 100, 0), 100)
    penalty = underperform_weeks * 5

    score = 0.40 * risk_adjusted + 0.30 * drawdown + 0.30 * consistency - penalty
    return min(max(score, 0), 100)
```

**验证**:
- 夏普 2.0, 回撤 10%, 胜率 60% → 得分 88 → A 级
- 夏普 0.5, 回撤 25%, 胜率 40% → 得分 25 → D 级
- 连续跑输 4 周 → 扣 20 分

---

## 四、Phase 3: 策略池管理器

**目标**: 实现策略池的核心业务逻辑。

### 任务清单

#### 4.1 实现 PoolManager

**文件**: `src/domain/strategy/pool/services/pool_manager.py`

核心方法:

| 方法 | 功能 | 依赖 |
|------|------|------|
| `register()` | 注册新策略到池中 | StrategyPoolEntry 构造 |
| `evaluate_strategy()` | 评估策略并更新评级 | RatingEngine |
| `check_auto_retire()` | 检查是否有策略需要自动下线 | StrategyPoolEntry.should_auto_retire |
| `get_active_strategies()` | 获取所有上线策略 | 持久化接口 |
| `get_pool_summary()` | 获取策略池汇总信息 | 持久化接口 |

**验证**:
- 注册新策略 → 状态为 CANDIDATE
- 评估策略 → 评级更新、快照记录
- 连续跑输 4 周 → should_auto_retire 返回 True

---

## 五、Phase 4: 持久化 + 集成

**目标**: 实现持久化接口和与现有系统的集成。

### 任务清单

#### 5.1 定义 IStrategyPoolRepository 接口

**文件**: `src/domain/strategy/pool/interfaces/strategy_pool_repository.py`

```python
from typing import Protocol

class IStrategyPoolRepository(Protocol):
    def save(self, entry: StrategyPoolEntry) -> None: ...
    def find_by_name(self, name: str) -> StrategyPoolEntry | None: ...
    def find_all(self) -> list[StrategyPoolEntry]: ...
    def find_by_status(self, status: StrategyStatus) -> list[StrategyPoolEntry]: ...
    def find_active(self) -> list[StrategyPoolEntry]: ...
    def delete(self, name: str) -> None: ...
```

#### 5.2 实现内存版仓储 (用于测试和回测)

**文件**: `src/infrastructure/persistence/memory_strategy_pool_repo.py`

简单字典存储，无需数据库。

#### 5.3 与现有 registry.py 的集成

**集成点**: `PoolManager.register()` 内部调用 `get_strategy()` 验证策略是否已注册。

```python
def register(self, name: str, ...) -> StrategyPoolEntry:
    # 验证策略在 registry 中已注册
    get_strategy(name)  # 不存在则抛 KeyError
    # 创建池条目
    entry = StrategyPoolEntry(strategy_name=name, ...)
    self._repo.save(entry)
    return entry
```

**验证**: 注册已存在的策略成功，注册不存在的策略抛异常。

---

## 六、Phase 5: ML 版本管理

**目标**: 支持 ML 模型的版本记录和切换。

### 任务清单

#### 6.1 扩展 StrategyPoolEntry 的 ML 方法

已在 Phase 1 的实体中定义，此处实现具体逻辑:

- `add_model_version()`: 添加新版本，自动设为非活跃
- `activate_model_version()`: 指定版本设为活跃，其他版本设为非活跃
- `rollback_model_version()`: 回退到上一个活跃版本

#### 6.2 与 ModelLoader 的集成

集成点: `PoolManager` 中提供辅助方法，根据活跃版本号调用 `ModelLoader` 加载对应模型文件。

**验证**:
- 添加 3 个版本 → 只有最后激活的版本 is_active=True
- 回滚 → 活跃版本切换到前一个

---

## 七、Phase 6: 测试

**目标**: 覆盖所有核心逻辑的单元测试。

### 测试清单

| 测试文件 | 测试内容 | 预估用例数 |
|---------|---------|-----------|
| `tests/domain/strategy/pool/value_objects/test_strategy_status.py` | 枚举值 | 3 |
| `tests/domain/strategy/pool/value_objects/test_strategy_rating.py` | 枚举值 | 3 |
| `tests/domain/strategy/pool/value_objects/test_performance_snapshot.py` | 不可变性 | 3 |
| `tests/domain/strategy/pool/value_objects/test_ml_model_version.py` | 不可变性 | 3 |
| `tests/domain/strategy/pool/entities/test_strategy_pool_entry.py` | 状态机、ML版本管理 | 15 |
| `tests/domain/strategy/pool/services/test_rating_engine.py` | 评级算法 | 10 |
| `tests/domain/strategy/pool/services/test_pool_manager.py` | 生命周期管理 | 8 |
| **合计** | | **~45** |

### 关键测试用例

#### 状态机测试

```python
def test_candidate_can_activate():
    entry = make_entry(status=StrategyStatus.CANDIDATE)
    entry.activate()
    assert entry.status == StrategyStatus.ACTIVE

def test_candidate_cannot_pause():
    entry = make_entry(status=StrategyStatus.CANDIDATE)
    with pytest.raises(ValueError, match="Invalid status transition"):
        entry.pause()

def test_retired_is_terminal():
    entry = make_entry(status=StrategyStatus.RETIRED)
    with pytest.raises(ValueError):
        entry.activate()
```

#### 评级算法测试

```python
def test_high_sharpe_low_drawdown_gets_a():
    engine = RatingEngine()
    score = engine.calculate_score(
        sharpe_ratio=2.0, max_drawdown=0.10, win_rate=0.60
    )
    assert score >= 80  # A 级

def test_underperform_penalty():
    engine = RatingEngine()
    score_no_penalty = engine.calculate_score(1.5, 0.15, 0.55, underperform_weeks=0)
    score_with_penalty = engine.calculate_score(1.5, 0.15, 0.55, underperform_weeks=4)
    assert score_no_penalty - score_with_penalty == 20  # 4 周 * 5 分
```

#### 自动下线测试

```python
def test_auto_retire_after_4_weeks_underperform():
    entry = make_entry(status=StrategyStatus.ACTIVE)
    for i in range(4):
        snapshot = make_snapshot(underperform_weeks=i + 1)
        entry.add_snapshot(snapshot)
    assert entry.should_auto_retire is True
```

---

## 八、实现顺序与依赖关系

```
Phase 1 (数据模型)
    │
    ├── 1.1 目录结构
    ├── 1.2 StrategyStatus
    ├── 1.3 StrategyRating
    ├── 1.4 PerformanceSnapshot
    ├── 1.5 MLModelVersion
    └── 1.6 StrategyPoolEntry (依赖 1.2-1.5)
            │
            v
Phase 2 (评级引擎)
    │
    └── 2.1 RatingEngine (依赖 1.3, 1.4)
            │
            v
Phase 3 (策略池管理器)
    │
    └── 4.1 PoolManager (依赖 1.6, 2.1)
            │
            v
Phase 4 (持久化 + 集成)
    │
    ├── 5.1 IStrategyPoolRepository
    ├── 5.2 内存仓储
    └── 5.3 集成 registry.py
            │
            v
Phase 5 (ML 版本管理)
    │
    └── 6.1-6.2 ML 扩展 (依赖 1.5, 1.6)
            │
            v
Phase 6 (测试)
    │
    └── 全量单元测试
```

---

## 九、文件清单

### 新增文件 (Domain 层)

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/domain/strategy/pool/__init__.py` | 包 | 策略池子域 |
| `src/domain/strategy/pool/entities/__init__.py` | 包 | |
| `src/domain/strategy/pool/entities/strategy_pool_entry.py` | 实体 | 策略池条目 |
| `src/domain/strategy/pool/value_objects/__init__.py` | 包 | |
| `src/domain/strategy/pool/value_objects/strategy_status.py` | 枚举 | 策略状态 |
| `src/domain/strategy/pool/value_objects/strategy_rating.py` | 枚举 | 策略评级 |
| `src/domain/strategy/pool/value_objects/performance_snapshot.py` | 值对象 | 评估快照 |
| `src/domain/strategy/pool/value_objects/ml_model_version.py` | 值对象 | ML 模型版本 |
| `src/domain/strategy/pool/interfaces/__init__.py` | 包 | |
| `src/domain/strategy/pool/interfaces/strategy_pool_repository.py` | Protocol | 持久化接口 |
| `src/domain/strategy/pool/services/__init__.py` | 包 | |
| `src/domain/strategy/pool/services/rating_engine.py` | 领域服务 | 评级引擎 |
| `src/domain/strategy/pool/services/pool_manager.py` | 领域服务 | 策略池管理器 |

### 新增文件 (Infrastructure 层)

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/infrastructure/persistence/memory_strategy_pool_repo.py` | 实现 | 内存版仓储 |

### 新增文件 (测试)

| 文件 | 说明 |
|------|------|
| `tests/domain/strategy/pool/value_objects/test_strategy_status.py` | 状态枚举测试 |
| `tests/domain/strategy/pool/value_objects/test_strategy_rating.py` | 评级枚举测试 |
| `tests/domain/strategy/pool/value_objects/test_performance_snapshot.py` | 快照测试 |
| `tests/domain/strategy/pool/value_objects/test_ml_model_version.py` | ML 版本测试 |
| `tests/domain/strategy/pool/entities/test_strategy_pool_entry.py` | 实体测试 |
| `tests/domain/strategy/pool/services/test_rating_engine.py` | 评级引擎测试 |
| `tests/domain/strategy/pool/services/test_pool_manager.py` | 管理器测试 |

### 不修改的文件

| 文件 | 原因 |
|------|------|
| `src/domain/strategy/registry.py` | 开闭原则，通过引用集成而非修改 |
| `src/domain/backtest/entities/backtest_report.py` | 只读使用，无需修改 |
| `src/infrastructure/ml_engine/model_loader.py` | 只读使用，无需修改 |

---

## 十、验收标准

### Phase 1 验收

- [ ] 所有枚举和值对象可正常创建
- [ ] StrategyPoolEntry 状态机覆盖所有合法转换
- [ ] StrategyPoolEntry 非法转换抛 ValueError
- [ ] RETIRED 状态不可逆

### Phase 2 验收

- [ ] RatingEngine 评级结果与设计文档一致
- [ ] 边界值测试通过（夏普 0/2/5，回撤 0%/15%/30%，胜率 0%/50%/100%）

### Phase 3 验收

- [ ] register() 创建 CANDIDATE 状态条目
- [ ] evaluate_strategy() 正确更新评级和快照
- [ ] check_auto_retire() 正确识别需要下线的策略

### Phase 4 验收

- [ ] IStrategyPoolRepository 接口定义完整
- [ ] 内存仓储 CRUD 操作正确
- [ ] 与 registry.py 集成无报错

### Phase 5 验收

- [ ] ML 版本添加、激活、回滚功能正确
- [ ] 同一时间只有一个活跃版本

### Phase 6 验收

- [ ] 所有单元测试通过
- [ ] 测试覆盖核心逻辑路径

---

**文档结束**
