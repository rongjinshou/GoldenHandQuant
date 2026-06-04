# Spec 2 · 架构治理 — 实施计划

> **执行模式**:自主 inline 闭环(用户全权委托)。每个 Task 小步推进、跑测试、提交。本计划为执行清单与可追溯文档。

**Goal:** 消除 application→infrastructure 运行时依赖 + 删除 EventBus 架构剧场,纯结构重构、行为不变。

**护栏:** 每步保持测试绿、`ruff` 无新增;`domain/` 零第三方;回测关键指标重构前后一致。

**执行约定:** 分支 `feat/spec2-architecture-governance`;commit message 结尾附 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`;测试用 `python -m pytest`。

---

## Task 顺序与依赖

```
T1 build_cross_section 归位 domain (G2)   ── 独立,先做
T2 删 EventBus 回测空壳+死代码 (G1)        ── 独立
T3 RiskSettings → TYPE_CHECKING (G3)       ── 独立,轻量
T4 dashboard 端口 Protocol (G4a)           ── 独立
T5 config 端口 Protocol + 注入 (G4b)       ── 独立
T6 backtest progress/plotter 注入 (G5)     ── 依赖 T2(同改 backtest_app)
T7 全套回归 + DIP 验证 + 行为对拍          ── 收尾
```

---

## Task 1 · build_cross_section 归位 domain (G2)

**Files:**
- Create: `src/domain/strategy/services/cross_section_builder.py`
- Modify: `src/infrastructure/ml_engine/feature_pipeline.py`(移出纯 Python 部分,保留 `extract_features`)
- Modify 调用方: `src/application/strategy_runner.py:164`、`src/interfaces/cli/data_loader.py:326`、`src/interfaces/cli/factor_test.py:247`、`src/interfaces/cli/ml_train.py:205`
- Test: `tests/infrastructure/ml_engine/test_feature_pipeline_cross_section.py`(改 import 指向新位置)

**步骤:**
- [ ] 读 `feature_pipeline.py` 全文,确认要移动的纯 Python 单元:`build_cross_section`、`_compute_bar_metrics`、`_compute_fundamental_metrics`、`_std`、`_ema`(均无 numpy)。
- [ ] 新建 `cross_section_builder.py`,定义 `class CrossSectionBuilder` 承载 `build_cross_section`(静态方法,签名不变)+ 私有 helper。import 仅 domain(`Bar`、`StockSnapshot`、`FundamentalRegistry`)。
- [ ] 从 `feature_pipeline.py` 删除这些函数;`extract_features`(numpy)与 `FeaturePipeline` 类保留。
- [ ] 全量改调用方:`FeaturePipeline.build_cross_section(...)` → `CrossSectionBuilder.build_cross_section(...)`,更新 import。
- [ ] 改测试 import 指向 `CrossSectionBuilder`。
- [ ] 验证:`grep -rn -E "import (pandas|numpy)" src/domain/strategy/services/cross_section_builder.py`(应为空)；`python -m pytest tests/infrastructure/ml_engine/ tests/application/test_strategy_runner_lookahead.py tests/infrastructure/mock/test_micro_value_integration.py -q`。
- [ ] 提交:`refactor(arch): build_cross_section 归位 domain (G2)`

---

## Task 2 · 删 EventBus 回测空壳 + 死代码 (G1)

**Files:**
- Modify: `src/application/backtest_app.py`(删 `_run_with_event_bus`、`use_event_bus` 参数+分支、EventBus 延迟 import)
- Modify: `src/infrastructure/event_bus/handlers.py`(删 `handle_strategy_execution`)、`src/infrastructure/event_bus/__init__.py`(删其 export)
- Test: `tests/application/test_backtest_app.py`、`tests/infrastructure/mock/test_micro_value_integration.py`(去 `use_event_bus` parametrize 的 `True`)

**步骤:**
- [ ] `backtest_app.py`:删 `run_backtest` 的 `use_event_bus` 参数与 `if use_event_bus:` 分支;删 `_run_with_event_bus` 整个方法;删其内 `from src.infrastructure.event_bus import ...`。
- [ ] `handlers.py`:删 `handle_strategy_execution`(半成品死代码);`__init__.py` 移除其 export 与 `__all__` 条目。保留 `EventBus`、`events`、`handle_order_logging`。
- [ ] 测试:两处 `@pytest.mark.parametrize("use_event_bus", [False, True])` 改为不传 `use_event_bus`(用默认),移除该参数。
- [ ] 验证:`python -m pytest tests/application/test_backtest_app.py tests/infrastructure/mock/test_micro_value_integration.py tests/infrastructure/event_bus/ -q`。
- [ ] 提交:`refactor(arch): 删除 EventBus 回测空壳与死代码 handler (G1)`

---

## Task 3 · RiskSettings → TYPE_CHECKING (G3)

**Files:** Modify `src/application/strategy_runner.py`、`src/application/backtest_app.py`

**步骤:**
- [ ] 确认两文件运行时不实例化 `RiskSettings`,仅作类型注解 + 读字段(`risk_settings.system_gate.index_symbol`、`risk_settings.stop_loss.max_loss_ratio`)。
- [ ] 将 `from src.infrastructure.config.settings import RiskSettings` 移入 `if TYPE_CHECKING:` 块(文件顶部加 `from typing import TYPE_CHECKING`);注解处 `RiskSettings` 改为字符串字面量 `"RiskSettings"` 或保持(`from __future__ import annotations` 下可直接用)。
- [ ] 验证:`python -m pytest tests/application/ -q`(运行时无 `NameError`);`ruff check src/`。
- [ ] 提交:`refactor(arch): RiskSettings 降为 TYPE_CHECKING 类型依赖 (G3)`

---

## Task 4 · dashboard 端口 Protocol (G4a)

**Files:**
- Create: `src/domain/backtest/interfaces/dashboard_ports.py`
- Modify: `src/application/dashboard_app.py`(import 改 Protocol)
- Test: `tests/application/test_dashboard_app.py`

**步骤:**
- [ ] 按现有用法定义 Protocol(`from typing import Protocol`):
  - `IDashboardDataProvider`: `get_snapshot() -> DashboardSnapshot`、`get_equity_curve(limit: int) -> list[...]`
  - `IWebSocketManager`: `async start_heartbeat()`、`async stop_heartbeat()`、`async broadcast(message: dict)`
- [ ] `dashboard_app.py`:删 `from src.infrastructure.web...` import,构造注解改用 Protocol。
- [ ] 验证:`python -m pytest tests/application/test_dashboard_app.py -q`。
- [ ] 提交:`refactor(arch): dashboard 应用服务依赖 Protocol 端口 (G4a)`

---

## Task 5 · config 端口 Protocol + 注入 (G4b)

**Files:**
- Create: `src/domain/common/interfaces/config_ports.py`
- Modify: `src/application/config_app.py`(改注入)、调用方(grep `ConfigAppService`)
- Test: `tests/application/test_config_app.py`

**步骤:**
- [ ] 定义 Protocol:
  - `IConfigReloadService`: `change_history`、`take_snapshot()`、`reload_from_file()`、`update_param(path, value, *, user_id)`、`rollback()`
  - `IConfigWatcher`: `start()`、`stop()`、`is_running`(属性)
- [ ] `config_app.py`:构造改为注入 `reload_service: IConfigReloadService` 与 `watcher_factory: Callable[[Path, Callable], IConfigWatcher]`(或注入已构造 watcher);删 infrastructure import。
- [ ] grep `ConfigAppService(` 调用方,组装传入 infrastructure 实现。
- [ ] 验证:`python -m pytest tests/application/test_config_app.py -q`(测试相应改为传入 fake/real 实现)。
- [ ] 提交:`refactor(arch): config 应用服务依赖注入 Protocol 端口 (G4b)`

---

## Task 6 · backtest progress/plotter 接口注入 (G5)

**Files:**
- Create: `src/domain/backtest/interfaces/progress_reporter.py`、`report_plotter.py`
- Modify: `src/application/backtest_app.py`(构造注入,删延迟 import)、`src/interfaces/cli/run_backtest.py`(组装注入)
- Test: `tests/application/test_backtest_app.py`、`test_backtest_app_plot.py`

**步骤:**
- [ ] 定义 Protocol:
  - `IProgressReporter`: `update(current_time: datetime)`(`__init__(total)` 由实现负责;application 接收已构造实例或工厂)
  - `IReportPlotter`: `plot(report: BacktestReport)`
- [ ] `backtest_app.py`:构造加可选参数 `progress_reporter: IProgressReporter | None = None`、`plotter: IReportPlotter | None = None`;`_run_unified_loop` 用注入的 reporter(`None` 则跳过 `update`);plot 用注入的 plotter(`None` 则跳过)。删 `BacktestProgress`/`BacktestPlotter` 的函数级延迟 import。
- [ ] `run_backtest.py`(CLI 组装层):构造 `BacktestProgress`/`BacktestPlotter` 注入。
- [ ] 验证:`python -m pytest tests/application/test_backtest_app.py tests/application/test_backtest_app_plot.py -q`。
- [ ] 提交:`refactor(arch): backtest 进度/绘图接口注入,消除延迟 import (G5)`

---

## Task 7 · 全套回归 + DIP 验证 + 行为对拍

**步骤:**
- [ ] **DIP 终检**:`grep -rn "from src.infrastructure" src/application/` → 命中应**仅在 `TYPE_CHECKING` 块内**(RiskSettings);无运行时 import。
- [ ] **domain 红线**:`grep -rnE "import (pandas|numpy|np)" src/domain/` → 空。
- [ ] **全套测试**:`python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q` → all passed。
- [ ] **lint**:`ruff check src/` → 无新增告警(8 个 pre-existing 不计)。
- [ ] **行为对拍**:跑一次 `python -m src.interfaces.cli.run_backtest`(或现有集成测试 `test_micro_value_integration` / `test_integration_backtest` 覆盖),确认回测可正常完成、关键指标合理(纯结构重构,行为应不变)。
- [ ] 提交(若有收尾):`test(arch): Spec 2 回归验证`

---

## Spec 覆盖矩阵(自审)

| Spec 决策 | Task |
|---|---|
| G1 删 EventBus 空壳+死代码 | T2 |
| G2 build_cross_section 归位 domain | T1 |
| G3 RiskSettings TYPE_CHECKING | T3 |
| G4a dashboard Protocol | T4 |
| G4b config Protocol+注入 | T5 |
| G5 progress/plotter 注入 | T6 |
| 验收(DIP/红线/行为不变) | T7 |
| factor_pipeline 不动 | — 非目标,记录在案 |
