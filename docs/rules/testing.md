# 单元测试规范 (Testing Standards)

> 框架：pytest（+ pytest-mock）。测试代码质量必须等同甚至高于生产代码。

## 1. 核心原则 (FIRST)

- **Fast**: 测试秒级运行完毕。
- **Isolated**: 用例间绝对独立，禁止共享状态或依赖执行顺序。涉及 infrastructure 层
  的外部网络调用或 QMT 客户端连接，必须 Mock 拦截。
- **Repeatable**: 任何环境、任何时间运行结果完全一致。
- **Self-validating**: 只输出 Pass/Fail，禁止人工肉眼比对 print 日志。
- **Thorough**: 关键业务流（资金冻结、订单状态机、策略池状态机、熔断器状态机、
  盘前闸、预算闸）必须覆盖边界条件与异常分支。

## 2. AAA 结构 (Arrange-Act-Assert)

每个用例内部清晰划分三块，用空行或注释隔开：

1. `Arrange`: 准备数据/替身、实例化实体、设置初始状态。
2. `Act`: 调用被测方法。
3. `Assert`: 严格断言返回值或状态变化。

## 3. 语义化命名

- 测试文件、类、函数一律 `snake_case`。
- 函数命名公式：`test_<待测方法名>_<特定场景>_<预期行为>`。
- ❌ `test_order_logic()`
- ✅ `test_apply_trade_with_partial_fill_should_update_filled_volume_and_keep_submitted_status()`

## 4. DDD 分层测试策略

- **领域层**: 覆盖率目标 90%+。纯业务逻辑**完全不需要也不允许 Mock**。
  重点死磕 `Position` T+1、`Order` 状态机、`StrategyPoolEntry` 状态机、
  `CircuitBreaker` 状态机、`pre_trade_checks` 闸函数。
- **应用层**: 测业务流编排。完整 Mock/Fake 掉所有 Gateway，验证编排逻辑正确调用
  领域服务与基础设施。
- **基础设施层**: 测防腐层数据转换（QMT/Tushare 映射）与通知渠道适配。

## 5. 目录镜像映射

- 测试目录按**层与子域**镜像 `src/`；子域内部（entities/services/value_objects）
  允许扁平放置；文件名 `test_<源文件名>.py`。
- 例：`src/domain/account/entities/asset.py` → `tests/domain/account/test_asset.py`；
  `src/application/auto_trade_app.py` → `tests/application/test_auto_trade_app.py`。
- 例外：需要 xtquant 的网关测试在 `tests/infrastructure/gateway/`（CI/WSL 默认跳过），
  离线可跑的网关测试放 `tests/infrastructure/gateway_offline/`。

## 6. 测试工具约定

- 优先手写 `Fake` 对象替代 `MagicMock`，可读性与可维护性更高。
- 共享 fixture 放 `tests/conftest.py`。
- 测试替身的轮询/时钟类行为要防死循环：替身状态序列耗尽后应返回终态而非中间态
  （教训记录：`docs/feat/0611-closed-loop/2026-06-11-night-review.md`）。

## 7. 本机环境注记 (Windows + WSL)

- 运行命令：`python -m pytest tests/ --ignore=tests/infrastructure/gateway/`。
- `pyproject.toml` 已配置 `--basetemp=.pytest_tmp`（系统 Temp 下 pytest-of-* 目录
  ACL 损坏不可用，**勿改回**；`.pytest_tmp/` 已 gitignore）。
- pytest 末尾汇总行偶被终端吞掉，以 **exit code** 为准。
- `tests/interfaces/cli/test_factor_test_cli.py` 直连真实 `data/market.duckdb`，
  与 data refresh 写锁互斥时会环境性 ERROR（登记债 D7，非代码问题）。
