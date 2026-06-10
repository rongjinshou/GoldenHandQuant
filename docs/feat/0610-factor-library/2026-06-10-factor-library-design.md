# A 股因子假设库 — 设计文档（Factor Hypothesis Library）

> **日期**: 2026-06-10 ｜ **状态**: 设计稿（待评审）
> **定位**: 验证优先路线图 Phase 0/1 的"弹药库"——可直接开测的 A 股因子清单
> **配套**: 数据地基修复（缓存覆盖 bug + 全市场股票池，2026-06-10 已完成）

---

## 1. 这份文档是什么 / 不是什么

**是**：一份**有经济逻辑、可直接转成 DSL 表达式、标好数据可得性与测法、按优先级排序**的 A 股因子假设清单。每条因子是一次"廉价的试"，走同一条验证漏斗，幸存者才组装成策略。

**不是**：不是策略，不是承诺会赚钱的因子。**所有因子的去留以"样本外、扣成本、跑赢基准"的硬门槛为准**（见 §7）。

**为什么是它**：你的真实瓶颈不是工具（factor-test 引擎已具备），是**手里可测的想法太少**。这份库把"策略太少"变成"廉价多筛"——但**有纪律的多，不是过拟合的多**。

**北向暂排除**：`fetch_northbound` 数据口径（2024-08 起披露频率变化）待核对，本轮不纳入，留待单独验证。

---

## 2. 排序原则：押在你相对机构的优势区

个人 A 股量化的 edge **不在跟机构拼慢变量**（价值/质量——机构资金体量碾压）。在**机构进不去或看不上的地方**：

- **微盘**（容量受限，机构买不进）
- **短期反转 / 换手 / 博彩**（换手太快、太"散户"，机构不屑做）
- **流动性溢价**（非流动性，机构反而是流动性提供方）
- **龙虎榜博弈**（事件、结构性）

**优先级 = A股证据强度 × 数据是否已就绪 × 容量是否适合个人**，而不是"听起来多专业"。

| 优先级 | 含义 |
|---|---|
| **P0** | 证据强 + 字段已在 StockSnapshot 上 + 容量适合个人 → **先做这批** |
| **P1** | 证据中 / 字段需补一步（接 fetcher 或派生） |
| **P2** | 证据弱 / 作对照 / 备选 |

---

## 3. 怎么测一个因子（验证漏斗）

每个因子走**同一条**流水线，杜绝挑数据：

```
因子表达式(DSL str)
   │
   ▼  FactorTestRunner.run(expression, snapshots_by_date, returns_by_date, prices_by_date)
   ├─ IC 序列 (Spearman, 因子@T vs 收益@T+1) → IC均值/IC标准差/IR/IC正率
   ├─ 分层回测 (默认5层) → 各层收益、多空收益、单调性 monotonicity_score
   ├─ 因子衰减 (decay) → 不同持有期的 IC 半衰期
   └─ 综合评分 → score / grade / reasons (FactorScorer)
   │
   ▼  叠加我们自己的样本外硬门槛 (§7) → 过 / 不过
```

**真实接口**（`src/infrastructure/factor_test/test_runner.py`）：

```python
from src.infrastructure.factor_test.test_runner import FactorTestRunner
report = FactorTestRunner().run(
    expression_str="0 - return_20d",          # 因子表达式
    snapshots_by_date={...},                  # {date: [StockSnapshot,...]}
    returns_by_date={...},                    # {date: {symbol: 次日收益}}
    prices_by_date={...},                     # {date: {symbol: close}}
    test_period=("2021-01-01", "2025-12-31"),
    num_layers=5,
)
# report.report.ic_mean / ir / ic_positive_rate / monotonicity_score / long_short_return ...
```

---

## 4. ⚠️ 现状与缺口（落地前必须知道）

1. **`quant factor-test` CLI 是占位**（只打印"即将推出"）。真引擎 `FactorTestRunner` 完整可用，但要么**写个小脚本驱动**，要么**把 CLI 接上引擎**（推荐，半天工作量，是 Phase 0 的收尾小任务）。
2. **技术字段要由 snapshot 构建管道填充**：`return_20d / volatility_20d / avg_turnover_20d / illiquidity_20d / skewness_20d` 等是 `StockSnapshot.technical` 的字段，需要构建快照时算好。`FeaturePipeline.build_cross_section()` 已有部分逻辑——开测前要核对**哪些字段真的被填了**（下表"字段就绪"列标注）。
3. **防未来函数**：基本面用 `ann_date`（公告日）而非 `end_date`（报告期）对齐；IC 用 T→T+1；point-in-time。`FundamentalRegistry` 已是 ann_date 双索引设计，沿用即可。

---

## 5. 可用字段 & DSL 速查

**StockSnapshot 字段**（因子的"原子"）：

