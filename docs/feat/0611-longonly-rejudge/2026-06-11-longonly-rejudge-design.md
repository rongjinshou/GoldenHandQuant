# 长多重判漏斗 · 设计文档（2026-06-11）

> 把因子判决记分牌从「多空风味」（IC-IR 稳定性 + 多空价差变现）整体替换为
> 「长多风味」（Top 层超额信息比 + Top 层纯多头超额 vs 等权基准），在正确的记分牌下
> 重判全部 field_ready 因子。回答：第二轮「0/10 不过」是否是用错记分牌测出的假阴性。

## 一、背景与问题

第二轮判决（`docs/feat/0610-factor-library/2026-06-11-night-round2-report.md`）0/10 通过，
真正的发现是**分裂结构**：

- 过 IC-IR 门槛（排序稳）的 F04 低波动/F05 低偏度，**OOS 多空变现为负**；
- 多空变现强的 F01 小市值(+27%)/F03 换手率(+17%)，**卡 IC-IR**（IC 不稳）。

两个集合不相交。但有一个被报告点破、尚未行动的关键质疑：

**漏斗判决用的是「多空」记分牌（IC-IR 稳定性 + 多空价差），而 ¥146k 实盘账户只能做多。**
A 股散户没有空头腿。多空价差里"空头腿赚的钱"散户吃不到；IC-IR 测的"全截面排序稳定性"
也是多空才需要的性质（长多只吃 Top 一篮子，不关心 Bottom 排得准不准）。

因此「0/10 不过」很可能是**拿错记分牌**测出的假阴性。F01/F03/F04 的排序信息都是真的
（OOS IC 与 IS 同号同量级），只是被两条「多空风味」的闸判了死刑。本设计的目标，是把记分牌
换成与实盘可执行口径一致的「长多」记分牌，重判，看真实过闸数。

## 二、目标与非目标

### 目标

1. 新增 `objective ∈ {long_short, long_only}` 判决模式，`long_only` 用「Top 层纯多头
   超额（对等权基准）」做变现与稳定性记分牌。默认 `long_short`，**旧链路零回归**。
2. 用 `long_only` 重判**全部 field_ready 因子**（F01/02/03/04/05/06/07/08/09/11；F10
   field_ready=False 排除），主报告聚焦 F01/F03/F04。
3. 判决门槛**跑前 pre-register**（写死阈值），防 p-hacking。
4. 新指标贯穿 留痕（factor_verdicts 加列）与驾驶舱（判决页可见 + 上色）。
5. 加调仓敏感性（1/5/20 日）与分位集中度（5 分位 vs 10 分位）两组旁路，复刻第二轮
   F04 敏感性的诊断方式。

### 非目标（明确写下，避免范围蔓延）

- **不接真实指数基准**（沪深300/中证1000）：库内无指数表、无离线缓存，整夜离线跑不通；
  且指数会把"选股 alpha"混入"universe vs 指数的 size/风格偏移"。用等权全市场基准更干净更保守。
- **不加可投性过滤**（ST/新股/停牌/最小市值/主板）：会改 universe，破坏与第二轮的可比性。
  本步回答"长多排序 alpha 是否存在"，不是"建出 ¥146k 的确切组合"。
- **不做 Top-N 定额选股**（如固定前 50 只）：沿用现有分位法，保持 apples-to-apples。
- **不升级实盘真成本模型**（印花税单边千0.5 + 滑点0.1%）：这些在 MockTradeGateway/
  DailySettlementService，属下游回测。因子筛沿用 cost_rate=0.003 双边换手成本，保持可比。

上述非目标均归属一个**下游"可投性回测"阶段**：长多重判出正候选 → 进 BacktestAppService +
MockTradeGateway（已内置真成本/流动性限制/T+1）做可执行验证。本设计是漏斗的"记分牌纠偏"环节。

## 三、记分牌数学（核心）

沿用引擎现有的逐日前向收益约定（`returns_by_date[cur][sym] = (p_cur − p_prev)/p_prev`，
`exec_close` 前复权；`_next_date` 对齐 `factor@T → returns[next_date]`，杜绝 off-by-one）。

设某调仓日 `t`、当日参与截面的股票全集为 `common_t`（= 有因子值且有次日收益的股票），
Top 层成员为 `members_top,t`（因子值最高的 1/num_layers 组，**因子已定向，Top = 想做多端**）：

