# 投研驾驶舱前端体验整改 — 设计文档

- 日期：2026-07-10
- 状态：待评审
- 范围：`frontend/`（Vue3 + Vite + TS），六页驾驶舱
- 依据：2026-07-09 十维设计审核（Playwright 双主题读图 + 全量源码走查 + WCAG 对比度实算 + Nielsen 启发式）

## 1. 背景与目标

十维审核给出总分 **65/100**，结论是「工程质量明显高于体验完成度」：竞态守卫、轮询暂停、防错设计扎实，但三块系统性洼地拉低整体——

1. **无障碍 4/10**：3 条核心业务流对键盘用户完全不可用；亮色主题 12 组语义色实测不达标 WCAG AA。
2. **交互反馈缺口**：4 个任务提交按钮 3 个无 pending 态；长任务零完成通知；日志强制滚底；Live 页加载态冒充空态。
3. **设计系统半成品**：色彩令牌化 98%（强），但字号/间距完全无标尺（146+169 处裸 px）；同一套品牌色手抄在三处已漂移。

本轮目标：把这三块洼地填平，让体验完成度追上工程质量，并把 WCAG 2.2 AA 作为硬门槛。

### 已锁定的三个决策（用户拍板）

| 决策 | 结论 |
|---|---|
| 修复范围 | **全部三档**（速赢 + 中等 + 战略）一次立项，分批实施 |
| 收益/盈亏正负号配色 | **全站统一 A 股行情色**（涨/正=红，跌/负=绿），回测表加图例 |
| 导航顺序 | **按流水线重排**：总览 / 行情 / 判决 / 回测 / 实盘 / 任务 |

### 执行策略：地基优先

审核约 40% 的修复项（对比度整改、badge 抽象、间距收敛）都要消费令牌。因此**先建令牌地基，再往上叠**，避免「速赢档用硬编码修对比度 → 战略档再令牌化」的返工。据此拆成 11 个依赖有序的阶段（§12）。

## 2. 非目标（本轮不做）

- **后端改动**：本轮限定 `frontend/`。唯一例外见 §11（gates 404 实为陈旧服务进程，重启即解，不改代码）。
- **新功能**：不加页面、不加业务能力，只改既有界面的体验与合规。
- **换 UI 框架 / 图表库**：naive-ui、ECharts 保留。
- **移动端完整适配**：这是刻意的桌面工具，仅做「窄屏不崩」的兜底（§10），不做移动端专属布局。
- **重构无关代码**：不碰与本轮目标无关的领域/应用层。

## 3. 设计原则

1. **令牌单一真相源**：颜色/字号/间距/圆角/阴影/动效/层级/断点全部走令牌，使用点零硬编码（图表 JS option 内的少量值通过助手函数消费令牌）。
2. **合规是门槛不是加分**：WCAG 2.2 AA 为硬性验收，P10 用 axe-core + 人工键盘走查 + 对比度复算三重把关。
3. **一处修复推广全站**：重复模式（页头/徽章/表格）抽成组件，修一次全站受益，不再逐页打补丁。
4. **渐进 + 检查点**：分批实施，每批实施完过一次验收（build/typecheck/vitest/ui_smoke）再进下一批，可评审可回滚。
5. **保留既有优点**：glossary 术语教学体系、金融风险披露、实盘只读红线、竞态守卫、reduced-motion 令牌归零——这些是审核认定的标杆项，整改中不得破坏。

## 4. P0 — 令牌地基（tokens.css / base.css / theme.ts）

这是全部下游的依赖。所有色值经本设计独立用 WCAG 相对亮度公式复算（见 §4.5 验证记录）。

### 4.1 新增令牌类别

```css
:root {
  /* 字号：6 档，取代现状 15 档（含 5 个半像素值）。modular-ish，行高配套 */
  --fs-xs: 11px;   --lh-xs: 1.5;
  --fs-sm: 12.5px; --lh-sm: 1.5;
  --fs-base: 14px; --lh-base: 1.6;
  --fs-md: 15px;   --lh-md: 1.65;   /* body 基准 */
  --fs-lg: 20px;   --lh-lg: 1.3;
  --fs-xl: 26px;   --lh-xl: 1.2;    /* KPI 大数 */

  /* 间距：4px 基网格，取代 169 处裸 px。允许 1-2px hairline 例外 */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px;
  /* 既有 --gap/--gap-lg 保留为 --space-4/--space-5 别名，减少迁移面 */

  /* 层级阶梯，取代魔数 100/50/-1 */
  --z-bg: -1; --z-base: 1; --z-sticky: 100; --z-popover: 200; --z-modal: 300;

  /* 断点（登记为约定；CSS 变量进不了 media query，仅作单一出处注释引用） */
  /* --bp-wide: 1080px; --bp-mid: 860px; --bp-narrow: 640px */
}
```

