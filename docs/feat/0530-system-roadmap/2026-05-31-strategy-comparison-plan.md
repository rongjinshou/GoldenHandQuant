# 策略对比面板 — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划 / 任务分解
**状态**: 草案
**关联设计文档**: `2026-05-31-strategy-comparison-design.md`

---

## 实现概览

共 6 个阶段，预计 12 个原子任务。依赖关系如下：

```
Phase 1: Domain 层（无依赖）
  ├── Task 1: BacktestReport 新增 strategy_name 字段
  ├── Task 2: 新增 ComparisonReport 实体
  ├── Task 3: 新增 ComparisonReportService 领域服务
  └── Task 4: 单元测试

Phase 2: Application 层（依赖 Phase 1）
  ├── Task 5: 新增 StrategyComparisonAppService
  └── Task 6: 单元测试

Phase 3: Infrastructure 层（依赖 Phase 1）
  ├── Task 7: 新增 ComparisonPlotter
  └── Task 8: 新增 ComparisonRichPrinter

Phase 4: Interfaces 层（依赖 Phase 2 + 3）
  ├── Task 9: 新增 CLI 入口 compare_strategies.py
  └── Task 10: 集成测试

Phase 5: 配置扩展（可选）
  └── Task 11: compare.yaml 配置支持

Phase 6: 收尾
  └── Task 12: 文档更新 + ruff check
```

---

## Phase 1: Domain 层（纯业务逻辑，无第三方依赖）

### Task 1: BacktestReport 新增 strategy_name 字段

**文件**: `src/domain/backtest/entities/backtest_report.py`

**变更**:
- 在 `BacktestReport` dataclass 中新增 `strategy_name: str = ""` 字段
- `frozen=True` 下默认值允许向后兼容，现有代码无需改动

**验证**: 现有测试全部通过，无回归。

**预估**: 5 分钟

---

### Task 2: 新增 ComparisonReport 实体

**文件**: `src/domain/backtest/entities/comparison_report.py`（新建）

**内容**:
- `StrategyMetricRow` dataclass：单策略指标摘要行
  - 字段：strategy_name, total_return, annualized_return, max_drawdown, sharpe_ratio, sortino_ratio, calmar_ratio, win_rate, trade_count, turnover_rate
- `ComparisonReport` dataclass：多策略对比报告
  - 字段：reports, metric_table, correlation_matrix, aligned_dates, aligned_equity_curves, best_by_sharpe, best_by_calmar, recommended_combo

**验证**: 文件可 import，dataclass 实例化无报错。

**预估**: 15 分钟

---

### Task 3: 新增 ComparisonReportService 领域服务

**文件**: `src/domain/backtest/services/comparison_report_service.py`（新建）

**核心方法**:

```python
class ComparisonReportService:
    def build_comparison(self, reports: list[BacktestReport]) -> ComparisonReport:
        """从多个 BacktestReport 构建对比报告。"""
        # 1. 提取指标表
        metric_table = self._extract_metrics(reports)
        # 2. 对齐时间轴
        aligned_dates, aligned_curves = self._align_equity_curves(reports)
        # 3. 计算相关性矩阵
        corr_matrix = self._compute_correlation_matrix(reports, aligned_dates)
        # 4. 排名
        best_sharpe = max(reports, key=lambda r: r.sharpe_ratio).strategy_name
        best_calmar = max(reports, key=lambda r: r.calmar_ratio).strategy_name
        # 5. 推荐组合
        combo = self._recommend_combo(reports, corr_matrix)
        return ComparisonReport(...)
```

**内部方法**:

1. `_extract_metrics(reports)` -> `list[StrategyMetricRow]`
   - 从每个 BacktestReport 提取指标，构造 StrategyMetricRow

2. `_align_equity_curves(reports)` -> `(dates, curves_dict)`
   - 取所有报告 dates 的交集
   - 将各策略 equity_curve 按公共日期对齐
   - 归一化到初始值 = 1.0

3. `_compute_correlation_matrix(reports, aligned_dates)` -> `list[list[float]]`
   - 纯 Python 实现皮尔逊相关系数
   - 仅使用对齐日期上的 daily_returns
   - 公共日期 < 30 时打印警告

4. `_recommend_combo(reports, corr_matrix)` -> `list[str]`
   - 找相关系数 < 0.5 的策略对
   - 从中选 Sharpe 之和最高的一组
   - 若无低相关对，返回 Sharpe 最高的单策略

**约束**:
- 纯 Python，禁止 numpy/scipy/pandas
- 皮尔逊相关系数公式：`r = Σ[(xi-x̄)(yi-ȳ)] / sqrt[Σ(xi-x̄)² × Σ(yi-ȳ)²]`
- 所有计算基于 `math` 标准库

**验证**: 单元测试覆盖（见 Task 4）。

**预估**: 45 分钟

---

### Task 4: Domain 层单元测试

**文件**: `tests/domain/backtest/services/test_comparison_report_service.py`（新建）

**测试用例**:

