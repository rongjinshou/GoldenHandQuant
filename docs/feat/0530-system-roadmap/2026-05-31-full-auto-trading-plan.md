# Phase 4: 全自动交易 — 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划 / 里程碑拆解
**状态**: 草案
**设计文档**: `2026-05-31-full-auto-trading-design.md`

---

## 一、总体时间线

**预计总工期**: 6-8 个月（每周 10-15 小时）

```
Month 1-2:  子项目 4.1 基础（自动执行引擎核心）
Month 2-3:  子项目 4.2 基础（异常检测框架）
Month 3-4:  子项目 4.3 基础（通知推送 + CLI 监控）
Month 4-5:  子项目 4.1 完善（执行优化 + 拆单）
Month 5-6:  子项目 4.2 完善（ML 异常检测 + 自动暂停）
Month 6-7:  子项目 4.3 完善（Web Dashboard + 远程控制）
Month 7-8:  集成测试 + 实盘验证 + 文档
```

---

## 二、子项目 4.1：策略自动执行引擎

### 里程碑 4.1.1：执行记录与监控（2 周）

**目标**: 建立执行记录的数据模型和基础监控能力，为后续自动执行提供数据基础。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 1.1 | 定义 `ExecutionRecord` 值对象 | domain | `src/domain/trade/value_objects/execution_record.py` | 0.5d |
| 1.2 | 定义 `ExecutionStatus` 枚举 | domain | `src/domain/trade/value_objects/execution_status.py` | 0.5d |
| 1.3 | 实现 `ExecutionMonitor` 服务 | domain | `src/domain/trade/services/execution_monitor.py` | 1d |
| 1.4 | 编写 `ExecutionMonitor` 单元测试 | test | `tests/domain/trade/services/test_execution_monitor.py` | 1d |
| 1.5 | 扩展 `LiveSignalService` 记录执行结果 | application | `src/application/live_signal_service.py` | 1d |
| 1.6 | 编写集成测试 | test | `tests/application/test_live_signal_service_exec.py` | 1d |

#### 验收标准

- [ ] `ExecutionRecord` 包含：order_id, symbol, direction, target_price, actual_price, slippage, status, timestamps
- [ ] `ExecutionMonitor` 能统计：成功率、平均滑点、最大滑点
- [ ] `ExecutionMonitor.check_health()` 返回健康状态（HEALTHY/WARNING/CRITICAL）
- [ ] `LiveSignalService.place_confirmed_orders()` 返回 `ExecutionRecord` 列表
- [ ] 所有测试通过

---

### 里程碑 4.1.2：信号管线（2 周）

**目标**: 将现有的信号生成逻辑封装为可复用的管线，支持多策略信号聚合、去重、过滤。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 2.1 | 实现 `SignalPipeline` 应用服务 | application | `src/application/signal_pipeline.py` | 2d |
| 2.2 | 实现信号去重逻辑 | application | `src/application/signal_pipeline.py` | 1d |
| 2.3 | 实现信号置信度过滤 | application | `src/application/signal_pipeline.py` | 0.5d |
| 2.4 | 实现 BUY/SELL 冲突解决 | application | `src/application/signal_pipeline.py` | 0.5d |
| 2.5 | 编写 `SignalPipeline` 单元测试 | test | `tests/application/test_signal_pipeline.py` | 1.5d |
| 2.6 | 与现有 `SingleStrategyRunner` 集成测试 | test | `tests/application/test_signal_pipeline_integration.py` | 1d |

#### 验收标准

- [ ] `SignalPipeline.generate(context)` 返回 `list[OrderTarget]`
- [ ] 多策略信号正确聚合（同一标的取置信度最高的信号）
- [ ] BUY/SELL 冲突时优先 SELL
- [ ] 低于置信度阈值的信号被过滤
- [ ] 复用现有 `SingleStrategyRunner` / `CrossSectionalStrategyRunner`
- [ ] 所有测试通过

---

### 里程碑 4.1.3：自动下单执行器（2 周）