### 4.2 状态色三件套（取代 21 处现场 color-mix）

暗/亮各定义，统一淡底比例（现状 14%/16%/18% 三种不一 → 收敛）。

```css
:root[data-theme='dark'] {
  --c-pass-soft: rgba(139,163,107,.16); --c-pass-border: rgba(139,163,107,.42);
  --c-fail-soft: rgba(229,115,90,.16);  --c-fail-border: rgba(229,115,90,.42);
  --c-warn-soft: rgba(217,169,87,.16);  --c-warn-border: rgba(217,169,87,.42);
  --c-info-soft: rgba(106,155,204,.16); --c-info-border: rgba(106,155,204,.42);
  --c-info: #6a9bcc;               /* 补 info 语义色（LvBadge 现回退 bg-3） */
  --text-on-accent: #141413;       /* 5.90:1 on accent，取代硬编码 #faf9f5(2.96:1) */
  --border-input: #726f68;         /* 3.32:1 on bg-2，取代 --border(1.42:1) 用于表单控件 */
}
:root[data-theme='light'] {
  --text-on-accent: #141413;       /* 5.90:1 on accent */
  --border-input: #827f78;         /* 3.50:1 on bg-2 */
  --c-info: #46708f;               /* 亮色达标蓝，见 §4.3 */
  /* pass/fail/warn/info 的 -soft(统一 12% 淡底) / -border(38%) 四组，
     取亮色整改后的 §4.3 色值按暗色块同结构定义 */
  --c-pass-soft: rgba(90,107,64,.12);  --c-pass-border: rgba(90,107,64,.38);
  --c-fail-soft: rgba(171,69,48,.12);  --c-fail-border: rgba(171,69,48,.38);
  --c-warn-soft: rgba(138,102,38,.12); --c-warn-border: rgba(138,102,38,.38);
  --c-info-soft: rgba(70,112,143,.12); --c-info-border: rgba(70,112,143,.38);
}
```

### 4.3 亮色主题对比度整改（12 组 FAIL → 全部达标）

审核实测亮色语义色近乎全线崩坏。替换值（均经复算，正文档 ≥4.5:1）：

```css
:root[data-theme='light'] {
  --text-3: #64625a;        /* 4.17 → 5.36:1 */
  --accent-strong: #a8462e; /* 新增：文字级 accent，5.14:1。--accent 保留给填充/边框 */
  --c-up: #ab4530;   --c-buy: #ab4530;  --c-fail: #ab4530;  /* 3.97 → 5.08:1 */
  --c-down: #5a6b40; --c-sell: #5a6b40; --c-pass: #5a6b40;  /* 3.79 → 5.10:1 */
  --c-warn: #8a6626;        /* 2.72 → 4.59:1 */
  --accent-blue: #46708f;   /* 2.57 → 4.63:1 */
}
```

文字用色切换：`base.css` 的 `a{color}`、`.router-link-active`、SubNav `.active` 等**文字**场景改用 `var(--accent-strong, var(--accent))`（暗色不定义 `--accent-strong` 即回退原 accent，暗色本就达标）。填充/边框场景仍用 `--accent`。

### 4.4 暗色主题边缘修 + 全局原语

```css
/* 暗色三处边缘不达标 */
/* badge.running 文字 → #e08a6d (4.39 → 5.24:1) */
/* badge.failed  文字 → #ef8069 (4.33 → 4.98:1) */
/* .run-id 删除 opacity:.75（3.98 → 恢复 5.98:1） */

/* base.css 全局新增 */
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button:active { transform: scale(.98); }          /* respect reduced-motion */
.sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px;
           overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }

/* 骨架屏动画补 reduced-motion 归零（现绕开了令牌归零机制） */
@media (prefers-reduced-motion: reduce) { .kpi-skeleton { animation:none; opacity:.7; } }
```

