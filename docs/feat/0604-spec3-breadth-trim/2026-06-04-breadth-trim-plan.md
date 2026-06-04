# Spec 3 — 广度瘦身实施计划

> **执行模式**：全权自主闭环（温和力度）。本计划为「删除/归档型」TDD：每个任务 = 独占性验证 → 条件删除 → 回归绿 → 提交。

**Goal**：移除 11 个零调用 application 孤儿 + 死 event_bus + 废弃 trading_app，主干净减数千行，全程可逆、测试绿、DIP/domain 红线不退。

**Architecture**：逐簇外科手术。每簇删除前强制 grep 独占性，共享核心一律保留；每簇独立提交并附复活坐标。

**Tech Stack**：git tag 归档锚定、pytest 回归、grep 独占性验证、ruff lint。

**回归基线命令**（每任务末执行）：
```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```

**复活坐标**：所有归档模块均可 `git checkout archive/pre-spec3-breadth -- <path>` 复活。

---

## Task 0：归档锚定 + 基线确认

- [ ] **Step 1：打 archive tag（锚定瘦身前全量）**
```bash
git tag archive/pre-spec3-breadth
git tag | grep archive
```
Expected: 输出 `archive/pre-spec3-breadth`

- [ ] **Step 2：记录基线测试通过数**
```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q 2>&1 | tail -3
```
Expected: 全绿，记录 passed 数（瘦身后保留测试应仍全绿）。

---

## Task 1：删除 trading_app（C 档 · 真剧场）

**理由**：`prod=0`、无独占下游、与 `trading_orchestrator`/`auto_trading_engine` 重叠的废弃早期编排。

**Files（删除）**：`src/application/trading_app.py`、`tests/application/test_trading_app.py`

- [ ] **Step 1：复核无生产引用**
```bash
grep -rl "trading_app\b" src/ --include="*.py" | grep -v __pycache__ | grep -v "application/trading_app.py"
```
Expected: 空（仅其测试引用，已确认 prod=0）。

- [ ] **Step 2：删除**
```bash
git rm src/application/trading_app.py tests/application/test_trading_app.py
```

- [ ] **Step 3：回归**（Expected: 绿，passed 数 = 基线 − test_trading_app 用例数）

- [ ] **Step 4：提交**
```bash
git commit -m "$(printf 'refactor(spec3): 删除 trading_app(废弃重复编排)\n\nprod=0 无独占下游, 功能被 trading_orchestrator/auto_trading_engine 取代。\n复活: git checkout archive/pre-spec3-breadth -- src/application/trading_app.py\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 2：归档 event_bus（B 档 · 死基础设施）

**理由**：116 行，全 src 零引用，handler 从未订阅（Spec 2 已清空壳分支）。

**Files（删除）**：`src/infrastructure/event_bus/`（events.py、event_bus.py、handlers.py、__init__.py）、`tests/infrastructure/event_bus/`

- [ ] **Step 1：复核零生产引用**
```bash
grep -rl "infrastructure.event_bus\|from src.infrastructure.event_bus" src/ --include="*.py" | grep -v __pycache__ | grep -v "/event_bus/"
```
Expected: 空。

- [ ] **Step 2：删除**
```bash
git rm -r src/infrastructure/event_bus tests/infrastructure/event_bus
```

- [ ] **Step 3：回归**（Expected: 绿）

- [ ] **Step 4：提交**（msg：`refactor(spec3): 归档 event_bus(空壳基础设施,handler无订阅)` + 复活坐标）

---

## Task 3：归档 health_service（B 档）

**Files（删除）**：`src/application/health_service.py`、`src/domain/trade/value_objects/health_status.py`、`tests/application/test_health_service.py`

- [ ] **Step 1：验证 health_status 独占**
```bash
grep -rl "health_status\b" src/ --include="*.py" | grep -v __pycache__ | grep -v "value_objects/health_status.py"
```
Expected: 仅 `health_service.py`（孤儿）。若出现 A 档引用则保留 health_status，仅删 app。

- [ ] **Step 2：删除** `git rm` 上述 3 文件
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档 health_service(健康检查,微服务用)` + 复活坐标）

