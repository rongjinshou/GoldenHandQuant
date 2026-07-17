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

## 五、第二轮清偿（2026-07-10 六西格玛体检 Q7, 用户授权"有债务就还"）

> **净减**: 51 个文件 / 3141 行（src+tests）。
> **复活坐标**: 本轮删除所在提交的父提交（`git log --diff-filter=D --name-only` 可查
> 每个路径的删除提交, `git checkout <删除提交>^ -- <路径>` 复活）。
> **删除前验证**: 每个模块经 grep 全仓引用计数确认生产 0 引用, 删后全量 pytest + ruff 全绿。

| # | 功能 | 处置 | 路径 |
|---|---|---|---|
| 14 | 资金分配子系统（Spec3 §10 "去留未决"两轮无下文, 台账开放项清偿） | 删除 | `src/domain/portfolio/services/capital_allocation_engine.py`(311L) + `services/allocation_algorithms/`整树 + `services/rebalance_triggers/`整树 + `services/kelly_sizer.py` + `entities/{strategy_allocation,strategy_performance}.py` + `interfaces/{allocation_algorithm,rebalance_trigger}.py` + `value_objects/rebalance_frequency.py` + 对应测试树 |
| 15 | EventStore/UnitOfWork（"做了没接线"台账项: 协议+实现俱全, 从未被任何 composition root 使用; 审计已由 audit_logs 承担） | 删除 | `src/domain/common/{event_store,unit_of_work}.py` + `src/infrastructure/persistence/{event_store,unit_of_work}.py` + 两测试。注: `domain_event.py` 保留(circuit_breaker 在用) |
| 16 | 双 web 栈之死栈（TokenAuth/CORS/SSE 从未被启动 app 装配, 有被误复活与只读红线冲突的风险） | 删除 | `src/infrastructure/web/` 整目录 + `tests/infrastructure/web/` |
| 17 | PerformanceTracker（0 引用, 依赖已删的 StrategyPerformance） | 删除 | `src/domain/backtest/services/performance_tracker.py` + 测试 |
| 18 | IHealthGateway 死接口 | 删除 | `src/domain/trade/interfaces/gateways/health_gateway.py` |
| 19 | 死 VO 六件（全部 0 引用） | 删除 | `strategy/value_objects/shadow_comparison_log.py`、`account/value_objects/{position_difference,monitor_query}.py`、`trade/value_objects/{order_events,place_order_command}.py`、`risk/value_objects/risk_domain_events.py` + 对应测试 |
| 20 | interfaces/events 空包 | 删除 | `src/interfaces/events/` |
| 21 | MockTradeGateway 重复桩（台账"重复死代码"项: 生产走 DailySettlementService, 桩内解冻分支是 pass, 两条注释互相矛盾） | 删除方法 | `mock_trade.py::{cancel_all_open_orders,daily_settlement}`; 唯一测试使用点迁移为逐持仓 `settle_t_plus_1()`(语义等价) |

**明确保留（本轮复核后不删）**：
- `strategy/pool/` 整域（pool_manager/rating_engine 虽 0 生产引用, 但 Spec3 §三已裁定保留、系 roadmap Phase 3 策略池地基, 尊重在先裁定）;
- `risk/services/anomaly_detectors/` 链（`interfaces/cli/monitor.py` → auto_pause_manager → anomaly_detector 消费链是活的）;
- `risk_policies/{drawdown,daily_loss}_policy.py`（M5 刚激活同族的 PositionLimit/TotalPosition, 家族接线概率高）;
- `strategy/interfaces/inference_engine.py`（registry 与 ml_return_prediction_strategy 在用, 旧勘察"近死"判定有误）。

## 六、第三轮清偿（2026-07-11 六西格玛架构张力批次）

| # | 功能 | 处置 | 复活坐标 |
|---|---|---|---|
| 22 | live_trade.py 旧半自动入口(05-09 需求 0509-semi-auto-live-trade 引入, 05-31 统一 CLI 复制为 commands/live.py 后未退役形成双入口) | 删除; rich 审核台已迁 `quant live --review-mode rich` | `src/interfaces/cli/live_trade.py`(删除提交父提交) |
| 23 | cli/factor_test.py 死入口(quant.py 从未分发, 功能由 commands/factor_test.py 承担) | 删除 | `src/interfaces/cli/factor_test.py`(同上) |

另: `infrastructure/factor_test/` 八个纯计算引擎文件**迁移**(git mv 保历史)至
`domain/strategy/factor_test/`, 非删除, 无需复活坐标。

## 七、误单防线审计批次（2026-07-11, 用户提出"担心意外下错单子"触发的旁门清理）

| # | 功能 | 处置 | 复活坐标 |
|---|---|---|---|
| 24 | cli/main.py 远古试单入口(首个 spec 的 demo: 真网关硬编码买入 600000.SH 100股@¥10, 无三重确认/无六道闸, 仅 SimpleRiskPolicy; pyproject 未暴露、全仓零引用, 但 `python -m src.interfaces.cli.main` 一跑即发真单) | 删除——正是"意外下错单"最短路径 | `src/interfaces/cli/main.py`(删除提交父提交) |
| 25 | application/order_service.py(唯一消费方=main.py, 自身无测试; codebase-map 早标"旧编排链归档候选 D9") | 随 main.py 连坐删除 | `src/application/order_service.py`(同上) |
| 26 | application/order_executor.py + 其测试(全仓唯一引用=自己的测试; 同为 D9 归档候选; 持有 place_order 调用点) | 删除 | `src/application/order_executor.py` + `tests/application/test_order_executor.py`(同上) |

审计结论(留档): 真单 API 出口全仓唯一 `qmt_trade.py:249 order_stock`; 影子盘周二链
(dry_run)的下单被 DryRunTradeGateway 吸收(place_order 不触 _real), 构造期有
mode↔is_dry_run 配对断言(auto_trade_app.py:104-107)+resolve_mode 三重确认降级
(缺一强制 dry_run, 有测试)。删除本批次后, 剩余真单入口全部要求显式人工调用+确认:
quant order buy(六道闸+--yes) / quant live(人工逐单确认+M6 盘前闸) / auto-trade --live(三重确认)。