### 4.5 theme.ts 联动

- `Button.textColorPrimary/Hover/Pressed/Focus = #141413`（主按钮白字 2.96:1 → 墨黑 5.90:1）。
- 死令牌处理：`--accent-green`、`--neutral` 全站 0 引用，但其值又硬编码在 useChartTheme.ts。P1 接活（令牌化）或删除，二选一。

### 4.6 对比度复算验证记录（本设计独立复算，非引用审核）

| 值 | 场景 | 复算比值 | 判定 |
|---|---|---|---|
| `#141413` on `#d97757` | 主按钮/激活 chip | 5.90:1 | PASS |
| `#faf9f5` on `#d97757` | 旧白字（对照） | 2.96:1 | FAIL ✓识别正确 |
| `#64625a` on 亮 bg-2 | text-3 | 5.36:1 | PASS |
| `#a8462e` on 亮 bg-2 | accent-strong | 5.14:1 | PASS |
| `#ab4530` / `#5a6b40` on 亮 bg-2 | 涨跌/判定 | 5.08 / 5.10:1 | PASS |
| `#8a6626` on 亮 bg-2 | c-warn | 4.59:1 | PASS |
| `#46708f` on 亮 bg-2 | accent-blue | 4.63:1 | PASS |
| `#726f68` on 暗 bg-2 | border-input | 3.32:1 | PASS(UI 3:1) |
| `#827f78` on 亮 bg-2 | border-input | 3.50:1 | PASS(UI 3:1) |

> 注：审核给的 border-input 建议值（暗 `#5d5a51`/亮 `#a5a294`）经复算实为 2.42/2.25:1 **不达标**，已由本设计解算替换为上表达标值。这是分批实施前独立验证的价值。

## 5. P1 — 三源调色板同源化

同一套品牌色手抄三处：tokens.css（CSS 变量）、theme.ts（23 hex naive 覆盖）、useChartTheme.ts（36 hex ECharts）。且已出现值漂移（chart `panelBg:#ffffff` 与 naive `inputColor:#ffffff` 在 tokens 中无对应令牌）。

- **策略**：运行时 `getComputedStyle(document.documentElement).getPropertyValue('--x')` 读取令牌，供 theme.ts / useChartTheme.ts 消费，消除手抄。naive-ui 因 prop 驱动、ECharts 因 setOption 显式控制，两者确实无法直接吃 CSS 变量，故用「读令牌 → 注入」桥接。
- **兜底防线**：加一个 vitest spec，断言三源关键色同值（若运行时读取改造成本高，至少先上这条断言，把「改 tokens 一处不改另两处」变成红灯）。
- **图表主题内部去重**：`EquityChart.vue` 逐字重抄了 `useChartTheme.ts` 的 tooltip 样式串，改为 import `tooltipStyle()` 助手（同仓已有正确复用样板 chart-options.ts）。

## 6. P2 — 语义横扫

### 6.1 涨跌色统一规则（全站）

现状：回测页收益正号用 `t-pass`（判定绿），实盘页用 `t-up`（行情红），同量反色。统一规则：

| 语义 | 用色 | 适用 |
|---|---|---|
| **行情色**（`--c-up` 红 / `--c-down` 绿） | 任何**带符号的收益率/盈亏额/超额收益** | 回测总收益·年化·超额·OOS超额；实盘累计收益·持仓盈亏；因子超额 |
| **判定色**（`--c-pass` 绿 / `--c-fail` 红） | **PASS/FAIL 闸门判定**（此处绿=判定通过，非价格方向） | 因子卡 PASS/FAIL 徽章·闸门轨道 |
| **中性色**（`--text`） | **质量指标**（越大越好但非涨跌） | 夏普·Calmar·索提诺·胜率·换手 |

理由：一个界面一条颜色轴。收益符号是价格方向的类比 → 行情色；质量指标不是涨跌，强行上红绿会出现「好夏普显红」的怪象 → 中性。判定徽章是 PASS/FAIL 文字块，与数字视觉分离，图例覆盖即可。

