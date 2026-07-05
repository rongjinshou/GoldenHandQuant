# 因子判决页卡片化重构 — 设计文档

日期：2026-07-05
状态：待评审
前置：`docs/feat/0705-research-narrative`（run 人话命名）、`docs/feat/0704-frontend-framework`（Vue3 迁移）

---

## 1. 背景与动机

现状（`frontend/src/pages/Verdicts.vue`）：判决结果是一张 8 数值列 + 评分 + 判决徽章的宽表格，
每个因子占两行（主行指标 + reasons 明细行），检验表单在页面最底部的 `<details>` 里。

痛点（按用户思路归纳）：

1. **表格横排扫读难**。8 个数值列一字排开，回答"这轮哪些因子能用、挂在哪"要逐行横扫；
   PASS/FAIL 徽章在最右端，视线到达成本最高。
2. **两行制造噪音**。reasons 行常驻穿插在因子之间，表格的"行=记录"心智被打断；
   展开态和折叠态混在同一张表里，密度失控。
3. **工作流倒置**。用户动线是"发起检验 → 等结果 → 看判决"，而发起入口埋在页面最底部，
   每次都要滚过整张表格。
4. **细节无处安放**。expression、全量判定明细只能塞在展开行里挤着显示；
   表格列宽被 objective 联动切换进一步压缩，无法承载"所有细节"。

## 2. 目标与非目标

**目标**

- 因子检验表单置顶（页面第一个功能区），判决结果紧随其后。
- 表格行 → **因子卡片网格**：一卡一因子，第一眼判决、第二眼身份、第三眼关键指标。
- 卡片可**排序 + 过滤**，默认"放榜序"（PASS 在前，组内评分降序）。
- 点击卡片弹出**详情弹框**，承载该因子已入库的全部细节（指标 IS/OOS 对照、
  expression、逐关判定明细），支持弹框内 ←/→ 切换相邻因子。
- 建立**全站首个 modal 规范**（选型、尺寸、a11y、token 化样式），供后续页面复用。
- Verdicts.vue（现 ~710 行）拆分组件，排序/闸门逻辑抽纯函数并补 Vitest。

**非目标**

- 不改后端。API `/api/research/verdicts` 与 `factor_verdicts` 表结构不动。
- 不展示未入库数据：IC 时序、分层累计收益曲线、评分构成（`grade_reasons`）、
  `neutralized_ic` 均未入库 → 弹框不含图表区。未来若入库，弹框预留"扩展区"锚位即可，
  本次不做。
- 不动检验表单的字段与提交逻辑（chips 分组/P0 默认勾/field_ready 禁用/多重检验提示/JobCard
  闭环全部原样保留），只挪位置。
- 不做卡片/表格双视图切换开关（YAGNI；表格如确有留恋，git 历史可查）。

## 3. 页面结构重排

新的纵向顺序（对比现状：表单从底部移到顶部，run 选择器下沉到结果区）：

```
┌──────────────────────────────────────────────────────┐
│ 因子判决                                    (页头,仅标题+引导语) │
├──────────────────────────────────────────────────────┤
│ ▼ 因子检验                                  (details open, 置顶) │
│   P0  [chip][chip][chip]…                              │
│   P1  [chip][chip]…                                    │
│   起始[  ] 结束[  ] 切分[  ] 记分牌[  ] 分层[ ] … [提交检验] │
│   (JobCard 区: 提交后任务卡在此出现, 完成自动刷新下方结果)      │
├──────────────────────────────────────────────────────┤
│ 判决结果   [轮次下拉 ▾]      [全部 12|PASS 3|FAIL 9] [排序 ▾] │ ← 结果区头
│ ┌ meta 条: 区间 · 切分 · 调仓 · 记分牌 · 股票池 · 特征版本 ┐   │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│ │ 因子卡  │ │ 因子卡  │ │ 因子卡  │ │ 因子卡  │          │
│ └────────┘ └────────┘ └────────┘ └────────┘          │
│ ┌────────┐ ┌────────┐ …                               │
└──────────────────────────────────────────────────────┘
```

决策说明：

- **表单默认展开**。用户把它挪到最上面就是要用它；保留 `<details open>` 的折叠能力，
  不想看时一击收起。不做"折叠成摘要行"的花活。