**目标**: 实现自动下单的核心执行器，集成风控检查，支持执行跟踪。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 3.1 | 实现 `OrderExecutor` 应用服务 | application | `src/application/order_executor.py` | 2d |
| 3.2 | 实现卖出优先排序逻辑 | application | `src/application/order_executor.py` | 0.5d |
| 3.3 | 集成 `RiskChain` 风控检查 | application | `src/application/order_executor.py` | 0.5d |
| 3.4 | 实现执行结果查询（QMT 成交回报） | infrastructure | `src/infrastructure/gateway/qmt_trade.py` | 1d |
| 3.5 | 实现滑点计算逻辑 | domain | `src/domain/trade/services/execution_monitor.py` | 0.5d |
| 3.6 | 编写 `OrderExecutor` 单元测试 | test | `tests/application/test_order_executor.py` | 1.5d |

#### 验收标准

- [ ] `OrderExecutor.execute(targets)` 返回 `list[ExecutionRecord]`
- [ ] 卖出订单优先于买入订单执行
- [ ] 每笔订单经过 `RiskChain.check()` 风控检查
- [ ] 被风控拦截的订单记录为 `REJECTED` 状态
- [ ] 成交后计算实际滑点
- [ ] 所有测试通过

---

### 里程碑 4.1.4：自动交易引擎（2 周）

**目标**: 实现主控引擎，将信号管线、下单执行器、执行监控串联为完整的自动交易循环。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 4.1 | 定义 `AutoTradingConfig` 配置 | domain | `src/domain/trade/value_objects/auto_trading_config.py` | 0.5d |
| 4.2 | 定义 `CycleResult` 值对象 | domain | `src/domain/trade/value_objects/cycle_result.py` | 0.5d |
| 4.3 | 实现 `AutoTradingEngine` 主控引擎 | application | `src/application/auto_trading_engine.py` | 2d |
| 4.4 | 实现交易时段校验 | application | `src/application/auto_trading_engine.py` | 0.5d |
| 4.5 | 实现定时循环（sleep-based） | application | `src/application/auto_trading_engine.py` | 1d |
| 4.6 | 扩展 `settings.py` 添加 `AutoTradeSettings` | infrastructure | `src/infrastructure/config/settings.py` | 0.5d |
| 4.7 | 创建自动交易 CLI 入口 | interfaces | `src/interfaces/cli/auto_trade.py` | 1d |
| 4.8 | 编写 `AutoTradingEngine` 集成测试 | test | `tests/application/test_auto_trading_engine.py` | 1.5d |

#### 验收标准

- [ ] `AutoTradingEngine.run_cycle()` 完成：信号生成 → 风控 → 下单 → 记录的完整闭环
- [ ] `AutoTradingEngine.start()` 启动守护循环，按配置时间执行
- [ ] `AutoTradingEngine.stop()` 优雅停止
- [ ] 交易时段外自动跳过（9:25-11:30, 13:00-15:00 之外不执行）
- [ ] `python -m src.interfaces.cli.auto_trade --config resources/trading.yaml` 可运行
- [ ] 所有测试通过

---

### 里程碑 4.1.5：执行优化 — 拆单（2 周，P1）

**目标**: 大额订单自动拆分，降低市场冲击。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 5.1 | 实现 `OrderSplitter` | application | `src/application/order_splitter.py` | 1d |
| 5.2 | 集成到 `OrderExecutor` | application | `src/application/order_executor.py` | 1d |
| 5.3 | 编写拆单逻辑测试 | test | `tests/application/test_order_splitter.py` | 1d |

#### 验收标准

- [ ] 单笔超过阈值的订单自动拆分
- [ ] 拆分后每笔不超过当日成交量 10%
- [ ] 所有测试通过

---

## 三、子项目 4.2：异常检测与自动暂停

### 里程碑 4.2.1：异常检测框架（2 周）

