# 组合风险管理 -- 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**关联设计**: `2026-05-31-portfolio-risk-design.md`
**所属阶段**: Phase 3 -- 多策略组合 (子项目 3.3)
**状态**: 草案

---

## 一、任务概览

将组合风险管理设计文档拆分为可执行的实现任务。按依赖关系排序，每个任务可独立提交。

**总任务数**: 12
**预估总工时**: 8-10 天
**前置依赖**: 策略对比面板（`ComparisonReport`）、资金分配引擎（`CapitalAllocationEngine`）

---

## 二、依赖关系图

```
T1: 值对象定义 ──────────┬──────────────────────────────────────┐
                         │                                      │
T2: CorrelationAnalyzer ──┤                                      │
                         │                                      │
T3: DiversificationEvaluator ──┤                                 │
                         │                                      │
T4: PortfolioVaRCalculator ──┤                                   │
                         │                                      │
T5: StressScenario + 历史场景 ──┤                                │
                         │                                      │
T6: StressTestRunner ────┤                                      │
                         │                                      │
T7: MLModelRiskMonitor ──┤                                      │
                         │                                      │
T8: PortfolioRiskService ┘                                      │
                         │                                      │
T9: PortfolioRiskRichPrinter (Infrastructure)                   │
                         │                                      │
T10: PortfolioRiskPlotter (Infrastructure)                      │
                         │                                      │
T11: PortfolioRiskAppService (Application)                      │
                         │                                      │
T12: CLI 入口 + 集成测试 ┘
```

**关键路径**: T1 → T2 → T8 → T11 → T12

---

## 三、任务详细分解

### T1: 值对象定义

**目标**: 定义组合风控所需的全部值对象。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/value_objects/correlation_matrix.py` | `CorrelationMatrix` 类 |
| `src/domain/risk/value_objects/diversification_result.py` | `DiversificationResult` 类 |
| `src/domain/risk/value_objects/var_result.py` | `VaRResult` 类 |
| `src/domain/risk/value_objects/stress_test_result.py` | `StressTestResult` 类 |
| `src/domain/risk/value_objects/ml_risk_alert.py` | `MLRiskAlert` 类 |
| `src/domain/risk/value_objects/portfolio_risk_report.py` | `PortfolioRiskReport` 类 |

**代码模式**: 统一使用 `@dataclass(frozen=True, slots=True, kw_only=True)`。

**验收标准**:
- [ ] 所有值对象定义完整，字段与设计文档一致
- [ ] `CorrelationMatrix` 的 `average_correlation`、`max_correlation_pair`、`min_correlation_pair` 属性实现正确
- [ ] `src/domain/risk/value_objects/__init__.py` 导出所有新类
- [ ] 单元测试覆盖：构造、属性计算、边界条件（空矩阵、单策略）

**预估工时**: 0.5 天

---

### T2: CorrelationAnalyzer

**目标**: 实现纯 Python 的相关性分析器。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/__init__.py` | 包初始化 |
| `src/domain/risk/services/portfolio/correlation_analyzer.py` | `CorrelationAnalyzer` 类 |

**核心方法**:
- `compute_correlation_matrix(strategy_returns) -> CorrelationMatrix`
- `compute_rolling_correlation(returns_a, returns_b, window) -> list[float]`
- `_pearson(x, y) -> float` (静态方法)

**算法要点**:
- 皮尔逊相关系数：`r = cov(X,Y) / (std_X * std_Y)`
- 滚动窗口：滑动窗口计算，窗口不足时返回空序列
- 时间对齐：调用方负责对齐，分析器假设输入已对齐

**测试文件**: `tests/domain/risk/services/portfolio/test_correlation_analyzer.py`

**验收标准**:
- [ ] 完全正相关 (r=1.0)、完全负相关 (r=-1.0)、无关 (r≈0) 三种情况正确
- [ ] 滚动相关性序列长度正确
- [ ] 边界条件：空序列、单元素、全零序列
- [ ] 与 numpy.corrcoef 结果对比（测试中可用 numpy 验证，生产代码不用）
- [ ] 无任何第三方 import

**预估工时**: 1 天

---

### T3: DiversificationEvaluator

