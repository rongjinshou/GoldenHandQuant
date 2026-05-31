# 风控熔断机制 实现计划

**文档版本**: v1.0
**创建日期**: 2026-05-31
**文档类型**: 实现计划 / 任务分解
**状态**: 草案
**设计文档**: [2026-05-31-risk-circuit-breaker-design.md](./2026-05-31-risk-circuit-breaker-design.md)

---

## 一、实现概览

### 1.1 工作量估算

| 阶段 | 任务 | 预估工时 | 新增代码 |
|------|------|---------|---------|
| P0 | 值对象 + 熔断器核心 | 2h | ~150 行 |
| P1 | 新增策略 + 通知接口 | 2h | ~120 行 |
| P2 | 应用层集成 | 2h | ~80 行 |
| P3 | 通知实现 | 1.5h | ~100 行 |
| P4 | 配置扩展 | 1h | ~40 行 |
| P5 | 单元测试 | 3h | ~300 行 |
| P6 | 集成测试 | 2h | ~150 行 |
| **合计** | | **~13.5h** | **~940 行** |

### 1.2 依赖关系

```
P0 (值对象+熔断器) ──→ P1 (策略+通知接口) ──→ P2 (应用层集成)
                                               ↓
                    P4 (配置) ←──────── P3 (通知实现)
                                               ↓
                                         P5 (单元测试)
                                               ↓
                                         P6 (集成测试)
```

---

## 二、任务分解

### P0: 值对象 + 熔断器核心

**目标**: 实现风控核心领域模型，不依赖任何外部组件。

#### Task 0.1: CircuitBreakerState 值对象

- **文件**: `src/domain/risk/value_objects/circuit_breaker_state.py`
- **内容**: `BreakerStatus` 枚举 + `CircuitBreakerState` dataclass
- **验证**: 单元测试通过
- **验收标准**:
  - `BreakerStatus` 有 NORMAL / TRIGGERED / COOLDOWN 三个值
  - `CircuitBreakerState` 属性正确：`is_normal`, `blocks_all_trading`, `allows_sell_only`
  - 使用 `@dataclass(slots=True, kw_only=True)` 模式

#### Task 0.2: RiskEvent 值对象

- **文件**: `src/domain/risk/value_objects/risk_event.py`
- **内容**: `RiskEventType` 枚举 + `RiskSeverity` 枚举 + `RiskEvent` dataclass
- **验证**: 单元测试通过
- **验收标准**:
  - 包含所有事件类型（7 种）
  - 包含三个严重级别（INFO / WARNING / CRITICAL）
  - `RiskEvent` 有 timestamp 默认值

#### Task 0.3: CircuitBreaker 核心服务

- **文件**: `src/domain/risk/services/circuit_breaker.py`
- **内容**: `CircuitBreaker` 类，包含状态机和风险评估逻辑
- **验证**: 单元测试覆盖所有状态转换
- **验收标准**:
  - `reset_daily()` 正确处理状态转换（TRIGGERED → COOLDOWN → NORMAL）
  - `evaluate()` 检查单日亏损和总回撤
  - 触发时产出 `RiskEvent`
  - 已经在 TRIGGERED/COOLDOWN 时不重复触发
  - 所有阈值通过构造函数注入

#### Task 0.4: 更新 `__init__.py`

- **文件**: `src/domain/risk/value_objects/__init__.py`, `src/domain/risk/__init__.py`
- **内容**: 导出新类型
- **验证**: import 不报错

---

### P1: 新增策略 + 通知接口

**目标**: 实现订单级熔断策略和通知协议。

#### Task 1.1: DailyLossPolicy

- **文件**: `src/domain/risk/services/risk_policies/daily_loss_policy.py`
- **内容**: 订单级策略，检查 `CircuitBreaker` 状态
- **验证**: 单元测试通过
- **验收标准**:
  - TRIGGERED 状态拒绝所有订单
  - COOLDOWN 状态拒绝 BUY，允许 SELL
  - NORMAL 状态放行所有
  - 依赖注入 `CircuitBreaker` 实例

#### Task 1.2: TotalPositionPolicy

