# Spec 3 广度瘦身 · 复活手册

> **执行日期**：2026-06-04
> **锚点 tag**：`archive/pre-spec3-breadth`（瘦身前全量状态，永久有效，独立于分支）
> **通用复活**：`git checkout archive/pre-spec3-breadth -- <路径>`，恢复后 `git add` + `git commit` 即回归主干。

## 一、本轮处置总览

- **净减**：src −6912 行 / tests −6678 行，删除 90 个文件，application 模块 28 → 15。
- **全程可逆**：每项独立提交，提交信息内含复活坐标；本手册为汇总索引。

## 二、复活清单（13 项）

| # | 功能 | 处置 | 复活命令（`git checkout archive/pre-spec3-breadth -- ...`） |
|---|---|---|---|
| 1 | trading_app（废弃重复编排） | 删除 | `src/application/trading_app.py` |
| 2 | event_bus（空壳事件总线） | 归档 | `src/infrastructure/event_bus tests/infrastructure/event_bus` |
| 3 | health_service（健康检查） | 归档 | `src/application/health_service.py`（注：`health_status` 已保留） |
| 4 | 配置热更新 | 归档 | `src/application/config_app.py src/infrastructure/config/config_hot_reload.py src/infrastructure/config/config_watcher.py src/domain/common/value_objects/config_change_log.py` |
| 5 | 算法交易 TWAP/VWAP/冰山 | 归档 | `src/application/algo_trading_app.py src/domain/trade/services/algo_order_manager.py src/domain/trade/services/algo_strategies src/domain/trade/value_objects/algo_order_config.py src/domain/trade/value_objects/algo_order_status.py src/domain/trade/value_objects/algo_progress.py src/domain/trade/value_objects/algo_slice.py src/domain/trade/interfaces/gateways/algo_trader.py` |
| 6 | 业绩归因 Brinson | 归档 | `src/application/attribution_app.py src/domain/backtest/services/attribution src/domain/backtest/value_objects/attribution_report.py` |
| 7 | 实时风控 realtime_* | 归档 | `src/application/realtime_risk_app.py src/domain/risk/services/realtime_risk_monitor.py src/domain/risk/services/realtime_stop_loss.py src/domain/risk/value_objects/risk_alert.py`（注：`anomaly_event`/`ml_risk_alert` 已保留） |
| 8 | 多账户 | 归档 | `src/application/multi_account_app.py src/domain/account/entities/account_group.py src/domain/account/interfaces/account_group_repository.py src/domain/account/services/multi_account_service.py`（注：`asset`/`position` 已保留） |
| 9 | 账户对账 | 归档 | `src/application/reconciliation_app.py src/domain/account/interfaces/reconciliation_repository.py src/domain/account/services/reconciliation_service.py src/domain/account/value_objects/reconciliation_report.py` |
| 10 | ML 部署/影子模式 | 归档 | `src/application/ml_deployment_app.py src/domain/strategy/services/shadow_mode_service.py`（注：`ml_model_version`/`model_deployment_strategy`/`strategy.pool`/`ml_engine` 训练评估均已保留） |
| 11 | 因子流水线编排 | 归档 | `src/application/factor_pipeline_app.py src/domain/strategy/services/factor_pipeline.py src/domain/strategy/value_objects/factor_lifecycle_status.py`（注：`factor_repository`/`strategy.factor_test` 已保留） |
| 12 | 组合优化（黑-里特曼/均值方差/风险预算） | 归档 | `src/application/portfolio_optimization_app.py src/domain/portfolio/services/optimization src/domain/portfolio/value_objects/optimization_result.py` |
| 13 | 策略生命周期 | 归档 | `src/application/strategy_lifecycle_app.py src/domain/strategy/services/strategy_lifecycle_manager.py src/domain/strategy/value_objects/strategy_lifecycle_status.py` |

## 三、明确保留（核心 + 牵连依赖 + 预留扩展点）

- **内核**：回测、实盘交易、下单撮合、T+1 结算、核心风控信号、策略框架、数据网关
- **ML 训练/评估**：`infrastructure/ml_engine`（`ml-train`/`ml-evaluate` 命令）
- **因子测试**：`strategy.factor_test` + `infrastructure/factor_test`（`factor-test` 命令）
- **预留扩展点（本轮仅观察）**：API/web/dashboard、`event_store`/`audit`
- **保守保留观察**：portfolio allocation 子系统（`capital_allocation_engine`/`allocation_algorithms`/`strategy_allocation`/`strategy_performance`，牵涉 `backtest.performance_tracker`，留待下轮评估）
- **未提交文件（全程未碰）**：`pyproject.toml`、`models/`、`src/infrastructure/persistence/repositories/audit_log_repository.py`

## 四、整体回退（如需放弃全部瘦身）

```bash
# 查看瘦身前的完整状态
git checkout archive/pre-spec3-breadth
# 或将主干某路径整体还原到瘦身前
git checkout archive/pre-spec3-breadth -- src/ tests/
```
