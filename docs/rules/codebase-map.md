# 代码库地图 (Codebase Map)

> 与代码同步日期 **2026-06-11**。本图只做导航——**代码即真相**，发现失配以代码为准
> 并回头修本图。只列实际存在的组件；规划中能力见
> `docs/feat/0531-system-subsequent-development/`。

## 顶层

```
GoldenHandQuant/
├── resources/        # 运行时配置 (backtest.yaml, trading.yaml)
├── data/             # 本地数据 (market.duckdb 研究库, trading.db 交易留痕, CSV 缓存)
├── docs/             # rules/ 规范 + feat/ 设计与计划文档
├── tests/            # 与 src 镜像 (+ infrastructure/gateway_offline 离线网关测试)
└── src/              # domain ← application ← infrastructure ← interfaces
```

## domain/ — 九个子域

### account（账户与持仓）
- entities: `asset.py`（资金冻结三方法）、`position.py`（T+1 双量）
- services: `settlement_service.py`（日终撤单 + T+1 释放）
- interfaces: `account_gateway.py`、`account_repository.py`
- value_objects: monitor_query / monitor_snapshot / position_detail / position_difference

### trade（交易执行）
- entities: `order.py`（状态机，match/case）
- services: `pre_trade_checks.py`（**六道盘前闸纯函数**，见 live-trading.md）、
  `execution_monitor.py`
- interfaces: gateways `trade_gateway.py`（ITradeGateway）、`health_gateway.py`；
  repositories `trade_history_repo.py`
- value_objects: order_direction / order_status / order_type / order_events /
  place_order_command / execution_record / execution_stats / execution_status / health_status
- exceptions.py：领域异常定义范例

### market（行情与数据模型）
- value_objects: `bar.py`（复权 + unadjusted_close）、`quote.py`（五档）、
  `stock_snapshot.py`（三子对象拆分）、`fundamental_snapshot.py`、`price_limit.py`、
  `suspension.py`、`timeframe.py`
- services: `feature_engine.py`（特征列计算，研究库 features 表的口径源）、
  `fundamental_registry.py`
- interfaces/gateways: market_gateway / history_fetcher / fundamental_fetcher /
  realtime_quote_fetcher

### strategy（最大子域：信号、因子、检验、策略池）
- services: `base_strategy.py`、`cross_sectional_strategy.py`、`cross_section_builder.py`
  - strategies/: dual_ma / micro_value / multi_factor / ml_return_prediction
  - filters/: st / penny_stock / new_listing / trading_status / quality
- factors/: value / quality / technical / price_volume / reversal / low_volatility /
  fundamental / mined（均实现 Factor 协议）
- factor_test/: lexer / parser / expressions / evaluator / scorer / report /
  `factor_catalog.py`（候选因子目录，含 `field_ready` 标志）/ `verdict.py`（硬门槛判决）/
  `field_mapping.py`
- pool/: `strategy_pool_entry.py`（状态机 CANDIDATE→ACTIVE→…→RETIRED）、
  rating_engine / pool_manager、`ml_model_version.py`（不可变，with_active 切版本）
- interfaces: `inference_engine.py`（IInferenceEngine，ML 推理解耦）、`factor_repository.py`

### risk（风控）
- services 根: `risk_chain.py`（责任链）、`system_risk_gate.py`（指数 MA20 盘前门禁，
  SELL 不受限）、`circuit_breaker.py`（NORMAL→TRIGGERED→COOLDOWN 状态机）、
  `alert_engine.py`、`risk_event_dispatcher.py`、`risk_signal_generator.py`
  - risk_policies/: simple / hard_stop_loss / daily_loss / drawdown / position_limit /
    total_position / limit_up_break
  - alert_rules/: concentration / daily_loss / position_ratio / stock_loss
  - anomaly_detectors/: strategy / data / market / ml_model
  - portfolio/: portfolio_risk_service / correlation_analyzer / diversification_evaluator /
    portfolio_var_calculator / stress_test_runner（含 stress_scenarios/）/ ml_model_risk_monitor
- interfaces: `notification.py`（IRiskNotifier，跨子域解耦范例）

### portfolio（仓位与资金分配）
- services 根: `capital_allocation_engine.py`、`equal_weight_sizer.py`、`kelly_sizer.py`
  - sizers/: `fixed_ratio_sizer.py`（实盘自动循环在用）
  - allocation_algorithms/: equal_weight / sharpe_weight / risk_parity / kelly
  - rebalance_triggers/: daily / weekly / monthly

### notification（通知抽象）
- value_objects: message / priority（EMERGENCY>CRITICAL>WARNING>INFO）/ receipt / history
- services: deduplicator（滑动窗口去重）/ priority_queue
- interfaces: `notification_gateway.py`、repositories/notification_history_repository

