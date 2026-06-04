# Spec 2 · 架构治理 — 设计文档

| 项 | 值 |
|---|---|
| **状态** | Draft → 自主闭环(用户全权委托,不逐节确认) |
| **创建日期** | 2026-06-04 |
| **文档类型** | 技术设计 / SDD Spec |
| **所属 Epic** | GoldenHandQuant 系统重构(Spec 2 / 3) |
| **前置** | Spec 1 回测引擎正确性(已合并 main) |

---

## 一、背景与动机

诊断发现的架构债(P1-5 + 治理项),核心是**依赖方向违规**与**架构剧场**:

| 问题 | 证据 | 性质 |
|---|---|---|
| application 直接依赖 infrastructure | `strategy_runner.py:21-22`(RiskSettings、FeaturePipeline)、`backtest_app.py:33`(RiskSettings)+ 函数内延迟 import(BacktestProgress/Plotter/EventBus)、`config_app.py:12-13`、`dashboard_app.py:5-6` | **依赖方向违规**(违反 CLAUDE.md「应用层永不直接依赖 infrastructure」) |
| EventBus 回测空壳 | `backtest_app.py:_run_with_event_bus`:`bus.publish(...)` 全程无 `bus.subscribe(...)`,事件被静默丢弃(`event_bus.py:25-26`),runner 仍同步调用 | **架构剧场**(~100 行复制粘贴 + 误导) |
| EventBus handlers 死代码 | `handlers.py:handle_strategy_execution` 自注"还没完全实现"、对截面策略直接 `return`;从未被任何 `subscribe` 调用 | **半成品死代码** |

### 范围澄清(对 Spec 1 路线图的修正)

Spec 1 design.md 路线图曾写"Spec 2: domain 因子计算归位(去手写高斯消元)"。**深入探查后修正**:

- `domain/strategy/services/factor_pipeline.py` 经核实**纯 Python、零第三方依赖**——它**合规地待在 domain**,手写高斯消元只是实现啰嗦(**风格债**),**不违反依赖方向**。按 YAGNI(合规 + 正确 + 有测试 + 无性能证据)**本次不重构**,记录为已知技术债。
- "因子计算归位"的**真正对象**是 `infrastructure/ml_engine/feature_pipeline.py` 中**纯 Python 的 `build_cross_section`**——它是领域逻辑(从 bar+fundamental 构建截面 `StockSnapshot`),却错放在 infrastructure 且被 application(`strategy_runner`)直接调用。这才是要治理的方向违规(见 G2)。

---

## 二、目标与非目标

### 目标
1. 消除 application 层对 infrastructure 的**运行时具体依赖**,回归"application 依赖抽象、infrastructure 实现抽象"的依赖倒置。
2. 删除 EventBus 回测空壳与死代码,消除架构剧场。
3. 全程保持测试绿、`ruff` 无新增告警、回测行为不变(纯结构重构,不改业务逻辑)。

### 非目标
- ❌ 重构 `factor_pipeline.py` 手写线代(合规风格债,YAGNI)
- ❌ 删除 EventBus **基础设施本身**(`event_bus.py` 有完整 pub/sub + 测试,实盘/未来可用,仅删回测空壳用法)
- ❌ 改变任何回测/策略的业务行为(本 Spec 是**纯结构重构**)
- ❌ 广度功能裁剪(→ Spec 3)
- ❌ 配置体系大重构(把 20+ settings dataclass 迁出 infrastructure 是更大工程,本次用 TYPE_CHECKING 轻量解耦,见 G3)

---

## 三、设计决策

### G1 · 删除 EventBus 回测空壳 + 死代码

**决策**:删除 `BacktestAppService._run_with_event_bus`、`run_backtest` 的 `use_event_bus` 参数、`backtest_app.py` 内 EventBus 相关延迟 import;删除 `handlers.py` 中半成品死代码 `handle_strategy_execution`。保留 `event_bus.py`/`events.py`/`EventBus` 与 `test_event_bus.py`。

**理由**:`_run_with_event_bus` 从不 `subscribe`,publish 被静默丢弃,回测逻辑仍是同步循环——它是 `_run_unified_loop` 的复制粘贴,零功能价值,纯减法删除收益最大。

**否决**:做实 EventBus 驱动回测——回测是确定性顺序推进,事件驱动在此是 over-engineering,无收益。

**影响**:`test_backtest_app.py`、`test_micro_value_integration.py` 的 `use_event_bus` parametrize 去掉 `True` 分支(保留 `False`)。

### G2 · `build_cross_section` 归位 domain

**决策**:把纯 Python 的截面构建逻辑(`build_cross_section` + `_compute_bar_metrics` + `_compute_fundamental_metrics` + `_std` + `_ema`)从 `infrastructure/ml_engine/feature_pipeline.py` 移到 **`domain/strategy/services/cross_section_builder.py`**(新建 `CrossSectionBuilder`)。`extract_features`(用 numpy,ML 训练用)**留在** infrastructure。更新所有调用方 import。

**理由**:截面快照构建是领域逻辑(产出 `StockSnapshot`,输入全是 domain 对象),错放 infrastructure 导致 application→infrastructure 违规;且它纯 Python,移入 domain 守红线无碍。

**否决**:定义 `ICrossSectionBuilder` 接口 + DI——对一个纯函数式的领域逻辑过度抽象;直接归位 domain 更简洁(YAGNI)。

**影响**:调用方 `strategy_runner.py:164`、`interfaces/cli/data_loader.py:326`、`interfaces/cli/factor_test.py:247`、`interfaces/cli/ml_train.py:205` 改 import。

### G3 · RiskSettings 降为类型依赖(TYPE_CHECKING)

