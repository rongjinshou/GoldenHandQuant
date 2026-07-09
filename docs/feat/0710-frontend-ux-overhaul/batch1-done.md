# 批一·地基（P0-P3）完成记录

- 完成日期：2026-07-10
- 分支：`feat/frontend-ux-overhaul`
- 提交：T1-T8 各一 commit（对比度守卫/base 原语/主按钮墨黑+三源断言/图表去重/导航重排/涨跌色统一/PageHeader/AppBadge+DataTable+ErrorBanner）

## 验收结果（全绿）

| 检查 | 结果 |
|---|---|
| `npm run typecheck` | 0 error |
| `npm run lint` | 0 error / 15 warning（全在既有 `chart-options.spec.ts` 的 `any`，非本批引入） |
| `npm run test` | 240 passed / 28 files |
| `npm run build` | ✓ built |
| `check_frontend_fresh.py` | OK（产物不落后源码） |
| `ui_smoke.py` | 六页锚点全 OK；FAIL 仅因 gates 404（陈旧服务进程，设计 §11，非代码） |
| 对比度守卫 spec | 3 passed（双主题达标） |
| 双主题读图 | 六页暗色目视零回归 |

## 交付项

- **P0 令牌地基**：字号 6 档 + 行高、间距 4px 标尺、层级阶梯、状态色 soft/border 三件套、`--text-on-accent`/`--border-input`/`--accent-strong`/`--c-info`；亮色 12 组对比度整改（text-3/accent-blue/c-up/down/pass/fail/warn 全达标）；暗色主按钮白字→墨黑（2.96→5.90:1）；全局 `:focus-visible`/`button:active`/`.sr-only`/骨架 reduced-motion。色值经 WCAG 公式独立复算（含更正审核给错的 border-input）。
- **P1 三源同源**：palette-sync 断言 spec 锁死三源关键色；EquityChart tooltip 改用 `tooltipStyle()` 助手消除逐字重抄。
- **P2 语义横扫**：导航按流水线重排（总览/行情/判决/回测/实盘/任务）；回测页收益/超额统一 A 股行情色（涨红跌绿，`marketCell`），夏普等质量指标转中性（`qualityCell`），回撤超阈红（`ddCell`），表加图例 caption。抽 `metric-cell.ts` 纯函数带单测。
- **P3 组件抽象**：`PageHeader`（六页 page-head/guide 去重，含 `#meta` 富内容插槽）；`AppBadge`（状态色三件套，accent 用 text-on-accent 达标）；`DataTable` th `scope=col` + `clickable` 门控（仅可点才 hover 高亮，堵幽灵点击）；`ErrorBanner` 底色 accent-soft 误用→c-fail-soft，加可选关闭/重试。

## 工具链变更

- 新增 dev 依赖 `@types/node@22` + tsconfig `types` 加 `"node"`：令读源文件做断言的守卫测试（对比度/三源同值）通过 typecheck。vitest `?raw` 对 CSS 在 jsdom 下不可靠，故走 `fs` 运行时读取。

## 显式遗留（移出批一，批二处理）

1. **FactorCard OOS超额 配色一致性**：回测页超额已翻行情色（正=红），但判决页 FactorCard 的 OOS超额仍判定色（正=绿）。设计 §6.1 把"因子超额"也列进行情色，但本批 T6 只 scope 了 Backtests.vue。**存在设计张力**：FactorCard 是判定主导面（PASS/FAIL 绿=好），若超额也翻红会与相邻绿 PASS 徽章冲突，违背"一面一色轴"原则。**批二定夺**：建议 FactorCard 保持判定色（判定面优先），或按 §6.1 翻行情色——批二规划时与用户确认。
2. **JobCard/Jobs 表状态徽章迁移 AppBadge**：本批只迁了 App 顶栏任务徽章验证组件。JobCard 状态徽章（queued/running/succeeded/failed/canceled 五态）随批二 JobCard 大改（完成通知/dead 重试/日志滚动）一并迁移，避免两次动其状态逻辑。
3. **px→token 全量机械迁移**：146 处裸字号 + 169 处裸间距。标尺已建、新/改动组件已消费，全量迁移为低风险增量清理，不阻塞验收，滚动进行。
4. **DataTable 四表归口**：Jobs/Backtests/PositionsTable/CyclesTable 手写表归口 DataTable 与键盘可达（C1/C2）强耦合，随批二无障碍一起做。

## gates 404 更正

后端 `meta.py:49` 有 `/gates` 路由，`strategies`/`factors` 实时 200 唯 `gates` 404，因该路由 2026-07-05 14:48 才入代码而 8501 服务是更早进程。**重启 dashboard 即解，不改代码，已移出范围。**