- **run 下拉从页头移到结果区头**。表单置顶后，页头的 run 下拉与它作用的结果区隔了
  整个表单，产生归属歧义；下拉、过滤、排序同属"我在看哪批结果、怎么看"，聚在结果区头
  一行。页头回归纯标题。
- 空态文案方位词更新：「暂无判决轮次 — 用**上方**表单提交一次因子检验。」（现为"下方"）。

## 4. 因子卡片

### 4.1 信息层级

小空间里按三级视线排布，回答三个问题：**能不能用 → 是谁 → 好到什么程度**。

```
┌│───────────────────────────┐   │← 左缘 3px 判决色条(pass 绿/fail 红)
││ momentum_20d        [B 72] │   ← id(mono,加粗) + 等级评分徽章(右上)
││ 20 日动量                   │   ← 中文名(次级色)
││                             │
││ IC均值      超额IR    OOS超额 │   ← 关键指标三元组(标签 11px 次级色)
││ .0312      0.82     +3.2%  │   ← 数值 mono 右对齐同基线, gate 着色
││                             │
││ ▮▮▮▮▮▯▯          FAIL      │   ← 闸门轨道 + 判决徽章(底部行)
││ 单调性=0.52 < 0.6           │   ← FAIL 卡: 首要死因一行(红,截断)
└│───────────────────────────┘
```

- **网格**：`display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:12px`。
  典型一轮 10~25 个因子，1280px 宽约 4 列，一屏半内看完整轮。
- **卡片容器语义为 `<button>`**（重置默认样式）：回车/空格开弹框、焦点环、tab 序全部免费，
  不用手写 `role/tabindex/keydown`。
- **关键指标三元组**随 objective 联动，与现表格列逻辑同源（复用 `gates.ts` 的
  `gateClass` 着色 + `f2/f4/pct` 格式化）：
  - `long_only`：IC均值 · 超额IR · Top超额(OOS)
  - `long_short`：IC均值 · IR · 多空(OOS)
  - 选这三个的理由：预测力（IC）、稳定性（IR 系）、样本外变现（OOS 系）各取其一，
    是 PASS/FAIL 之外区分度最高的三轴；其余指标进弹框。
- **grade 徽章**合并"等级+分数"为一体（`B 72`），沿用 `gradeClass` 四档配色；
  score 为 null 时只显示"—"。
- **FAIL 死因行**：取 `failedReasons(f)[0]`（后端 reasons 顺序即闸门判定顺序，
  第一条失败即最先挂掉的关卡），单行 ellipsis，title 属性带全文。PASS 卡此行不渲染，
  卡片高度用 min-height 拉齐避免网格参差。

### 4.2 签名元素：闸门轨道（gate track）

判决的领域语言是"闯关"——一列硬门槛，全过才 PASS。轨道把它编码成形状：
一格一道闸，**绿=过、红=挂、灰=该轮未测**（如未设 split 时的两道 OOS 闸）。
FAIL 卡不用读数字就能看出"挂在第几关、挂了几关"；一轮 20 张卡扫过去，
红格聚集的位置直接暴露这批因子的系统性短板（比如全军覆没在单调性）。

- 视觉：10×10px 圆角 2px 方格，gap 3px；pass = `--c-pass` 72% 混合底，
  fail = `--c-fail` 实底（失败更醒目），na = 透明底 + `--border` 描边。
- 悬停单格 title 显示闸门名与判定值；轨道整体 `aria-label="7 道闸门通过 5 道"`。
- 闸门序列固定 7 道，顺序与 `verdict.py` 判定顺序一致：
  ① IC 门槛 → ② 稳定性（IR 或 超额IR）→ ③ 一致性（IC正率 或 超额正率）→
  ④ 单调性 → ⑤ IS 变现 → ⑥ OOS 符号一致 → ⑦ OOS 变现。

数据口径（重要）：轨道由前端从数值字段**重算**，新增纯函数
`gateTrack(f: VerdictFactor): GateCell[]` 放入 `gates.ts`：

- ①②④⑤⑦ 直接复用现有 `GATES` 表；
- ③ 需**补键**：`ic_positive_rate >= 0.52` 与 `excess_positive_rate >= 0.52`
  （`excess_positive_rate` 已有；`ic_positive_rate` 现缺失，导致现表格该列一直无着色，
  顺手补齐，阈值与 `verdict.py` 的 0.52 同步）;