| # | 测试名 | 场景 | 预期 |
|---|--------|------|------|
| 1 | `test_build_comparison_two_strategies` | 两个策略，相同日期范围 | metric_table 有 2 行，corr_matrix 为 2x2 |
| 2 | `test_build_comparison_three_strategies` | 三个策略 | metric_table 有 3 行，corr_matrix 为 3x3 |
| 3 | `test_correlation_perfect_positive` | 两个完全正相关策略 | pearson ≈ 1.0 |
| 4 | `test_correlation_perfect_negative` | 两个完全负相关策略 | pearson ≈ -1.0 |
| 5 | `test_correlation_uncorrelated` | 两个不相关策略 | pearson ≈ 0.0 |
| 6 | `test_align_equity_curves_different_dates` | 策略 A 有 100 天，策略 B 有 80 天 | 对齐后长度 = 交集天数 |
| 7 | `test_recommend_low_correlation_pair` | 三个策略，A-B 低相关 | 推荐 A+B |
| 8 | `test_recommend_single_when_all_correlated` | 所有策略高相关 | 推荐 Sharpe 最高的单策略 |
| 9 | `test_insufficient_data_warning` | 公共日期 < 30 | 打印警告（用 capsys 验证） |
| 10 | `test_single_strategy_no_correlation` | 只有一个策略 | corr_matrix 为空，combo 为该策略 |

**测试数据构造**:
- 使用 `DailySnapshot` 手动构造已知收益率序列
- 使用 `BacktestReport` 构造已知 equity_curve

**验证**: `pytest tests/domain/backtest/services/test_comparison_report_service.py -v` 全绿。

**预估**: 40 分钟

---

## Phase 2: Application 层（编排层）

### Task 5: 新增 StrategyComparisonAppService

**文件**: `src/application/strategy_comparison_app.py`（新建）

**职责**:
1. 接收策略名称列表 + 回测参数
2. 通过 StrategyRegistry 创建策略实例
3. 复用 BacktestAppService.run_backtest(strategies=list) 执行多策略回测
4. 调用 ComparisonReportService.build_comparison() 构建对比报告
5. 触发 Infrastructure 层的可视化输出

**核心方法**:

```python
class StrategyComparisonAppService:
    def __init__(
        self,
        backtest_service: BacktestAppService,
        comparison_service: ComparisonReportService,
    ): ...

    def run_comparison(
        self,
        strategy_names: list[str],
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        base_timeframe: Timeframe = Timeframe.DAY_1,
        strategy_params: dict[str, dict[str, Any]] | None = None,
        plot: bool = False,
    ) -> ComparisonReport:
        """执行多策略对比回测，返回 ComparisonReport。"""
        # 1. 从 registry 创建策略实例
        strategies = [create_strategy(name, strategy_params.get(name)) for name in strategy_names]
        # 2. 填入 strategy_name
        for s in strategies:
            # BaseStrategy 子类可能已有 name 属性
            pass
        # 3. 执行多策略回测
        reports = self.backtest_service.run_backtest(
            symbols=symbols, start_date=start_date, end_date=end_date,
            base_timeframe=base_timeframe, strategies=strategies,
        )
        # 4. 填充 strategy_name
        for report, name in zip(reports, strategy_names):
            # BacktestReport 是 frozen，需要 replace
            pass
        # 5. 构建对比报告
        return self.comparison_service.build_comparison(reports)
```

**注意**: `BacktestReport` 是 `frozen=True`，填充 `strategy_name` 需使用 `dataclasses.replace()` 或在 `PerformanceEvaluator.evaluate()` 时传入。

**更优方案**：修改 `PerformanceEvaluator.evaluate()` 增加 `strategy_name` 参数，直接在构造时填入，避免 frozen 对象的 replace 开销。

**验证**: 单元测试。

**预估**: 30 分钟

---

### Task 6: Application 层单元测试

**文件**: `tests/application/test_strategy_comparison_app.py`（新建）

**测试用例**:

| # | 测试名 | 场景 | 预期 |
|---|--------|------|------|
| 1 | `test_run_comparison_returns_report` | 传入 2 个策略名 | 返回 ComparisonReport，metric_table 有 2 行 |
| 2 | `test_run_comparison_unknown_strategy_raises` | 传入不存在的策略名 | 抛出 KeyError |
| 3 | `test_run_comparison_passes_params` | 传入自定义参数 | 策略使用自定义参数创建 |

**验证**: `pytest tests/application/test_strategy_comparison_app.py -v` 全绿。

**预估**: 20 分钟

---

## Phase 3: Infrastructure 层（可视化输出）

### Task 7: 新增 ComparisonPlotter

**文件**: `src/infrastructure/visualization/comparison_plotter.py`（新建）

**功能**:
- 图 1：多策略收益曲线叠加（归一化净值）
- 图 2：多策略回撤曲线叠加
- 图 3：滚动夏普比率（120 日窗口）
- 图 4：相关性热力图

**设计要点**:
- 复用 `BacktestPlotter` 的样式风格（`bmh` 样式、网格、标题格式）
- matplotlib 不可用时优雅降级（`HAS_MATPLOTLIB` 检查）
- 图表保存到 `output/comparison_{timestamp}.png`

