# Spec 3 — 广度瘦身（Breadth Trimming）设计文档

- **状态**: Approved（全权闭环授权，温和力度）
- **日期**: 2026-06-04
- **Epic**: 回测引擎正确性（Spec 1 ✅）→ 架构治理（Spec 2 ✅）→ **广度瘦身（Spec 3，本文）**
- **作者**: 架构治理（自主闭环）
- **力度档位**: 温和 —— 先清剧场，边缘归档观察

---

## 1. 背景与问题

GoldenHandQuant 定位为**个人/小团队的 A 股量化交易系统**，核心价值是两条：**回测正确性**与**实盘交易闭环**。然而 P3/P4 阶段堆砌了大量"显得专业"的边缘功能（算法交易、归因分析、组合优化、多账户、实时风控、策略生命周期、ML 部署、配置热更新、健康检查……），它们：

- **从未接入任何生产入口**（CLI/API），仅有自带单元测试在 import；
- **拖着成片独占的 domain/infrastructure 子树**，是 `domain/strategy`(4146行)、`domain/risk`(3067行)、`domain/portfolio`(1897行) 臃肿的主因；
- 稀释核心、抬高认知与维护成本，是典型的**广度过载（breadth overload）**。

本 Spec 通过**证据驱动的反向依赖体检**识别这些孤儿，并以**温和、可逆**的方式将其请出主干。

### 1.1 与前两个 Spec 的本质区别

| | Spec 1 / Spec 2 | Spec 3（本文） |
|---|---|---|
| 变更性质 | 行为保持（重构，对外不变） | **行为改变 + 不可逆删除** |
| 决策性质 | 纯技术判断 | 含产品/战略判断（哪些为未来铺路） |
| 风险控制 | 测试回归即可 | **必须可逆**：archive tag + 独占性验证 |

正因决策含战略性，本轮采用**温和力度**：真剧场才删，边缘孤儿一律"归档观察"（移出主干但 `git` 可秒级复活）。

---

## 2. 目标与非目标

### 2.1 目标
- G1：移除应用层**零调用孤儿**及其独占下游，主干只保留有生产入口或被核心引用的代码。
- G2：归档**可逆**——任何被移除模块都能通过 `git checkout <archive-tag> -- <path>` 完整复活。
- G3：瘦身后**全套测试绿、domain 红线不破、DIP 不回退、ruff 零新增**。
- G4：每个被移除模块在 spec 中留有**复活坐标**（tag + 路径），形成可追溯档案。

### 2.2 非目标（明确不做）
- **不删 API/web/dashboard 层**：CLAUDE.md 明示其为"预留 FastAPI 路由"（有意扩展点），且 Spec 2 刚完成其 DIP 治理。定位"保留观察"，留待未来 web 化或后续 Spec。
- **不删 `auto_trading_engine` 等实盘核心**：实盘是核心价值；`auto_trade.py` 入口虽未接线（空壳），属"未完成"而非"剧场"，保留待接线。
- **不动 `audit_log_repository.py`**：该文件是工作区**未提交的新文件**（`git status ??`），可能是用户在途工作，本轮完全排除。
- **不重写、不优化保留代码**：只做减法，不夹带重构（遵循外科手术式变更原则）。

---

## 3. 瘦身原则

1. **锚定内核**：A 股回测正确性 + 实盘交易闭环（下单/撮合/风控/T+1 结算）。一切减法围绕保护内核。
2. **证据优先**：去留以反向 grep 事实为准，不凭感觉。`prod=0`（零生产引用）是孤儿的**必要非充分**条件，每个判定经双重证伪。
3. **降级 ≠ 删除**：边缘孤儿"请出主干"而非销毁，保留 git 历史与复活路径。
4. **独占才删，共享必留**：删孤儿下游前先 grep 引用方；凡被核心（非孤儿）引用的 domain 一律保留（如 `asset`/`position`/`backtest_report`）。
5. **逐簇提交、步步回归**：每个孤儿簇独立提交，删后立即跑测试，残留 import 断裂即刻暴露。

---

## 4. 现状分析（体检结论 · 事实数据）

### 4.1 真实生产表面
- **唯一正式入口**：`quant = src.interfaces.cli.quant:main`，注册子命令：`research / backtest / live / compare / factor-test / list / auto-trade / ml-train / ml-evaluate / monitor`。
- **生产 application 链路**（`prod>0`）：`backtest_app`、`live_signal_service`、`monitor_service`、`strategy_runner`、`signal_pipeline`、`order_executor`、`order_service`、`notification_hub`、`auto_pause_manager`、`anomaly_detector`、`auto_trading_engine`、`trading_orchestrator`、`trading_scheduler`、`strategy_comparison_app`。
- **API 层**：`interfaces/api` + `infrastructure/web` —— **完全未部署**（无 uvicorn 启动入口，仅 `pip install .[api]` 可选依赖 + 预留路由）。
- **microservice-assessment**：`docs/feat/0601-microservice-assessment/` 为**纯文档**评估，代码中无微服务实现。