- ⑥ OOS 符号一致是双字段比较（`ic_mean` 与 `oos_ic_mean` 同号），不进 GATES 表，
  在 `gateTrack` 内单独判；
- run 未设 split → ⑥⑦ 置 `na`。判别依据只看 `run.params.split`（由父组件传入），
  不从 OOS 字段值反猜（无 split 时后端存 0.0，会与真实 0 混淆）。

前端重算与后端 `reasons` 权威留痕之间的阈值同步问题是**既有债 D2**（`gates.ts` 头注释
已声明），本设计不扩大也不收敛该债：轨道与现表格单元格着色同一现状口径；
**弹框内的逐关明细则直接渲染后端 reasons 原文**（权威真相），两层各司其职。
`neutralized_ic` 闸只存在于 reasons 里（数值未入库）→ 轨道不含它、弹框明细自然含它，
文档口径以弹框为准。

### 4.3 卡片状态

| 状态 | 表现 |
|---|---|
| 默认 | `--bg-2` 底 + 1px `--border`，左缘判决色条 |
| hover | 边框转 `--accent`，`translateY(-1px)`（`@media (prefers-reduced-motion)` 下禁位移） |
| focus-visible | 全站既有焦点环 token |
| 进场 | 网格首渲 30ms/卡 stagger fade-up，上限 12 卡后不再延迟；仅 motion-safe |

## 5. 排序与过滤

结果区头一行工具条（run 下拉右侧）：

- **过滤**：分段控件 `全部 12 · PASS 3 · FAIL 9`（带实时计数）。默认"全部"。
  过滤后 0 卡显示行内空态：「无匹配因子 — 清除过滤」（带一键清除）。
- **排序**：`NSelect`（小尺寸），选项与 objective 联动取字段：

| 选项 | 键 | 说明 |
|---|---|---|
| 判决 + 评分（默认） | passed 降序 → score 降序 | "放榜序"：能用的在前，组内择优 |
| 评分 | score 降序 | 忽略判决，看综合分 |
| IC 均值 | ic_mean 降序 | 预测力 |
| 样本外变现 | oos_top_excess_return / oos_long_short_return 降序 | 按 objective 取键 |
| 提交顺序 | 入库原序 | 与后端返回一致（factor_id 序） |

- null 值一律排队尾（旧数据 score 可能为 null）。
- 实现为纯函数 `sortFactors(factors, key, objective): VerdictFactor[]` +
  `filterFactors(factors, filter)`，新文件 `pages/verdicts/sort.ts`，Vitest 直测
  （null 排序、objective 切键、稳定性）。
- 排序/过滤状态为页面级 ref，**不持久化**（切 run 保留，刷新重置，YAGNI）。
- 弹框的"上一个/下一个"遍历序 = 当前过滤 + 排序后的可见序列（所见即所得）。

## 6. 详情弹框（全站首个 modal 规范）

### 6.1 选型

用 **naive-ui `NModal`**（`preset="card"` 关闭，走默认插槽自定义内容）。理由：
naive-ui 已是运行时依赖（表单组件在用），NModal 免费提供 focus-trap、Esc 关闭、
遮罩点击关闭、滚动锁定、挂载 body 层，这些自研成本高且易错；样式层用项目 token 覆盖，
不引入 naive 视觉。备选"侧滑 drawer"被否：细节内容是"对照阅读"型（IS vs OOS 表），
居中宽幅比窄侧栏更适合表格排版；备选"行内展开大卡"被否：会把网格撑出布局抖动，
且无法承载弹框级信息量。

规范固化（后续页面复用同参数）：

- 尺寸 `width: min(760px, 92vw)`，`max-height: 84vh`，内容区 `overflow-y: auto`；
- 遮罩 `rgba(0,0,0,.4)`（naive-ui 默认色，天然吻合，无需覆盖）+ `backdrop-filter: blur(2px)`
  （深浅主题同参；实现记录：NModal 非 preset 模式下组件自身的 `style`/`overlay-style`
  落到内容子节点而非遮罩元素上，遮罩模糊需要一段非 scoped CSS 直接命中 naive-ui 内部
  的 `.n-modal-mask` 类名才能生效——见 `FactorDetailModal.vue` 实现）；
