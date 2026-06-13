# F01 可投性回测 — 设计文档

| 项 | 值 |
|---|---|
| **状态** | 已定稿（全权委托模式：决策以文档留痕，事后补审） |
| **创建日期** | 2026-06-13 |
| **文档类型** | 需求 + 技术设计 / SDD Spec |
| **前置** | 长多重判（`0611-longonly-rejudge`，找到首个过闸 edge F01 小市值，OOS Top 超额 +16.52%，但读作乐观上界）；回测 DuckDB 数据源（`0611-backtest-duckdb`，`DuckDBHistoryDataFetcher` 已就绪）；截面策略 + 截面回测 runner（`MicroValueStrategy` / `CrossSectionalStrategyRunner` 已就绪） |
| **配套** | 同目录 `*-plan.md`（实施计划）、`*-report.md`（产出报告） |

---

## 一、背景与现状盘点

主线漏斗在长多重判后**第一次有了过闸 edge**：F01 小市值，OOS Top 超额 +16.52%、集中增强、跨持有期稳健。但重判报告 §五/§六 已诚实校准：这是**三重乐观偏置叠加的合成上界**（小盘双暴露 / 基准 costless 不对称 / excess_ir 自相关高估），本质是 size premium。重判报告 §六明确写下主线下一岔口的首选：

> **F01 可投性回测（首选，graduation gate）**：把 Top-N（最小市值且可投的前 30–50 只，剔 ST/停牌/次新）喂 `BacktestAppService + MockTradeGateway`（真成本/滑点/流动性 10%/T+1），看 size edge 在 **¥146k 可建仓、对称成本、真实指数基准** 下还剩多少。这是"上界 → 可执行收益"的收敛，也是 live 前提。

**找到 F01 之后的两天，全部精力投在了驾驶舱 UI 上，这个毕业闸没有推进。** 本 Spec 把它做掉。

### 现状核查（开工前对回测链路的全面盘点）

| 组件 | 现状 | 结论 |
|---|---|---|
| **策略** | `MicroValueStrategy`（截面）已实现：过滤链 ST→次新→仙股→停牌→质量，按 `market_cap` 升序取最小 `top_n`。**这就是 F01 可投策略**，且自带稳健化叠层（1/4 月空仓、错峰周二调仓、质量过滤） | ✅ 策略不缺，无需新建 |
| **回测撮合** | `BacktestAppService` + `CrossSectionalStrategyRunner` + `MockTradeGateway`：A 股真实成本（佣金双向万2.5最低5 / 印花税卖千0.5 / 过户费 / 滑点±0.1% / 流动性10%）、T+1、`EqualWeightSizer` 等权再平衡、`CrossSectionBuilder` 逐日建截面（T-1 因子、T 开盘执行，无前视） | ✅ 撮合机器齐备 |
| **基本面/宇宙装配（回测侧）** | **三个回测入口各写一份截面装配逻辑，且口径分叉** | ❌ **本 Spec 的最大缺口** |
| **离线数据** | `market.duckdb`：bars 621万行（5207 只，仅个股，**无指数**）、fundamental_snapshots 654万行（列与 `FundamentalSnapshot` VO 1:1，span 2020-06-15→2026-06-11）、instruments 5207 只 | ✅ 个股/基本面全；⚠️ **无指数 bars** |

### 三个回测入口的口径分叉（核心待修）

| 入口 | 宇宙上限 | 基本面/宇宙来源 | 谁在用 |
|---|---|---|---|
| `run_backtest.py main()` | ✅ 已解除（全市场） | QMT 在线 | 漏斗/手册规范命令 |
| `commands/backtest.py`（`quant backtest`） | ❌ **随机 500 截断** | QMT 在线 | CLI |
| `compare_strategies.py`（**驾驶舱交互回测**经 `job_commands.build_backtest_argv` 走此入口） | ❌ **随机 500 截断** | QMT 在线 | 对比 / Web |

**两个问题：**

1. **正确性陷阱（已发布功能里）：** 对 micro-cap 这种"取全市场最小 N 只"的策略，把宇宙随机截到 500 只 ⇒ "随机 500 的最小 9 只" ≠ "全市场最小 9 只" ⇒ 结果**静默错误**。偏偏驾驶舱新做的"网页内跑回测"和 `quant compare` 都走截断入口。
2. **无法离线复现：** 三入口都靠 QMT 在线枚举宇宙（`get_stock_list_in_sector('沪深A股')`）+ 拉基本面，**没有 DuckDB 基本面读取路径** —— 尽管 654 万行基本面已在库。factor-test 能全离线跑全市场（经 `MarketDataAppService.prepare()` 读 store），回测却不能。⇒ 回测必须 Windows+QMT 在线、首次全市场逐只补历史很慢、且不可复现。