---

## Task 4：归档配置热更新（B 档）

**Files（删除）**：`src/application/config_app.py`、`src/infrastructure/config/config_hot_reload.py`、`src/infrastructure/config/config_watcher.py`、`src/domain/common/value_objects/config_change_log.py`、`tests/infrastructure/config/test_config_hot_reload.py`、`tests/domain/common/value_objects/test_config_change_log.py`

- [ ] **Step 1：验证独占**（config_change_log 已确认仅 config_app+config_hot_reload 引用）
```bash
for m in config_hot_reload config_watcher config_change_log; do echo "-- $m --"; grep -rl "$m\b" src/ --include="*.py" | grep -v __pycache__ | grep -vE "(config_hot_reload|config_watcher|config_change_log).py"; done
```
Expected: 仅 config 簇内部互引（config_app/config_hot_reload）。无 A 档引用。
> 注：`src/infrastructure/config/settings.py`（被 backtest/trading 读取）**不在删除范围**，保留。

- [ ] **Step 2：删除** `git rm` 上述 6 文件
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档配置热更新(零调用)` + 复活坐标）

---

## Task 5：归档算法交易（B 档）

**Files（删除）**：
- app：`src/application/algo_trading_app.py`
- domain：`src/domain/trade/services/algo_order_manager.py`、`src/domain/trade/services/algo_strategies/`（iceberg/twap/vwap/__init__）、`src/domain/trade/value_objects/algo_order_config.py`、`algo_order_status.py`、`algo_progress.py`、`algo_slice.py`、`src/domain/trade/interfaces/gateways/algo_trader.py`
- tests：`tests/application/test_algo_trading_app.py`、`tests/domain/trade/services/test_algo_order_manager.py`

- [ ] **Step 1：验证 algo_* 整簇独占**
```bash
grep -rlE "algo_order_manager|algo_trader|algo_order_config|algo_progress|algo_slice|algo_strategies|algo_order_status" src/ --include="*.py" | grep -v __pycache__ | grep -vE "/(services/algo|value_objects/algo|gateways/algo|algo_strategies)" | grep -v "algo_trading_app.py"
```
Expected: 空（algo 簇自洽，仅 algo_trading_app 是外部引用点）。任何意外命中者保留。

- [ ] **Step 2：删除** `git rm` 上述文件/目录
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档算法交易 TWAP/VWAP(零调用)` + 复活坐标）

---

## Task 6：归档业绩归因（B 档）

**Files（删除）**：
- app：`src/application/attribution_app.py`
- domain：`src/domain/backtest/services/attribution/`（brinson/factor/__init__）、`src/domain/backtest/value_objects/attribution_report.py`
- tests：`tests/application/test_attribution_app.py`、`tests/domain/backtest/services/attribution/`、`tests/domain/backtest/value_objects/test_attribution_report.py`

- [ ] **Step 1：验证独占（保护 backtest_report 等核心）**
```bash
grep -rlE "services.attribution|attribution_report" src/ --include="*.py" | grep -v __pycache__ | grep -vE "(services/attribution|attribution_report.py)" | grep -v "attribution_app.py"
echo "--- 确认 backtest_report 未被误删(应保留) ---"; grep -c "backtest_report" src/domain/backtest/entities/backtest_report.py
```
Expected: 第一段空；attribution 簇独占。`backtest.entities.backtest_report` 不在删除清单（核心保留）。