**目标**: 实现分散度评估器。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/diversification_evaluator.py` | `DiversificationEvaluator` 类 |

**核心方法**:
- `evaluate(weights, volatilities, correlation) -> DiversificationResult`

**算法要点**:
- 组合波动率：`σp = sqrt(w^T × Σ × w)`，其中 `Σ[i][j] = ρ[i][j] × σi × σj`
- 分散比率：`DR = Σ(wi × σi) / σp`
- HHI：`Σ(wi²)`
- 有效策略数：`1 / HHI`

**测试文件**: `tests/domain/risk/services/portfolio/test_diversification_evaluator.py`

**验收标准**:
- [ ] 等权、完全正相关组合：DR ≈ 1.0
- [ ] 等权、零相关组合：DR = sqrt(N)
- [ ] 单策略：DR = 1.0, N_eff = 1.0
- [ ] HHI 计算正确
- [ ] `is_well_diversified` 判定正确

**预估工时**: 0.5 天

---

### T4: PortfolioVaRCalculator

**目标**: 实现组合 VaR 计算器。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/portfolio_var_calculator.py` | `PortfolioVaRCalculator` 类 |

**核心方法**:
- `calculate_historical_var(...) -> VaRResult`
- `calculate_parametric_var(...) -> VaRResult`
- `calculate_portfolio_returns(strategy_returns, weights) -> list[float]`
- `_percentile(data, p) -> float` (静态方法)
- `_z_score(confidence_level) -> float` (静态方法)

**算法要点**:
- 历史 VaR：排序后取分位数，`VaR = -percentile(returns, α)`
- 参数 VaR：`VaR = -(μ - z_α × σ) × value × sqrt(N)`
- CVaR：`-mean(returns[returns <= -VaR])`
- 组合收益：`rp_i = Σ(wj × rj_i)`

**测试文件**: `tests/domain/risk/services/portfolio/test_portfolio_var_calculator.py`

**验收标准**:
- [ ] 历史 VaR 与手动排序计算一致
- [ ] 参数 VaR 与手动公式计算一致
- [ ] CVaR >= VaR（数学性质）
- [ ] 持有期调整：`sqrt(N)` 规则正确
- [ ] `_percentile` 与 numpy.percentile 结果一致
- [ ] 组合收益加权求和正确
- [ ] 边界条件：空序列、单元素

**预估工时**: 1 天

---

### T5: StressScenario + 历史场景数据

**目标**: 定义压力测试场景，预置 A 股历史极端行情数据。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/stress_scenarios/__init__.py` | 包初始化 |
| `src/domain/risk/services/portfolio/stress_scenarios/historical_scenarios.py` | 4 个历史场景定义 + 工厂函数 |
| `src/domain/risk/services/portfolio/stress_scenarios/hypothetical_scenarios.py` | 5 个假设场景定义 + 工厂函数 |

**历史场景**:
- 2015 股灾：2015-06-12 ~ 2015-07-09，基准跌幅 -43%
- 2018 熊市：2018-01-29 ~ 2018-12-28，基准跌幅 -30%
- 2020 新冠：2020-01-20 ~ 2020-03-23，基准跌幅 -16%
- 2022 调整：2022-01-04 ~ 2022-10-31，基准跌幅 -27%

**假设场景**:
- 市场暴跌：shock_factor = -0.10
- 相关性崩溃：crisis_correlation = 0.9
- 流动性危机：liquidity_penalty = 2.0
- 单策略失效：loss_per_day = -0.05, duration = 5
- ML 模型失效：duration = 20

**验收标准**:
- [ ] 4 个历史场景定义完整，日期和跌幅准确
- [ ] 5 个假设场景参数合理
- [ ] 工厂函数返回正确的 `StressScenario` 列表
- [ ] 场景类型标识正确（"historical" / "hypothetical"）

**预估工时**: 0.5 天

---

### T6: StressTestRunner

**目标**: 实现压力测试运行器。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/stress_test_runner.py` | `StressTestRunner` 类 |

**核心方法**:
- `run_historical(strategy_reports, weights) -> list[StressTestResult]`
- `run_hypothetical(strategy_reports, weights, correlation) -> list[StressTestResult]`
- `run_all(strategy_reports, weights, correlation) -> list[StressTestResult]`