---

## 二、目标与非目标

### 目标（Requirements）

- **R1 离线全市场回测能力**：新增 `DuckDBFundamentalFetcher`（`QmtFundamentalFetcher` 的离线对偶），让 `history_fetcher: DuckDBHistoryDataFetcher` 配置下，**基本面与宇宙也从 `market.duckdb` 取**，QMT 不在线也能跑全 ~5000 只 A 股截面回测、可复现。
- **R2 统一回测入口 + 消除截断陷阱**：抽一个共享的"截面装配" helper，三入口统一调用；**去掉随机 500 截断**（或改为显式 `--max-universe` 选项，默认无上限）。修掉驾驶舱/对比给出静默错误 micro-cap 结论的陷阱。
- **R3 重判口径对齐**：刷新 `resources/backtest.yaml` 到重判窗口（2021-01-01→2026-06-11，split 2024-06-30）、`MicroValueStrategy`、可投 `top_n`、真实对称成本。
- **R4 可投性产出**：跑 IS/OOS + `top_n` 敏感性，结果入库 `backtest_runs`（驾驶舱回测页可查），并产出报告：真实 CAGR/最大回撤/Sharpe/胜率/换手/成本拖累 vs 基准 vs 因子检验 +16.5% OOS 上界 → **size edge 在 ¥146k 真实约束下还剩多少 → 是否过毕业闸**。
- **R5 工程留痕**：设计（本文）+ 计划 + 报告；逐逻辑单元 commit 直推 main。

### 非目标（Non-Goals，白纸黑字不做）

- ❌ **不新建策略**：`MicroValueStrategy` 已是 F01 可投策略，直接用。
- ❌ **不动 factor-test 引擎/重判判决**：本 Spec 只消费重判结论，不改判决链路。
- ❌ **不碰实盘**：可投性确认后才进 D1/D4/D8 实盘硬化 + 小资金 live（P1，下一 Spec）。
- ❌ **不改驾驶舱 UI**（除验证修正后的回测结果能正确显示）。
- ❌ **不删 QMT 基本面 fetcher**：QMT 路径保留可用，仅去截断。
- ❌ **不引入新基准框架**：基准在报告 harness 内计算（等权投资域），不动核心 evaluator。

---

## 三、关键设计决策（Decision Records）

### DD-1 · 离线基本面走新 `DuckDBFundamentalFetcher`，不复用 `MarketDataAppService.prepare()`

factor-test 的离线能力来自 `MarketDataAppService.prepare()` 读 store，但其产出是 `snapshots_by_date` 向量结构，**与回测的事件循环架构（bars 装入 `MockMarketGateway` + `FundamentalRegistry` 逐日建截面）不兼容**，无法直接搬。最干净的方案是镜像已有的 `DuckDBHistoryDataFetcher`：新增 `DuckDBFundamentalFetcher` 实现 `IFundamentalFetcher.fetch_by_range`，`SELECT ... FROM fundamental_snapshots WHERE date BETWEEN ? AND ?`（可选 `symbols` 过滤）→ `FundamentalSnapshot`。DuckDB 列与 VO **字段名 1:1**（symbol/date/name/list_date/market_cap/roe_ttm/ocf_ttm/pe_ratio/pb_ratio/earnings_growth/revenue_growth），映射零转换。持 `read_only` 连接（与写进程互斥：回测期间勿跑刷数）。

> 注：`IFundamentalFetcher.fetch_by_range(start, end)` 协议签名无 `symbols`，但 `QmtFundamentalFetcher` 已用 `symbols=None` 扩展签名（鸭子类型）。`DuckDBFundamentalFetcher` 同样加 `symbols: list[str] | None = None` 可选参，与协议兼容。

### DD-2 · 抽 `build_backtest_cross_section` 共享 helper，三入口统一

新增 `src/interfaces/cli/_backtest_wiring.py`（与 `_data_wiring.py` 同级、同思路）：

```
build_backtest_cross_section(
    history_fetcher_type, start_date, end_date, *,
    tushare_token=None, config_symbols, db_path="data/market.duckdb",
    max_universe=None,
) -> (fundamental_registry: FundamentalRegistry, stock_universe: list[str])
```

按 `history_fetcher_type` 选源：
- `DuckDBHistoryDataFetcher` → `DuckDBFundamentalFetcher` 装载基本面 + 宇宙取 `instruments` 全表（5207 只，离线、无上限）。
- `TushareHistoryDataFetcher` → Tushare 基本面（保持原逻辑）。
- 其它（QMT）→ `QmtFundamentalFetcher` + `get_stock_list_in_sector`（保持原逻辑，**去掉随机 500 截断**；如需限速改显式 `max_universe`）。