| 组 | 字段 |
|---|---|
| 价量 | `close open high low volume prev_close turnover_rate` |
| 基本面 | `market_cap pe_ratio pb_ratio ps_ratio pcf_ratio roe_ttm roa_ttm ocf_ttm gross_margin net_margin asset_turnover current_ratio debt_to_equity dividend_yield earnings_growth revenue_growth` |
| 技术(时序,需管道填充) | `return_5d return_20d return_60d volatility_20d volatility_60d avg_turnover_20d illiquidity_20d skewness_20d rsi_14 macd macd_signal ma_5 ma_20 ma_60 high_20d low_20d atr_14 obv_slope_20d` |

**DSL 算子**：二元 `+ - * /`（逐股票，除零自动剔除）；一元 `abs(x) log(x) sign(x)`；**截面** `rank(x)`→百分位[0,1]、`zscore(x)`。
**取负方向**：无一元负号，用 `0 - x`。**取倒数**：`1 / x`。

> **方向约定**：本库所有表达式都**已朝"高=预期跑赢"定向**，这样分层回测的最高层就是多头。raw IC 符号在每张卡注明。

---

## 6. 因子卡片

### 6.1 P0 短名单（字段已就绪 · 证据强 · 个人优势区 → 先做这 5 个）

---

**F01 · 小市值 (Size)** — 类别: 规模
- **经济逻辑**: A 股小/微盘长期溢价（壳价值、流动性、关注度），机构容量受限买不进，是个人最天然的优势区。
- **A股证据**: **强**
- **DSL**: `0 - log(market_cap)`
- **方向**: 高=小盘=预期跑赢；raw `log(market_cap)` 对次日收益 **IC 为负**
- **字段就绪**: ✅ `market_cap`
- **怎么测**: IC 定向后为正、|IC| 偏大；分层强单调（最小市值层最强）；衰减慢（规模是慢变量）
- **正交化**: 后续因子都要**对市值中性化**（很多异象本质是市值的影子）
- **优先级**: **P0**

**F02 · 短期反转 (Reversal)** — 类别: 量价
- **经济逻辑**: A 股散户主导，短期超买超卖后均值回归；流动性提供者获补偿。**A 股最稳健异象之一**。
- **A股证据**: **强**
- **DSL**: `0 - return_20d`（可进阶：剔除最近 1–2 日微观噪声）
- **方向**: 高=过去跌得多=预期反弹；raw `return_20d` **IC 为负**
- **字段就绪**: ✅ `return_20d`
- **怎么测**: 定向后 IC 正且 |IC| 高；分层单调；衰减半衰期数日–数周（短）
- **优先级**: **P0**

**F03 · 换手率 (Turnover)** — 类别: 流动性/情绪
- **经济逻辑**: 高换手 = 高关注/投机/分歧，A 股**高换手负向**显著（关注度溢价反转）。
- **A股证据**: **强**
- **DSL**: `0 - avg_turnover_20d`
- **方向**: 高=低换手=预期跑赢；raw 换手 **IC 为负**
- **字段就绪**: ✅ `avg_turnover_20d`（或 `turnover_rate` 单日）
- **怎么测**: IC 负→定向后正；**与市值、反转正交化后看增量**（三者相关）
- **优先级**: **P0**

**F04 · 低波动 (Low-Vol)** — 类别: 风险
- **经济逻辑**: 低波异象——高波动股长期跑输（彩票偏好+杠杆约束），A 股存在。
- **A股证据**: **中强**
- **DSL**: `0 - volatility_20d`
- **方向**: 高=低波=预期跑赢；raw 波动 **IC 为负**
- **字段就绪**: ✅ `volatility_20d`
- **怎么测**: 分层单调；与市值正交化（小盘往往高波，需剥离）
- **优先级**: **P0**

**F05 · 抗博彩 / 低偏度 (Lottery)** — 类别: 行为
- **经济逻辑**: A 股散户偏好"彩票股"（高右偏、近期暴涨），推高估值→未来跑输。卖出博彩属性即赚反向钱。
- **A股证据**: **中**（A 股博彩偏好强，值得一试）
- **DSL**: `0 - skewness_20d`
- **方向**: 高=低偏度=预期跑赢；raw 偏度 **IC 为负**
- **字段就绪**: ⚠️ `skewness_20d`（确认管道是否填充，否则需补算）
- **怎么测**: 与反转/换手正交后看增量
- **优先级**: **P0**（数据就绪则做，否则降 P1）

---

### 6.2 P1（证据中 / 需补一步）

**F06 · Amihud 非流动性** — `illiquidity_20d`｜方向正（非流动性溢价）｜字段⚠️待确认｜与市值/换手高度相关，看正交增量。

**F07 · BP 账面市值比 (Value)** — `1 / pb_ratio`｜方向正（高BP=便宜）｜✅`pb_ratio`｜A股价值中等，剔除 PB≤0。

**F08 · EP 盈利市值比 (Value)** — `1 / pe_ratio`｜方向正｜✅`pe_ratio`｜⚠️单独处理 PE<0（亏损股）。

