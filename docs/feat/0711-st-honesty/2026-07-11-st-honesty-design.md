# ST 诚实债清偿（演进点 E3 / 台账 DD-6）设计

| 项 | 值 |
|---|---|
| **状态** | 已定稿（用户全权委托模式，方案取舍自裁留痕） |
| **创建日期** | 2026-07-11 |
| **动机** | 台账 DD-6（P0·资金正确性）：回测对 ST 股按 ±10% 撮合（真实 ±5%），系统性低估 F01 这类小市值策略的尾部风险；选股期 ST 过滤用"当前名称"均匀回填的历史（摘帽股在其 ST 期被当普通股买入）。产出即影子盘过闸判据 **G7**：修复后 F01 gate 重验仍 PASS 才有资格上真钱 |
| **前置侦察（2026-07-11 实测）** | ① 深交所官方 `stock_info_sz_change_name(symbol="简称变更")`：**7439 行带日期简称变更，1994→2026-07-09，一次批量 0.3s，2605 行涉 ST** ✅；② 新浪逐股曾用名**无日期**（源页面即无）✗；③ tushare `namechange` 覆盖沪深但 **TUSHARE_TOKEN 未配置** ⏸；④ cninfo 概况"曾用简称"无日期 ✗；⑤ cninfo 公告检索 `stock_zh_a_disclosure_report_cninfo(keyword="风险警示")`：带日期、覆盖沪深，2025Q1 实测 303 条（沪 135）✅ 但标题混"进展/提示/继续/可能"需分类 |

---

## 一、目标与范围

给回测引擎接上**时点正确的 ST 状态**，三个消费点一次修齐：