- [ ] **Step 2：删除** `git rm` 上述文件/目录
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档业绩归因 Brinson(零调用)` + 复活坐标）

---

## Task 7：归档实时风控（B 档 · ⚠️ 保留 anomaly_event）

**Files（删除）**：
- app：`src/application/realtime_risk_app.py`
- domain：`src/domain/risk/services/realtime_risk_monitor.py`、`realtime_stop_loss.py`、`src/domain/risk/value_objects/risk_alert.py`
- tests：`tests/application/test_realtime_risk_app.py`、`tests/domain/risk/services/test_realtime_risk_monitor.py`、`test_realtime_stop_loss.py`

**⚠️ 必须保留**（A 档共享，已验证）：`anomaly_event.py`（被 anomaly_detector/auto_pause_manager/notification_hub/anomaly_detectors/* 引用）、`ml_risk_alert.py`（portfolio risk 用）、整套 `anomaly_detectors/`。

- [ ] **Step 1：验证 risk_alert 独占 + anomaly_event 须留**
```bash
echo "--- risk_alert 引用(应仅 realtime 簇) ---"; grep -rl "\brisk_alert\b" src/ --include="*.py" | grep -v __pycache__ | grep -v "value_objects/risk_alert.py"
echo "--- anomaly_event 引用(证明须保留) ---"; grep -rl "\banomaly_event\b" src/ --include="*.py" | grep -v __pycache__ | grep -v "value_objects/anomaly_event.py" | grep -v realtime_risk_app
```
Expected: risk_alert 仅 realtime_risk_app + realtime_risk_monitor + realtime_stop_loss；anomaly_event 有 A 档引用 → 确认保留。

- [ ] **Step 2：删除** `git rm` 上述文件（**不含 anomaly_event/ml_risk_alert/anomaly_detectors**）
- [ ] **Step 3：回归**（绿。anomaly_detector 等 A 档应不受影响）
- [ ] **Step 4：提交**（`归档实时风控 realtime_*(零调用,保留共享 anomaly_event)` + 复活坐标）

---

## Task 8：归档多账户（B 档 · ⚠️ 保留 asset/position）

**Files（删除）**：
- app：`src/application/multi_account_app.py`
- domain：`src/domain/account/entities/account_group.py`、`src/domain/account/interfaces/account_group_repository.py`、`src/domain/account/services/multi_account_service.py`
- tests：`tests/application/test_multi_account_app.py`、`tests/domain/account/entities/test_account_group.py`、`tests/domain/account/services/test_multi_account_service.py`

**⚠️ 必须保留**：`account.entities.asset/position`（25 引用，核心交易实体）。

- [ ] **Step 1：验证 account_group/multi_account 独占**
```bash
grep -rlE "account_group|multi_account_service" src/ --include="*.py" | grep -v __pycache__ | grep -vE "(account_group|multi_account_service).py" | grep -v "multi_account_app.py"
echo "--- 确认 asset 保留 ---"; grep -c "class Asset" src/domain/account/entities/asset.py
```
Expected: 第一段空（multi_account 簇独占）；asset 保留。

- [ ] **Step 2：删除** `git rm` 上述文件
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档多账户(零调用,保留核心 asset/position)` + 复活坐标）

---

## Task 9：归档账户对账（B 档）

**Files（删除）**：
- app：`src/application/reconciliation_app.py`
- domain：`src/domain/account/interfaces/reconciliation_repository.py`、`src/domain/account/services/reconciliation_service.py`、`src/domain/account/value_objects/reconciliation_report.py`
- tests：`tests/application/test_reconciliation_app.py`、`tests/domain/account/services/test_reconciliation_service.py`

- [ ] **Step 1：验证独占**
```bash
grep -rl "reconciliation" src/ --include="*.py" | grep -v __pycache__ | grep -v "reconciliation" --include="*.py" 2>/dev/null; grep -rlE "reconciliation_service|reconciliation_repository|reconciliation_report" src/ --include="*.py" | grep -v __pycache__ | grep -vE "reconciliation_(service|repository|report).py" | grep -v "reconciliation_app.py"
```
Expected: 仅 reconciliation 簇内部互引。`account_gateway`（共享）不删。