- 容器 `--bg-2` 底（`--bg-1` 不存在，token 表最浅一级是 `--bg-2`）、1px `--border`、
  `border-radius: var(--radius)`（`--radius-lg` 不存在，token 表只有 `--radius`/`--radius-sm`
  两级）、24px 内边距；
- 关闭途径：Esc / 遮罩点击 / 右上关闭钮，三者等价；
- 进出场沿 NModal 默认 scale-fade，不另配。

### 6.2 内容结构（自上而下）

```
┌────────────────────────────────────────────────┐
│ momentum_20d  20 日动量        [B 72]  [FAIL]  ✕ │ ← 头部: 身份+结论
│ 3 因子 · 长多 · 切分 2024-06-30 (轮次上下文, 次级小字)   │
│ ─────────────────────────────────────────────── │
│ expression: rank(close/delay(close,20))  (mono 代码条) │
│                                                  │
│ 指标对照                    IS         OOS       │
│   IC 均值                 .0312      .0198      │ ← gate 着色沿 gateClass
│   超额IR / IR              0.82       0.55      │
│   超额正率 / IC正率         54.1%      51.2%     │
│   单调性                   0.52        —        │ ← OOS 未入库项显 —
│   Top超额 / 多空收益        +4.1%     +3.2%     │
│                                                  │
│ 逐关判定 (后端权威留痕, 含中性化闸)                     │
│   ✓ IC=0.0312 >= 0.02                            │
│   ✗ 单调性=0.52 < 0.6 (单调性不足)      ← 失败行红底 │
│   ✓ 样本外IC符号一致: IS=0.0312 vs OOS=0.0198      │
│   …                                              │
│ ─────────────────────────────────────────────── │
│ ‹ 上一个 (pe_ttm)      3 / 12      下一个 (roe_q) › │ ← 底部导航
└────────────────────────────────────────────────┘
```

- **头部**：factor_id（mono 加粗）+ 中文名 + grade/score 徽章 + PASS/FAIL 大徽章。
  下挂一行轮次上下文（`buildVerdictRunLabel(run).title`）——弹框遮盖页面后
  用户不丢失"我在看哪轮"。
- **指标对照表**：行=指标、列=IS/OOS 的两列窄表，替代原表格的 8 列横排；
  行标签随 objective 显示对应口径名，数值沿 `gateClass` 着色 + GlossaryTip 术语提示。
  OOS 侧无对应入库字段的行（单调性、评分）显 `—`。
- **逐关判定**：reasons 数组逐条渲染为列表行（非 chip 流）：`isPassReason` 判 ✓/✗，
  失败行 `--c-fail` 12% 混合底。这是后端权威留痕，包含轨道没有的中性化闸。
- **底部导航**：‹ ›按钮（带相邻因子 id 预览）+ 位置计数；键盘 ←/→ 等效；
  到序列两端对应侧禁用（不循环）。导航序=当前过滤排序后的可见序列。

### 6.3 交互与 a11y

- 打开：卡片 click/Enter/Space。关闭后焦点还原到来源卡片（NModal 默认行为，验收时确认）。
- 弹框打开时 ←/→ 被导航占用；Tab 序被 trap 在弹框内。
- 标题行做 `aria-labelledby` 源；judgment 徽章带 GlossaryTip 的 pass/fail 术语解释（沿现状）。

## 7. 数据与兼容

- **零后端改动**：全部数据来自现有 `/api/research/verdicts` 返回。
- `VerdictFactor` 前端类型不变；新增的 `gateTrack/sortFactors` 均是对现有字段的纯计算。
- 兼容旧数据：score/grade 为 null、reasons 为空数组、OOS 字段为 0 且无 split、
  '√'(U+221A) 历史判定符 —— 现有防御逻辑（`isPassReason` 双符号兼容等）全部保留。

## 8. 组件拆分与文件变更

