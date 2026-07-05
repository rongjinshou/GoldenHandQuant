# GoldenHandQuant 架构宪法 (Architecture Constitution)

> **版本**: v4.0 | **更新日期**: 2026-06-11 | **适用范围**: 全项目 AI 编码助手 & 人类开发者
>
> v4.0 起规范按主题拆分为多个文档（见 §1 索引），本文件只保留**宪法级内容**：
> 系统定位、分层红线、AI 执行协议。读规范时按需加载对应主题文档，不必整目录通读。

## 1. 规范文档索引

| 文档 | 内容 | 何时读 |
|---|---|---|
| `architecture.md`（本文） | 定位、分层、依赖红线、AI 协议 | 任何改动前 |
| `coding-style.md` | Python 3.13 风格/命名/异常/导入/docstring | 写代码前 |
| `testing.md` | FIRST/AAA/命名公式/分层策略/镜像目录/本机注记 | 写测试前 |
| `domain-rules.md` | A 股业务规则：T+1/冻结/状态机/成本/滑点/复权/StockSnapshot | 动 domain 或网关前 |
| `live-trading.md` | 实盘脊柱、三层防线、dry-run/live 三重确认、交易留痕 | 动实盘链路前 |
| `data-layer.md` | QMT API 陷阱、数据源矩阵、DuckDB/SQLite 双库约束 | 动数据获取/持久化前 |
| `codebase-map.md` | 三层真实组件地图（与代码同步） | 找代码/定改动位置时 |
| `debt-ledger.md` | 技术债务台账：待清偿/挂账观察/已核销/未动工 | 大改前排查"是否早有人踩过这坑"；处理完债务随手回来核销 |

## 2. 系统定位

- **系统**: GoldenHandQuant — 中国 A 股量化交易系统（回测框架 + 实盘交易 + 策略研发）
- **架构**: 基于 DDD 的单体架构，Python 3.13+
- **三种运行形态**:
  - **回测**: `BacktestAppService` 编排历史行情推进 → 策略信号 → 模拟撮合 → 日终结算
  - **实盘**: `AutoTradeAppService` 自动循环（dry_run 纸面前向为默认；live 需三重确认）
  - **研究**: 数据刷新（DuckDB 研究库）→ 因子硬门槛判决（factor-test）→ ML 管道

## 3. 核心红线（绝对禁令）

1. **领域层无副作用**: `src/domain` **允许**纯计算库（numpy/pandas/scipy——无 I/O、
   无网络、无全局状态）；**严禁**带副作用或环境依赖的库：数据源 SDK（xtquant、tushare）、
   存储引擎（duckdb、sqlite 包装）、Web 框架（fastapi）、可视化（matplotlib）、
   ML 训练库（lightgbm 等）。红线本质是"领域逻辑无副作用、可独立测试"
   （变更记录：`docs/feat/0611-market-data-store/2026-06-11-market-data-store-design.md` §2）。
2. **依赖只能由外向内**: `interfaces → infrastructure → application → domain`；
   **domain 不调用任何其他层**。
3. **接口隔离 (DIP)**: 领域层只定义 Protocol/ABC 接口，外部对接（QMT、通知、ML 推理、
   存储）在 infrastructure 实现；应用层经依赖注入接收实现，永不直接依赖 infrastructure。
   跨子域通信走接口（如 risk 经 `IRiskNotifier` 通知；strategy 经 `IInferenceEngine`
   调 ML；回测经 `IBacktestBroker` 组合 `ITradeGateway + IAccountGateway`）。
4. **强制类型注解**: 所有函数签名、类属性必须有完整准确的 Type Hints。
5. **实盘安全**: live 真单三重确认（配置 `mode: live` + `enabled: true` + CLI `--live`），
   dry_run 为默认；金额与预算闸常量收口在 `pre_trade_checks.py` 与配置
   （详见 `live-trading.md`）。
6. **通知脱敏与状态文件完整性**: 交易通知支持脱敏模式；持久化状态文件附 HMAC 签名
   （详见 `domain-rules.md` §7）。

## 4. 分层职责

- **`src/domain/`** — 纯业务逻辑。实体（充血模型，含状态转换方法）、不可变值对象、
  领域服务、外部依赖接口。子域：account / trade / market / strategy / risk /
  portfolio / notification / backtest / common。
- **`src/application/`** — 用例编排，协调领域对象与基础设施，自身不含业务规则。
- **`src/infrastructure/`** — 外部依赖实现：QMT/Tushare 网关、回测 Mock、
  DuckDB/SQLite 持久化、ML 引擎、通知渠道、配置加载。
- **`src/interfaces/`** — 入口：CLI（`quant.py` 统一入口 + auto_trade 守护）、
  FastAPI 驾驶舱（REST + 静态 UI）。

子域内部结构约定：`entities/`、`value_objects/`、`services/`（接口/基类在根，
实现在子包）、`interfaces/`（gateways/ 与 repositories/ 分设）。
完整组件清单见 `codebase-map.md`。

## 5. AI 执行协议

每次接到新任务：

1. **分析**: 确认任务属于哪一层/哪个子域，简述设计思路。
2. **编码**: 遵循对应主题文档（按 §1 索引加载）。
3. **自检**: 核对是否违反 §3 红线（如 domain 层 import 了 xtquant/duckdb）；
   违反立即自行修正。
4. **验证**: 跑受影响测试与 `ruff check src/`，以 exit code 为准。

## 6. v4.0 变更记录（2026-06-11）

- **拆分**: 原 v3.0 单文件 1051 行 / 40 章节拆为 7 个主题文档，支持按需渐进加载。
- **剔除虚构内容**: v3.0 将《系统后续开发设计》（`docs/feat/0531-system-subsequent-development/`）
  中的**规划**误写为现状。经逐路径核查（78 条路径 32 条不存在），以下章节描述的组件
  并不存在，已整体移除：EventBus、HealthService 应用服务、策略生命周期管理器、
  因子流水线服务、ML 影子模式/灰度发布、盘后对账、实时风控领域服务、算法交易
  （TWAP/VWAP/Iceberg）、归因分析、组合优化器、配置热更新、多账户。
  这些仍是有效的**规划**，实现时从设计文档出发，落地后再入 `codebase-map.md`。
- **补齐现状**: 闭环 v1（2026-06-11）的自动交易脊柱、盘前闸、双库持久化、驾驶舱
  此前完全缺失，现收录于 `live-trading.md` / `data-layer.md` / `codebase-map.md`。