**验证**: 手动运行，确认图表生成正确。

**预估**: 35 分钟

---

### Task 8: 新增 ComparisonRichPrinter

**文件**: `src/infrastructure/visualization/comparison_printer.py`（新建）

**功能**:
- 使用 rich 库输出对比表格（StrategyMetricRow 表）
- 使用 rich 库输出相关性矩阵
- 输出推荐组合
- rich 不可用时降级为普通 print

**输出格式**：参见设计文档第六章。

**验证**: 手动运行，确认终端输出格式正确。

**预估**: 25 分钟

---

## Phase 4: Interfaces 层（CLI 入口）

### Task 9: 新增 CLI 入口

**文件**: `src/interfaces/cli/compare_strategies.py`（新建）

**功能**:
- 解析命令行参数（argparse）
- 初始化基础设施（data fetcher, market gateway, trade gateway）
- 构建 StrategyComparisonAppService
- 执行对比
- 输出报告

**核心流程**:

```python
def main():
    args = parse_args()
    # 1. 加载配置
    settings = load_backtest_config()
    # 2. 初始化基础设施
    market_gateway = MockMarketGateway()
    trade_gateway = MockTradeGateway(...)
    fetcher = create_fetcher(...)
    # 3. 准备数据（一次性加载）
    app_service.prepare_data(symbols, timeframe, start_date, end_date)
    # 4. 执行对比
    comparison_service = ComparisonReportService()
    comparison_app = StrategyComparisonAppService(app_service, comparison_service)
    report = comparison_app.run_comparison(...)
    # 5. 输出
    ComparisonRichPrinter().print(report)
    if args.plot:
        ComparisonPlotter().plot(report)
```

**验证**: 端到端运行，确认完整流程无报错。

**预估**: 30 分钟

---

### Task 10: 集成测试

**文件**: `tests/interfaces/cli/test_compare_strategies.py`（新建）

**测试用例**:

| # | 测试名 | 场景 | 预期 |
|---|--------|------|------|
| 1 | `test_compare_two_strategies_e2e` | 使用 mock 数据，对比 dual_ma 和 micro_value | 返回 ComparisonReport，metric_table 有 2 行 |
| 2 | `test_compare_prints_table` | 运行 main() | 终端输出包含策略名称（用 capsys 验证） |

**验证**: `pytest tests/interfaces/cli/test_compare_strategies.py -v` 全绿。

**预估**: 20 分钟

---

## Phase 5: 配置扩展（可选）

### Task 11: compare.yaml 配置支持

**文件**: `src/infrastructure/config/settings.py`（扩展）

**新增配置结构**:

```yaml
# resources/compare.yaml
compare:
  strategies:
    - name: micro_value
      params:
        top_n: 9
    - name: multi_factor
      params:
        top_n: 10
    - name: dual_ma
  backtest:
    symbols: ["000021.SZ"]
    start_date: "2020-01-01"
    end_date: "2025-12-31"
    initial_capital: 1000000
  plot: true
```

**验证**: 配置文件加载正确。

**预估**: 15 分钟

---

## Phase 6: 收尾

### Task 12: 文档更新 + 代码检查

**变更**:
1. 更新 `CLAUDE.md` 的"常用命令"章节，添加对比命令示例
2. `ruff check src/` 确保无 lint 错误
3. `pytest tests/ --ignore=tests/infrastructure/gateway/` 全量回归
4. 确认所有新增文件遵循项目规范：
   - `@dataclass(slots=True, kw_only=True)`（非 frozen 用 slots=True）
   - `@dataclass(frozen=True, slots=True, kw_only=True)`（不可变实体）
   - `list[X]` / `dict[K,V]` / `X | None`（Python 3.13+ 类型注解）

**验证**: 全量测试通过，ruff 无报错。

**预估**: 15 分钟

---

## 总预估工时

| Phase | 任务数 | 预估时间 |
|-------|--------|---------|
| Phase 1: Domain | 4 | 105 分钟 |
| Phase 2: Application | 2 | 50 分钟 |
| Phase 3: Infrastructure | 2 | 60 分钟 |
| Phase 4: Interfaces | 2 | 50 分钟 |
| Phase 5: Config | 1 | 15 分钟 |
| Phase 6: 收尾 | 1 | 15 分钟 |
| **合计** | **12** | **295 分钟（~5 小时）** |

---

## 风险与应急

| 风险 | 应急方案 |
|------|---------|
| PerformanceEvaluator 接口改动影响现有代码 | 仅新增可选参数 strategy_name=""，不改现有签名 |
| MockTradeGateway 子账户隔离不完整 | 优先验证：两个策略的 asset 互相独立 |
| rich 库不可用 | ComparisonRichPrinter 降级为普通 print |
| 相关性计算精度 | 纯 Python float 精度足够（日频 < 300 个数据点） |
| frozen BacktestReport 无法修改 | 在 PerformanceEvaluator 构造时直接传入 strategy_name |