### 4.2 孤儿清单（`prod=0`，经双重证伪：全 src 无任何引用）

| # | 孤儿 app（行数） | 独占下游（随簇归档） | 释放的"广度" |
|---|---|---|---|
| 1 | `algo_trading_app` (128) | `trade.services.algo_order_manager`、`trade.interfaces.gateways.algo_trader`、`trade.value_objects.algo_order_config/algo_progress` | 算法交易 TWAP/VWAP |
| 2 | `attribution_app` (256) | `backtest.services.attribution.*`（Brinson/factor），`backtest.value_objects.attribution_report` | 业绩归因 |
| 3 | `portfolio_optimization_app` (274) | `portfolio.services.optimization.*`（黑-里特曼/均值方差/风险预算），`portfolio.value_objects.optimization_result` | 组合优化 |
| 4 | `realtime_risk_app` (222) | `risk.services.realtime_risk_monitor/realtime_stop_loss`，`risk.value_objects.anomaly_event/risk_alert` | 实时风控 |
| 5 | `multi_account_app` (202) | `account.entities.account_group`、`account.services.multi_account_service`、`account.interfaces.account_group_repository` | 多账户 |
| 6 | `reconciliation_app` (151) | `account.services.reconciliation_service`、`account.value_objects.reconciliation_report`、`account.interfaces.reconciliation_repository` | 账户对账 |
| 7 | `strategy_lifecycle_app` (209) | `strategy.services.strategy_lifecycle_manager`、`strategy.value_objects.strategy_lifecycle_status` | 策略生命周期 |
| 8 | `ml_deployment_app` (244) | `strategy.services.shadow_mode_service`、`strategy.value_objects.model_deployment_strategy`、`strategy.pool.value_objects.ml_model_version` | ML 部署/影子 |
| 9 | `factor_pipeline_app` (282) | `strategy.services.factor_pipeline`（**完全独占**）、`strategy.value_objects.factor_lifecycle_status`、`strategy.factor_test.report` | 因子流水线编排 |
| 10 | `config_app` (107) | `infrastructure.config.config_hot_reload/config_watcher`、`domain.common.value_objects.config_change_log` | 配置热更新 |
| 11 | `health_service` (190) | `trade.value_objects.health_status` | 健康检查（微服务用） |

> 应用层合计约 **2265 行**，连同独占下游 domain/infrastructure 预计移除 **数千行**。

### 4.3 死基础设施
- **`event_bus`**（116 行）：全 src 零引用（仅 `event_bus/` 内部自引用），`handle_order_logging` 从未被订阅。Spec 2 曾清理其空壳分支并保留基础设施，本轮体检确认其整体无生产调用方 → 归档。

### 4.4 待删除（真剧场）
- **`trading_app`**（137 行）：`prod=0` 且**无任何独占下游**（依赖全是核心共享 domain），功能与 `trading_orchestrator`/`auto_trading_engine` 重叠，系被取代的早期重复编排 → **直接删除**（git 历史已足够回溯，无需单独归档分支）。

---

## 5. 分档决策

| 档 | 处置 | 范围 |
|---|---|---|
| **A 保留** | 不动 | 内核（回测/实盘/风控信号/策略/数据网关/ML 训练评估）+ API/web/dashboard（预留观察）+ `auto_trading_engine`（实盘待接线）+ `event_store`/`audit`（演进中设计） |
| **B 归档观察** | 移出主干 + tag 留档 | §4.2 的 11 个孤儿 app + 其独占下游 + 对应测试；§4.3 的 `event_bus` |
| **C 删除** | 直接删 | `trading_app`（废弃重复编排） |
| **D 排除** | 完全不碰 | `audit_log_repository.py`（未提交新文件） |

### 5.1 灰色地带（plan 阶段逐项 grep 裁决）
部分下游被**多个孤儿共享**或可能被核心触及，删除前必须验证独占性：
- `portfolio.entities.strategy_allocation`（9 引用）、`capital_allocation_engine`（2 引用，疑似仅 `portfolio_optimization_app`+`strategy_lifecycle_app` 两孤儿共享）：若引用方全为 B 档孤儿则随簇归档，否则保留。
- `backtest.entities.backtest_report`（12 引用）：核心回测产物，**保留**（`attribution_app`/`strategy_lifecycle_app` 依赖它，但删 app 不删它）。
- `account.entities.asset/position`（25 引用）：核心交易实体，**保留**。
- `domain.notification.value_objects.notification_message`：被多个 app 依赖，需验证是否仍有 A 档引用，有则保留。

