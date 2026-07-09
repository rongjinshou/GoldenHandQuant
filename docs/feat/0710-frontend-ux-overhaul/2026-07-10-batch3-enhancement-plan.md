# 批三·增强（P7-P9）实施计划（subagent 并行版）

> 5 路并行，按页面独占文件（同批二切分），中央集成。设计依据 design §12（P7-P9）。

## 范围调整（务实决定）
- **P9 字体**：自托管中文 webfont 子集**不打进 bundle**——`static/` 已入库，@fontsource CJK 会灌入数十 MB 子集污染仓库。改为**强化 `--font-body`/`--font-display` 的系统 CJK 回退**（Microsoft YaHei / PingFang SC / Noto Serif SC / 思源系，零体积即时改善）。真正的 fonttools 子集化 webfont 另立专项，不在本批。
- **P8 glossary**：孤儿词条**接线**（加 GlossaryTip 用法），不删词条、不改 `glossary.ts`（词条已存在）；枚举中译用页面内 label map，不动 glossary.ts。→ `glossary.ts` 本批零编辑，无冲突。

## 文件所有权切分
| 流 | 独占文件 |
|---|---|
| Backtests | `pages/Backtests.vue`·`pages/backtests/**` |
| Verdicts | `pages/Verdicts.vue`·`pages/verdicts/**` |
| Explorer | `pages/Explorer.vue`·`pages/explorer/**` |
| Live-Jobs | `pages/Live.vue`·`pages/live/**`·`pages/Jobs.vue`·`components/JobCard.vue`·`pages/jobs/**` |
| Shared | `App.vue`·`styles/base.css`·`styles/tokens.css` |

## 各流任务

### Backtests
- **P7 URL 深链**：选中回测轮 `run_id` ↔ `?run=` query（`router.replace` 不污染历史）；挂载读 query 恢复选中；query 变化（前进/后退）响应。叠加对比 `?overlay=` 可选。
- **P8 日期显年**：`backtests/run-naming.ts` 副标题日期不再 `slice` 省年（跨年可分辨）；纯函数改动配单测。
- **P8 精度统一**：回测 pct/数值精度与全站对齐（若已一致则跳过并说明）。

### Verdicts
- **P7 URL 深链**：选中判决轮 ↔ `?run=` query；挂载恢复；前进后退响应。
- **P8 孤儿术语接线**：`oos_ic`/`oos_ir`/`ls_oos`/`score`/`verdict_badge` 五个 0 引用词条接到对应 UI——FactorDetailModal 的 IS/OOS 列头挂 `oos_ic`/`oos_ir`，grade 徽章挂 `score`，PASS/FAIL 徽章挂 `verdict_badge`（用 Wave1 已焦点可达的 GlossaryTip）。
- **P8 日期显年**：`verdicts/run-naming.ts` 同上。

### Explorer
- **P7 URL 深链**：标的组合 ↔ `?symbols=` query（逗号分隔）；挂载恢复并加载；前进后退响应。

### Live-Jobs
- **P8 枚举中译**：Live 审计动作 `cycle_start`/`place_order_failed` 等→中文 label map；`enabled`/`disabled`→「已启用」/「已停用」；Jobs 任务「类型」列 `job_type`（backtest/factor_test/data_refresh/ml_train/ml_eval）→中文。用页面内映射函数 + 单测，不改 glossary.ts。
- **P8 精度统一**：`live/logic.ts` 持仓盈亏 %（1 位）与 KPI 累计收益（2 位）等精度漂移，收敛到一致规则 + 单测。

### Shared
- **P9 响应式兜底**：`App.vue` 顶栏窄屏 `flex-wrap`（nav 换行不溢出/不遮挡）；`base.css` 加 `.table-scroll{overflow-x:auto}` 工具类（页面已多处有 overflow-x，补全局工具便于复用，不强制改页面）；`content` max-width 在超窄屏留边。
- **P9 CJK 字体栈**：`tokens.css` 的 `--font-body`（Lora 后补 'Microsoft YaHei','PingFang SC','Noto Serif SC','Source Han Serif SC',serif）与 `--font-display`（Poppins 后补 'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif）强化回退，未装机器不再退到默认宋。

## 铁律（各流）
- npm Windows 侧 powershell；纯逻辑 TDD；读文件测试用 fs。
- 只改独占文件；不跑 build/commit（中央做）；跑相关 vitest 确认绿。
- URL 深链用 `router.replace`（不 push），watch query 支持前进后退；挂载恢复要防「恢复→写回」死循环。
- 返回：改动清单/新增测试/typecheck·test 结果/关键决策/遗留。

## 集成验收
typecheck→test→lint→build→fresh→smoke 全绿；六页读图（深链手测：带 ?run=/?symbols= 刷新恢复）；提交 + batch3-done.md；三批毕走 finishing-a-development-branch。