- **等权基准日收益**：`b_t = mean({ ret_{t+1}(s) : s ∈ common_t })` ——"等权买全部"。
- **Top 层日净收益**：`r_t = mean({ ret_{t+1}(s) : s ∈ members_top,t }) − turnover_top,t × cost_rate`
  （即引擎已算的 `layer_daily_gross[top]` 扣 Top 腿换手成本；**基准视为无成本参考腿**）。
- **Top 层日超额**：`e_t = r_t − b_t`。
- **年化超额**（套用 `_long_short_net` 的复利+244 年化骨架，把 Bottom 腿换成基准腿）：
  `top_excess_return = (∏_t (1 + e_t)) ** (244 / n_days) − 1`。
- **超额信息比（年化）**：`excess_ir = mean(e_t) / std(e_t, ddof=1) × sqrt(244)`。
- **超额正率**：`excess_positive_rate = #{t : e_t > 0} / n_days`。

OOS 段用同口径在 `date > split_date` 子集上再算一遍，得 `oos_top_excess_return` 等。

> 口径一致性：年化用 244 交易日、cost_rate=0.003、等权——与现有 `layer_returns`/
> `long_short_return` 完全同源，新旧指标可直接并排比较（这正是验证"分裂结构"是否被纠正所必需）。

## 四、判决门槛 pre-registration（防 p-hacking 的关键）

`long_only` 模式下 `judge_factor` 的门槛（**全 AND，任一 fail 即不过**；阈值在实跑前写死）：

| # | 闸 | 阈值 | 相对多空记分牌 | 理由 |
|---|---|---|---|---|
| 1 | 排序有效性 | `ic_mean ≥ 0.02`（有符号） | 不变 | 因子必须在正确方向上有排序力；记分牌中立 |
| 2 | 经济单调 | `monotonicity_score ≥ 0.6` | 不变 | 高分位应更赚——长多尤其要 Top 是最好的一组 |
| 3 | 抗冗余 | 中性化后 `\|IC\| ≥ 0.02`（非控制类） | 不变 | F03/F04 不能只是市值/反转影子；F01=规模类豁免 |
| 4 | OOS 排序不翻转 | OOS 与 IS 的 `ic_mean` 同号 | 不变 | 基本有效性 |
| 5 | **稳定性** | **`excess_ir ≥ 0.50`**（IS） | **替换 IC-IR ≥ 0.30** | 长多稳定性主体是 Top 超额序列，非全截面 IC |
| 6 | **一致性** | **`excess_positive_rate ≥ 0.52`**（IS） | **替换 IC 正率 ≥ 0.52** | 长多一致性主体是"Top 跑赢基准的期数占比" |
| 7 | **变现(IS)** | **`top_excess_return > 0`**（扣成本） | **替换 多空价差 > 0** | Top 一篮子在样本内须跑赢等权基准 |
| 8 | **变现(OOS)** | **`oos_top_excess_return > 0`** | **替换 OOS 多空 > 0** | **绑定闸**：超额须 OOS 持续，正是杀死多空 F04 的那道闸 |

### 关键决策：为何连 IR 闸一起换（而非只换变现闸）

只换变现闸（多空→Top 超额）、保留 IC-IR≥0.30 的"最小改动"方案，会让 F01/F03（IR 0.11/0.17）
**仍死在 IR 闸上**——而它们恰是变现最强的两个，重判对它们毫无意义。分裂结构的根因正是
"IC-IR 与变现在测不同的东西"。用户给定方向的原话是「把**多空 IR** 换成 Top 层纯多头超额」，
把 IC-IR（多空风味的稳定性）换成 excess-IR（长多的稳定性）才是忠实执行。

**这是诚实的纠偏，不是放水**：

- 阈值跑前写死（0.50/0.52），不看结果调。
- F01/F03 仍可能诚实地不过：若其 Top 超额序列同样飘/为负，说明多空 edge 全来自空头腿
  （做空大盘股/高换手股），散户做多吃不到 → 判不过是**正确**结论。
- F04（过 IC-IR、OOS 多空为负）可能翻盘也可能不翻：若其 Top（低波股）超额 vs 等权为正且稳，
  则"0/10"对它确是假阴性；若 Top 超额仍为负，则其 alpha 同样不可长多变现。

