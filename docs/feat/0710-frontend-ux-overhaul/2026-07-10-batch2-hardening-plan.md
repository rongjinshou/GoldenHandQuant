# 批二·硬化（P4-P6）实施计划（subagent 并行版）

> 执行方式：Wave1 地基（同步 subagent）先行 → Wave2 五路页面流并行 subagent（按目录切分文件所有权，互不冲突）→ 中央集成验收。设计依据 `2026-07-10-frontend-ux-overhaul-design.md` §8-§10。

## 文件所有权切分（防并行冲突铁律）

| Wave | 流 | 独占文件 |
|---|---|---|
| W1 | 地基 | `composables/usePolling.ts`·`api/fetch.ts`·`stores/jobs.ts`·`App.vue`·`router.ts`·`components/GlossaryTip.vue`·`components/SubNav.vue`·`components/KpiCard.vue` |
| W2 | Jobs | `pages/Jobs.vue`·`components/JobCard.vue`·`pages/jobs/**` |
| W2 | Live | `pages/Live.vue`·`pages/live/**` |
| W2 | Backtests | `pages/Backtests.vue`·`pages/backtests/**` |
| W2 | Verdicts | `pages/Verdicts.vue`·`pages/verdicts/**` |
| W2 | Explorer | `pages/Explorer.vue`·`pages/explorer/**` |

W2 各流只**消费** W1 改好的共享组件/infra，不编辑它们。

## Wave1 地基（P6 基础设施 + P4 共享 a11y）

1. **usePolling 补强**：加 `lastSuccessAt`/`isStale`（超 2×interval 未成功即 stale）；失败退避（间隔 ×2 封顶 60s，成功复位）；每 tick `AbortController` 取消在途。返回值**追加**字段，保持既有 API 向后兼容。
2. **fetch.ts 错误中文化**：status→三段式中文（404 记录不存在/422 参数校验失败/500 服务内部错误/网络错误 无法连接服务）；原始串保留进可展开详情。503 写锁文案样板保留推广。
3. **任务轮询全局化**：`stores/jobs.ts` 增 App 级轮询 `/api/jobs`（或等价）回填 activeCount，使徽章在任意页鲜活；`App.vue` 挂载即启动。修复 503 文案依赖 activeCount 失效。
4. **document.title 随路由**：`router.afterEach` → `「{页名} · GoldenHandQuant」`。
5. **GlossaryTip 焦点可达**：触发 span `tabindex=0 role=button`，NPopover 支持 focus/blur/Esc（满足 1.4.13）；API（`term` prop + 插槽）不变。
6. **SubNav aria-current**：当前项 `aria-current="page"`。
7. **KpiCard 从旧值滚**：记录上次终值，从旧值滚到新值（避免刷新归零）。

## Wave2 五路（P4 键盘/aria + P5 交互 + 图表 aria）

- **Jobs**：C1 任务行 `<tr @click>`→真 button + aria-expanded；训练/评估提交 pending；日志近底跟随+「回到最新」；完成通知（naive `useNotification`）+ title「✓」；dead 重试；取消 NPopconfirm+乐观；状态徽章迁移 `AppBadge`（queued→info/running→accent/succeeded→pass/failed→fail/canceled→warn）。
- **Live**：C2 循环行→真 button + aria-expanded + aria-label；九端点按激活子视图分频轮询；各表/KPI 加骨架（`xxxData !== null` 判定）；CyclesTable 明细失败重展开重试（`'error'` truthy 修）；筛选切换降透明度反馈；NSelect aria-label；OverviewPanel 权益图 role=img+aria-label+`aria:{enabled:true}`。
- **Backtests**：C3 删除 span→拆平级双 button + focus 显形；叠加对比 value 用 run_id（修下标错位 bug）；reload 保留 selectedRunId；基准切换占位；提交 pending；空态改引导页内表单；symbol 联想 combobox 键盘（↑↓/Esc/aria）；deletingId 接线或删；EquityChart role=img+aria-label+aria enabled；NSelect aria-label。
- **Verdicts**：FactorCard **OOS超额 统一行情色**（marketCell: 正=红 t-up/负=绿 t-down），IC均值/超额IR 转中性，PASS/FAIL 与闸门轨道保留判定色（全站统一 A 股行情色，用户firm决策）；FactorDetailModal 标题 span→h3 + 打开 focus 弹框修方向键；提交 pending；filter-seg aria-pressed；NSelect aria-label。
- **Explorer**：symbol 联想 combobox 键盘；特征自动重拉在途 spinner 反馈；FeaturePanel/kline 图 role=img+aria-label。

## Wave2 各流通用要求

- 有纯逻辑处走 TDD（vitest 先失败→实现→通过）；纯模板/样式 a11y 属性可直接改并跑既有 spec 不回归。
- 只改独占文件；消费 W1 的 usePolling 新字段/GlossaryTip/AppBadge。
- npm 铁律：Windows 侧 powershell 包装；读文件测试用 `fs`（@types/node 已装）。
- 不跑 build、不 commit（中央统一做）；跑自己相关 vitest 确认绿。
- 返回：改动文件清单 + 关键决策 + 遗留/风险。

## 集成验收

`typecheck`→`test`→`lint`→`build`→`check_frontend_fresh`→`ui_smoke`(应 PASS，gates 已修) 全绿；六页双主题读图；axe 关键项人工核对；提交 + 写 batch2-done.md。