### backtest（回测报告与对比）
- entities: backtest_report / comparison_report
- services: performance_evaluator / performance_tracker / comparison_report_service
- interfaces/gateways: `backtest_broker.py`（**IBacktestBroker = ITradeGateway +
  IAccountGateway 组合继承**，防接口碎片化）、backtest_market_gateway
- value_objects: daily_snapshot / trade_record / bar_window / dashboard_snapshot

### common（跨子域公共）
- `domain_event.py`（事件基类）、`event_store.py`（EventStore 协议）、
  `unit_of_work.py`（UoW 协议）
- services: `audit_service.py`（审计，append-only）
- value_objects: audit_log_entry；interfaces/repositories: audit_log_repository

## application/ — 用例编排（19 文件，按线分组）

| 线 | 文件 | 说明 |
|---|---|---|
| 回测 | backtest_app.py | 主循环编排（行情推进→信号→撮合→结算→快照） |
| | strategy_comparison_app.py | 多策略对比 |
| **实盘（现行脊柱）** | **auto_trade_app.py** | AutoTradeAppService.run_cycle 自动循环 |
| | live_signal_service.py | 实时信号扫描 |
| | trading_scheduler.py | 槽位调度（防漂移/双触发） |
| | order_ticket_app.py | 受控单笔下单（与 auto 共用盘前闸） |
| | auto_pause_manager.py | 暂停状态 + HMAC 持久化 |
| | monitor_service.py / anomaly_detector.py / notification_hub.py | 监控/异常/通知中心 |
| 研究 | factor_test_app.py | 因子判决编排（入库 factor_verdicts） |
| | market_data_app.py | 研究库刷新编排 |
| | dashboard_app.py | 旧 Web 监控数据编排 |
| 旧编排链（不再接线，归档候选 D9） | auto_trading_engine.py / trading_orchestrator.py / signal_pipeline.py / order_executor.py / order_service.py / strategy_runner.py | 闭环 v1 决策 DD-1 弃用 |

## infrastructure/ — 外部依赖实现

- **gateway/**: qmt_trade（含 cancel_order）/ qmt_market / qmt_history_data /
  qmt_fundamental_fetcher / qmt_realtime_quote / **dry_run_trade**（写模拟读透传）/
  **duckdb_history_data** / tushare_history_data / tushare_fundamental_fetcher /
  tushare_index_fetcher / xtquant_client（xtquant 导入收口）
- **mock/**: mock_market / mock_trade（回测撮合：成本+滑点+流动性+涨跌停）
- **persistence/**: database（SQLite 连接，WAL）/ **trading_store**（交易留痕四表）/
  **market_data_store**（DuckDB 研究库）/ backtest_run_mapper / event_store /
  memory_strategy_pool_repo / repositories（order / snapshot / audit_log / unit_of_work）/
  migrations
- **ml_engine/**: training_pipeline（LGBM walk-forward + Optuna + embargo）/
  feature_pipeline / feature_transforms / feature_combiner / label_generator /
  time_series_cv / dataset_builder / trainer / evaluator / inference / model_loader /
  model_registry / factor_miner / factor_evaluator / factor_repository
- **factor_test/**: ic_calculator / decay_analyzer / layer_backtest / neutralizer / test_runner
- **notification/**: console / wechat（gateway+notifier）/ email / telegram_gateway /
  risk_notifier_adapter / factory
- **web/**: auth（Token + hmac.compare_digest + mask_sensitive）/ websocket_manager /
  dashboard / dashboard_data_provider —— 旧实时监控通道；新驾驶舱在 interfaces/api
- **config/**: settings.py（AppSettings 树 + YAML + `${VAR}` 环境变量替换；
  load_backtest_config / load_trading_config）
- snapshot/ logging/ visualization/（plotter / comparison_plotter / comparison_printer）

## interfaces/ — 系统入口

- **api/**（FastAPI，驾驶舱）: app.py 挂载 `/ui` 静态站；routes: research（因子判决、
  回测列表）/ live（实盘留痕五端点，ro）/ backtest_routes / account_routes / dashboard；
  static/: index.html + app.js + style.css + vendor/echarts（零构建前端）
- **cli/**: `quant.py` 统一入口（commands/: data / backtest / compare / factor_test /
  dashboard / live / order / research + _data_wiring）；`auto_trade.py`（守护/单次循环）；
  run_backtest.py / compare_strategies.py（独立入口，与 quant backtest 共用
  build_history_fetcher + store_backtest_reports）；signal_review/（审核 UI + ReviewStore）；
  其余 fetch_* / ml_* / monitor 等为早期单用途脚本（legacy，按需使用）
- events/: 空壳预留

## 已知幽灵目录（待清理）

`domain/backtest/services/attribution/`、`domain/portfolio/services/optimization/`、
`domain/trade/services/algo_strategies/`、`tests/infrastructure/event_bus/`
仅剩 `__pycache__`——源文件已删除，对应能力（归因/组合优化/算法交易/事件总线）
**不存在**，勿引用。
