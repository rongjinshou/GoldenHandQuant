# 全项目体检与六西格玛（DMAIC）演进设计

- 日期：2026-07-10
- 方法：DMAIC（Define 定义 → Measure 度量 → Analyze 分析 → Improve 改进 → Control 控制）
- 输入：7 路并行只读勘察（架构/数据/回测/实盘/测试/前端/文档）+ 全量测试与 lint 实跑 + market.duckdb / trading.db 只读探针
- 范围声明：本轮 Improve 只做「低风险、可当场验证」的改进；凡改变实盘核心行为或需业务拍板的项，一律进 §6 决策清单，不擅动。

---

## 1. Define：系统 CTQ（Critical to Quality）

项目北极星（`docs/feat/0530-system-roadmap/`）：渐进式自动化，验证优先。当前阶段：**dry-run 纸面影子盘攒样本期（2026-07-04 起），未投真金**。据此定义四个质量关键特性：

| CTQ | 定义 | 缺陷定义（defect） |
|---|---|---|
| CTQ1 资金安全 | 实盘链路不发错单、不重复下单、风控硬闸有效 | 任何一笔无防线可拦截的错单路径 |
| CTQ2 研究诚实 | 回测/因子结论无前视、无幸存者偏差、可复现可审计 | 任何一条使结论系统性偏乐观的口径 |
| CTQ3 数据诚实 | 行情/特征/基本面完整、新鲜、缺口可见 | 静默的 NULL/缺口/过期数据被下游消费 |
| CTQ4 过程受控 | 质量门禁自动化、防回退 | 依赖「人记得跑」的任何门禁 |

## 2. Measure：质量基线（2026-07-10 实测）

**过程能力（好的一面）**
- 全量测试：约 1390 用例全绿（Windows Python，exit 0）；另有 30 个 gateway 测试被 `--ignore` 排除，**实测直接跑全过**（它们 mock 了 SDK，不需要真 QMT）。
- `ruff check src/`：0 违规。domain 层依赖纯度：跨层违规 **0**、禁用库 import **0**（满分）。
- 债务治理：代码内可执行 TODO/FIXME = **0**，债务统一入 `docs/rules/debt-ledger.md`（单一真相源，维护优秀）。

**缺陷与缺口（量化）**
- 实盘链路：2 高（幂等窗口 H1 / 连接假初始化 H2）+ 7 中 + 4 低；`order_poller`/`trading_sessions`/`drawdown_policy`/`position_limit_policy`/`order_service` 测试覆盖 **0**；QMT 回报回调重写 **0** 处、自动重连 **0** 处。
- 实锤缺陷（trading.db 取证）：2026-06-30 dry-run 周期产生 `signal_price = -0.32165` 的卖单（000021.SZ，QMT 真账户负成本持仓 → 清仓路径无正价防线，`equal_weight_sizer.py:81/127`）；同批 `strategy_name` 被误记为 `EqualWeightSizer`。
- 数据：bars 646 万行 0 重复 0 NULL-close（优）；特征 NULL 率 2022 年后 0.13%–0.53%；但 2025-11-25→2026-02-26 曾有 **103,466 行 NULL 静默固化**（潜伏数周，靠人肉偶然发现，d5a8f4d 已一次性修复，残留 459 行属新股预热）；**数据新鲜度停在 2026-07-03，落后 5 个交易日**；`instruments` 退市股仅 203/5414。
- 回测入库：`backtest_runs` 仅 3 行，16 个字段中 git_sha/数据指纹/特征版本/成本参数 = **0**（不可复现审计）。
- 工程门禁：CI **0**、pre-commit **0**、覆盖率度量 **0**、锁文件 **0**、类型检查 **0**；`ruff check tests/` **263 错**、`scripts/` **5 错**；`check_frontend_fresh.py` 因 mtime 机制**当前正在误报（exit 1）**。
- 环境：CLAUDE.md 承诺「WSL Python 跑回测」，实测 WSL conda 环境缺 duckdb/scipy/sklearn/lightgbm/pyarrow —— **文档承诺与环境事实不符**。
- 堆积物：领域层死代码 ≥1500 行（资金分配整树、再平衡整树、4 个 anomaly_detector、若干死 VO/死接口）；`data/` 根 5209 个散落 CSV + 2.5G `market.duckdb.bak-featfix` 备份；双 web 栈（`infrastructure/web/dashboard.py` 死代码含 TokenAuth/SSE）。