- **文件**: `src/domain/risk/services/risk_policies/total_position_policy.py`
- **内容**: 总仓位上限策略
- **验证**: 单元测试通过
- **验收标准**:
  - 总持仓市值 / 总资产 > max_ratio 时拒绝买入
  - SELL 订单始终放行
  - 支持 current_prices 注入

#### Task 1.3: IRiskNotifier 接口

- **文件**: `src/domain/risk/interfaces/notification.py`
- **内容**: `IRiskNotifier` Protocol 类
- **验证**: 类型检查通过
- **验收标准**:
  - 使用 `Protocol`（不用 ABC）
  - 单一方法 `notify(event: RiskEvent) -> None`
  - 符合现有接口模式（如 `ITradeGateway`）

#### Task 1.4: RiskEventDispatcher

- **文件**: `src/domain/risk/services/risk_event_dispatcher.py`
- **内容**: 事件分发器，广播事件给所有通知器
- **验证**: 单元测试通过
- **验收标准**:
  - `add_notifier()` 注册通知器
  - `dispatch()` 分发单个事件
  - `dispatch_all()` 分发事件列表
  - 通知器异常不影响其他通知器

---

### P2: 应用层集成

**目标**: 将熔断器集成到策略执行流程中。

#### Task 2.1: CrossSectionalStrategyRunner 集成

- **文件**: `src/application/strategy_runner.py`
- **改动**:
  - 构造函数接收 `CircuitBreaker` 参数（可选，默认不启用）
  - `evaluate()` 方法开头检查熔断状态
  - TRIGGERED 时返回空 targets
  - COOLDOWN 时过滤 BUY 信号
- **验证**: 已有测试不回归
- **验收标准**:
  - 不传 `CircuitBreaker` 时行为不变（向后兼容）
  - TRIGGERED 时 `evaluate()` 返回空 targets + 空 prices
  - COOLDOWN 时 BUY 信号被移除

#### Task 2.2: BacktestAppService 集成

- **文件**: `src/application/backtest_app.py`
- **改动**:
  - 构造函数接收 `CircuitBreaker` 参数（可选）
  - `_run_unified_loop()` 中添加盘前 reset + 盘后 evaluate + 事件分发
  - `_run_with_event_bus()` 同样集成
  - 向 `_build_runner()` 传递 `CircuitBreaker`
- **验证**: 已有测试不回归
- **验收标准**:
  - 不传 `CircuitBreaker` 时行为不变
  - 熔断触发后后续交易日不再下单
  - 冷却期仅允许卖出

#### Task 2.3: SingleStrategyRunner 集成

- **文件**: `src/application/strategy_runner.py`
- **改动**:
  - 构造函数接收 `CircuitBreaker` 参数（可选）
  - `evaluate()` 中检查熔断状态
- **验证**: 已有测试不回归

---

### P3: 通知实现

**目标**: 实现终端和企业微信通知。

#### Task 3.1: ConsoleNotifier

- **文件**: `src/infrastructure/notification/console_notifier.py`
- **内容**: 终端彩色输出
- **验证**: 手动运行确认输出格式
- **验收标准**:
  - INFO 蓝色、WARNING 黄色、CRITICAL 红色
  - 包含事件类型和消息

#### Task 3.2: WeChatNotifier

- **文件**: `src/infrastructure/notification/wechat_notifier.py`
- **内容**: 企业微信 Webhook 推送
- **验证**: 使用 mock URL 测试
- **验收标准**:
  - 使用 `urllib.request`（不引入 requests 依赖）
  - 通知失败不抛异常
  - 超时 5 秒

#### Task 3.3: EmailNotifier

- **文件**: `src/infrastructure/notification/email_notifier.py`
- **内容**: SMTP 邮件通知
- **验证**: 使用 mock 测试
- **验收标准**:
  - 使用标准库 `smtplib` + `email`
  - 支持多个收件人
  - 通知失败不抛异常

#### Task 3.4: 通知工厂

- **文件**: `src/infrastructure/notification/factory.py`
- **内容**: 根据配置创建通知器列表
- **验证**: 单元测试
- **验收标准**:
  - 接收 `NotificationSettings`
  - 返回 `list[IRiskNotifier]`