无论哪种结果都是决策级信息：要么找到第一个可长多变现的候选，要么确证"这批单因子在长多口径下
也无解"，从而把注意力转向组合/择时（factor-funnel 主线的下一岔口）。

### excess_ir = 0.50 阈值的标定

`excess_ir` 是 Top 超额日收益的年化信息比（≈ 年化超额 / 年化跟踪误差）。优质长多因子倾斜的
信息比经验区间 0.3–0.7；取 **0.50** 为"真 edge"门槛，中等偏严但可达。报告同时输出每个因子的
实际 `excess_ir` 与到阈值的距离，便于判断"差多少"。OOS 段的 `excess_ir` 一并输出（不设闸，仅观测）。

## 五、架构与改动面（最小侵入，高复用）

依赖方向不变：`interfaces → infrastructure → application → domain`。新指标计算落在 infrastructure
（`layer_backtest.py`，纯 numpy 计算，符合 domain 红线豁免），判决/评分/VO 落在 domain（纯计算）。

### 直接复用（不改）

- **Top 层多头收益已现成**：`LayerBacktester` 已产出 `layer_daily_gross[top]`、
  `layer_daily_turnover[top]`、`layer_returns[-1]`、`layer_cumulative[-1]`（已扣换手成本，长仓口径）。
- 数据准备链、`_next_date` 对齐、`_compute_forward_returns`、IS/OOS 切分、evaluator、字段映射、
  IC/IR/单调/衰减/中性化——全部原样复用。
- F01/F03/F04 表达式已定向（`0 - log(market_cap)` / `0 - avg_turnover_20d` / `0 - volatility_20d`），
  Top 层天然是想做多端，**无需改 expression**。

### 需新增/改动（按层）

| 层 | 文件 | 改动 |
|---|---|---|
| infra | `infrastructure/factor_test/layer_backtest.py` | `run()` 加 `objective`、可选基准腿；主循环并行累积 `common` 等权基准日收益与 Top 超额；新增 `_top_excess_net()`（仿 `_long_short_net`）；`LayerBacktestResult` 加 `top_layer_return/top_excess_return/benchmark_return/excess_ir/excess_positive_rate` 字段（默认 0.0，向后兼容） |
| infra | `infrastructure/factor_test/test_runner.py` | 透传 `objective`；把新指标装入 `FactorTestReport` |
| domain | `domain/strategy/factor_test/report.py` | `FactorTestReport`/`ScoredFactorTestReport` 加 `top_excess_return` 等字段 + @property 代理（默认 0.0） |
| domain | `domain/strategy/factor_test/verdict.py` | `judge_factor()` 加 `objective` 参数 + long_only 门槛分支（§四 5/6/7/8）；`FactorVerdict` 加 `top_excess_return/oos_top_excess_return/excess_ir/excess_positive_rate`（默认 0.0）；新增常量 `EXCESS_IR_MIN=0.50`、`EXCESS_POSITIVE_RATE_MIN=0.52`、`TOP_EXCESS_MIN=0.0` |
| domain | `domain/strategy/factor_test/scorer.py` | `score()` 加 `objective`；long_only 下 20% 变现项从 `long_short_return` 切到 `top_excess_return`（线性档需重标，见下） |
| app | `application/factor_test_app.py` | `run_batch`/`run_single` 透传 `objective`、`cost_rate`；基准由引擎内 `common` 等权合成（零额外取数） |
| iface | `interfaces/cli/quant.py` | `factor-test` 加 `--objective {long_short,long_only}`（默认 long_short）、`--cost-rate`（默认 0.003） |
| iface | `interfaces/cli/commands/factor_test.py` | 透传 args；`verdict_rows` 加新键；终端 SUMMARY 增列；`run_params` 记 objective |
| infra | `infrastructure/persistence/market_data_store.py` | factor_verdicts **迁移加列**（见 §六）；`_VERDICT_NUMERIC_COLS` 扩展；`insert_verdicts`/`load_verdict_runs`（位置切片 offset 同步更新） |
| iface | `interfaces/api/static/app.js` + `index.html` | 判决表加 top_excess 列；long_only run 的 gate 上色用新阈值副本（注：阈值在 JS 与 verdict.py 双处硬编码，本次同步，重复源收敛留作债 [[D2]]） |

