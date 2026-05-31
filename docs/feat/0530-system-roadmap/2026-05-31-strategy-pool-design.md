# 策略池管理系统 -- 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 技术设计文档
**所属阶段**: Phase 3 -- 多策略组合 (子项目 3.1)
**状态**: 草案

---

## 一、需求概述

### 1.1 背景

当前系统有 3 个已注册策略（dual_ma、micro_value、multi_factor），但缺乏统一的生命周期管理机制。随着策略数量增长（包括 ML 策略），需要一个策略池管理系统来：

- 统一管理策略的上线、监控、下线全流程
- 基于历史表现自动评级，辅助投资决策
- 为后续的资金分配引擎（子项目 3.2）提供策略质量数据

### 1.2 核心能力

| 能力 | 说明 | 优先级 |
|------|------|--------|
| 策略注册 | 新策略加入策略池，记录元数据 | P0 |
| 策略评级 | A/B/C/D 四级评级，基于回测指标 | P0 |
| 策略监控 | 每周自动评估，跟踪表现趋势 | P1 |
| 策略下线 | 连续 4 周跑输基准自动下线 | P1 |
| ML 模型版本管理 | 模型版本追踪、A/B 测试 | P2 |

### 1.3 与现有系统的关系

```
现有: StrategyConfig (registry.py) -- 静态注册，无状态管理
新增: StrategyPoolEntry          -- 动态管理，有生命周期
关联: BacktestReport             -- 提供评级所需的历史表现数据
关联: ModelLoader                -- ML 模型加载，扩展版本管理
```

---

## 二、领域模型设计

### 2.1 整体结构

```
src/domain/strategy/
  pool/
    __init__.py
    entities/
      __init__.py
      strategy_pool_entry.py      # 策略池条目实体 (充血模型)
    value_objects/
      __init__.py
      strategy_status.py          # 策略状态枚举
      strategy_rating.py          # 策略评级枚举
      performance_snapshot.py     # 单次评估快照 (不可变值对象)
      ml_model_version.py         # ML 模型版本元数据 (不可变值对象)
    interfaces/
      __init__.py
      strategy_pool_repository.py # 策略池持久化接口 (Protocol)
    services/
      __init__.py
      rating_engine.py            # 评级引擎 (领域服务)
      pool_manager.py             # 策略池管理器 (领域服务)
```

### 2.2 策略状态机

```
                    ┌─────────────┐
                    │  CANDIDATE  │  新策略注册，待验证
                    └──────┬──────┘
                           │ 回测验证通过
                           v
                    ┌─────────────┐
              ┌────>│   ACTIVE    │  上线运行中
              │     └──────┬──────┘
              │            │
              │     ┌──────┴──────┐
              │     v             v
              │ ┌────────┐  ┌──────────┐
              │ │PAUSED  │  │SUSPENDED │  主动暂停 / 风控暂停
              │ └───┬────┘  └────┬─────┘
              │     │            │
              │     └─────┬──────┘
              │           │ 恢复 / 人工解除
              │           v
              │     ┌─────────────┐
              └─────│   ACTIVE    │
                    └──────┬──────┘
                           │ 连续4周跑输基准 / 人工决策
                           v
                    ┌─────────────┐
                    │  RETIRED    │  退役，不再使用
                    └─────────────┘
```

**状态定义**:

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `CANDIDATE` | 候选策略，待验证 | 新策略注册 |
| `ACTIVE` | 上线运行中 | 回测验证通过 + 人工确认 |
| `PAUSED` | 主动暂停 | 人工暂停（如市场环境不匹配） |
| `SUSPENDED` | 风控暂停 | 自动触发（回撤超限、信号异常） |
| `RETIRED` | 退役 | 连续 4 周跑输基准 / 人工下线 |

**合法状态转换**:

```python
VALID_TRANSITIONS: dict[StrategyStatus, set[StrategyStatus]] = {
    CANDIDATE:  {ACTIVE, RETIRED},
    ACTIVE:     {PAUSED, SUSPENDED, RETIRED},
    PAUSED:     {ACTIVE, RETIRED},
    SUSPENDED:  {ACTIVE, RETIRED},
    RETIRED:    set(),  # 终态，不可逆
}
```

### 2.3 策略评级

**评级等级**:

| 评级 | 综合得分 | 含义 | 资金分配建议 |
|------|---------|------|-------------|
| A | >= 80 | 优秀 | 最高权重 |
| B | 60-79 | 良好 | 标准权重 |
| C | 40-59 | 一般 | 降低权重 |
| D | < 40 | 差 | 考虑下线 |

**综合得分算法** (基于 BacktestReport 指标):

```
composite_score = w1 * risk_adjusted_score
                + w2 * drawdown_score
                + w3 * consistency_score
                - penalty

其中:
  w1 = 0.40 (风险调整收益)
  w2 = 0.30 (回撤控制)
  w3 = 0.30 (稳定性)

  risk_adjusted_score = clamp(sharpe_ratio / 2.0 * 100, 0, 100)
  drawdown_score      = clamp((1 - max_drawdown / 0.30) * 100, 0, 100)
  consistency_score   = clamp(win_rate * 100, 0, 100)
  penalty             = underperform_weeks * 5  (连续跑输基准，每周扣 5 分)
```

**评级阈值说明**:

- `sharpe_ratio / 2.0`: 夏普 2.0 对应满分，这是优秀量化策略的标准
- `max_drawdown / 0.30`: 30% 回撤对应 0 分，这是个人投资者的承受上限
- `underperform_weeks * 5`: 连续跑输基准 4 周扣 20 分，可将 A/B 级降至 C/D 级

### 2.4 自动下线规则

策略满足以下任一条件时自动标记为待下线（需人工确认后变为 RETIRED）:

| 条件 | 阈值 | 说明 |
|------|------|------|
| 连续跑输基准 | 4 周 | 周收益率 < 基准周收益率 |
| 最大回撤超限 | 25% | 从激活以来的累计最大回撤 |
| 评级持续为 D | 4 周 | 连续 4 周评级为 D |

**设计决策**: 下线采用"半自动"模式 -- 系统自动检测并标记，但最终下线需要人工确认。这是为了防止短期市场波动导致误判。

### 2.5 ML 模型版本管理

ML 策略与传统策略共享同一套状态机和评级体系，但额外增加模型版本追踪:

```
MLModelVersion:
  version_id: str          # 如 "v1.0.0"
  model_type: str          # "lightgbm" | "xgboost" | "catboost"
  trained_at: datetime
  training_samples: int
  feature_count: int
  metrics: dict[str, float]  # {"ic": 0.058, "sharpe": 1.8, ...}
  is_active: bool
  notes: str
```

**版本生命周期**:

```
训练完成 → 候选版本 → 回测验证 → (A/B 测试) → 上线 → 监控 → (回滚/替换)
```

**A/B 测试方案**:

- 新旧模型同时运行，各自管理独立的虚拟资金池
- 对比周期: 4 周
- 胜出条件: 新模型夏普比率 > 旧模型夏普比率 * 1.1 (10% 优势)
- 失败回滚: 新模型表现低于旧模型时自动回滚

---

## 三、核心数据模型

### 3.1 StrategyStatus (枚举)

```python
class StrategyStatus(StrEnum):
    CANDIDATE  = "CANDIDATE"   # 候选，待验证
    ACTIVE     = "ACTIVE"      # 上线运行中
    PAUSED     = "PAUSED"      # 主动暂停
    SUSPENDED  = "SUSPENDED"   # 风控暂停
    RETIRED    = "RETIRED"     # 退役
```

### 3.2 StrategyRating (枚举)

```python
class StrategyRating(StrEnum):
    A = "A"  # 优秀 (>= 80)
    B = "B"  # 良好 (60-79)
    C = "C"  # 一般 (40-59)
    D = "D"  # 差   (< 40)
```