## 3. Analyze：六大核心矛盾（根因分析）

### 矛盾一：质量投入的分布与风险的分布倒挂（CTQ1）
研究侧纪律近乎满分（domain 纯度/测试/lint/台账），而**钱真正流过的实盘链路是全系统测试最薄弱、缺陷最密集的地方**——恰逢影子盘→真金的关口。
根因（5 Why）：实盘链路最年轻（0611 起）→ 依赖 Windows-only 的 xtquant → `xtquant_client.py` 导入即抛 → 测试整目录被 `--ignore` 连坐 → 实盘代码失去回归防线 → 缺陷（负价格、假初始化、绕闸路径）潜伏无人拦。
**本质：测试可达性问题被误当成测试必要性问题处理了。**

### 矛盾二：「只刷缺口」的性能设计压倒数据诚实（CTQ3）
`fetch_meta` 履约标记让刷新只拉缺口（好设计），但 `mark_fulfilled` 在 bars（`market_data_app.py:77-84`）与 features（`:126-130`）两条链上都是**无条件调用**：瞬时失败/空产出/全 NaN 也被标「已履约」→ 永不重试 → 静默固化。10 万行 NULL 事故只是该缺陷家族的一次发作；`refix_feature_gap.py` 修了症状，根因原样保留。且全系统 **0 个自动数据质量门禁**，`data status` 只报行数不报 NULL 率。
**本质：把「标记完成」当成了「验证完成」。**

### 矛盾三：回测结论的诚实度存在三处系统性偏乐观（CTQ2）
1. **幸存者宇宙默认口径**：`_backtest_wiring.py:24` 默认 `include_sources=("qmt",)`（QMT 无退市股），F01 主跑与入库口径均为幸存者宇宙——而 MicroValue 专选最小市值，退市股恰是暴跌出局的小盘股（B1 敏感性分析已量化影响可控，但主口径未切换、入库未标注）。
2. **基本面腿前视**：技术特征严格 as-of T-1（`shift(1)`，优秀），但 `market_cap/PE/PB` 取 T 日收盘派生值、执行在 T 日开盘（`strategy_runner.py:219-228` + `qmt_fundamental_fetcher.py:189`）；实盘实际拿到的是 T-1 值 → 回测与实盘口径分裂且回测偏乐观。`fundamental_registry.py:39` 已有 `latest_date_at_or_before` API 可修。
3. **ST ±5% 涨跌停从未生效**（DD-6，台账已登记）：`StockStatusRegistry` 生产从不构造，回测对 ST 尾部风险系统性乐观。
另：`backtest_runs` 无可复现元数据，同参不同数据版本的两次跑不可区分。

### 矛盾四：门禁存在但全靠人手（CTQ4）
验收链 6+ 条命令（pytest/ruff/vitest/typecheck/fresh-check/ui_smoke）散落文档靠人记得跑；无 CI/pre-commit/覆盖率；`testing.md` 写「领域层覆盖率 90%+」却无度量工具 = 口号；`check_frontend_fresh.py` 用 mtime 判新鲜度，git checkout 后**正在误报**。
**本质：门禁的存在性 ≠ 门禁的强制性。**

### 矛盾五：单体清晰度被「做了没接线」的堆积物侵蚀
反复出现的模式：EventStore/UnitOfWork（建了没接）、正式风控四策略+熔断器（建了没接实盘）、资金分配整树（Spec3 瘦身后悬置）、双 web 栈、标量/向量化双实现、双缓存元数据（CSV `_fetch_meta.json` vs DuckDB `fetch_meta`）。≥1500 行死代码使地图失真、审查变慢。
**本质：交付定义停在「代码写完」，没到「接线上线或删除」。**

### 矛盾六：双环境割裂的边界处理粗糙
QMT 锁死 Windows（无解，接受），但边界代价被放大：WSL 环境缺依赖与文档承诺矛盾；xtquant 导入即崩连坐 30 个 mock 测试；npm 必须 Windows 侧。环境事实与文档承诺的漂移会让「按文档执行」的人（或 AI）在 WSL 里白撞。

## 4. Improve：本轮实施范围（低风险、当场验证、逐项 TDD）