---

### P4: 配置扩展

**目标**: 扩展 RiskSettings 支持熔断器和通知配置。

#### Task 4.1: 扩展 Settings

- **文件**: `src/infrastructure/config/settings.py`
- **改动**:
  - 新增 `CircuitBreakerSettings` dataclass
  - 新增 `NotificationSettings`、`WeChatNotificationSettings`、`EmailNotificationSettings`
  - `RiskSettings` 增加 `circuit_breaker` 和 `notification` 字段
- **验证**: 已有配置加载不回归
- **验收标准**:
  - 所有新字段有合理默认值
  - `load_backtest_config()` 正确解析新配置
  - 不传新配置时使用默认值（向后兼容）

#### Task 4.2: 更新 YAML 示例

- **文件**: `resources/backtest.yaml`（如存在）
- **改动**: 添加 `circuit_breaker` 和 `notification` 配置段
- **验证**: 配置加载成功

---

### P5: 单元测试

**目标**: 核心组件的单元测试覆盖。

#### Task 5.1: CircuitBreaker 测试

- **文件**: `tests/domain/risk/test_circuit_breaker.py`
- **用例**:
  - 初始状态为 NORMAL
  - 单日亏损超限触发 TRIGGERED
  - 总回撤超限触发 TRIGGERED
  - TRIGGERED 次日转 COOLDOWN
  - COOLDOWN 次日转 NORMAL
  - TRIGGERED 状态不重复触发
  - 事件正确产出

#### Task 5.2: DailyLossPolicy 测试

- **文件**: `tests/domain/risk/test_daily_loss_policy.py`
- **用例**:
  - NORMAL 状态放行所有订单
  - TRIGGERED 状态拒绝所有订单
  - COOLDOWN 状态拒绝 BUY、允许 SELL

#### Task 5.3: TotalPositionPolicy 测试

- **文件**: `tests/domain/risk/test_total_position_policy.py`
- **用例**:
  - 仓位未超限放行
  - 仓位超限拒绝 BUY
  - SELL 始终放行

#### Task 5.4: RiskEventDispatcher 测试

- **文件**: `tests/domain/risk/test_risk_event_dispatcher.py`
- **用例**:
  - 分发给单个通知器
  - 分发给多个通知器
  - 通知器异常不影响其他通知器

---

### P6: 集成测试

**目标**: 验证熔断器在回测流程中的端到端行为。

#### Task 6.1: 回测熔断集成测试

- **文件**: `tests/application/test_backtest_with_circuit_breaker.py`
- **用例**:
  - 模拟单日亏损 3.5% → 验证当日后续订单被拒绝
  - 验证次日仅允许卖出
  - 验证第三日恢复正常
  - 不启用熔断器时行为不变

#### Task 6.2: 策略运行器集成测试

- **文件**: `tests/application/test_strategy_runner_with_breaker.py`
- **用例**:
  - CrossSectionalStrategyRunner + CircuitBreaker
  - TRIGGERED 时返回空 targets
  - COOLDOWN 时过滤 BUY 信号

---

## 三、文件清单

### 新增文件（11 个）

| 文件路径 | 代码行 | 说明 |
|---------|--------|------|
| `src/domain/risk/value_objects/circuit_breaker_state.py` | ~40 | 熔断状态值对象 |
| `src/domain/risk/value_objects/risk_event.py` | ~35 | 风控事件值对象 |
| `src/domain/risk/services/circuit_breaker.py` | ~100 | 熔断器核心 |
| `src/domain/risk/services/risk_policies/daily_loss_policy.py` | ~35 | 单日亏损策略 |
| `src/domain/risk/services/risk_policies/total_position_policy.py` | ~40 | 总仓位策略 |
| `src/domain/risk/interfaces/notification.py` | ~10 | 通知接口 |
| `src/domain/risk/services/risk_event_dispatcher.py` | ~25 | 事件分发器 |
| `src/infrastructure/notification/console_notifier.py` | ~20 | 终端通知 |
| `src/infrastructure/notification/wechat_notifier.py` | ~30 | 微信通知 |
| `src/infrastructure/notification/email_notifier.py` | ~40 | 邮件通知 |
| `src/infrastructure/notification/factory.py` | ~25 | 通知工厂 |