### 3.3 PerformanceSnapshot (值对象)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PerformanceSnapshot:
    """单次评估快照（不可变）。"""
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
    benchmark_return: float = 0.0   # 基准同期收益
    underperform_weeks: int = 0     # 连续跑输基准周数
```

### 3.4 MLModelVersion (值对象)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class MLModelVersion:
    """ML 模型版本元数据（不可变）。"""
    version_id: str
    model_type: str          # "lightgbm" | "xgboost" | "catboost"
    trained_at: datetime
    training_samples: int
    feature_count: int
    metrics: dict[str, float]
    is_active: bool = False
    notes: str = ""
```

### 3.5 StrategyPoolEntry (实体)

```python
@dataclass(slots=True, kw_only=True)
class StrategyPoolEntry:
    """策略池条目（充血模型）。

    管理单个策略的完整生命周期：注册 → 评级 → 监控 → 下线。
    """
    strategy_name: str
    strategy_type: str           # "bar" | "cross_section" | "ml"
    description: str
    registered_at: datetime
    status: StrategyStatus = StrategyStatus.CANDIDATE
    rating: StrategyRating = StrategyRating.C
    params: dict[str, Any] = field(default_factory=dict)
    snapshots: list[PerformanceSnapshot] = field(default_factory=list)
    ml_versions: list[MLModelVersion] = field(default_factory=list)
    notes: str = ""

    # -- 状态转换方法 --
    def activate(self) -> None: ...
    def pause(self, reason: str = "") -> None: ...
    def suspend(self, reason: str = "") -> None: ...
    def retire(self, reason: str = "") -> None: ...

    # -- 评估方法 --
    def add_snapshot(self, snapshot: PerformanceSnapshot) -> None: ...
    def update_rating(self, rating: StrategyRating) -> None: ...

    # -- 查询方法 --
    @property
    def latest_snapshot(self) -> PerformanceSnapshot | None: ...
    @property
    def is_tradeable(self) -> bool: ...
    @property
    def should_auto_retire(self) -> bool: ...
    @property
    def active_model_version(self) -> MLModelVersion | None: ...

    # -- ML 版本管理 --
    def add_model_version(self, version: MLModelVersion) -> None: ...
    def activate_model_version(self, version_id: str) -> None: ...
    def rollback_model_version(self) -> str | None: ...
```

---

## 四、接口设计

### 4.1 策略池持久化接口

```python
class IStrategyPoolRepository(Protocol):
    """策略池持久化接口。"""

    def save(self, entry: StrategyPoolEntry) -> None: ...
    def find_by_name(self, name: str) -> StrategyPoolEntry | None: ...
    def find_all(self) -> list[StrategyPoolEntry]: ...
    def find_by_status(self, status: StrategyStatus) -> list[StrategyPoolEntry]: ...
    def find_active(self) -> list[StrategyPoolEntry]: ...
    def delete(self, name: str) -> None: ...
```

### 4.2 评级引擎接口

```python
class RatingEngine:
    """评级引擎 -- 基于回测指标计算策略评级。"""

    def calculate_score(self, report: BacktestReport, benchmark_return: float = 0.0) -> float: ...
    def calculate_rating(self, score: float) -> StrategyRating: ...
    def evaluate(self, report: BacktestReport, benchmark_return: float = 0.0) -> PerformanceSnapshot: ...
```

### 4.3 策略池管理器接口

```python
class PoolManager:
    """策略池管理器 -- 协调策略生命周期。"""

    def register(self, name: str, strategy_type: str, description: str, params: dict) -> StrategyPoolEntry: ...
    def evaluate_strategy(self, name: str, report: BacktestReport, benchmark_return: float) -> StrategyPoolEntry: ...
    def check_auto_retire(self) -> list[StrategyPoolEntry]: ...
    def get_active_strategies(self) -> list[StrategyPoolEntry]: ...
    def get_pool_summary(self) -> dict: ...
```