| 批 | 项 | 治理的矛盾 | 改动 |
|---|---|---|---|
| A1 | 清仓路径正价防线 + strategy_name 审计修正 | 一 | `equal_weight_sizer.py` 清仓分支 `p<=0` 时跳过并留痕原因；`strategy_name` 回退值改为持仓语义 |
| A2 | QMT 连接失败 fail-fast（H2） | 一 | `qmt_trade.py` connect/subscribe 非 0 抛异常，不再假初始化 |
| A3 | SQLite `busy_timeout`（M8 最小片） | 一 | `database.py` 加 PRAGMA |
| A4 | `seed_paper_trading` 清库护栏（L11） | 一 | 清生产 `data/trading.db` 需显式 `--yes` |
| A5 | 下单后审计写库异常不误标 FAILED（L10） | 一 | `_audit_order` 失败仅告警不冒泡 |
| B1 | `ensure_bars` 空返回不再无条件履约（P2） | 二 | 空返回仅当区间落在上市前/退市后才履约，否则跳过+告警 |
| B2 | `ensure_features` 履约前产出校验（P1） | 二 | 关键列非空率达阈值才 mark_fulfilled |
| B3 | `quant data status --check` 数据质量门禁（P3） | 二/四 | NULL 率、覆盖缺口、新鲜度、方差=0 告警；非 0 退出码 |
| C1 | 截面回测基本面腿改 as-of T-1 | 三 | `strategy_runner.py` 用 `latest_date_at_or_before(T-1)`；**回测数字会变（更诚实）** |
| C2 | `backtest_runs` 强制记录 survivorship + git_sha + feature_version | 三 | 入库 params 增强（wiring/脚本注入，domain 不碰 git） |
| D1 | `check_frontend_fresh` 由 mtime 改内容哈希 | 四 | 修正在发生的误报 |
| D2 | ruff 扩围 tests/ scripts/ 并清零存量 | 四 | 263+5 错清零，门禁写进文档 |
| D3 | `scripts/verify_all.py` 一键验收链 | 四 | pytest 全量（含 gateway）+ ruff（src/tests/scripts）+ data --check + fresh-check |
| D4 | gateway 测试回归标准命令 | 一/六 | 去掉 `--ignore` + WSL 兼容 skip 守卫；CLAUDE.md 同步 |
| D5 | 补零覆盖实盘模块测试 | 一 | `order_poller`、`trading_sessions` 等 |
| D6 | domain 测试 mock 违规清理 | 四 | 3 个文件换手写 Fake，删死导入 |
| E1 | WSL 环境补装依赖 | 六 | `pip install -e ".[dev,api,ml]"`（对齐文档承诺） |
| E2 | 文档勘校 | 五/六 | codebase-map 前端段、live-trading 限额口径、CLAUDE.md 测试命令 |
| E3 | 债务台账登记本轮发现与核销 | 五 | 按台账惯例记账 |

## 5. Control：控制计划

1. **一键验收链** `scripts/verify_all.py` 成为唯一入口：任何改动后一条命令全绿才算完（替代「人记得跑六条」）。
2. **数据质量门禁** `data status --check` 进验收链与周二 runbook：NULL 率/覆盖/新鲜度越限即红。
3. **gateway 测试进标准命令**：实盘防腐层从此有回归防线。
4. **入库元数据**：此后每条 `backtest_runs` 自带 git_sha/宇宙口径/特征版本，结论可审计。
5. **台账闭环**：本轮全部发现进 debt-ledger（含未修项），防「发现即遗忘」。

## 6. 决策清单（需用户拍板，本轮不动）

| # | 事项 | 建议 | 为什么不擅动 |
|---|---|---|---|
| Q1 | H1 下单幂等重构（下单前预写 PENDING 记录 + 启动对账） | 强烈建议下轮首位 | 改实盘核心事务顺序与预算/去重口径 |
| Q2 | M5 正式风控接线（单票 30%/总仓 80%/熔断进实盘硬闸） | 建议接线 | 阈值与生效层需业务拍板 |
| Q3 | M6 `quant live` 半自动路径复用盘前闸 | 建议统一 | 改交互语义（会开始拒单） |
| Q4 | M3 QMT 回报回调 + 断线重连 | 建议实现 | 需 QMT 实环境联测 |
| Q5 | DD-6 ST 涨跌停数据源（新表+回填+接线） | 立项修复 | 工程量堪比 B1 |
| Q6 | F01 主跑宇宙默认切含退市（`qmt+akshare`） | 建议切换后重跑 | 研究口径变更需重跑对照 |
| Q7 | 死代码删除 ≥1500 行（资金分配树等，走 REVIVAL.md 惯例） | 建议删 | 业务「去留未决」在案 |
| Q8 | M7 交易日历（法定节假日） | 建议引入 | 需选定数据源 |
| Q9 | 数据刷新（补 2026-07-04→07-10 缺口） | 建议尽快跑 | 需 QMT 客户端在线 |