| 文件 | 动作 | 职责 |
|---|---|---|
| `pages/Verdicts.vue` | 重构 | 编排：数据加载、run 选择、过滤排序状态、弹框开关；目标瘦身到 ~250 行 |
| `pages/verdicts/FactorCard.vue` | 新增 | 卡片展示（props: factor, objective, split）+ click/keyboard 事件 |
| `pages/verdicts/FactorDetailModal.vue` | 新增 | 弹框全部内容 + 前后导航（props: factors 可见序列, index; emit: navigate, close） |
| `pages/verdicts/FactorTestForm.vue` | 新增（抽取） | 检验表单整块平移（chips/字段/提交/JobCard），行为零改动；JobCard 完成回调改为 `emit('done')` 由父页刷新判决列表 |
| `pages/verdicts/sort.ts` | 新增 | `sortFactors` / `filterFactors` 纯函数 |
| `pages/verdicts/gates.ts` | 扩展 | 补 `ic_positive_rate/excess_positive_rate` 闸键；新增 `gateTrack()` |
| `pages/verdicts/__tests__/sort.spec.ts` | 新增 | 排序/过滤纯逻辑 |
| `pages/verdicts/__tests__/gates.spec.ts` | 新增 | gateTrack（含 na 判定、objective 切换）— 顺手补上 gates.ts 现存"无覆盖测试"缺口 |

检验表单抽组件的理由：置顶后它是页面第一屏主角，独立组件让 Verdicts.vue 回归编排职责；
抽取是纯平移（模板+其 ref 打包搬走），不改行为。

## 9. 测试与验收

1. **Vitest**：sort.ts 全分支；gateTrack 的 pass/fail/na 三态与 objective 联动；
   FactorCard 渲染快照（PASS 无死因行 / FAIL 有）；Modal 导航边界（首/尾禁用）。
2. **既有测试**：`run-naming.spec.ts` 不受影响；全套 `npm run test / typecheck / lint`。
3. **构建链**：`npm run build` → `scripts/check_frontend_fresh.py` 过。
4. **ui_smoke**：`ft-factor-chip` 锚点**保留原值**（smoke 断言不破坏）；
   卡片新增 `data-testid="verdict-card"`、弹框 `verdict-modal`、
   工具条 `verdict-sort/verdict-filter`——smoke 的 verdicts 锚点数组**不新增断言**
   （空库时卡片不存在会误报），截图自然覆盖新版式。
5. **读图自查**：`frontend/scripts/shot.py verdicts` 双主题截图 + `ui_smoke.py --deep`
   跑一次真因子检验闭环（提交 → JobCard → 完成刷新 → 新卡片出现）。
6. **交互验收清单**：Esc/遮罩/关闭钮三途径关闭；←/→ 导航尊重过滤排序；
   焦点还原到来源卡片；reduced-motion 下无位移动画；深浅主题下轨道三态可辨。

## 10. 备选方案与取舍记录

| 备选 | 结论 | 理由 |
|---|---|---|
| 保留表格 + 卡片双视图切换 | 否 | 双视图双倍维护，卡片+弹框已覆盖表格的密度优势场景 |
| 行内展开大卡替代弹框 | 否 | 网格布局抖动，信息量放不下 |
| 侧滑 drawer 替代居中弹框 | 否 | IS/OOS 对照是宽幅阅读，窄侧栏排不开 |
| 自研 modal | 否 | focus-trap/滚动锁定/层级管理自研易错，naive-ui 已在依赖内 |
| 排序状态持久化 localStorage | 否 | YAGNI，默认"放榜序"已覆盖主场景 |
| 闸门轨道从 reasons 字符串解析 | 否 | 字符串脆；数值字段重算与表格着色同口径，reasons 留给弹框做权威明细 |

## 11. 风险

- **阈值双源漂移（既有债 D2）**：`verdict.py` 改阈值而 `gates.ts` 未同步时，
  轨道/着色与 reasons 结论可能不一致。本设计维持现状债规模，弹框以 reasons 为权威
  已给出兜底口径；收敛方案（后端下发阈值）另立项。
- **一轮因子数极大**（>60，如未来全因子面板）：网格仍可滚动但扫读优势衰减；
  过滤器 + 排序缓解，必要时再加分页，本次不做。
- **NModal 主题覆盖成本**：naive-ui 组件样式需 token 化覆盖；表单组件已有同类先例
  （NSelect/NDatePicker 已在用），风险低。