### scorer 变现档重标

现 `long_short` 变现项 `_linear_score(long_short_return, 0.03, 0.15)*20`（3%→15% 线性满分）。
长多超额量级远小于多空价差，沿用 0.03/0.15 会过严失真。long_only 下改 `_linear_score(top_excess_return,
0.0, 0.05)*20`（0→5% 线性满分）。score/grade 仅作展示维度，不参与 passed（passed 由 §四硬门槛决定）。

## 六、持久化与可视化

### factor_verdicts schema 迁移

`CREATE TABLE IF NOT EXISTS` 不会对存量表加列。新增**幂等迁移**（store 初始化时执行
`ALTER TABLE factor_verdicts ADD COLUMN IF NOT EXISTS <col> DOUBLE`，DuckDB 支持）：

新增列：`top_excess_return`、`oos_top_excess_return`、`excess_ir`、`excess_positive_rate`
（DOUBLE，存量 run 该列 NULL）、`objective`（VARCHAR，存量 run 回填
`'long_short'`）。主键 `(run_id, factor_id)` 不变（每次 factor-test 调用是单一 objective →
单一 run_id，无冲突）。

> **实现修正（2026-06-12 审查后）**：`benchmark_return` 最终**未落库**——它在 `FactorTestReport`
> VO 内算出（供报告/JSON），但不进 verdict 列（YAGNI：超额已自含 top−benchmark，基准非门槛非显示项）。
> 登记为债 L1，需要时再补落库或在 SUMMARY 输出。详见判决报告 §七。

`load_verdict_runs` 按行位置切片解析（offset 敏感）——加列后必须同步更新 offset，并加回归测试
覆盖"旧 run（新列 NULL）+ 新 run"混读不错位。

### 驾驶舱

判决页表格按 objective 区分列显示：long_short run 显示 `long_short_return` 列，long_only run
显示 `top_excess_return/excess_ir` 列；gate 上色读各自阈值。null 值显示 `-`（现有 gateCell 已处理）。

## 七、数据与执行

- 数据已就绪：`market.duckdb` bars/features/fundamentals 覆盖 **2020-06-15 → 2026-06-11**，
  5207 只。评测纯 duckdb 读取，**不 import xtquant**，可离线实跑（Windows conda python.exe）。
- universe 离线化：`resolve_universe` source='qmt' 会先试 `xtdata.get_stock_list_in_sector`（需 QMT
  客户端）；离线回退 `store.load_symbols`（读 instruments 表，已存在）。实跑前确认走离线回退或
  显式传库内符号集，避免触发在线取数。
- **运行矩阵**（窗口 2021-01-01 → 2026-06-11，切分 2024-06-30，与第二轮一致以便对照）：
  - 主判决：全 field_ready 因子，`--objective long_only --num-layers 5 --rebalance-days 5`。
  - 调仓敏感性：F01/F03/F04 在 1/5/20 日（复刻 F04 第二轮诊断）。
  - 分位集中度：F01/F03/F04 在 `--num-layers 10`（Top 十分位，探可投性集中度）。
- 判决自动入库 `factor_verdicts`（新列），驾驶舱判决页可核对。

## 八、风险与限制（诚实记录）

1. **Top 分位 ≈ 1/5 ≈ 千只股**，与 ¥146k 实盘只能持几十只严重不符——本步是"alpha 是否存在"的
   理想化上界，非可执行组合。缓解：报告输出 Top 层股票数 + 年换手，使可投性差距可见；分位集中度
   旁路（10 分位）给一个更集中的视角。可投性约束留给下游回测。
2. **等权基准对小市值因子偏宽**（小盘股本就跑赢等权全体）——这是已知偏置。但等权基准对 F03/F04
   不偏，且是唯一离线可得的自洽口径。真实指数基准列入下游可投性回测。
3. **成本乐观**：cost_rate=0.003 双边换手 < 实盘真成本（印花+滑点）。报告输出换手率使成本敏感性
   可见；`--cost-rate` 提供手动加严的旁路。