## 7. 验收标准

- 全量 pytest（**含** `tests/infrastructure/gateway/`）全绿；
- `ruff check src/ tests/ scripts/` 0 错；
- `quant data status --check` 输出质量面板且对已知残留（新股预热 NULL）不误报；
- `check_frontend_fresh.py` 在未改前端的当前工作区退出 0；
- 每个行为变更项有对应新测试证明（TDD）；
- 本文档 §4 每项在 §8 实施记录中有「改动 + 证据」两栏。

## 8. 实施记录（2026-07-10 当日完成）

全部条目 TDD（先红灯复现缺陷，再实现，后绿灯），逐项证据如下：

| 项 | 改动 | 证据 |
|---|---|---|
| A1 | `equal_weight_sizer.py` 两条清仓分支补 `_liquidation_price`(p<=0 弃单+警告日志) 与 `_liquidation_strategy_name`(信号策略名 > "liquidation" 常量, 不再误记 sizer 类名) | `tests/domain/portfolio/test_equal_weight_sizer.py` +5 用例（含 000021.SZ=-0.32165 实证复现）；红灯 4 失败 → 绿灯 |
| A2 | `qmt_trade.py` connect/subscribe 非 0 抛 `RuntimeError`，外层不再吞异常 | `tests/infrastructure/gateway/test_qmt_trade.py` +2 用例；fixture 补默认 connect=0（旧 fixture 靠吞异常才通过，本身就是缺陷证据） |
| A3 | `database.py` 补 `PRAGMA busy_timeout=5000` | `tests/infrastructure/persistence/test_database.py` 新文件 2 用例 |
| A4 | `seed_paper_trading.py` 清生产库需 `--yes`，护栏前置到装载数据前 | 实测：无 --yes exit 2、trading.db md5 前后一致 |
| A5 | `auto_trade_app.py` `_audit_order` 与 `_poll` 撤单审计吞异常+高声日志（审计是观测面不是控制流） | `tests/application/test_auto_trade_app.py` +ExplodingAudit 用例：审计爆炸后订单仍记真实终态 DRY_RUN 而非 FAILED |
| B1 | `market_data_app.ensure_bars`：空返回仅当缺口整体在上市前/退市后（查 `instrument_windows`）才履约，否则跳过+警告留待重试；`refreshed` 语义收紧为"实际拉到数据" | `tests/application/test_market_data_app.py` +4 用例（上市窗内空返回不履约/上市前空返回照旧履约/退市后履约/无登记保守不履约） |
| B2 | `ensure_features`：`_defective_feature_symbols` 哨兵（库内首根 bar+WARMUP 之后仍 NULL ma_20 = 被喂截断 bars）→ 不入库（防 NaN 覆盖好数据）不履约 | +2 用例（600 天史深截断喂数复现事故模式/次新股合法 NULL 不误伤）；生产库实测校准：修复后全年份成熟区 NULL=0 |
| B3 | 新模块 `infrastructure/persistence/data_quality.py` + `quant data status --check`（固化哨兵零容忍/新鲜度 WARN>6 FAIL>10 可配/对齐/方差退化/跨源重复），FAIL 退出码 1 | `tests/infrastructure/persistence/test_data_quality.py` 5 用例；生产库端到端：6 PASS + 1 WARN（新鲜度滞后 7 天，本身即有效告警→决策项 Q9） |
| C1 | `strategy_runner.py` 截面路径基本面改 `latest_date_at_or_before(T-1)`；`cross_section_builder.build_cross_section` 增 `fundamental_date` 参数（缺省行为不变） | `tests/application/test_strategy_runner_lookahead.py` +2 用例（T-1 取值/缺口回退）；**行为变更**：截面策略回测数字会变（更诚实、与实盘 T-1 alias 口径一致）；全套件无回归 |
| C2 | `run_backtest.store_backtest_reports` 统一注入 `repro` 块（git_sha/git_dirty/feature_version/bars_rows/bars_max_date）与 `survivorship`（未标注记 unspecified）；F01 主跑显式标 `qmt_only(剔除退市)` | `tests/interfaces/cli/test_run_backtest_store.py` 新文件 2 用例 |
| D1 | `check_frontend_fresh.py` mtime → 源码内容哈希；`write-stamp.js` 同规格双端实现；stamp 升级 JSON；旧格式回退 mtime+升级提示 | Node/Python 双端哈希交叉验证一致（e58ec7…）；修复前实测 exit 1 误报 → 修复后 exit 0 |
| D2 | ruff 扩围 tests/scripts：268 处清零（--fix 252 + 手修 16，含 N806 真名变量/E501/E702/F841） | `ruff check src/ tests/ scripts/` → All checks passed |
| D3 | 新增 `scripts/verify_all.py` 一键验收链 | 端到端全绿：ruff 0.1s + pytest 27.8s + fresh 0.0s + data-quality 0.6s |
| D4 | gateway 测试回归标准命令：`tests/infrastructure/gateway/conftest.py` importorskip 守卫；CLAUDE.md/testing.md 同步去 --ignore | Windows 32 用例全过 exit 0；WSL 优雅跳过 exit 0 |
| D5 | 零覆盖实盘模块补测：`test_order_poller.py`（9 用例, 含超时撤单成功/被拒/无状态三分支）、`test_trading_sessions.py`（4 用例, 边界值钉死） | trade 域全绿 |
| D6 | `test_risk_chain.py`/`test_risk_event_dispatcher.py` MagicMock → 手写 Fake + 真实 Order；domain 测试 MagicMock 实际使用清零 | risk 域全绿；`grep MagicMock tests/domain/` 仅剩 3 处注释提及 |
| E1 | WSL conda 环境 `pip install -e ".[dev,api,ml]"` 补齐 duckdb/scipy/sklearn/lightgbm/optuna | WSL python 跑 portfolio 域测试全绿 |
| E2 | 文档勘校：CLAUDE.md（验收链/测试命令/--check/seed --yes）、testing.md §7、codebase-map.md interfaces/api 段（Vue3 产物入库+29 端点+任务系统）、live-trading.md（ceiling 可配 10000/cap 9000/48 单/320000/分 mode 预算） | 勘校前逐条对代码核实（含 `trading_store.py:121-140` 分 mode 隔离） |
| E3 | debt-ledger 登记：2 个已核销批次行（15 项）+ 6 个新开待清偿行（H1/M5/M6/M3/M7/C1-b）+ 2 个挂账观察行 + 数据退化侦测债结案 | `docs/rules/debt-ledger.md` |