**落地**：回测指标表 `总收益/年化/超额` 的 `t-pass/t-fail` 类改为 `t-up/t-down`；质量指标列去色；回测「净值与回撤」区加一次性图例「红=正收益/涨，绿=负收益/跌（A股行情色）」。实盘页已是行情色，不动。

### 6.2 导航重排

`router.ts` `NAV_ITEMS` 顺序改为 `总览 / 行情 / 判决 / 回测 / 实盘 / 任务`，与总览页 PipelineMap 教给用户的「数据→判决→回测→实盘」心智一致。路由 name 不变，仅数组顺序变，改动面极小、可逆。

## 7. P3 — 共享组件抽象

| 新增/改造 | 取代 | API 契约 |
|---|---|---|
| `PageHeader.vue`（新） | `.page-head + .guide` 六页逐字复制 | `props: { title, meta?, guide? }` + `#guide` 插槽 |
| `AppBadge.vue`（新） | 8 份 badge 变体（含两处逐字节相同） | `props: { kind: 'info'\|'pass'\|'warn'\|'fail'\|'accent', size? }`，消费 §4.2 状态色三件套 |
| `DataTable.vue`（改） | 5 份 th/td 配方拷贝（字号 padding 已漂移） | 表头统一出 `scope="col"`；密度 prop；`clickable` prop（仅监听 rowClick 时才给 hover 高亮+cursor，堵住幽灵点击） |
| `ErrorBanner.vue`（改） | 现底色误用品牌橙 `--accent-soft`（应为失败红） | 底色改 `--c-fail-soft`；加可选 `@retry` emit + 重试钮；加关闭钮 |

命名一致性顺带收敛：`ErrorBanner` 的 `msg` → 与全站一致的完整词；`.section-title`/`.section-label` 双名归一。

## 8. P4 — 无障碍硬化（冲 WCAG 2.2 AA）

### Critical（键盘用户核心功能不可用）
- **C1** `Jobs.vue` 任务行 `<tr @click>` → ID 单元格内真 `<button>` 承载钻取，`aria-expanded` 标注。
- **C2** `CyclesTable.vue` 循环行 → 首列真 `<button>` + `aria-expanded` + `aria-label`，caret 保持 `aria-hidden`。
- **C3** `Backtests.vue` 轮次删除 `<span @click>` 嵌在 `<button>` 内 + `opacity:0` 仅 hover：`.run-row` 改 `<div>` 容器 + 内部两个平级 `<button>`（主体/删除），删除钮补 `:focus-visible` 显形。

### Serious
- **S1 GlossaryTip 焦点可达**（118 处术语层现 hover-only）：触发 span 加 `tabindex=0 role=button`，`NPopover` 改 manual + `@focus/@blur/@mouseenter/@mouseleave/@keydown.escape` 控制，满足 1.4.13。
- **S5 图表替代文本**：4 处 ECharts 容器加 `role="img"` + 动态 `aria-label`（含标的/区间/曲线数摘要），启用 ECharts `aria: { enabled: true }`。
- **S6 aria-live**：任务状态徽章 `role=status aria-live=polite`；chips 校验错误 `role=alert`。
- **S7 NSelect 可及名称**：全部 NSelect 透传 `aria-label`（判决轮次/排序/基准/叠加/mode/审计筛选）。
- **S8 联想 combobox**：input `role=combobox aria-autocomplete=list aria-expanded aria-controls aria-activedescendant`，`ul role=listbox`/`li role=option`，上下键 + Esc（同时满足 §9.交互）。
- **S9 触点 ≥24px**：统一工具类给 chip-x/panel-remove/vm-close/run-delete/cancel/filter-seg 等 `min 24×24`。

### Moderate / Minor
- th `scope="col"`（多数经 P3 DataTable 归口一次解决）；空 th 补 `.sr-only`。
- `aria-current`（SubNav 当前页签）、`aria-pressed`（filter-seg）。
- **document.title 随路由更新**：`router.afterEach` → `「{页名} · GoldenHand 投研驾驶舱」`。
- 字段错误 `aria-describedby` + `aria-invalid`；必填组标「（至少选 1 项）」。
- 模态标题 span → `<h3>`（修 h2→h4 跳级）。
- skip link「跳到主内容」；`scrollIntoView` 检测 reduced-motion；禁用态去删除线改 dashed+后缀文本。