`run_backtest.py` / `commands/backtest.py` / `compare_strategies.py` 三处 cross_section 装配块**删除各自副本，统一调用此 helper**。一处修复，三入口同时正确，消除漂移。

### DD-3 · 基准 = 报告 harness 内计算的"等权投资域"，不依赖指数 bars

DuckDB **无指数 bars**（000300/000852/932000 均 0 行）。为保证**全离线 + 可复现 + 直接对照重判**，基准在报告 harness 内从同一份 DuckDB bars 计算：每个交易日**投资域（覆盖池）等权日收益**复利成净值序列 —— 与重判的"等权因子覆盖池基准"同口径，使可投性收益能与重判 +16.5% **诚实并排**（同为对等权基准的超额）。

中证1000（000852.SH）作为**可选次级基准**：若能 best-effort 经 QMT 把指数 bars 入库则一并对照（更贴近"散户本可买 ETF"口径），不可得则报告显式标注"指数基准缺失，仅等权投资域基准"。**不阻塞主结论。**

### DD-4 · 系统风控闸（中证1000 趋势）离线失效——显式留痕，不静默

`CrossSectionalStrategyRunner` 对所有截面策略套 `SystemRiskGate`（中证1000 MA20 趋势，`pass_buy` 为假则滤掉买入）。离线无指数 bars ⇒ `set_index_data` 不被调用 ⇒ 闸大概率"开放"（等于关闭趋势过滤）。这会**改变 `MicroValueStrategy` 行为**（少了趋势择时）。处置：① 回测启动时检测指数数据缺失并**在日志/报告显著标注**；② 优先 best-effort 把中证1000 bars 入库使闸离线生效；③ 不可得则在"闸失效"前提下跑，报告明确写"本轮趋势闸 inert"。**绝不静默吞掉一道防线**（沿用闭环夜审 #4/#11 的红线）。

### DD-5 · 主跑 `MicroValueStrategy`，对照口径写清"非 like-for-like"

重判测的是**裸因子** `0 - log(market_cap)` 分位（factor-test 引擎，无叠层、基准 costless），而 `MicroValueStrategy` = size + 稳健化叠层（日历熔断/错峰/质量/趋势闸）+ 对称真实成本。两者**不是 like-for-like**：本回测产出是"**可部署策略的真实可执行收益**"，重判 +16.5% 是"**裸因子的乐观上界**"。报告并排时必须写清这一区别 —— 我们要的答案是"可投性"（能不能部署），不是"复现 +16.5%"。

> 可选增量（YAGNI，计划列为 stretch）：若 `factors/` 已有市值因子，加一个 `MultiFactorStrategy([size],[1.0],top_n)` 的"裸 size"配置作更干净的桥接；不易则跳过并记录。

### DD-6 · 全程 `$WIN_PYTHON` 执行，离线全市场

WSL 仅 `/usr/bin/python3`（无项目依赖）；规范解释器是 Windows conda `python.exe`，可从 WSL 直接调用并读 `data/market.duckdb`（相对路径解析到 `C:\Codes\...`）。测试与离线回测**均走 `$WIN_PYTHON`**。离线路径免去 QMT 逐只补历史（`run_backtest` 注释里警告的慢点），全市场 × ~1316 日内存事件循环虽重但可行（`BacktestProgress` 有进度）。

---

## 四、架构与数据流

```
resources/backtest.yaml (DuckDB 源 + 重判窗口 + MicroValue + top_n + 真实成本)
        │
        ▼
build_backtest_cross_section(helper, DD-2)
   ├── DuckDBFundamentalFetcher.fetch_by_range → FundamentalRegistry   (DD-1)
   └── instruments 全表 → stock_universe (全市场, 无截断)               (DD-2)
        │
        ▼
BacktestAppService(history=DuckDBHistoryDataFetcher, fundamental_registry, ...)
   prepare_data(universe+index, ...)  → bars 装入 MockMarketGateway (指数走 QMT 回退或缺失)
   run_backtest:
     每个交易日 → CrossSectionalStrategyRunner.evaluate
       CrossSectionBuilder 逐日建截面(T-1 因子) → MicroValueStrategy 选最小 top_n
       SystemRiskGate(中证1000, 离线 inert — DD-4) → EqualWeightSizer 等权
       MockTradeGateway 撮合(真实成本/滑点/流动性10%/T+1) → DailySettlement
        │
        ▼
BacktestReport → store_backtest_reports → backtest_runs (驾驶舱回测页)
        │
        ▼
报告 harness: 读 equity curve + 从 DuckDB 算等权投资域基准(DD-3)
   → CAGR/MaxDD/Sharpe/胜率/换手/成本拖累 vs 基准 vs 重判 +16.5% 上界
   → 毕业闸结论
```

### 组件（隔离单元）