## 9. 第二轮实施记录（决策清单获批执行, 2026-07-10 晚间）

用户批复「有问题就修, 有债务就还」后, §6 决策清单逐项落地:

| 决策项 | 结果 |
|---|---|
| Q1/H1 幂等 | ✅ PENDING 预写 → place 后换真单号 → 终态覆盖; 启动对账告警; FAILED_AFTER_SUBMIT 保守占用; API 预算镜像同步(守卫测试自动拦截脱节) |
| Q2/M5 风控接线 | ✅ 单票 30%/总仓 80% 执行期硬闸(RiskChain 复用 domain 正式策略, yaml 可配); CircuitBreaker 因无状态持久化明确不接(防假安全感), 另立专项 |
| Q3/M6 半自动绕闸 | ✅ place_confirmed_orders 强制全闸, 无报价源一律拒单, 三个调用方全部装配真实报价源 |
| Q4/M3 断线防护 | 🔧 保守版: GhqTraderCallback 断线置不可用+拒单+告警; 不自动重连(待实环境); 回报回填 M4 另立 |
| Q5/DD-6 ST 数据源 | ⏸ 未动(需 akshare 全市场名称历史回填, 长时网络作业, 唯一剩余 P0 大项) |
| Q6 含退市宇宙 | ✅ F01 默认切 qmt+akshare 并重跑全窗口新基线三档(20/10/30), 含 repro 块入库; 新旧口径不可直接对比 |
| Q7 死代码 | ✅ 51 文件/3141 行(资金分配树/EventStore/UnitOfWork/双web死栈/死VO×6/死接口×2/空包/Mock桩); pool 子域与 anomaly 链经引用复核判活保留; REVIVAL.md §五 记录复活坐标 |
| Q8 交易日历 | ✅ TradingCalendar(bars 推导, 零手工维护), 时段闸+调度器贯通 |
| Q9 数据刷新 | ✅ QMT 在线补齐 07-04→07-10(bars +25,966 行), 门禁七项全 PASS 滞后 0 天 |