**算法要点**:
- 历史场景：从 BacktestReport 的 dates 中找到场景区间，提取该区间的收益率，加权求和得到组合损失
- 假设场景：根据参数构造冲击（收益率缩放、相关性替换等）
- 通过/不通过判定：组合损失 < loss_threshold（默认 15%）

**测试文件**: `tests/domain/risk/services/portfolio/test_stress_test_runner.py`

**验收标准**:
- [ ] 历史场景能正确从 BacktestReport 中提取区间数据
- [ ] 假设场景的冲击计算正确
- [ ] 通过/不通过判定逻辑正确
- [ ] 边界条件：场景区间无数据、单策略

**预估工时**: 1 天

---

### T7: MLModelRiskMonitor

**目标**: 实现 ML 模型风险监控器。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/ml_model_risk_monitor.py` | `MLModelRiskMonitor` 类 |

**核心方法**:
- `check_overfitting(strategy_name, train_metrics, test_metrics) -> list[MLRiskAlert]`
- `check_feature_drift(strategy_name, feature_name, train_mean, train_std, online_mean, online_std) -> MLRiskAlert | None`
- `check_performance_degradation(strategy_name, rolling_sharpe, rolling_win_rate, consecutive_loss_days) -> list[MLRiskAlert]`

**算法要点**:
- 过拟合：IC 衰减率 > 50%、夏普衰减率 > 40%、胜率衰减 > 15%
- 特征漂移：均值偏移 > 1.0 (warning) / > 2.0 (critical)，方差比 < 0.5 或 > 2.0
- 表现退化：滚动指标 z-score < -2，连续亏损 >= 5 天

**测试文件**: `tests/domain/risk/services/portfolio/test_ml_model_risk_monitor.py`

**验收标准**:
- [ ] 过拟合检测：衰减率计算正确，阈值判定正确
- [ ] 特征漂移：均值偏移和方差比计算正确，告警级别正确
- [ ] 表现退化：z-score 计算正确，连续亏损检测正确
- [ ] 边界条件：train_std = 0（防止除零）、空序列

**预估工时**: 1 天

---

### T8: PortfolioRiskService

**目标**: 实现组合风控服务（聚合入口）。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/domain/risk/services/portfolio/portfolio_risk_service.py` | `PortfolioRiskService` 类 |

**核心方法**:
- `generate_report(strategy_reports, weights) -> PortfolioRiskReport`
- `assess_risk_level(...) -> str`
- `generate_recommendations(...) -> list[str]`

**依赖注入**:
```python
def __init__(
    self,
    correlation_analyzer: CorrelationAnalyzer | None = None,
    diversification_evaluator: DiversificationEvaluator | None = None,
    var_calculator: PortfolioVaRCalculator | None = None,
    stress_test_runner: StressTestRunner | None = None,
    ml_risk_monitor: MLModelRiskMonitor | None = None,
    var_confidence_levels: list[float] | None = None,
) -> None:
```

**流程**:
1. 计算相关性矩阵
2. 计算各策略波动率
3. 评估分散度
4. 计算组合收益率
5. 计算 VaR（95% 和 99%）
6. 运行压力测试
7. 检查 ML 风险（若有数据）
8. 综合评定风险等级
9. 生成风险建议
10. 组装 PortfolioRiskReport

**测试文件**: `tests/domain/risk/services/portfolio/test_portfolio_risk_service.py`

**验收标准**:
- [ ] 端到端：传入 3 个策略的 BacktestReport + 权重，输出完整报告
- [ ] 风险等级判定逻辑与设计文档一致
- [ ] 建议生成逻辑覆盖所有触发条件
- [ ] 所有子服务通过依赖注入，可独立 mock 测试
- [ ] 无第三方 import

**预估工时**: 1 天

---

### T9: PortfolioRiskRichPrinter (Infrastructure)

**目标**: 实现 rich 终端输出。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/infrastructure/visualization/portfolio_risk_printer.py` | `PortfolioRiskRichPrinter` 类 |

**输出内容**:
- 组合风控报告头部（策略数、整体风险等级）
- 相关性矩阵表格
- 分散度指标
- VaR / CVaR 表格
- 压力测试结果表格
- ML 风险告警列表
- 风险建议

**依赖**: `rich` 库（仅 Infrastructure 层可用）

**验收标准**:
- [ ] 输出格式与设计文档示例一致
- [ ] 风险等级有颜色标识（green/yellow/red）
- [ ] 数值格式化正确（百分比、小数位）
- [ ] rich 不可用时优雅降级为 print

**预估工时**: 0.5 天

---

### T10: PortfolioRiskPlotter (Infrastructure)

**目标**: 实现 matplotlib 图表。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/infrastructure/visualization/portfolio_risk_plotter.py` | `PortfolioRiskPlotter` 类 |