## 9. P5 — 交互状态补齐

- **提交 pending**（3/4 缺失）：`Jobs.vue` 训练/评估、`BacktestForm`、`FactorTestForm` 加 `:loading :disabled` + submitting ref（照 `Overview.vue:134` 样板）。
- **日志近底跟随**：仅当 `scrollHeight-scrollTop-clientHeight < 40` 才自动滚底，离底显「↓ 回到最新」浮钮（`Jobs.vue`/`JobCard.vue`）。
- **KpiCard 从旧值滚**：记录上次终值，避免刷新时 646 万先归零再滚（读作数据被清空）。
- **叠加对比 run_id 修 bug**：overlay 选项 value 从数组下标改 `run_id`；reload 后若原 `selectedRunId` 仍在则保留选中（现删任意轮致已选曲线静默错位——数据误读风险）。
- **基准切换占位**：加载期保留「基准计算中…」占位，消除控制条宽度跳变。
- **循环明细重试**：`CyclesTable` 展开条件改 `if (!details[id] || details[id]==='error')`（现 `'error'` truthy 致重展开不重拉）。
- **缺失骨架**：Backtests 左轨+详情、Live KPI/各表加骨架（现空态文案冒充加载态）。
- **空态 CTA**：Backtests 空态从「跑 CLI 命令」改引导页内「新建回测」表单，CLI 作补充。
- **任务完成通知**：naive `useNotification`（NConfigProvider 已就位）done/failed 弹非阻塞通知 + `document.title` 加「✓」前缀。
- **取消确认 + 乐观反馈**：套 NPopconfirm（Backtests 已有样板）；点击后行内乐观置「取消中…」并禁钮；仅静默 404/409，其余走 ErrorBanner。
- **dead 态重试**：JobCard 5 连败后加「重试」钮，重置 failCount 重启轮询。
- **Live 分频轮询**：概览端点常轮 5s，非激活子视图端点降频 30s 或切到该视图才启动。
- **Overview JobCard 移出 details**：提交后运行中任务不随折叠消失。

## 10. P6 — 基础设施与错误处理

- **任务轮询上移 App 级全局**（审核判定最高危）：现顶栏「任务」徽章只由 `Jobs.vue` 回填，别页提交后徽章永不亮；且 503 写锁友好文案以此计数为条件一并失效。改为 App 级全局轮询，徽章与 503 文案共用始终鲜活的计数。
- **fetch 错误分类中文化**：默认通道现直出 `500 /api/...:{"detail":...}` 英文技术串。按 status 映射三段式中文（404 记录不存在 / 422 参数校验 / 500 服务内部错误 / TypeError 无法连接服务），原始串收进可展开「技术详情」。503 写锁文案已是样板，推广之。
- **usePolling 补强**：失败退避（间隔 ×2 封顶 60s，成功复位）+ `isStale`（超 2×interval 未成功即陈旧，页面显「数据更新于 HH:mm · 连接中断」）+ 每 tick AbortController 取消在途。
- **PipelineMap 区分错误 vs 空**：三个 catch 现静默置 null，把「接口挂了」呈现成「没有实盘留痕」的业务事实。catch 里区分 error 态，节点显「数据不可用」+ warn 色。
- **表单校验**：四表单加日期区间校验（起<止、切分日在区间内）；`cost_rate` 补 `:min=0`；`model_name` 模式校验从 tooltip 落到输入框。

## 11. gates 404 更正（移出代码范围）

审核速赢清单原列「修 gates 404」。经排查：后端 `meta.py:49` 确有 `@router.get("/gates")`，同文件 `strategies`/`factors` 实时 200、唯 `gates` 404，因该路由 2026-07-05 14:48 才入代码，而 8501 上运行的是更早启动的服务进程。**结论：陈旧进程，重启 dashboard 即解，不改任何代码。** 本项从范围剔除。

> 可选加固（不阻塞）：`gates.ts` 端点不可达时现静默回退硬编码阈值 + console warn。按 D2 单一真相源设计意图，回退应在 UI 可见（否则显示的 PASS/FAIL 可能与后端实际阈值不一致而用户不知），可在判决页头挂一枚「阈值回退中」小标。列为 P8 内容项，非硬性。