4. **1 日逐日重排噪声**：默认 rebalance_days 已定 5（非 1），且做 1/5/20 敏感性，避免单一频率误判。
5. **窗口短段年化外推**：OOS≈2 年，年化噪声仍在；OOS 超额作绑定闸而非唯一判据，与 IS 一致性合看。
6. **判决阈值三处硬编码**（verdict.py / app.js / CLI 格式）：本次同步更新，单一真相源收敛留作债 [[D2]]。
7. **基准 costless 不对称**（2026-06-12 审查 MEDIUM）：基准腿不扣换手、Top 腿扣自身换手，把基准应付的
   换手成本让渡给超额，方向性抬高 top_excess/excess_ir。对慢因子（F01 排序稳）量级小，对高换手 universe
   偏宽。债 L4：如需消除，对 bench_daily 同口径估换手扣成本。
8. **excess_ir 自相关高估**（2026-06-12 审查 LOW）：mean/std×√244 隐含日超额 IID，N 日持有使其强自相关
   → IR 高估（F01 1.37 真值或 ~0.7–0.9，仍 ≫0.50；恰卡线因子更受影响）。与既有多空 IC-IR 同源老惯例。
   债 L3：可改不重叠块 IR / Newey-West。
   → 综合 §八.2/§八.7/§八.8：long_only headline 超额应读作**乐观上界**，真实可投收益由下游可投性回测确认。

## 九、验收标准

1. 全量 `pytest`（忽略 gateway）绿 + `ruff check src/` 干净；新增逻辑 TDD 覆盖（基准合成、Top 超额
   年化、excess_ir/正率、long_only 门槛分支、schema 迁移混读、向后兼容 long_short 零回归）。
2. `--objective long_only` 实跑全 field_ready 因子成功，判决入库新列，驾驶舱可见。
3. 产出**长多重判报告**（`docs/feat/0611-longonly-rejudge/2026-06-11-longonly-rejudge-report.md`）：
   - long_only 真实过闸数 + 完整指标表（IC/excess_ir/excess_pos_rate/top_excess IS&OOS/passed）；
   - 与第二轮多空记分牌并排对照（哪些因子在长多口径下翻盘/仍不过/新发现）；
   - F01/F03/F04 的调仓敏感性 + 分位集中度小表；
   - 结论：是否找到首个可长多变现候选；若无，分裂结构在长多口径下是否仍存在，主线下一岔口建议。
4. 旧 `long_short` 路径回归测试全绿（默认行为零变化）。

## 十、决策记录附录（开放问题 → 裁定）

| 开放问题 | 裁定 | 依据 |
|---|---|---|
| 基准取等权全市场/等权池内/真实指数？ | **等权"当日因子覆盖池"（common 集）截面均值** | 零依赖、纯离线、与 Top 同口径；指数混入风格偏移且离线不可得 |
| Top 取分位还是 Top-N 定额？ | **沿用分位（主 5 分位）**，加 10 分位集中度旁路 | apples-to-apples；Top-N 是新逻辑，YAGNI |
| 替换全部多空闸还是只换变现闸？ | **替换 IR/正率/变现共 4 闸**，保留 IC/单调/中性化/OOS不翻转 | 忠实"换多空 IR"；只换变现则 F01/F03 仍死于 IR，重判失义 |
| score/grade 是否切长多口径？ | **切**（变现项档位重标 0→5%） | 否则 score 仍按多空算，延续排序/变现分裂 |
| 持久化加列还是塞 params JSON？ | **ALTER 加列**（幂等迁移） | 驾驶舱可上色；params JSON 是二等公民 |
| 重判范围？ | **全 field_ready 因子**，报告聚焦 F01/F03/F04 | 答"正确记分牌下真实过闸数"；F10 field_ready=False 排除 |
| 调仓频率默认？ | **5 日**（对齐第二轮 P0/P1），加 1/5/20 敏感性 | 1 日逐日不可执行；敏感性复刻 F04 诊断方式 |
| 实盘真成本是否纳入？ | **否**（沿用 0.003），输出换手率 + `--cost-rate` 旁路 | 保持与第二轮可比；真成本属下游回测 |

---

**相关**：第二轮判决报告 `docs/feat/0610-factor-library/2026-06-11-night-round2-report.md`；
主线状态 memory `factor-funnel-status`；理解阶段图谱（4 路精读）见本会话 workflow `understand-factor-funnel`。