**决策**:`strategy_runner.py`、`backtest_app.py` 对 `RiskSettings` 的 import 改为 `if TYPE_CHECKING:` 守卫。运行时读值用 duck typing(本就只读 `risk_settings.system_gate.index_symbol` 等,无需类对象)。

**理由**:`RiskSettings` 是纯 dataclass(配置契约)。application 只在类型注解处需要它、运行时仅读字段。`TYPE_CHECKING` 消除**运行时** infrastructure 依赖,零行为风险、改动极小。配置值对象彻底迁出 infrastructure 是更大工程(20+ dataclass),不在本次。

**否决**:(a) 把全部 settings dataclass 迁到 domain/独立 config 层——牵连过广,超出本 Spec;(b) 定义配置 Protocol——配置是横切数据,Protocol 收益边际。

### G4 · config_app / dashboard_app 依赖抽象

**决策**:
- `dashboard_app.py`:它**已是依赖注入**(构造接收 `data_provider`、`ws_manager` 实例),仅类型注解用了 infrastructure 具体类。定义 Protocol `IDashboardDataProvider`、`IWebSocketManager`(放 `domain/backtest/interfaces/`),注解改用 Protocol,删除对 infrastructure 的 import。
- `config_app.py`:构造内部 `new ConfigHotReloadService/ConfigWatcher`(硬依赖)。改为定义 Protocol `IConfigReloadService`、`IConfigWatcher`(放 `domain/common/interfaces/`),通过构造注入,由调用方(interfaces 层)组装 infrastructure 实现。

**理由**:标准依赖倒置——application 依赖抽象端口,infrastructure 实现适配器。dashboard 改动极轻(已 DI);config 改为注入消除内部硬实例化。

**否决**:保持现状——它们是 application→infrastructure 的明确违规,且 Protocol 化成本低。

### G5 · backtest_app 进度/绘图接口注入

**决策**:为 `BacktestProgress`、`BacktestPlotter` 定义 Protocol `IProgressReporter`、`IReportPlotter`(放 `domain/backtest/interfaces/`)。`BacktestAppService` 构造接收可选注入(默认 `None`→无进度/不绘图),由 interfaces 层(CLI)组装 infrastructure 实现。删除 `backtest_app.py` 内所有函数级延迟 import。

**理由**:进度展示与绘图是展示关注点,application 不该直接依赖 infrastructure 实现。Optional 注入既解耦又不强制 UI 依赖。

**否决**:把 plot/progress 职责整体移到 interfaces 层——会改 `run_backtest` 公共签名(`plot` 参数)、牵连 CLI 与 `test_backtest_app_plot.py`,本次用注入式解耦更 surgical。

---

## 四、影响面(文件清单)

**新增:**
- `src/domain/strategy/services/cross_section_builder.py`(G2)
- `src/domain/backtest/interfaces/progress_reporter.py`、`report_plotter.py`(G5)
- `src/domain/backtest/interfaces/dashboard_ports.py`(G4)
- `src/domain/common/interfaces/config_ports.py`(G4)

**修改:**
- `src/application/backtest_app.py`(G1 删空壳、G3 TYPE_CHECKING、G5 注入)
- `src/application/strategy_runner.py`(G2 改 import、G3 TYPE_CHECKING)
- `src/application/config_app.py`、`dashboard_app.py`(G4)
- `src/infrastructure/ml_engine/feature_pipeline.py`(G2 移出 build_cross_section)
- `src/infrastructure/event_bus/handlers.py`(G1 删死代码)
- infrastructure 的 dashboard/config/progress/plotter 实现类(G4/G5:声明实现对应 Protocol,通常无需改动,Protocol 是结构化鸭子类型)
- interfaces/cli 调用方(G2 import、G5 组装注入)
- 相关测试(G1 parametrize、G2 import 路径)

---

## 五、验收标准

- [ ] `grep -rn "from src.infrastructure" src/application/` **无运行时命中**(仅允许 `TYPE_CHECKING` 块内)
- [ ] `use_event_bus` / `_run_with_event_bus` 已删除;`handle_strategy_execution` 已删除;`EventBus` 与 `test_event_bus.py` 保留
- [ ] `build_cross_section` 在 `domain/`,`domain/` 仍零第三方导入(红线)
- [ ] 全套测试(更新 parametrize/import 后)绿;`ruff check src/` 无新增告警
- [ ] **回测数值行为不变**:对同一输入,重构前后 `BacktestReport` 关键指标一致(纯结构重构的护栏)

---

## 六、风险与缓解

| 风险 | 缓解 |
|---|---|
| 移动 `build_cross_section` 漏改调用方 → ImportError | 全量 grep 调用方逐一改;移动后跑全套 |
| Protocol 与现有实现签名不匹配 | Protocol 按现有实现的实际方法签名定义;`runtime_checkable` 非必须(结构化鸭子类型) |
| 注入式重构改变 backtest 行为 | 验收标准最后一条:重构前后关键指标对拍;每步 TDD 小提交 |
| TYPE_CHECKING 后运行时 `NameError` | 确认 application 运行时确实不实例化 `RiskSettings`(仅读字段),只用于注解 |
| config_app 改注入牵连调用方 | grep `ConfigAppService` 调用方同步更新组装 |

---

## 七、未来(Out of Scope)

- `factor_pipeline.py` 手写线代:若将来因子规模扩大出现性能瓶颈,再评估迁 infrastructure + numpy。
- 配置体系:settings dataclass 彻底迁出 infrastructure(独立 config 契约层),作为专门迭代。
- Spec 3 广度瘦身(ML/微服务/Dashboard 去留)。