**图表**:
- 图 1：相关性热力图（NxN，蓝→红色阶）
- 图 2：滚动相关性折线图（策略对的 60 日滚动相关）
- 图 3：VaR 与 CVaR 柱状图
- 图 4：压力测试结果柱状图（各场景损失对比）

**依赖**: `matplotlib`（仅 Infrastructure 层可用）

**验收标准**:
- [ ] 4 个图表生成正确
- [ ] 中文标签正常显示
- [ ] 颜色方案与现有 BacktestPlotter 一致
- [ ] matplotlib 不可用时优雅降级

**预估工时**: 0.5 天

---

### T11: PortfolioRiskAppService (Application)

**目标**: 实现应用层服务，编排数据收集和报告生成。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/application/portfolio_risk_app.py` | `PortfolioRiskAppService` 类 |

**职责**:
1. 接收策略名称列表和权重
2. 从回测结果或策略池中收集各策略的 BacktestReport
3. 调用 `PortfolioRiskService.generate_report`
4. 调用 `PortfolioRiskRichPrinter` 输出终端报告
5. 调用 `PortfolioRiskPlotter` 生成图表（可选）

**依赖**:
- `PortfolioRiskService` (Domain)
- `PortfolioRiskRichPrinter` (Infrastructure)
- `PortfolioRiskPlotter` (Infrastructure)
- `BacktestAppService` 或策略池数据源

**验收标准**:
- [ ] 端到端流程可执行
- [ ] 依赖通过构造函数注入
- [ ] 错误处理：策略数据不足时给出明确提示

**预估工时**: 0.5 天

---

### T12: CLI 入口 + 集成测试

**目标**: 创建命令行入口和端到端集成测试。
**文件**:

| 文件路径 | 内容 |
|---------|------|
| `src/interfaces/cli/portfolio_risk.py` | CLI 入口 |
| `tests/integration/test_portfolio_risk.py` | 集成测试 |

**CLI 接口**:
```bash
# 组合风控报告
python -m src.interfaces.cli.portfolio_risk \
    --strategies micro_value,multi_factor,dual_ma \
    --start-date 2020-01-01 \
    --end-date 2025-12-31 \
    --weights 0.4,0.35,0.25 \
    --plot

# 使用默认等权
python -m src.interfaces.cli.portfolio_risk \
    --strategies micro_value,multi_factor,dual_ma \
    --equal-weight