另: 2026-05-31 批次二次抽样 3 项全部可关闭(DailySettlement 已有 10 测试/frozen 可变默认值 AST 扫描 0 处/双通知接口已 adapter 收敛); user-guide.html 加过时警告横幅; WSL 环境补 pyarrow。

**环境事件**: 实施中途 WSL interop 失效(Windows exe 无法新起, 需用户 `wsl --shutdown` 恢复), 全部工作切换 WSL Python 完成——E1 补装依赖的韧性收益当日兑现。gateway 测试(M3 新增 3 用例)暂只在 WSL skip 通道验证语法, **待 interop 恢复后用 `$WIN_PYTHON scripts/verify_all.py` 复核一次**。

## 10. 第三轮实施记录（架构张力 DMAIC, 2026-07-11）

用户对架构分析结论批复「还是按6sigma去排查改进」, 六项张力度量后逐项处置:

| 项 | Measure(量化痛感) | 处置 |
|---|---|---|
| T6 熔断持久化 | 熔断状态=进程态而保护对象=账户, --once 每次归零(假安全感, M5 遗留) | ✅ `breaker_states` 表(按 mode)+`restore_state`+`_sync_breaker`; TRIGGERED 禁全部→COOLDOWN 仅卖→恢复; 4 集成用例含跨进程恢复; fail-open 裁定(熔断故障不得演变为交易瘫痪) |
| T1 双 live 入口 | 275+189 行两份, M6 堵洞双倍改动(维护税实付) | ✅ rich 审核台迁 `--review-mode rich` 后退役 live_trade.py |
| T2 元数据收敛 | 5212 个散落 CSV + 两套履约账本(_fetch_meta.json vs fetch_meta 表) | ✅ CSV 缓存默认退役(显式 csv_cache=True 保留轻量通道), 文件归档 _legacy_csv; 顺带揪出一个暗依赖真实 data/ 的假绿测试 |
| T5 双实现 | 标量三件套 319 行 | 🔍 裁定**保留**——`--no-store` 显式回退通道是活的; 真死支是 cli/factor_test.py 死入口(276 行), 已删 |
| T4 分层纯度 | application 顶层 infra import: factor_test_app 5 类 + auto_trade_app 1 类 | ✅ factor_test 引擎(纯计算)归位 domain(Spec2 同款)、Mock 延迟导入、TradingStore 降 TYPE_CHECKING——顶层违规清零 |
| T3 上帝仓储 | 600+行/7表, 但新增已外置泄洪 | 🔍 裁定**不拆**——内聚源自单连接单写锁真实约束; 待 C1-b 专项顺势拆 |

Control 固化: `tests/architecture/test_layer_purity.py`(AST 三红线守卫, 纯度从人肉 grep 变自动门禁) + `scripts/run_gateway_tests_wsl.py`(WSL 假 SDK 驱动, 38 个 gateway 用例双环境可回归)。

方法论注: 六项里两项裁定"不动"并记录理由——6σ 的 Improve 以量化痛感为准, 不为改而改。

## 11. 第四轮：演进点识别（从消缺转向能力演进, 2026-07-11）

前三轮消缺后系统宣告受控, 用户指令转向「识别演进点」。本轮 Define 不再对准产品缺陷,
而是对准**过程能力**——通往北极星的证据流水线本身。

**Define**: 北极星已成文于 README: 数据诚实→因子判决→纸面前向→小资金→全自动。
新增 CTQ5=证据积累过程的受控性; CTQ2(研究诚实)延伸为"上钱判断的诚实性"。

**Measure（阶梯位置, 2026-07-11 实测）**:

| 阶梯 | 状态 | 证据 |
|---|---|---|
| 数据/引擎诚实 | ✅ | 1350 测试绿+数据门禁 PASS; 余 DD-6/C1-b 两笔诚实债 |
| 因子判决 | ✅ | 0626 已宣告纯因子挖尽(全为防御 beta); 唯一 OOS 过闸候选 = F01+中证1000趋势闸(OOS Sharpe 1.69→1.73, 回撤减半) |
| 纸面前向(影子盘) | 🔴 失控 | 计划 07-07 起每周二采样、攒 4-8 周开真单 Spec; 实际 trading.db 仅 06-30 与 07-04(周六冒烟)两个 cycle——**07-07 首个正式采样脱靶**, 纸面净值周度入库停在 SHADOW-PAPER-20260704 |
| 小资金实盘 | ⬜ | 真单前置三件套已备(0704: mode 隔离/实时 ST 闸/纸面净值); Spec 本体明文"待样本攒够另立" |
| 全自动 | ⬜ | 调度纯手动(QMT 需人工拉起), 无提醒/无补采/无告警 |

**Analyze**: 瓶颈已从代码质量移到过程能力——真单开闸唯一依赖「每周一次、事后不可补采
的采样事件」(live 快照错过即永失), 该过程 100% 人肉、零控制手段, 首采即脱靶(实测脱靶率
1/1)。影子等待期是日历时间约束(4-8 周躲不掉), 工程力气的正确去向: ① 把采样过程本身做成
受控过程; ② 用等待期清偿直接影响"该不该上钱"判断的诚实债——DD-6 尤甚: F01 恰是小市值
策略, ST 股天然聚集在其选股域边缘, 回测按 ±10% 处理 ST 涨跌停会系统性低估其尾部风险。

**演进点清单（本轮识别交付物, 优先级降序）**:

| # | 演进点 | 处置 |
|---|---|---|
| E1 | 影子盘过程受控化: 周二编排器+QMT 在线看护+错采告警+过程仪表 `quant shadow status` | **本轮实施** → `docs/feat/0711-shadow-control/` |
| E2 | 过闸判据量化固化(何谓"样本攒够", 机器可判) | 同上, tollgate 进 `shadow status --gate` |
| E3 | DD-6 ST 诚实债: 名称历史数据源+全市场回填+接 10+1 构造点+F01 重验 | ✅✅ 2026-07-12 **全口径核销**(`docs/feat/0711-st-honesty/` §六): 深市官方 1387 + 沪市 bak_basic 469 区间, 交叉验证 98.4%≤2td PASS; 裸 F01 乐观偏差全链挤干 210.8%→159.8%(−51pp); **G7 终局 PASS**(OOS ON 回撤 11.27%<基准、Sharpe 1.89、闸增益不蒸发)——影子盘继续攒样本, 数据侧再无上钱障碍 |
| E4 | M4 成交回报回填+自动重连 | 真单前置; 周二 QMT 在线窗口顺带联测 |
| E5 | 真单 Spec 本体: 首单 runbook/cancel_order 实盘验证/旧持仓过渡清仓方案/纸面 vs 实盘漂移分析 | tollgate PASS 后开 |
| E6 | C1-b 因子面板 as-of 口径(顺势拆 market_data_store) | 研究诚实, 排 E3 之后 |
| E7 | 驾驶舱影子盘证据可视化(采样日历/diff 历史/画像曲线) | 供前端线接力, 本轮不碰 frontend/ |
| E8 | 全自动无人值守(QMT 自动拉起议题) | 阶梯终态, 真单稳定后再议 |
| E9 | 研究长线: ML 因子挖掘管道重启/新因子域 | 🔧 2026-07-12 首铲完成(docs/feat/0712-ts-factor-mining/): tushare 新域 6 假设×双十年窗 12 判决入库, 晋升 0, R04 低自由流通换手进观察名单(R04b/c 预注册); 资金流域判 regime 依赖不可用 |

**用户裁定留痕(2026-07-11)**: 主攻方向=「通往小资金实盘」(E1→E5 主线); 实现路线=方案甲
·半自动看护——人只负责开 QMT, 其余机器编排并对人那一步包提醒与错采告警。备选路线否决
理由: 乙(全自动含 QMT 自动登录)=凭据安全风险+计划任务会话隔离脆+dry-run 阶段收益低;
丙(纯手动+日历提醒)=已实测脱靶的现状微调, 控制力不足。此后用户全权委托("按你推荐的来搞,
不要问我"), 决策自裁留痕。