**目标**: 建立异常检测的基础框架，定义接口和数据模型。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 6.1 | 定义 `AnomalyEvent` 值对象 | domain | `src/domain/risk/value_objects/anomaly_event.py` | 0.5d |
| 6.2 | 定义 `AnomalyType`, `AnomalySeverity`, `AutoAction` 枚举 | domain | `src/domain/risk/value_objects/anomaly_event.py` | 0.5d |
| 6.3 | 定义 `BaseAnomalyDetector` 抽象基类 | domain | `src/domain/risk/services/anomaly_detectors/base.py` | 0.5d |
| 6.4 | 实现 `AutoPauseManager` | application | `src/application/auto_pause_manager.py` | 1.5d |
| 6.5 | 实现暂停状态持久化（SQLite） | application | `src/application/auto_pause_manager.py` | 1d |
| 6.6 | 实现 `AnomalyDetector` 聚合器 | application | `src/application/anomaly_detector.py` | 1d |
| 6.7 | 编写框架层测试 | test | `tests/domain/risk/test_anomaly_base.py`, `tests/application/test_auto_pause_manager.py` | 1.5d |

#### 验收标准

- [ ] `BaseAnomalyDetector.detect()` 返回 `list[AnomalyEvent]`
- [ ] `AutoPauseManager` 支持暂停/恢复单策略和全部策略
- [ ] 暂停状态持久化到 SQLite，进程重启后恢复
- [ ] `AnomalyDetector.run_checks()` 聚合所有子检测器结果
- [ ] 所有测试通过

---

### 里程碑 4.2.2：策略异常检测器（1.5 周）

**目标**: 实现策略级别的异常检测。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 7.1 | 实现 `TradeHistoryRepository` 接口 | domain | `src/domain/trade/interfaces/repositories/trade_history_repo.py` | 0.5d |
| 7.2 | 实现 SQLite 版 `TradeHistoryRepository` | infrastructure | `src/infrastructure/persistence/sqlite_trade_history.py` | 1d |
| 7.3 | 实现 `StrategyAnomalyDetector` | domain | `src/domain/risk/services/anomaly_detectors/strategy_anomaly.py` | 1.5d |
| 7.4 | 编写策略异常检测测试 | test | `tests/domain/risk/test_strategy_anomaly_detector.py` | 1d |

#### 验收标准

- [ ] 检测滚动胜率突降（近 20 笔 < 45%）
- [ ] 检测连续亏损（连续 5 笔+）
- [ ] 检测信号频率异常（突然暴增或归零）
- [ ] 所有测试通过

---

### 里程碑 4.2.3：数据异常检测器（1.5 周）

**目标**: 实现数据质量异常检测。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 8.1 | 实现 `DataAnomalyDetector` | domain | `src/domain/risk/services/anomaly_detectors/data_anomaly.py` | 1.5d |
| 8.2 | 实现价格跳变检测 | domain | `src/domain/risk/services/anomaly_detectors/data_anomaly.py` | 0.5d |
| 8.3 | 实现成交量异常检测 | domain | `src/domain/risk/services/anomaly_detectors/data_anomaly.py` | 0.5d |
| 8.4 | 编写数据异常检测测试 | test | `tests/domain/risk/test_data_anomaly_detector.py` | 1d |

#### 验收标准

- [ ] 检测行情数据缺失（连续 3 日无数据）
- [ ] 检测价格跳变（单日涨跌幅 > 10%，非涨跌停）
- [ ] 检测成交量异常（突然放大/缩小 10 倍+）
- [ ] 所有测试通过

---

### 里程碑 4.2.4：市场异常检测器（1.5 周）

**目标**: 实现市场极端行情检测。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 9.1 | 实现 `MarketAnomalyDetector` | domain | `src/domain/risk/services/anomaly_detectors/market_anomaly.py` | 1.5d |
| 9.2 | 实现指数暴跌检测 | domain | `同上` | 0.5d |
| 9.3 | 实现连续下跌检测 | domain | `同上` | 0.5d |
| 9.4 | 编写市场异常检测测试 | test | `tests/domain/risk/test_market_anomaly_detector.py` | 1d |

