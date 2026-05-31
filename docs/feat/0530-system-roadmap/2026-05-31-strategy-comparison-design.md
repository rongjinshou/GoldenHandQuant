# 策略对比面板 — 设计文档

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 详细设计 / 技术方案
**状态**: 草案

---

## 一、需求概述

### 1.1 用户故事

> 同时回测"微盘价值"、"多因子"、"DualMa"三个策略，看哪个夏普最高、回撤最小，
> 并分析它们之间的相关性，判断能否组合使用。

### 1.2 核心能力

| # | 能力 | 优先级 |
|---|------|--------|
| 1 | 多策略并行回测（共享数据源，避免重复加载） | P0 |
| 2 | 统一时间轴对比（收益曲线叠加） | P0 |
| 3 | 关键指标对比表（夏普、最大回撤、年化收益、胜率、Calmar、Sortino） | P0 |
| 4 | 相关性分析（策略之间收益的相关性，用于组合构建） | P1 |
| 5 | 可视化对比报告（rich 终端表格 + matplotlib 图表） | P1 |
| 6 | 自动推荐最优策略组合 | P2 |

---

## 二、现有架构分析

### 2.1 现有能力盘点

现有代码已具备多策略回测的基础：

| 组件 | 文件 | 现有能力 | 缺口 |
|------|------|---------|------|
| BacktestAppService | `src/application/backtest_app.py` | `run_backtest(strategies=list)` 支持多策略顺序执行 | 共享数据源但每策略独立重建 gateway；无对比输出 |
| BacktestReport | `src/domain/backtest/entities/backtest_report.py` | 含 total_return / annualized_return / max_drawdown / win_rate / sharpe / sortino / calmar / equity_curve / daily_returns | 缺少策略名称标识 |
| PerformanceEvaluator | `src/domain/backtest/services/performance_evaluator.py` | 将 snapshots + trades 聚合为 BacktestReport | 功能完整 |
| BacktestPlotter | `src/infrastructure/visualization/plotter.py` | 单策略三面板图（NAV / 日收益 / 回撤） | 仅支持单策略叠加绘制 |
| StrategyRegistry | `src/domain/strategy/registry.py` | `list_strategies()` / `create_strategy()` | 功能完整 |
| run_backtest CLI | `src/interfaces/cli/run_backtest.py` | 单策略回测入口 | 无多策略对比模式 |

### 2.2 关键约束

1. **Domain 红线**：`src/domain/` 禁止 import 第三方库（numpy、pandas、scipy）。相关性计算必须用纯 Python 或放到 infrastructure 层。
2. **数据类型**：Python 3.13+，`@dataclass(slots=True, kw_only=True)`，`list[X]` / `dict[K,V]` / `X | None`。
3. **回测循环**：每策略有独立的 sub_account（`BT_{strategy.name}_{date}`），快照序列独立。
4. **共享数据源**：行情数据通过 `market_gateway.load_bars()` 加载，当前每策略执行前不会重复拉取（数据在 gateway 内存中），但每策略需要独立的 trade_gateway 状态。

---

## 三、数据流设计

### 3.1 整体数据流

```
                        ┌─────────────────────┐
                        │   用户 CLI 输入       │
                        │  --strategies A,B,C  │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │  StrategyComparison  │
                        │     AppService       │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
            ┌───────▼──────┐ ┌────▼──────┐ ┌────▼──────┐
            │ Strategy A   │ │ Strategy B │ │ Strategy C │
            │ (sub-loop)   │ │ (sub-loop) │ │ (sub-loop) │
            └───────┬──────┘ └────┬──────┘ └────┬──────┘
                    │              │              │
            ┌───────▼──────┐ ┌────▼──────┐ ┌────▼──────┐
            │ Report A     │ │ Report B   │ │ Report C   │
            └───────┬──────┘ └────┬──────┘ └────┬──────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │ ComparisonReport     │
                        │  - metric_table      │
                        │  - correlation_matrix│
                        │  - best_combo        │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │  Visualization       │
                        │  - rich 表格输出      │
                        │  - matplotlib 图表   │
                        └─────────────────────┘
```

### 3.2 数据共享策略

**行情数据**：一次加载，所有策略共享同一个 `MockMarketGateway` 实例（`load_bars` 只需调用一次）。

**交易状态**：每策略独立的 `MockTradeGateway` 子账户。当前 `MockTradeGateway` 已支持 `create_sub_account()` + `activate_account()`，可以复用同一个 gateway 实例，通过 `activate_account` 切换活跃账户。