---

## 五、与现有代码的集成

### 5.1 与 StrategyConfig (registry.py) 的关系

```
StrategyConfig: 静态注册（工厂函数、默认参数）-- 保持不变
StrategyPoolEntry: 动态管理（状态、评级、历史）-- 新增
```

**设计决策**: 不修改现有 `registry.py`。`StrategyPoolEntry` 通过 `strategy_name` 引用 `StrategyConfig`，两者是互补关系:

- `StrategyConfig` 负责"如何创建策略实例"
- `StrategyPoolEntry` 负责"策略的运行状态和表现"

### 5.2 与 BacktestReport 的关系

`RatingEngine` 接受 `BacktestReport` 作为输入，提取以下指标计算评级:

| BacktestReport 指标 | 评级权重 | 用途 |
|---------------------|---------|------|
| `sharpe_ratio` | 40% | 风险调整收益 |
| `max_drawdown` | 30% | 回撤控制能力 |
| `win_rate` | 30% | 交易稳定性 |

### 5.3 与 ML Engine 的关系

```
ModelLoader (infrastructure): 加载模型文件 -- 保持不变
MLModelVersion (domain): 记录版本元数据 -- 新增
StrategyPoolEntry.ml_versions: 管理版本列表 -- 新增
```

`MLModelVersion` 只记录元数据（版本号、训练时间、指标），不持有模型实例本身。模型加载仍由 `ModelLoader` 负责。

---

## 六、设计决策记录

### 决策 1: 下线采用半自动模式

**选项**:
- A) 全自动: 检测到条件满足直接下线
- B) 半自动: 检测 + 标记 + 人工确认
- C) 全人工: 完全依赖人工判断

**选择**: B (半自动)

**理由**: 全自动可能因短期市场波动误判; 全人工效率太低。半自动平衡了效率和安全性。

### 决策 2: 不修改现有 registry.py

**理由**: 开闭原则。新功能通过扩展（新增 pool 模块）实现，不修改已有代码。`StrategyConfig` 和 `StrategyPoolEntry` 职责清晰分离。

### 决策 3: PerformanceSnapshot 采用不可变设计

**理由**: 与 `BacktestReport` 保持一致。快照一旦生成不应被修改，保证评级历史的可信度。

### 决策 4: StrategyPoolEntry 采用可变设计

**理由**: 与 `DailySnapshot` 保持一致。池条目的状态、评级会随时间变化，需要支持原地更新。

### 决策 5: 评级算法纯基于回测指标

**选项**:
- A) 纯回测指标
- B) 回测 + 实盘混合
- C) 实盘优先

**选择**: A (纯回测指标，Phase 1)

**理由**: 当前系统以回测为主，实盘数据积累不足。后续 Phase 可扩展为回测+实盘混合评级。

---

## 七、非功能需求

### 7.1 性能

- 评级计算: 单策略 < 10ms（纯数学运算）
- 策略池查询: < 50ms（内存操作，无需持久化优化）
- 每周全量评估: 支持 50+ 策略并行评估

### 7.2 可测试性

- 所有领域模型纯 Python，无第三方依赖
- RatingEngine 可独立单元测试
- 状态机转换规则可通过参数化测试覆盖

### 7.3 可扩展性

- 评级算法可配置（权重、阈值通过参数传入）
- 状态机可扩展（新增状态只需更新枚举和转换规则）
- ML 模型类型可扩展（model_type 为字符串，不限于当前三种）

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 评级算法过于简单 | 评级不准确 | 设计为可配置权重，后续可迭代优化 |
| 状态机规则不完善 | 状态混乱 | 严格的合法转换表 + 单元测试覆盖 |
| 与现有代码集成困难 | 开发延迟 | 不修改现有代码，通过引用关系集成 |
| ML 版本管理复杂度 | 维护成本高 | Phase 1 先支持基本版本记录，A/B 测试延后 |

---

**文档结束**