#### 验收标准

- [ ] 检测指数单日暴跌 > 3%
- [ ] 检测指数连续 5 日下跌
- [ ] 触发 PAUSE_ALL 自动暂停
- [ ] 所有测试通过

---

### 里程碑 4.2.5：ML 模型异常检测器（2 周，P1）

**目标**: 实现 ML 模型健康检测（依赖 Phase 1 的 ML 预测能力）。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 10.1 | 定义 `PredictionLogRepository` 接口 | domain | `src/domain/risk/interfaces/repositories/prediction_log_repo.py` | 0.5d |
| 10.2 | 实现 `MlModelAnomalyDetector` | domain | `src/domain/risk/services/anomaly_detectors/ml_model_anomaly.py` | 2d |
| 10.3 | 实现特征漂移检测（PSI 计算） | domain | `同上` | 1d |
| 10.4 | 编写 ML 异常检测测试 | test | `tests/domain/risk/test_ml_anomaly_detector.py` | 1d |

#### 验收标准

- [ ] 检测预测 IC 下降 < 0.03
- [ ] 检测特征分布漂移（PSI > 0.3）
- [ ] 所有测试通过

---

## 四、子项目 4.3：远程监控与告警

### 里程碑 4.3.1：通知框架（1.5 周）

**目标**: 建立通知系统的领域模型和接口。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 11.1 | 定义 `INotificationGateway` Protocol | domain | `src/domain/notification/interfaces/notification_gateway.py` | 0.5d |
| 11.2 | 定义 `NotificationMessage` 值对象 | domain | `src/domain/notification/value_objects/notification_message.py` | 0.5d |
| 11.3 | 实现 `NotificationHub` 应用服务 | application | `src/application/notification_hub.py` | 1.5d |
| 11.4 | 实现频率限制器 | application | `src/application/notification_hub.py` | 0.5d |
| 11.5 | 编写通知框架测试 | test | `tests/application/test_notification_hub.py` | 1d |

#### 验收标准

- [ ] `INotificationGateway` 定义 `send()` 和 `send_batch()` 方法
- [ ] `NotificationHub` 支持多渠道路由
- [ ] 频率限制生效（每分钟最多 N 条）
- [ ] 所有测试通过

---

### 里程碑 4.3.2：企业微信通知（1 周）

**目标**: 实现企业微信机器人 Webhook 通知。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 12.1 | 实现 `WeChatNotificationGateway` | infrastructure | `src/infrastructure/notification/wechat_gateway.py` | 1d |
| 12.2 | 扩展 `settings.py` 添加 `NotificationSettings` | infrastructure | `src/infrastructure/config/settings.py` | 0.5d |
| 12.3 | 编写微信通知测试 | test | `tests/infrastructure/notification/test_wechat_gateway.py` | 0.5d |

#### 验收标准

- [ ] 通过企业微信 Webhook 发送文本/Markdown 消息
- [ ] 消息格式化：标题 + 正文 + 时间 + 级别标识
- [ ] 发送失败时记录日志，不抛异常
- [ ] 所有测试通过

---

### 里程碑 4.3.3：Telegram 通知（1 周）

**目标**: 实现 Telegram Bot 通知。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 13.1 | 实现 `TelegramNotificationGateway` | infrastructure | `src/infrastructure/notification/telegram_gateway.py` | 1d |
| 13.2 | 编写 Telegram 通知测试 | test | `tests/infrastructure/notification/test_telegram_gateway.py` | 0.5d |

#### 验收标准

- [ ] 通过 Telegram Bot API 发送消息
- [ ] 支持 Markdown 格式
- [ ] 所有测试通过

---

### 里程碑 4.3.4：事件集成（1.5 周）