### 修改文件（4 个）

| 文件路径 | 改动量 | 说明 |
|---------|--------|------|
| `src/infrastructure/config/settings.py` | +40 行 | 新增配置类 |
| `src/application/strategy_runner.py` | +30 行 | 熔断器集成 |
| `src/application/backtest_app.py` | +25 行 | 回测循环集成 |
| `src/domain/risk/__init__.py` | +5 行 | 导出新类型 |

### 测试文件（6 个）

| 文件路径 | 代码行 | 说明 |
|---------|--------|------|
| `tests/domain/risk/test_circuit_breaker.py` | ~100 | 熔断器核心测试 |
| `tests/domain/risk/test_daily_loss_policy.py` | ~50 | 单日亏损策略测试 |
| `tests/domain/risk/test_total_position_policy.py` | ~50 | 总仓位策略测试 |
| `tests/domain/risk/test_risk_event_dispatcher.py` | ~40 | 事件分发器测试 |
| `tests/application/test_backtest_with_circuit_breaker.py` | ~80 | 回测集成测试 |
| `tests/application/test_strategy_runner_with_breaker.py` | ~60 | 策略运行器测试 |

---

## 四、实施顺序

### 第一批（P0 + P1）：领域模型

纯 Domain 层代码，无外部依赖，可独立开发和测试。

1. Task 0.1: CircuitBreakerState
2. Task 0.2: RiskEvent
3. Task 0.3: CircuitBreaker
4. Task 0.4: 更新 `__init__.py`
5. Task 1.1: DailyLossPolicy
6. Task 1.2: TotalPositionPolicy
7. Task 1.3: IRiskNotifier
8. Task 1.4: RiskEventDispatcher
9. Task 5.1-5.4: 领域层单元测试

**验证**: `python -m pytest tests/domain/risk/ -v`

### 第二批（P4 + P3）：配置与通知

10. Task 4.1: 扩展 Settings
11. Task 4.2: 更新 YAML
12. Task 3.1: ConsoleNotifier
13. Task 3.2: WeChatNotifier
14. Task 3.3: EmailNotifier
15. Task 3.4: 通知工厂

**验证**: `python -m pytest tests/infrastructure/notification/ -v`

### 第三批（P2）：应用层集成

16. Task 2.1: CrossSectionalStrategyRunner 集成
17. Task 2.2: BacktestAppService 集成
18. Task 2.3: SingleStrategyRunner 集成

**验证**: `python -m pytest tests/application/ -v`（已有测试不回归）

### 第四批（P6）：集成测试

19. Task 6.1: 回测熔断集成测试
20. Task 6.2: 策略运行器集成测试

**验证**: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v`

---

## 五、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 与现有 RiskChain 集成冲突 | 低 | 中 | DailyLossPolicy 作为 RiskChain 的一个策略节点 |
| 回测结果因熔断而大幅变化 | 高 | 低 | 默认关闭熔断器（`enabled: false`），用户显式启用 |
| 通知服务不可用 | 中 | 低 | 通知失败静默处理，不影响交易 |
| 状态机边界条件 | 中 | 中 | 充分的单元测试覆盖所有状态转换 |

---

## 六、验收标准清单

- [ ] `CircuitBreaker` 状态机转换正确（NORMAL → TRIGGERED → COOLDOWN → NORMAL）
- [ ] 单日亏损 3% 触发熔断
- [ ] 总回撤 20% 触发熔断
- [ ] 熔断后所有订单被拒绝
- [ ] 冷却期仅允许卖出
- [ ] 冷却期结束后自动恢复
- [ ] 终端通知正常输出
- [ ] 企业微信通知正常推送（配置 webhook_url 后）
- [ ] 邮件通知正常发送（配置 SMTP 后）
- [ ] 不启用熔断器时，所有已有功能不变
- [ ] 配置文件正确加载
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] `ruff check src/` 无新增警告
- [ ] Domain 层无第三方依赖引入