- [ ] **Step 2：删除** `git rm` 上述文件
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档账户对账(零调用)` + 复活坐标）

---

## Task 10：归档 ML 部署/影子（B 档 · ⚠️ 非 ML 训练）

**Files（删除）**：
- app：`src/application/ml_deployment_app.py`
- domain：`src/domain/strategy/services/shadow_mode_service.py`、`src/domain/strategy/value_objects/model_deployment_strategy.py`、`src/domain/strategy/pool/value_objects/ml_model_version.py`
- tests：`tests/application/test_ml_deployment_app.py`、`tests/domain/strategy/services/test_shadow_mode_service.py`、`tests/domain/strategy/value_objects/test_model_deployment_strategy.py`

**⚠️ 必须保留**：`infrastructure/ml_engine/`（训练评估，ml-train/ml-evaluate 命令用）。

- [ ] **Step 1：验证独占 + ml_engine 不受影响**
```bash
grep -rlE "shadow_mode_service|model_deployment_strategy|ml_model_version" src/ --include="*.py" | grep -v __pycache__ | grep -vE "(shadow_mode_service|model_deployment_strategy|ml_model_version).py" | grep -v "ml_deployment_app.py"
echo "--- ml_engine 保留确认 ---"; grep -rl "infrastructure.ml_engine" src/interfaces/cli/ | grep -v __pycache__
```
Expected: 第一段空；ml-train/ml-evaluate 仍引用 ml_engine（保留）。若 ml_model_version 被 pool 其他模块共享则保留它。

- [ ] **Step 2：删除** `git rm` 上述文件
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档 ML 部署/影子模式(零调用,保留 ml_engine 训练)` + 复活坐标）

---

## Task 11：归档因子流水线编排（B 档 · ⚠️ 保留 factor_test/）

**Files（删除）**：
- app：`src/application/factor_pipeline_app.py`
- domain：`src/domain/strategy/services/factor_pipeline.py`、`src/domain/strategy/value_objects/factor_lifecycle_status.py`
- tests：`tests/application/test_factor_pipeline_app.py`、`tests/domain/strategy/services/test_factor_pipeline.py`

**⚠️ 必须保留**（A 档共享，已验证）：`domain/strategy/factor_test/`（factor-test 命令 + infrastructure/factor_test/test_runner 共享）、`strategy.interfaces.factor_repository`（验证后定）。

- [ ] **Step 1：验证 factor_pipeline 独占 + factor_test 须留**
```bash
echo "--- factor_pipeline(service) 引用(应仅 app) ---"; grep -rl "services.factor_pipeline\b" src/ --include="*.py" | grep -v __pycache__
echo "--- factor_lifecycle_status 引用 ---"; grep -rl "factor_lifecycle_status" src/ --include="*.py" | grep -v __pycache__ | grep -v "factor_lifecycle_status.py"
echo "--- factor_repository 引用(判断是否独占) ---"; grep -rl "factor_repository" src/ --include="*.py" | grep -v __pycache__ | grep -v "factor_repository.py"
```
Expected: factor_pipeline 仅 factor_pipeline_app；若 factor_repository/factor_lifecycle_status 仅被 factor_pipeline 系列引用则一并删，否则保留。`factor_test/` 不在删除清单。

- [ ] **Step 2：删除** `git rm` 上述文件（依 Step 1 结论决定 factor_repository/factor_lifecycle_status 去留）
- [ ] **Step 3：回归**（绿。factor-test 命令链路应不受影响）
- [ ] **Step 4：提交**（`归档因子流水线编排(零调用,保留 factor_test 评测)` + 复活坐标）

---

## Task 12：归档组合优化 + 策略生命周期（B 档 · 共享 portfolio 对象专项裁决）

**说明**：`portfolio_optimization_app` 与 `strategy_lifecycle_app` 共享 `capital_allocation_engine`、`strategy_allocation`、`strategy_performance`。先裁决这些共享对象去留，再删两簇。