**目标**: 将通知系统与自动交易引擎、异常检测器集成。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 14.1 | `AutoTradingEngine` 集成通知 | application | `src/application/auto_trading_engine.py` | 0.5d |
| 14.2 | `AnomalyDetector` 集成通知 | application | `src/application/anomaly_detector.py` | 0.5d |
| 14.3 | `AutoPauseManager` 集成通知 | application | `src/application/auto_pause_manager.py` | 0.5d |
| 14.4 | 实现每日报告通知 | application | `src/application/notification_hub.py` | 1d |
| 14.5 | 实现静默时段 | application | `src/application/notification_hub.py` | 0.5d |
| 14.6 | 编写集成测试 | test | `tests/application/test_notification_integration.py` | 1d |

#### 验收标准

- [ ] 交易执行后自动推送通知
- [ ] 异常检测后自动推送通知
- [ ] 暂停/恢复时推送通知
- [ ] 每日收盘后推送执行统计报告
- [ ] 静默时段（23:00-07:00）不推送（EMERGENCY 除外）
- [ ] 所有测试通过

---

### 里程碑 4.3.5：监控 CLI（1 周）

**目标**: 提供 CLI 监控入口，查看系统状态、暂停/恢复。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 15.1 | 实现监控 CLI | interfaces | `src/interfaces/cli/monitor.py` | 1.5d |

#### 验收标准

- [ ] `python -m src.interfaces.cli.monitor status` 显示系统状态
- [ ] `python -m src.interfaces.cli.monitor positions` 显示当前持仓
- [ ] `python -m src.interfaces.cli.monitor stats` 显示执行统计
- [ ] `python -m src.interfaces.cli.monitor pause --strategy xxx` 暂停策略
- [ ] `python -m src.interfaces.cli.monitor resume --strategy xxx` 恢复策略

---

### 里程碑 4.3.6：Web Dashboard（3 周，P1）

**目标**: 基于 FastAPI 的 Web Dashboard，支持远程监控和控制。

#### 任务清单

| # | 任务 | 层级 | 文件 | 预估 |
|---|------|------|------|------|
| 16.1 | 实现 FastAPI 应用骨架 | infrastructure | `src/infrastructure/web/dashboard.py` | 1d |
| 16.2 | 实现状态查询 API | infrastructure | `src/infrastructure/web/routes/status.py` | 1d |
| 16.3 | 实现持仓查询 API | infrastructure | `src/infrastructure/web/routes/status.py` | 0.5d |
| 16.4 | 实现控制 API（暂停/恢复） | infrastructure | `src/infrastructure/web/routes/control.py` | 1d |
| 16.5 | 实现 SSE 实时事件流 | infrastructure | `src/infrastructure/web/routes/events.py` | 1d |
| 16.6 | 实现 Token 认证中间件 | infrastructure | `src/infrastructure/web/auth.py` | 0.5d |
| 16.7 | 实现前端页面（HTML + Alpine.js） | infrastructure | `src/infrastructure/web/static/` | 2d |
| 16.8 | 编写 API 测试 | test | `tests/infrastructure/web/test_dashboard.py` | 1.5d |

#### 验收标准

- [ ] `GET /api/status` 返回系统运行状态
- [ ] `GET /api/positions` 返回当前持仓
- [ ] `GET /api/stats` 返回执行统计
- [ ] `POST /api/control/pause` 暂停交易（需 Token）
- [ ] `POST /api/control/resume` 恢复交易（需 Token）
- [ ] `GET /api/events` SSE 实时推送事件
- [ ] 前端页面可查看状态、持仓、统计
- [ ] 所有测试通过

---

## 五、集成测试与实盘验证

### 里程碑 5.1：端到端集成测试（2 周）

| # | 任务 | 预估 |
|---|------|------|
| 17.1 | 使用 MockGateway 的端到端测试 | 2d |
| 17.2 | 异常场景测试（数据缺失、网络断开、QMT 无响应） | 1d |
| 17.3 | 暂停/恢复流程测试 | 1d |
| 17.4 | 通知推送全流程测试 | 1d |

### 里程碑 5.2：模拟盘验证（4 周）

