# GoldenHandQuant 架构宪法与开发规范 (Architecture & Coding Guidelines)

## 1. 系统定位与核心架构
* **系统名称**: QuantFlow
* **业务场景**: 中国 A 股量化交易系统（实盘/回测框架）
* **架构模式**: 基于领域驱动设计 (DDD) 的单体架构 (Monolithic Architecture)
* **核心驱动**: 进程内事件驱动 (In-Memory Event-Driven)

## 2. 核心红线 (AI 编码绝对禁令)
作为本项目的 AI 编程助手，你在生成任何代码时，**必须绝对遵守以下红线，不可有任何逾越**：
1. **领域层绝对纯洁 (Domain Purity)**: `src/domain` 目录下的所有代码，**严禁**引入任何第三方库（如 pandas, numpy, xtquant, catboost 等）。只能使用 Python 标准库（如 dataclasses, enum, typing, datetime）。
2. **严格的依赖控制**: 依赖关系只能**由外向内**。
   * Infrastructure（基础设施层）可以调用 Application（应用层）和 Domain（领域层）。
   * Application 可以调用 Domain。
   * **Domain 不能调用任何其他层。**
3. **接口隔离原则 (DIP)**: 领域层只定义接口（Repository Interfaces / Gateway Interfaces），具体的外部调用（如对接 QMT 交易软件）必须在 `src/infrastructure` 层实现这些接口。
4. **强制类型注解 (Type Hinting)**: 所有函数签名、类属性必须包含完整且准确的 Python Type Hints。

## 3. 标准目录结构与职责说明
请严格按照以下目录结构划分模块：

QuantFlow/
├── config/                 # 配置文件存放区 (yaml/json)
├── data/                   # 本地数据缓存与预训练模型存放区
├── logs/                   # 运行日志存放区
└── src/
    ├── domain/             # 【领域层】核心业务逻辑，实体、值对象、领域服务、接口定义
    │   ├── account/        # 账户与持仓子域
    │   ├── trade/          # 交易执行子域
    │   ├── market/         # 行情与因子子域
    │   ├── strategy/       # 策略信号子域
    │   └── risk/           # 风控拦截子域
    ├── application/        # 【应用层】用例编排，协调领域对象与基础设施
    ├── infrastructure/     # 【基础设施层】脏活累活，外部依赖的具体实现
    │   ├── gateway/        # QMT/xtquant 的具体对接实现 (数据获取、下单执行)
    │   ├── ml_engine/      # CatBoost 模型的推理封装
    │   ├── event_bus/      # 进程内事件总线实现 (基于 asyncio.Queue 等)
    │   └── persistence/    # SQLite/文件存储等持久化实现
    └── interfaces/         # 【用户接口层】系统出入口
        ├── api/            # API 路由定义 (FastAPI 等)
        ├── cli/            # 命令行入口模块
        └── events/         # 外部回调接收器 (如 QMT 推送的回调转换)

## 4. A 股领域知识建模规范 (Domain Knowledge Constraints)
在设计领域模型时，必须内置以下 A 股特定业务规则：
1. **T+1 结算规则**: Position (持仓实体) 必须明确区分 total_volume (总持仓) 和 available_volume (可用持仓)。当日买入成交后，只能增加 total_volume，不可增加 available_volume。
2. **资金冻结规则**: Asset (资产实体) 必须包含 total_asset (总资产)、available_cash (可用资金) 和 frozen_cash (冻结资金)。Order 提交时必须立即冻结资金，成交或撤单时进行解冻/扣减。
3. **订单状态机**: Order 实体的 status 必须遵循以下严格的单向状态扭转：
   * CREATED (已创建) -> SUBMITTED (已报)
   * SUBMITTED -> PARTIAL_FILLED (部成) / FILLED (已成) / CANCELED (已撤) / REJECTED (废单)
   * PARTIAL_FILLED -> FILLED / PARTIAL_CANCELED (部成撤)
4. **价格与数量规则**: 买入数量必须为 100 的整数倍（一手）；行情特征计算必须使用**前复权 (Forward Adjusted)** 数据。

## 5. AI 执行协议 (AI Workflow Protocol)
每次接收到新任务时，AI 需按以下步骤执行：
1. **分析**: 确认该任务属于 DDD 的哪一层，并简述设计思路。
2. **编码**: 按照 `ARCHITECTURE.md` 的要求编写高质量代码。
3. **自检**: 生成完毕后，自行核对是否违反了上述红线（如：是否在 domain 层 import 了 pandas）。若有违反，立即自行修正。

## 6. Python 3.11 现代编码风格与规范 (Modern Coding Conventions)
为了保持代码库的极高可读性、执行性能和前沿性，本项目全面拥抱 Python 3.11+ 的现代特性。AI 在生成代码时必须严格遵循以下风格：

1. **现代类型注解 (Advanced Type Hinting)**:
   - **全面弃用**旧版 `typing` 模块中的大写集合（如 `List`, `Dict`, `Union`, `Optional`）。
   - 强制使用内置泛型和管道符：`list[str]`, `dict[str, int]`, `str | None`。
   - 在返回类实例自身时，强制使用 `typing.Self`。