| 单元 | 职责 | 依赖 | 可独立测试 |
|---|---|---|---|
| `DuckDBFundamentalFetcher` | DuckDB `fundamental_snapshots` → `FundamentalSnapshot` 列表 | duckdb, FundamentalSnapshot VO | ✅ tmp duckdb 注入 |
| `build_backtest_cross_section` | 按源选 fetcher + 解析全市场宇宙，组装 `FundamentalRegistry` | 三 fetcher + instruments | ✅ 注入假 store/fetcher |
| 报告 harness（脚本） | 算等权基准 + 出可投性指标对照 | duckdb bars + backtest_runs | ✅ 小样本 |

---

## 五、测试策略（TDD）

- **`DuckDBFundamentalFetcher`** → 测试落 **`tests/infrastructure/persistence/test_duckdb_fundamental_fetcher.py`**（**刻意不放镜像目录 `tests/infrastructure/gateway/`**：该目录因 QMT 文件导入失败被默认门 `--ignore`，而本 fetcher 纯 DuckDB 无 QMT，须放在门会跑到的位置才被覆盖；文件头注释说明此例外）：tmp duckdb 建表插几行 → 区间过滤、`symbols` 过滤、列映射正确、缺表/空结果回退、`read_only`。
- **`build_backtest_cross_section`**：DuckDB 源 → 返回全市场宇宙（无 500 截断，断言 > 500 时不被裁）+ 用 `DuckDBFundamentalFetcher`；Tushare/QMT 源分支装配正确；`max_universe` 显式生效。
- **回归**：三入口改为调用 helper 后，现有回测行为不变（`test_basic_backtest_run_with_mock_data` 等绿）。
- **全量门**：`$WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/` 全绿 + `ruff check src/` 干净，才跑实测。

---

## 六、运行矩阵（实测）

| 跑 | 策略 | 窗口 | top_n | 目的 |
|---|---|---|---|---|
| 主 | MicroValueStrategy | 2021-01-01→2026-06-11, split 2024-06-30 | 20 | 可投性 headline |
| 敏感性 | MicroValueStrategy | 同 | 10 / 30 | 集中度稳健性（呼应重判 q5/q10） |
| 可选 stretch | 裸 size（若 factors 有市值因子） | 同 | 20 | 更干净桥接 +16.5% |

¥146k 初始资金（对齐真实账户）。每跑入库 `backtest_runs`。

---

## 七、验收标准

1. 全量测试绿 + ruff 干净（新增单元有测试且在可运行目录）。
2. `history_fetcher: DuckDBHistoryDataFetcher` 配置下，**QMT 不在线**也能跑出全市场（宇宙 > 500，断言未被截断）micro-value 回测。
3. 三入口（run_backtest / quant backtest / compare_strategies）统一走 helper，随机 500 截断陷阱消除（驾驶舱交互回测对 micro-value 不再静默错误）。
4. 产出 `*-report.md`：含真实可执行指标 + vs 等权投资域基准 + vs 重判 +16.5% 上界的诚实对照 + 毕业闸结论（过/不过/有条件过）。
5. 结果入 `backtest_runs`，驾驶舱回测页可见。

---

## 八、风险与偏置（诚实校准）

- **指数缺失 → 趋势闸 inert（DD-4）**：MicroValue 离线少一道趋势择时，结果偏离"完整策略"。缓解：best-effort 入库中证1000；否则报告显式标注。
- **非 like-for-like（DD-5）**：回测含叠层+真实成本，重判是裸因子上界，不可机械相减。报告写清。
- **小微盘流动性/冲击成本**：`MockTradeGateway` 有流动性 10% + 滑点 0.1%，但极小市值真实冲击可能更高；¥146k/top_n 仓位小、影响有限，但报告需提示"真实小微盘成交可能更差"。
- **生存者偏差**：instruments 仅 5207 只活跃（delist_date 全 NULL），退市股可能未入库 → 宇宙偏向幸存者，**高估** size 收益。报告列为已知偏置。
- **基本面覆盖起点 2020-06-15**：早于回测起点 2021-01-01，warmup 充足；但财报公告对齐（ann_date）的稀疏性可能使早期截面偏薄。

---

## 九、登记债（不阻塞主结论）

| 项 | 内容 |
|---|---|
| B1 | 退市股未入 instruments/bars → 生存者偏差；后续可补退市标的历史消除 |
| B2 | 指数 bars 不在 `data refresh` 覆盖内 → 离线基准/风控闸缺指数；后续把指数纳入刷数管道 |
| B3 | `MicroValueStrategy` 的稳健化叠层（日历/错峰/质量/趋势闸）未做消融，无法分离"size 本体"与"叠层增益"；可作下一轮 §六.2 稳健化专题 |