| # | 任务 | 预估 |
|---|------|------|
| 18.1 | 使用 MockTradeGateway 模拟运行 2 周 | 持续 |
| 18.2 | 验证异常检测误报率 | 持续 |
| 18.3 | 验证通知送达率 | 持续 |
| 18.4 | 调优异常检测阈值 | 1d |

### 里程碑 5.3：实盘小资金验证（4 周）

| # | 任务 | 预估 |
|---|------|------|
| 19.1 | 小资金（1-3 万）实盘运行 | 持续 |
| 19.2 | 监控执行成功率和滑点 | 持续 |
| 19.3 | 验证异常检测在真实市场中的表现 | 持续 |
| 19.4 | 根据实盘反馈调优参数 | 2d |

---

## 六、代码量预估

| 子项目 | 业务代码 | 测试代码 | 小计 |
|--------|---------|---------|------|
| 4.1 自动执行引擎 | ~800 行 | ~400 行 | ~1,200 行 |
| 4.2 异常检测 | ~600 行 | ~300 行 | ~900 行 |
| 4.3 远程监控告警 | ~700 行 | ~350 行 | ~1,050 行 |
| **合计** | **~2,100 行** | **~1,050 行** | **~3,150 行** |

---

## 七、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| QMT 成交回报接口不稳定 | 中 | 高 | 轮询 + 超时重试 + 降级为只记录下单 |
| 异常检测误报率高 | 高 | 中 | 初期阈值宽松，根据实盘数据逐步收紧 |
| 企业微信 Webhook 限流 | 低 | 低 | 频率限制 + 消息合并 |
| 定时循环漂移 | 低 | 低 | 使用系统时钟校准，不依赖 sleep 精度 |
| SQLite 并发写入 | 低 | 低 | 单写多读模式，WAL 模式 |

---

## 八、里程碑总览

| 里程碑 | 内容 | 工期 | 依赖 |
|--------|------|------|------|
| M4.1.1 | 执行记录与监控 | 2 周 | 无 |
| M4.1.2 | 信号管线 | 2 周 | M4.1.1 |
| M4.1.3 | 自动下单执行器 | 2 周 | M4.1.1 |
| M4.1.4 | 自动交易引擎 | 2 周 | M4.1.2, M4.1.3 |
| M4.2.1 | 异常检测框架 | 2 周 | 无（可与 M4.1 并行） |
| M4.2.2 | 策略异常检测器 | 1.5 周 | M4.2.1 |
| M4.2.3 | 数据异常检测器 | 1.5 周 | M4.2.1 |
| M4.2.4 | 市场异常检测器 | 1.5 周 | M4.2.1 |
| M4.3.1 | 通知框架 | 1.5 周 | 无（可并行） |
| M4.3.2 | 企业微信通知 | 1 周 | M4.3.1 |
| M4.3.3 | Telegram 通知 | 1 周 | M4.3.1 |
| M4.3.4 | 事件集成 | 1.5 周 | M4.1.4, M4.2.*, M4.3.1 |
| M4.3.5 | 监控 CLI | 1 周 | M4.2.1, M4.3.1 |
| M4.1.5 | 执行优化（拆单） | 2 周 | M4.1.3 |
| M4.2.5 | ML 异常检测 | 2 周 | M4.2.1, Phase 1 ML |
| M4.3.6 | Web Dashboard | 3 周 | M4.3.4 |
| M5.1 | 端到端集成测试 | 2 周 | 所有里程碑 |
| M5.2 | 模拟盘验证 | 4 周 | M5.1 |
| M5.3 | 实盘小资金验证 | 4 周 | M5.2 |

**关键路径**: M4.1.1 → M4.1.2/M4.1.3 → M4.1.4 → M4.3.4 → M5.1 → M5.2 → M5.3

**并行路径**:
- M4.2.* 可与 M4.1.* 并行开发
- M4.3.1/M4.3.2/M4.3.3 可与 M4.1.* 并行开发
- M4.1.5（拆单）可与 M4.2.* 并行开发