2. **高性能数据类 (Modern Dataclasses)**:
   - 领域实体（Entities）和值对象（Value Objects）全面使用 `@dataclass(slots=True, kw_only=True)`。
   - `slots=True`：彻底杜绝动态字典，极致优化海量持仓/订单对象的内存占用。
   - `kw_only=True`：强制要求实例化时必须使用关键字传参，彻底杜绝参数错位导致的致命交易 Bug。

3. **结构化模式匹配 (Structural Pattern Matching)**:
   - 在处理复杂的领域状态机（如 `Order` 的状态流转 `CREATED` -> `SUBMITTED` -> `FILLED`）或事件路由时，**优先使用 `match / case` 语法**，替代冗长且易错的 `if-elif-else`。

4. **严格的命名与格式化 (PEP 8 严格模式)**:
   - 默认以 **Ruff** 和 **Black** 为隐式代码格式化标准。单行代码长度限制建议为 120 字符。
   - 类名使用 `PascalCase`；函数、变量、方法使用 `snake_case`；全局常量使用 `UPPER_SNAKE_CASE`。
   - 模块内部私有属性/方法严格使用单下划线前缀 `_`，绝不允许滥用双下划线 `__`（除非为规避命名冲突）。

5. **异常处理与错误边界 (Error Handling)**:
   - 绝不允许出现 bare `except:` 或 `except Exception: pass`。
   - 必须捕获具体的异常类型。在基础设施层捕获到第三方异常后，必须将其包装为领域层自定义的异常（如 `raise OrderSubmitError from e`）再向上抛出。

6. **专业文档字符串 (Docstrings)**:
   - 所有公共模块、类、复杂的领域方法必须包含 **Google Style** 的 Docstring。
   - 必须明确标注 `Args:`（参数说明）、`Returns:`（返回值说明）以及可能抛出的 `Raises:`（异常说明）。

## 7. 单元测试规范 (Unit Testing Standards)
本项目采用业内最先进的 Python 测试框架 `pytest`，并严格遵守工业级测试规范。测试代码的质量必须等同甚至高于生产代码。

1. **核心原则 (The FIRST Principle)**:
   - **Fast (快速)**: 测试必须秒级运行完毕。
   - **Isolated (隔离)**: 测试用例之间绝对独立，禁止共享状态或依赖执行顺序。涉及 `infrastructure` 层的外部网络调用或 QMT 客户端连接，**必须使用 `pytest-mock` 进行拦截和 Mock**。
   - **Repeatable (可重复)**: 在任何环境、任何时间运行的结果必须完全一致。
   - **Self-validating (自我验证)**: 测试只允许输出 Pass/Fail，禁止需要人工肉眼比对 Print 日志。
   - **Thorough (全面)**: 关键业务流（如资金冻结、订单状态机）必须覆盖边界条件和异常分支。

2. **AAA 结构模式 (Arrange-Act-Assert)**:
   - 每个测试用例内部必须清晰划分三个逻辑块，并建议用空行或注释隔开：
     1. `Arrange`: 准备 Mock 数据、实例化实体、设置初始状态。
     2. `Act`: 调用被测方法。
     3. `Assert`: 严格断言返回值或状态的改变。

3. **极致语义化的命名规范 (Descriptive Naming)**:
   - 测试文件、类、函数强制使用 `snake_case`。
   - 测试函数命名规范必须严格遵循公式：`test_<待测方法名>_<特定场景>_<预期行为>`。
   - ❌ 错误示例：`test_order_logic()` (毫无信息量)
   - ✅ 正确示例：`test_apply_trade_with_partial_fill_should_update_filled_volume_and_keep_submitted_status()`

4. **DDD 各分层的测试策略**:
   - **领域层 (Domain)**: 要求极高的测试覆盖率（目标 90%+）。因为是纯粹的业务逻辑（无外部依赖），此类测试**完全不需要也不允许 Mock**。重点死磕 `Position` 的 T+1 变更和 `Order` 的状态机流转。
   - **应用层 (Application)**: 重点测试业务流编排。必须完整 Mock 掉所有的 `Gateway`（如 `QmtTradeGateway`），验证在注入特定行情信号时，`TradingAppService` 是否正确调用了风控并下发了订单。
   - **基础设施层 (Infrastructure)**: 重点测试防腐层（ACL）的数据转换逻辑（如验证 QMT 晦涩的 API 字典是否被正确映射成了我们纯洁的 `Bar` 或 `Asset` 实体）。

5. **目录映射与文件命名规范 (Mirror Directory Structure)**:
   - 测试代码的目录层级必须与源代码 `src/` 下的层级保持 **1:1 绝对镜像映射**。
   - 测试文件的命名规范：必须严格以 `test_` 为前缀，后接对应的源文件名。
   - 举例对照：
     * 源文件：`src/domain/account/entities.py`
     * 测试文件：`tests/domain/account/test_entities.py`
     * 源文件：`src/infrastructure/gateway/qmt_trade.py`
     * 测试文件：`tests/infrastructure/gateway/test_qmt_trade.py`