**回测循环**：有两种方案：

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A: 顺序独立循环 | 每策略跑完整循环，独立 snapshot 序列 | 与现有代码完全兼容，改动最小 | 时间轴需后面对齐 |
| B: 逐日交错循环 | 每个交易日，依次执行所有策略的 evaluate + settle | 天然时间对齐，共享 set_current_time | 需重构回测循环 |

**选定方案 A**：复用现有 `_run_unified_loop`，每策略独立执行。时间轴对齐在 ComparisonReport 层通过日期交集处理。

---

## 四、核心数据模型设计

### 4.1 BacktestReport 扩展（向后兼容）

```python
# src/domain/backtest/entities/backtest_report.py
# 仅新增一个可选字段，不破坏现有接口
@dataclass(frozen=True, slots=True, kw_only=True)
class BacktestReport:
    # ... 现有字段不变 ...
    strategy_name: str = ""  # 新增：策略名称，用于对比面板标识
```

### 4.2 ComparisonReport（新实体，Domain 层）

```python
# src/domain/backtest/entities/comparison_report.py

@dataclass(frozen=True, slots=True, kw_only=True)
class StrategyMetricRow:
    """单策略的指标摘要行。"""
    strategy_name: str
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    win_rate: float
    trade_count: int
    turnover_rate: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ComparisonReport:
    """多策略对比报告实体。

    Attributes:
        reports: 各策略的 BacktestReport 列表。
        metric_table: 指标对比表（每行一个策略）。
        correlation_matrix: 策略日收益率相关性矩阵。
        aligned_dates: 对齐后的公共日期序列。
        aligned_equity_curves: 对齐后的各策略净值曲线（归一化到 1.0）。
        best_by_sharpe: 夏普最高的策略名称。
        best_by_calmar: Calmar 最高的策略名称。
        recommended_combo: 推荐的低相关策略组合。
    """
    reports: list[BacktestReport]
    metric_table: list[StrategyMetricRow]
    correlation_matrix: list[list[float]]  # NxN 对称矩阵
    aligned_dates: list[datetime]
    aligned_equity_curves: dict[str, list[float]]  # strategy_name -> NAV curve
    best_by_sharpe: str
    best_by_calmar: str
    recommended_combo: list[str]
```

### 4.3 相关性分析值对象

```python
# src/domain/backtest/value_objects/correlation_result.py

@dataclass(frozen=True, slots=True, kw_only=True)
class CorrelationResult:
    """两个策略之间的相关性分析结果。"""
    strategy_a: str
    strategy_b: str
    pearson_correlation: float    # 皮尔逊相关系数 [-1, 1]
    daily_return_correlation: float  # 日收益率相关系数
```

---

## 五、相关性分析算法设计

### 5.1 约束

Domain 层禁止 numpy/scipy，相关性计算必须使用纯 Python。

### 5.2 皮尔逊相关系数

```
r = Σ[(xi - x̄)(yi - ȳ)] / sqrt[Σ(xi - x̄)² × Σ(yi - ȳ)²]
```

其中 xi、yi 是两个策略在第 i 个交易日的日收益率。

### 5.3 时间对齐

两个策略的 snapshot 序列可能长度不同（如一个在某日无交易）。对齐逻辑：
1. 取两个 snapshot 序列的日期交集。
2. 仅在公共日期上计算相关性。
3. 若公共日期 < 30，输出警告"样本不足，相关性不可靠"。

### 5.4 推荐组合算法

1. 计算所有策略对的 pearson_correlation。
2. 过滤出相关系数 < 0.5 的策略对（低相关 = 适合组合）。
3. 从低相关对中，选出 Sharpe 之和最高的一组。
4. 若所有策略两两相关系数 > 0.5，推荐 Sharpe 最高的单策略。

---

## 六、对比报告格式设计

### 6.1 终端表格（rich 库）