---

## 6. 归档机制（确保可逆）

1. **执行前锚定**：`git tag archive/pre-spec3-breadth` 标记瘦身前全量状态，git 历史永久可回溯。
2. **逐簇提交**：每个孤儿簇一个 commit，提交信息注明复活坐标，例如：
   ```
   refactor(spec3): 归档算法交易（零调用孤儿）

   复活: git checkout archive/pre-spec3-breadth -- \
         src/application/algo_trading_app.py \
         src/domain/trade/services/algo_order_manager.py ...
   ```
3. **复活坐标档案**：完成报告汇总每个归档模块的 tag + 路径清单（见 §9 验收产物）。
4. **删除（C 档）**：`trading_app` 走普通删除提交，git 历史即回溯路径，不入 archive 分支。

---

## 7. 影响分析

- **测试**：移除 11 个 `test_<app>.py` + 各下游测试；保留测试全绿（残留 import 会触发 collection error，逐簇回归即暴露）。
- **CLI/API**：孤儿均未接入 `quant.py`，故 `quant.py` 与 api 路由**无需改动**。
- **domain 红线**：移除后重新全量扫描 `domain → 第三方` 与 `domain → infrastructure`，确保不破。
- **DIP**：移除后重扫 `application` 模块级 `infrastructure` import，确保 Spec 2 成果不回退。
- **行数**：预计主干净减数千行；`domain/strategy`、`domain/risk`、`domain/portfolio` 显著瘦身。

---

## 8. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 误删被核心共享的下游 | 每个下游删除前强制 grep 引用方，共享即保留（§5.1） |
| 残留 import 导致测试 collection 失败 | 逐簇删除 + 逐簇回归，立即定位 |
| 归档后需复活 | archive tag + 提交信息复活坐标，`git checkout` 秒级恢复 |
| 误碰未提交文件 | `audit_log_repository.py` 列入 D 档排除，全程不动 |
| 节奏过激偏离"温和" | API/dashboard/事件溯源（audit）保留观察，本轮不动 |

---

## 9. 验收标准

- [ ] `archive/pre-spec3-breadth` tag 已创建。
- [ ] §4.2 的 11 个孤儿 app + 独占下游 + 测试已归档；`event_bus` 已归档；`trading_app` 已删除。
- [ ] 共享核心（`asset`/`position`/`backtest_report` 等）完整保留。
- [ ] `python -m pytest tests/ --ignore=tests/infrastructure/gateway/` 全绿。
- [ ] domain 红线扫描：无第三方、无 infrastructure 依赖。
- [ ] DIP 扫描：`application` 无模块级 `infrastructure` import。
- [ ] `ruff check src/` 零新增告警。
- [ ] 完成报告含每个归档模块的复活坐标档案。
- [ ] `audit_log_repository.py` 等未提交文件保持原状未被触碰。

---

## 10. 实施期实际调整（执行偏差记录）

执行中通过 collection 终检发现下游依赖闭包比设计时预估更深，据「独占才删，共享必留」原则做了 **5 处保守收敛**（均比原计划更保守，无超范围删除）：

1. **`health_status` 保留**：被 `trade/services/execution_monitor.py` 依赖，而后者被 `auto_trading_engine`/`trading_orchestrator`（实盘核心）引用。Task 3 改为仅删 app。
2. **`ml_model_version` + `model_deployment_strategy` 保留**：`strategy.pool` 子系统存在依赖链 `memory_strategy_pool_repo → ml_model_version → model_deployment_strategy`。Task 10 改为仅删 `shadow_mode_service` + app。
   - ⚠️ 执行中一度误删 `model_deployment_strategy`（只看了 `ml_model_version` 第一层、漏了第二层），经 collection 检查捕获，已用 `fix(spec3)` 提交从 archive 恢复。
3. **`factor_repository` + `strategy.factor_test` 保留**：被 `registry`/`factor_miner`/`factor_mining` 命令及 `factor-test` 链路共享。Task 11 改为仅删 `factor_pipeline.py` service + `factor_lifecycle_status`。
4. **portfolio allocation 子系统保留观察**：`strategy_performance` 牵涉 `backtest/services/performance_tracker.py`；`capital_allocation_engine`/`allocation_algorithms`/`strategy_allocation` 暂留待下轮评估。Task 12 仅删 `optimization/`（黑-里特曼等）+ 两 app + lifecycle_manager。

**经验**：删除前的独占性验证必须覆盖「被保留代码依赖的传递闭包」，单层 grep 不足；collection 检查是兜底防线。

**最终验收**（全部达成）：全套测试 `pytest_exit=0`、domain 红线干净、application 无模块级 infra import、ruff 8→1（零新增）、未提交文件未碰。详见 `REVIVAL.md` 复活手册。