1. **撮合幅度**（DD-6 主体）：`MockTradeGateway` 的 10 处构造点注入 `StockStatusRegistry`，ST/*ST 日按 ±5% 判定能否成交；
2. **风控策略**：`LimitUpBreakPolicy` 的涨停价计算接入 is_st（现恒按普通幅度）；
3. **选股过滤**（同族债）：F01 的 `filter_st` 吃到时点正确的 ST 标记（修正"当前名称回填历史"的误标）。

**范围**：主板 60/000/001（F01 宇宙口径），窗口 2020-01-01 至今（bars 窗口）；ST/*ST/SST/S*ST 风险警示状态。
**非目标**：退市整理期 ±10%（B1 的 delist_date 已管退市；"XX退"名称不属 ST 语义）；停牌数据（`is_suspended` 维持现状）；北交所/创业板/科创板（不在 F01 宇宙，且其 ST 幅度规则不同——20%/30% 板块 ST 不改幅度只改标识，留待扩板时处理）；实盘链路（实时 ST 闸已有，0704 DD-3）。

## 二、方案取舍（委托模式自裁）

| 案 | 内容 | 裁定 |
|---|---|---|
| **A（采用）** | 深市=官方简称变更流（权威带日期）；沪市=巨潮"实施/撤销风险警示"公告分类推断；**用深市双源交叉验证公告法的日期误差**，达标才准入 | 唯一不依赖外部凭据且两所全覆盖的路线；自带方法校准 |
| B | tushare `namechange` 一个接口全解决 | **无 token 阻塞**。作为升级路径保留：设计的表结构与 source 字段兼容 tushare 灌入，token 到位可无痛替换沪市管道 |
| C | 只修深市，沪市留债 | 沪市主板 1781 只 > 深市主板 572 只，修一半等于没修，否决 |

## 三、数据设计

### 3.1 新表 `st_status_periods`（market.duckdb）

```sql
CREATE TABLE IF NOT EXISTS st_status_periods (
    symbol      VARCHAR NOT NULL,   -- 600186.SH
    start_date  DATE    NOT NULL,   -- 戴帽生效日(含)
    end_date    DATE,               -- 摘帽生效日(不含); NULL=至今仍 ST
    label       VARCHAR NOT NULL,   -- 'ST' | '*ST'(含 SST/S*ST 归一到二类)
    source      VARCHAR NOT NULL,   -- 'szse_name_change' | 'cninfo_notice' | 'tushare'(预留)
    evidence    VARCHAR,            -- 溯源: 变更行原文 / 公告标题+链接
    fetched_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (symbol, start_date, source)
);
```

区间模型（源数据即事件流，区间是自然形态）；`is_st(symbol, d)` = 存在区间 `start_date <= d < end_date(或 NULL)`。

### 3.2 深市管道（`szse_name_change`）

批量拉简称变更 → 按 symbol 时间线扫描：`变更后简称` 命中 ST 前缀（`ST/*ST/SST/S*ST`，与 `filter_st` 同一前缀口径，抽为共享常量）即"进入"，下一次变更失去前缀即"退出"；窗口起点在册状态由 ≤ 起点的最后一次变更决定；首条记录的 `变更前简称` 视为上市初始名（1994 年前无数据，接受）。

### 3.3 沪市管道（`cninfo_notice`）

1. 按季度窗口检索 `keyword="风险警示"`（实测每季 ~300 条，2020→今 ~26 个窗口）；
2. 只留代码 `60` 开头；标题分类为**决定性事件**：含"实施退市风险警示"→ 进入 *ST；含"实施其他风险警示"→ 进入 ST；含"撤销退市风险警示"/"撤销其他风险警示"→ 退出。**剔除**含"进展/提示/可能/继续/期间/相关事项的进展"的标题；同一 symbol 同类事件 5 个交易日内去重取首条；
3. 生效日 = 公告日的**次一交易日**（交易所规则：实施/撤销于公告后首个交易日生效，常伴停牌一日）；
4. "撤销退市风险警示同时实施其他风险警示"（*ST→ST 降档）标题两个模式都命中：解析为前区间闭合 + 新区间开启。

### 3.4 交叉验证（准入门，先于一切消费）

对**深市股票**同时跑两条管道，逐事件对齐：`|公告法生效日 − 官方变更日|` 的分布进验收报告。**准入标准：≥90% 事件误差 ≤2 个交易日，且无方向性系统偏差 >1 天**。不达标则沪市管道不入库，设计回炉（届时改从公告正文抽"自 X 年 X 月 X 日起"）。F01 周频调仓下 ≤2 天的边界模糊是可接受量级——对比现状是"整段 ST 期完全不知道"。

**终态对照**（实施中勘误）：开区间 symbol 对照 `instruments.name` 的差异经实测判明为 **instruments 名称滞后**（2026-04 戴帽潮已入交易所变更流、instruments 快照未跟上；退市时在册 ST 豁免），非推导错误——报告作"名称滞后观察"清单留档，不阻断。

**交叉验证实测结论（2026-07-11）**：官方事件 1145、对齐 597、≤2 交易日仅 255、均值带符号 **+81.5 交易日** → **FAIL，沪市公告法区间不入库**（回炉条款生效）。标题级分类不足以恢复生效日；升级路径：① 用户提供 `TUSHARE_TOKEN` 后以 `pro.namechange` 一次覆盖沪深（表结构 source 字段已预留 'tushare'）；② 公告正文抽"自 X 年 X 月 X 日起"（量级另立）。当前入库=深市官方 1387 区间——F01 宇宙中深市主板(000/001)已诚实、沪市主板(60)维持原状且**无回退**（部分覆盖防线：registry 只修正在册股票名称，见 §4.4 勘误）。

### 3.5 回填脚本 `scripts/backfill_st_status.py`

WSL 可跑（纯 HTTP）。幂等：全删全建（数据量 ~千行级，无需增量）；区间**按源数据全史入库不裁剪**（evidence 完整），窗口裁剪发生在 loader 稠密展开时；`--check-only` 只跑交叉验证不入库；`--report` 输出核对报告（区间数/涉及 symbol 数/交叉验证误差分布/SUSPECT 清单）到 `data/st_backfill_report.json`。

## 四、注入与接线

### 4.1 Registry 装载（infrastructure）

`MarketDataStore.load_st_periods(symbols?) -> list[StPeriod]` + `src/infrastructure/persistence/status_registry_loader.py`：`build_status_registry(store, *, start, end) -> StockStatusRegistry` —— 区间在 `trading_dates()` 上**稠密展开**成逐日 `StockStatus(is_st=, is_star_st=)`（registry 是精确日期索引，domain 不动；窗口 ~1350 交易日 × 在册 ST 股 ~200 → ~20 万条内存条目，可接受）。`is_tradable()` 的 `*ST→False` 语义无消费方（Mock 只用 `get_status`），维持现状不碰。

### 4.2 撮合侧（10 处构造点）

`MockTradeGateway(..., stock_status_registry=registry)`。构造点统一改：`run_backtest.py` / `commands/backtest.py` / `compare_strategies.py` / 7 个 scripts——各处调用同一个 loader（4.1），不复制装载逻辑。回测窗口取各处既有的 start/end。

### 4.3 风控侧（+1 处）

`LimitUpBreakPolicy` 在 domain，不能碰仓储 → 构造注入纯函数：`LimitUpBreakPolicy(is_st_fn: Callable[[str, datetime], bool] | None = None)`，`evaluate_positions` 内 `ratio = get_price_limit_ratio(pos.ticker, is_st=self._is_st_fn(pos.ticker, bar.timestamp) if self._is_st_fn else False)`。装配处（risk chain 构建）从 registry 包一个 lambda 传入。默认 None 保持现行为（实盘路径零影响——实盘的 LimitUpBreak 本就依赖 prev_close，K9 已单独处理）。

### 4.4 选股侧

不动 domain 的 `filter_st`（它只认 `snapshot.name` 前缀，且是与实盘 ST 闸同口径的单一事实源）。修在**离线/回测的数据装配路径**（DuckDB fundamentals → StockSnapshot 的组装处）：增加可选 `status_registry`，按 as-of 日修正名称前缀。**实盘路径零改动**——live 的名称来自 QMT 实时，当前名称对当前时点本就正确（且 0704 已有实时 ST 闸）。

**部分覆盖防线（实施中勘误，新增 `StockStatusRegistry.has_symbol`）**：名称双向修正只作用于**在册股票**；registry 不认识的股票（如沪市未回填）保持原名——否则"不认识→判非 ST→剥前缀"会把现状 ST 股错误放进选股池，比不修更糟——registry 判 ST 而名称无前缀 → 名称前加 `"ST"`；registry 判非 ST 而名称带前缀 → 去前缀。名称仅作 ST 布尔语义载体（F01 不消费名称本身），深市有真实历史名但统一走前缀修正，两所口径一致。

## 五、G7 重验（验收的核心）

1. 回填 + 交叉验证达标入库；
2. `$WIN_PYTHON scripts/run_f01_investability.py` 同参重跑（WSL DuckDB 离线路径已验证可跑），与 2026-07-10 基线（repro 块在库）对照：total_return / max_drawdown / sharpe 逐项列 Δ；
3. **gate 重验**：重跑 0626 阶段 0 的 gate 口径（`mainboard_f01_gate` 脚本，OOS Sharpe/回撤判据），结论写入台账 G7 行：PASS → 影子盘继续攒样本；FAIL → **不上真钱，回研究阶段**（这正是把 E3 排进等待期的意义——宁可现在难看，不可实盘后难看）；
4. 报告落 `docs/feat/0711-st-honesty/2026-07-11-st-honesty-report.md`：区间统计/交叉验证分布/SUSPECT 清单/F01 Δ/gate 结论。

## 六、测试策略（TDD）

- 深市区间推导：进入/退出/降档（*ST→ST）/窗口起点在册/上市初始名 ST——纯函数表驱动；
- 沪市标题分类：四类决定性标题/五类排除词/去重/降档双命中/次交易日生效——表驱动；
- 交叉验证器：构造已知偏差样本验证误差统计与准入判定；
- loader 稠密展开：区间→逐日、开区间（NULL end）、非交易日不展开；
- 接线回归：MockTradeGateway 带 registry 后 ST 日 ±5% 拒单/放行边界（既有 DD-6 参数化测试应已存在，激活）；LimitUpBreakPolicy 注入 is_st_fn 后涨停价按 5% 算；cross_section 名称前缀修正双向；
- golden 回归：不带 registry 的全部既有路径零漂移（默认参数向后兼容）。

## 七、风险与诚实校准

- **公告法固有模糊**：生效日 ±1~2 天、极端标题措辞漏检——交叉验证给出量化误差，验收报告如实公布；对周频策略是二阶小量，对比基线是"全盲"。
- **cninfo 检索的召回上限**：若某沪市 ST 事件公告标题完全不含"风险警示"四字（未见先例），会漏——终态自洽检查兜一半（当前仍 ST 的漏网必现形）；历史中段漏网无兜底，如实写进已知限制。
- **深市官方流的信任边界**：以交易所披露为准，不再二次验证。
- **akshare 接口漂移**：新增依赖记入 pyproject（akshare 已是 B1 依赖，本轮只是 WSL 环境补装）；接口变更属常态运维。
- **G7 可能 FAIL**：这是特性不是风险——判据存在的意义就是允许"不上钱"的结论。