**Files（删除 · 确定部分）**：
- app：`src/application/portfolio_optimization_app.py`、`src/application/strategy_lifecycle_app.py`
- domain：`src/domain/portfolio/services/optimization/`（black_litterman/mean_variance/risk_budget/__init__）、`src/domain/portfolio/value_objects/optimization_result.py`、`src/domain/strategy/services/strategy_lifecycle_manager.py`、`src/domain/strategy/value_objects/strategy_lifecycle_status.py`
- tests：`tests/application/test_portfolio_optimization_app.py`、`test_strategy_lifecycle_app.py`、`tests/domain/portfolio/services/optimization/`、`tests/domain/portfolio/value_objects/test_optimization_result.py`、`tests/domain/strategy/services/test_strategy_lifecycle_manager.py`

- [ ] **Step 1：裁决共享 portfolio 对象（capital_allocation_engine / strategy_allocation / strategy_performance）**
```bash
for m in capital_allocation_engine strategy_allocation strategy_performance; do echo "== $m 引用方 =="; grep -rl "\b$m\b" src/ --include="*.py" | grep -v __pycache__ | grep -vE "$m.py"; done
```
判定规则：列出的引用方**若全部 ∈ {portfolio_optimization_app, strategy_lifecycle_app, 及其下游}** → 随簇归档；**若含任何 A 档**（backtest/strategy_runner/sizer 等）→ **保留**。
> 强制保护：`strategy_runner`、`backtest_app`、`portfolio.interfaces.position_sizer`、`portfolio.services.sizers/*`（核心仓位管理）绝不删。

- [ ] **Step 2：删除** `git rm` 确定部分 + Step 1 裁定可删的共享对象
- [ ] **Step 3：回归**（绿）
- [ ] **Step 4：提交**（`归档组合优化+策略生命周期(零调用)` + 复活坐标）

---

## Task 13：全量回归 + 红线终检

- [ ] **Step 1：全套测试**
```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q 2>&1 | tail -5
```
Expected: 全绿。

- [ ] **Step 2：domain 红线（无第三方 + 无 infrastructure）**
```bash
grep -rnE "import (pandas|numpy|scipy|sklearn)" src/domain/ --include="*.py" | grep -v __pycache__ || echo "✓ domain 无第三方"
grep -rn "from src.infrastructure" src/domain/ --include="*.py" | grep -v __pycache__ || echo "✓ domain 无 infrastructure 依赖"
```

- [ ] **Step 3：DIP 不回退（application 无模块级 infra import）**
```bash
grep -rn "^from src.infrastructure\|^import src.infrastructure" src/application/ --include="*.py" | grep -v __pycache__ || echo "✓ application 无模块级 infra import"
```

- [ ] **Step 4：ruff 零新增**
```bash
ruff check src/ 2>&1 | tail -5
```
Expected: 无新增告警（与瘦身前持平）。

- [ ] **Step 5：瘦身行数统计**
```bash
git diff --stat archive/pre-spec3-breadth HEAD -- src/ | tail -1
```

---

## Task 14：合并 main + 完成报告

- [ ] **Step 1：合并**
```bash
git checkout main
git merge --no-ff feat/spec3-breadth-trim -m "$(printf 'merge: Spec 3 广度瘦身(11孤儿归档+event_bus+trading_app)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
git branch -d feat/spec3-breadth-trim
```

- [ ] **Step 2：输出完成报告**——含各归档模块复活坐标档案、瘦身行数、验收勾选。
> 未提交文件（`audit_log_repository.py`、`pyproject.toml` 等）全程未被触碰，保持原状。

---

## 自检（Self-Review）

- **Spec 覆盖**：Spec §4.2 的 11 孤儿 → Task 3~12 全覆盖；event_bus → Task 2；trading_app → Task 1。✓
- **共享保护**：anomaly_event(Task7)、asset/position(Task8)、backtest_report(Task6)、factor_test/(Task11)、ml_engine(Task10)、sizers(Task12) 均显式保护。✓
- **可逆**：Task 0 打 tag，每任务提交附复活坐标。✓
- **排除项**：audit_log_repository.py 未列入任何删除清单。✓
- **类型一致**：所有文件路径取自实测 `find` 输出，无臆测。✓