## 12. P7-P9 增强档

- **P7 URL 状态化**：回测轮 `run_id`、判决轮、行情标的组合入 query 参数（现仅 `/live/:view?` 入路由）。研究结果可深链/收藏/贴进复盘笔记。用 `router.replace` 避免污染历史。
- **P8 内容 i18n**：孤儿 glossary 词条（`score/verdict_badge/oos_ic/oos_ir/ls_oos` 5 个 0 引用）接线到对应 UI（IS/OOS 列头、grade 徽章）或删除；英文枚举中译（`enabled/disabled`、审计动作 `cycle_start/place_order_failed`、job_type）；运行副标题日期显示年份（现 `slice` 省年，跨年无法分辨）；数字精度统一（持仓盈亏 1 位 vs KPI 2 位 vs 回测 2 位）。
- **P9 字体 + 响应式兜底**：Lora/Poppins 仅拉丁字形，中文正文依赖系统回退彩票。用 fonttools 子集化思源宋体常用字自托管打进 bundle（与现有 @fontsource 策略一致，无 CDN）。响应式兜底：窄屏顶栏 `flex-wrap`；数据密集表格包 `overflow-x:auto` 横滚容器。

## 13. P10 — 验收

每批实施后必跑，全部绿灯方进下一批：

```bash
# 前端（Windows 侧 npm，铁律）
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck"
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test"
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run build"   # 写 static/ 入库
$WIN_PYTHON scripts/check_frontend_fresh.py    # 漂移防线
$WIN_PYTHON scripts/ui_smoke.py                # 六页锚点截图 + console 零错
```

- **对比度复算**：P0 改动后重跑本设计的 WCAG 复算脚本，双主题全表 PASS。
- **无障碍**：P4 后 ui_smoke 注入 axe-core，纳入冒烟；人工 NVDA + 纯键盘走查六页（重点：删除回测轮、联想第 2 条候选、GlossaryTip、任务行钻取、循环展开）。
- **读图自查**：每批后 Claude 读 `data/ui_screenshots/` 双主题截图，肉眼核验无回归。

## 14. 分批与检查点

| 批次 | 阶段 | 验收检查点 |
|---|---|---|
| **批一 · 地基** | P0 令牌 → P1 三源 → P2 语义 → P3 组件 | 对比度全 PASS；六页视觉无回归；typecheck/test/build/smoke 绿 |
| **批二 · 硬化** | P4 无障碍 → P5 交互 → P6 基础设施 | axe-core 零 violation；键盘走查通过；反馈闭环手测 |
| **批三 · 增强** | P7 URL → P8 内容 → P9 字体响应式 | 深链可用；中文字体落地；窄屏不崩 |

每批一份 writing-plans 计划，实施走 executing-plans 检查点机制。批一通过再出批二计划。

## 15. 风险与回滚

| 风险 | 缓解 |
|---|---|
| P0 令牌重命名波及全站，一次改崩 | 保留 `--gap/--gap-lg` 为新令牌别名；分文件迁移；每步 build 验证 |
| P3 组件抽象改变 6 页结构，回归面大 | 先建组件 + 单页接入验证，再逐页迁移；vitest 覆盖组件 API |
| 三源同源运行时读取改造成本超预期 | 降级为「先上断言 spec」把漂移变红灯，运行时读取可延后 |
| 涨跌色统一后老用户瞬时不适 | 图例常驻；实盘页本就行情色，仅回测页变，且方向与真钱侧对齐 |
| 中文字体子集化漏字 | 子集覆盖 GB2312 常用字 + 界面实际用字扫描并集；保留系统回退兜底 |
| 全量工作量数周，中途需求变化 | 分批立项，每批独立可交付；批间检查点可叫停或调整后续批次 |

## 16. 保留清单（整改中不得破坏的标杆项）

glossary 48 词条术语教学 · 金融风险主动披露（超额偏乐观 2~3%/年等）· 实盘只读三重声明 · 截面策略自动禁用标的框 · 多因子无切分日多重检验警告 · usePolling 页签隐藏暂停/恢复即刷/迟到响应丢弃 · reduced-motion 令牌级归零 · 买卖 ▲▼ 形状区分（非仅颜色）· 模态焦点管理 · 删除二次确认三行说明。