**F09 · ROE 质量** — `roe_ttm`｜方向正｜✅`roe_ttm`｜机构主战场，个人增量有限，作组合补充。

**F10 · 毛利率 (Quality)** — `gross_margin`｜方向正（Novy-Marx 毛利率）｜✅`gross_margin`｜比 ROE 更稳的质量代理。

**F11 · 龙虎榜机构净买入** — 类别: 另类/事件 ⭐
- **经济逻辑**: 龙虎榜机构席位净买入对短期收益有预测力；这是**你已抓 `fetch_dragon_tiger`、却从没用起来的"被埋因子"**。
- **A股证据**: 中（事件型，短窗口）
- **数据**: ⚠️ 需把 `fetch_dragon_tiger` 的机构净买额**接进 snapshot**（新增字段，如 `lhb_inst_net`），再写表达式 `rank(lhb_inst_net)`
- **优先级**: **P1**（数据接好后可升 P0，是优势区）

---

### 6.3 P2（对照 / 备选 / 证据弱）

| 因子 | DSL | 说明 |
|---|---|---|
| 中期动量 | `return_60d` | A 股动量**弱/不稳**，作反转的对照 |
| SP 营收市值比 | `1 / ps_ratio` | 价值补充 |
| 营收/净利增速 | `revenue_growth` / `earnings_growth` | 成长，A 股有"成长陷阱" |
| 应计利润 | 需派生 `roa_ttm` vs `ocf_ttm/资产` | 盈余质量，需派生 |
| 板块动量 | 需 `fetch_sector` 接入 | 轮动，需板块数据 |
| 估值分位择时 | overlay，非选股 | 与已有 `SystemRiskGate` 配合 |

---

## 7. 验证协议与硬门槛（防自欺的核心）

一个因子要**晋级**（进入组合 / Phase 2 纸面前向），必须同时满足：

1. **IC 有效**: |IC 均值| ≥ ~0.02–0.03，IC 正率明显偏离 50%，**IR ≥ 0.3**
2. **分层单调**: `monotonicity_score` 高，多空（top-bottom）收益方向正确
3. **样本外保持**: 样本内/外（如 2021–2023 训练 / 2024–2025 验证，walk-forward）**符号与量级不崩**
4. **扣成本后多空为正**: 计入双向万 2.5 + 印花税千 0.5 + 滑点（系统已内置）后，多空年化仍为正
5. **正交增量**: 对**市值 + 反转**中性化后仍有边际（否则只是它们的影子）

**多重检验纪律**：你测的因子越多，单个"显著"越可能是噪声。规矩：
- 任何因子的**最终判决以样本外为准**，样本内只用于形成假设；
- 同类因子（都是量价反转族）只留**正交后增量最大**的 1–2 个，不堆同质因子。

---

## 8. 落地顺序（Phase 0 收尾 → Phase 1）

1. **接通引擎**（小任务）：把 `quant factor-test` 占位接上 `FactorTestRunner`，或写一个 `scripts/run_factor_test.py` 驱动器（构建 `snapshots_by_date` + 调 runner + 打印报告）。
2. **核对字段填充**：确认 snapshot 构建管道填了 P0 所需的 `return_20d / volatility_20d / avg_turnover_20d / skewness_20d`（缺则补）。
3. **跑 P0 五因子**（全市场、`batch_download` 预热后的全历史、样本内外切分）。
4. **读判决**：哪些过 §7 硬门槛。
5. **正交组合**：幸存者对市值/反转中性化后，组合成 1–2 个候选策略 → 进 Phase 2 纸面前向。

---

## 9. 附：一眼看全（优先级 × 数据就绪）

| 因子 | DSL（已定向） | 证据 | 字段就绪 | 优先级 |
|---|---|---|---|---|
| 小市值 | `0 - log(market_cap)` | 强 | ✅ | P0 |
| 短期反转 | `0 - return_20d` | 强 | ✅ | P0 |
| 换手率 | `0 - avg_turnover_20d` | 强 | ✅ | P0 |
| 低波动 | `0 - volatility_20d` | 中强 | ✅ | P0 |
| 抗博彩/低偏度 | `0 - skewness_20d` | 中 | ⚠️ | P0* |
| Amihud 非流动性 | `illiquidity_20d` | 中 | ⚠️ | P1 |
| BP | `1 / pb_ratio` | 中 | ✅ | P1 |
| EP | `1 / pe_ratio` | 中 | ✅ | P1 |
| ROE | `roe_ttm` | 中 | ✅ | P1 |
| 毛利率 | `gross_margin` | 中 | ✅ | P1 |
| 龙虎榜机构净买 | `rank(lhb_inst_net)` | 中 | ❌ 需接 fetcher | P1 |
| 中期动量(对照) | `return_60d` | 弱 | ✅ | P2 |

\* 偏度字段未填充则降 P1。