```

**集成测试场景**:
- 3 个策略的完整风控报告生成
- 等权 vs 自定义权重
- 单策略退化情况
- 相关性过高时的告警

**验收标准**:
- [ ] CLI 参数解析正确
- [ ] 端到端：从回测到报告输出完整可执行
- [ ] 集成测试通过
- [ ] 帮助信息清晰

**预估工时**: 0.5 天

---

## 四、前置依赖清单

| 依赖项 | 状态 | 影响范围 |
|--------|------|---------|
| `ComparisonReport` (策略对比面板) | 待实现 | T8 可复用 correlation_matrix，但不阻塞（可独立计算） |
| `CapitalAllocationEngine` (资金分配引擎) | 待实现 | T8 需要 weights，但可通过参数传入，不阻塞 |
| `StrategyPoolEntry` (策略池管理) | 待实现 | T7 的 ML 风险告警反馈需要策略池，但 T7 本身不阻塞 |
| `BacktestReport` (回测报告) | **已完成** | T2-T8 的核心数据源 |

**关键结论**: `BacktestReport` 已存在，组合风控的核心功能可以独立于其他 Phase 3 子项目先行实现。`weights` 通过参数传入，不硬依赖资金分配引擎。

---

## 五、测试策略

### 5.1 单元测试

每个 Domain 层组件都有对应的单元测试：

| 组件 | 测试文件 | 测试重点 |
|------|---------|---------|
| `CorrelationAnalyzer` | `tests/domain/risk/services/portfolio/test_correlation_analyzer.py` | 皮尔逊相关系数正确性、滚动相关性、边界条件 |
| `DiversificationEvaluator` | `tests/domain/risk/services/portfolio/test_diversification_evaluator.py` | DR、HHI、N_eff 计算正确性 |
| `PortfolioVaRCalculator` | `tests/domain/risk/services/portfolio/test_portfolio_var_calculator.py` | 历史/参数 VaR、CVaR、分位数计算 |
| `StressTestRunner` | `tests/domain/risk/services/portfolio/test_stress_test_runner.py` | 历史/假设场景执行、通过判定 |
| `MLModelRiskMonitor` | `tests/domain/risk/services/portfolio/test_ml_model_risk_monitor.py` | 过拟合、漂移、退化检测 |
| `PortfolioRiskService` | `tests/domain/risk/services/portfolio/test_portfolio_risk_service.py` | 端到端报告生成、风险等级、建议 |

### 5.2 集成测试

| 测试文件 | 测试场景 |
|---------|---------|
| `tests/integration/test_portfolio_risk.py` | 3 策略完整流程、权重敏感性、告警触发 |

### 5.3 测试数据

使用构造的确定性数据（非随机），确保测试可重复：
- 3 个策略各 100 天的日收益率
- 预设相关性：策略 A 与 B 高相关 (0.8)，A 与 C 低相关 (0.2)
- 预设波动率：A=15%, B=18%, C=12%

---

## 六、实施顺序建议

### Sprint 1: 核心计算引擎 (T1-T4)

**目标**: 相关性、分散度、VaR 三大核心计算能力就绪。

| 天 | 任务 | 交付物 |
|----|------|--------|
| Day 1 | T1: 值对象定义 | 6 个值对象文件 + 测试 |
| Day 2 | T2: CorrelationAnalyzer | 相关性分析器 + 测试 |
| Day 3 | T3 + T4: 分散度 + VaR | 两个计算服务 + 测试 |

### Sprint 2: 风险评估扩展 (T5-T7)

**目标**: 压力测试和 ML 风险监控就绪。

| 天 | 任务 | 交付物 |
|----|------|--------|
| Day 4 | T5 + T6: 场景定义 + 压力测试 | 压力测试完整功能 + 测试 |
| Day 5 | T7: ML 风险监控 | ML 监控完整功能 + 测试 |

### Sprint 3: 聚合与输出 (T8-T12)

**目标**: 端到端可执行。

| 天 | 任务 | 交付物 |
|----|------|--------|
| Day 6 | T8: PortfolioRiskService | 聚合服务 + 测试 |
| Day 7 | T9 + T10: 终端输出 + 图表 | 可视化层 |
| Day 8 | T11 + T12: AppService + CLI | 端到端可执行 |

---

## 七、验收标准总览

### 功能验收

- [ ] 传入 3 个策略的 BacktestReport + 权重，输出完整的 PortfolioRiskReport
- [ ] 相关性矩阵计算正确（与手工计算/交叉验证一致）
- [ ] VaR 计算正确（历史法 + 参数法）
- [ ] 压力测试覆盖 4 个历史场景 + 5 个假设场景
- [ ] ML 风险监控覆盖过拟合、特征漂移、表现退化三种告警
- [ ] 风险等级判定与设计文档一致
- [ ] 风险建议覆盖所有触发条件

### 非功能验收

- [ ] Domain 层零第三方 import（ruff check 验证）
- [ ] 所有值对象使用 `frozen=True, slots=True, kw_only=True`
- [ ] 单元测试覆盖率 > 90%
- [ ] 集成测试端到端通过
- [ ] CLI 可执行，帮助信息清晰

### 成功指标对照

| 指标 | 目标 | 验证方式 |
|------|------|---------|
| 组合最大回撤 < 单一策略最大回撤的 70% | 通过分散度和相关性评估辅助实现 | 压力测试 + 回测对比 |
| 组合相关性 < 0.5 | 通过相关性分析监控和告警 | CorrelationMatrix 输出 |
| 通过历史极端行情压力测试 | 4 个历史场景全部通过 | StressTestRunner 输出 |

---

**文档结束**