```
======================================================================
              STRATEGY COMPARISON REPORT
======================================================================
Date Range: 2020-01-01 to 2025-12-31 | Capital: 1,000,000
======================================================================

┌─────────────────┬──────────┬──────────┬──────────┬─────────────┐
│ Metric          │ 微盘价值  │ 多因子    │ DualMa   │ Best        │
├─────────────────┼──────────┼──────────┼──────────┼─────────────┤
│ Total Return    │ 156.32%  │ 89.45%   │ 42.18%   │ 微盘价值     │
│ Annualized      │  21.08%  │ 13.67%   │  7.32%   │ 微盘价值     │
│ Max Drawdown    │ -18.45%  │ -22.30%  │ -31.50%  │ 微盘价值     │
│ Sharpe Ratio    │   1.82   │   1.15   │   0.58   │ 微盘价值     │
│ Sortino Ratio   │   2.45   │   1.62   │   0.79   │ 微盘价值     │
│ Calmar Ratio    │   1.14   │   0.61   │   0.23   │ 微盘价值     │
│ Win Rate        │  58.30%  │  52.10%  │  45.60%  │ 微盘价值     │
│ Trade Count     │      126 │      340 │       87 │ -           │
│ Turnover Rate   │   0.15%  │   0.28%  │   0.08%  │ -           │
└─────────────────┴──────────┴──────────┴──────────┴─────────────┘

Correlation Matrix:
┌──────────┬──────────┬──────────┬──────────┐
│          │ 微盘价值  │ 多因子    │ DualMa   │
├──────────┼──────────┼──────────┼──────────┤
│ 微盘价值  │   1.00   │   0.72   │   0.35   │
│ 多因子    │   0.72   │   1.00   │   0.28   │
│ DualMa   │   0.35   │   0.28   │   1.00   │
└──────────┴──────────┴──────────┴──────────┘

Recommended Combo: [微盘价值, DualMa] (low correlation: 0.35, combined Sharpe: 2.40)
======================================================================
```

### 6.2 Matplotlib 图表

**图 1：收益曲线叠加**（主图）
- X 轴：日期（统一时间轴）
- Y 轴：归一化净值（初始值 = 1.0）
- 每策略一条曲线，颜色区分
- 标注 Best 标记

**图 2：回撤曲线叠加**
- 每策略一条回撤曲线
- 半透明填充

**图 3：滚动夏普比率**（120 日窗口）
- 展示策略的风险调整收益稳定性

**图 4：相关性热力图**
- NxN 热力图，显示策略间相关系数
- 色阶：蓝（低相关）→ 红（高相关）

---

## 七、CLI 接口设计

```bash
# 多策略对比
python -m src.interfaces.cli.compare_strategies \
    --strategies micro_value,multi_factor,dual_ma \
    --start-date 2020-01-01 \
    --end-date 2025-12-31 \
    --symbols 000021.SZ \
    --plot

# 使用配置文件
python -m src.interfaces.cli.compare_strategies --config resources/compare.yaml

# 指定参数覆盖
python -m src.interfaces.cli.compare_strategies \
    --strategies multi_factor \
    --params multi_factor.top_n=20
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `--strategies` | str | 是 | 逗号分隔的策略名称列表 |
| `--start-date` | str | 否 | 回测开始日期（默认从配置） |
| `--end-date` | str | 否 | 回测结束日期（默认从配置） |
| `--symbols` | str | 否 | 标的列表（默认从配置） |
| `--plot` | flag | 否 | 是否显示 matplotlib 图表 |
| `--config` | str | 否 | YAML 配置文件路径 |
| `--params` | str | 否 | 策略参数覆盖（key=value 格式） |

---

## 八、层职责划分

| 层 | 新增组件 | 职责 |
|----|---------|------|
| Domain | `ComparisonReport`, `StrategyMetricRow` | 对比报告实体，纯数据 |
| Domain | `ComparisonReportService` | 从多个 BacktestReport 构建 ComparisonReport（指标提取、时间对齐、相关性计算） |
| Application | `StrategyComparisonAppService` | 编排多策略回测 → 构建 ComparisonReport → 触发可视化 |
| Infrastructure | `ComparisonPlotter` | matplotlib 多策略叠加图表 |
| Infrastructure | `ComparisonRichPrinter` | rich 终端表格输出 |
| Interfaces | `compare_strategies.py` | CLI 入口 |

### 依赖方向

```
Interfaces (CLI)
    ↓
Application (StrategyComparisonAppService)
    ↓
Domain (ComparisonReport, ComparisonReportService, BacktestReport)
    ↑
Infrastructure (ComparisonPlotter, ComparisonRichPrinter)
```

注意：`ComparisonReportService` 是纯 Domain 服务，不依赖任何第三方库。相关性计算使用纯 Python 实现。rich 和 matplotlib 仅在 Infrastructure 层使用。

---

## 九、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 多策略顺序执行耗时长 | 用户体验差 | Phase 1 先保证正确性；Phase 2 可引入并行执行（multiprocessing） |
| 策略 snapshot 日期不对齐 | 相关性计算错误 | 严格取日期交集，不足 30 天警告 |
| Domain 层相关性计算性能 | 大样本 O(n) 可接受 | 仅日频，年化 252 个点，无性能问题 |
| MockTradeGateway 状态隔离 | 策略间资金互相影响 | 已有 create_sub_account + activate_account 机制 |
| rich/matplotlib 未安装 | 基础功能不可用 | 优雅降级：rich 不可用用普通 print，matplotlib 不可用跳过图表 |
