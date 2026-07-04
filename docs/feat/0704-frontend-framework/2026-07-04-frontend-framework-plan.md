# 前端框架化改造实施计划（Vue 3 + Vite + Anthropic 品牌视觉 v5）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把投研驾驶舱前端从原生 JS（11 模块 1840 行）整体迁移为 Vue 3 + Vite + TS 工程，视觉系统重建为 Anthropic 品牌语言 v5，生产形态（FastAPI 托管 static/、:8501/ui/、CLI）零变化。

**Architecture:** 仓库根新增 `frontend/` Vite 工程；构建产物落 `src/interfaces/api/static/` 并入库；迁移期一切验证走 Vite dev server（:5173），终章一次 build 切换。设计文档：`docs/feat/0704-frontend-framework/2026-07-04-frontend-framework-design.md`（含 DD-1..DD-5 决策与 §5.3 功能对等契约）。

**Tech Stack:** Vue 3.5 `<script setup lang="ts">` / Vite / TS strict / Pinia / vue-router(hash) / Naive UI（仅表单/弹层/反馈族）/ vue-echarts / @fontsource（拉丁三族）/ Vitest + Vue Testing Library。

## Global Constraints（每个任务隐含遵守）

- **npm/npx/node 一律 Windows 侧执行**：`powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; <命令>"`。WSL 侧直跑 npm = 毒化 node_modules（设计 §2.3）。
- **版本锁定**（DD-5）：package.json 无 `^`/`~`，全精确版本；echarts×vue-echarts 是硬 peer 配对，装前 `npm info vue-echarts peerDependencies` 核对。
- **并行纪律**（设计 §5.2）：页面任务只写 `frontend/src/**` 与自己的测试；**禁碰 `src/interfaces/api/static/`、禁跑 `npm run build`**（build 仅 Task 11 终章一次）。
- **迁移对等原则**：每个页面任务第一步=通读对应旧 JS 源文件，行为清单以旧代码为 source of truth；契约清单（各任务内嵌）之外发现的行为**一并保留并记录**，不得静默丢弃。
- **语义色对号**：旧 CSS 涨/买用 `gate-bad`(红)、跌/卖用 `gate-good`(绿)——迁移按**语义**对号入座到新 token（`--c-up/--c-down/--c-buy/--c-sell/--c-pass/--c-fail`），禁止按颜色名对号。
- **TS strict 全程**；组件全部 `<script setup lang="ts">`；`prefers-reduced-motion` 下所有动效退化为瞬时。
- **commit 频繁**，消息格式沿仓库惯例 `feat(ui-v2): ...`，尾行 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。

---

## Task 1: Vite 工程初始化 + 版本矩阵锁定

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/scripts/assert-win32.js`, `frontend/.gitignore`
- 注意：不用 `npm create vite` 脚手架交互式生成（交互不可用），手写配置文件后 `npm install`。

**Interfaces:**
- Produces: 可运行的 dev server（`npm run dev` → http://127.0.0.1:5173/ui/）；npm scripts：`dev`/`build`/`test`/`typecheck`/`lint`。

- [ ] **Step 1: 锁定版本矩阵**

```bash
powershell.exe -NoProfile -Command "npm info vue version; npm info vite version; npm info vue-router version; npm info pinia version; npm info naive-ui version; npm info echarts version; npm info vue-echarts version; npm info vue-echarts peerDependencies; npm info vitest version; npm info @vitejs/plugin-vue version"
```
把返回的**当前最新稳定版**逐一记录，填进 Step 2 的 package.json（下方版本号为占位示例，以查询结果为准；vue-echarts 的 echarts peer 范围必须包含所选 echarts 版本）。

- [ ] **Step 2: 写 `frontend/package.json`**（版本号用 Step 1 实测值替换）

```json
{
  "name": "ghq-dashboard",
  "private": true,
  "type": "module",
  "scripts": {
    "preinstall": "node scripts/assert-win32.js",
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "test": "vitest run",
    "typecheck": "vue-tsc --noEmit",
    "lint": "eslint src"
  },
  "dependencies": {
    "vue": "<锁定>", "vue-router": "<锁定>", "pinia": "<锁定>",
    "naive-ui": "<锁定>", "echarts": "<锁定>", "vue-echarts": "<锁定>",
    "@fontsource/poppins": "<锁定>", "@fontsource/lora": "<锁定>", "@fontsource/jetbrains-mono": "<锁定>"
  },
  "devDependencies": {
    "vite": "<锁定>", "@vitejs/plugin-vue": "<锁定>", "typescript": "<锁定>", "vue-tsc": "<锁定>",
    "vitest": "<锁定>", "@vue/test-utils": "<锁定>", "@testing-library/vue": "<锁定>", "jsdom": "<锁定>",
    "eslint": "<锁定>", "eslint-plugin-vue": "<锁定>", "typescript-eslint": "<锁定>"
  }
}
```

- [ ] **Step 3: 写 `frontend/scripts/assert-win32.js`（WSL 毒化守卫）**

```js
if (process.platform !== 'win32') {
  console.error('\n[GHQ] npm 必须在 Windows 侧执行 (powershell.exe 包装), 当前平台: ' + process.platform)
  console.error('[GHQ] WSL 侧安装会以 linux 二进制毒化 node_modules。见设计 §2.3。\n')
  process.exit(1)
}
```

- [ ] **Step 4: 写 `frontend/vite.config.ts`（base/outDir/proxy 三件套）**

```ts
import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  base: '/ui/',
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8501' },
  },
  build: {
    outDir: fileURLToPath(new URL('../src/interfaces/api/static', import.meta.url)),
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
  },
})
```

- [ ] **Step 5: 写最小 `frontend/index.html` / `src/main.ts` / `src/App.vue`**

index.html（防闪脚本在 Task 2 扩充，先立骨架）：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GoldenHand 投研驾驶舱</title>
  <script>
    document.documentElement.dataset.theme = localStorage.getItem('ghq-theme') || 'dark'
  </script>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```
main.ts：
```ts
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'

createApp(App).use(createPinia()).mount('#app')
```
App.vue：
```vue
<script setup lang="ts"></script>
<template>
  <main data-testid="app-shell">GHQ v2 骨架</main>
</template>
```
`.gitignore`：`node_modules/`、`dist/`。

- [ ] **Step 6: 安装依赖并验证 dev server**

```bash
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm install"
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run dev" # 后台起
curl -s http://127.0.0.1:5173/ui/ | grep -q 'id="app"' && echo DEV_OK
```
Expected: `DEV_OK`。若 preinstall 在 Windows 侧误报，核查 powershell 包装是否生效。

- [ ] **Step 7: Commit**

```bash
git add frontend/ && git commit -m "feat(ui-v2): Vite 工程骨架 — 版本矩阵锁定/base=/ui//outDir=static/preinstall win32 守卫"
```

---

## Task 2: 设计系统 tokens + 主题双驱动 + 应用壳与路由

**Files:**
- Create: `frontend/src/styles/tokens.css`, `frontend/src/styles/base.css`, `frontend/src/stores/theme.ts`, `frontend/src/components/ThemeToggle.vue`, `frontend/src/router.ts`, `frontend/src/pages/{Overview,Backtests,Explorer,Verdicts,Live,Jobs}.vue`（占位壳）
- Modify: `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/index.html`
- Test: `frontend/src/stores/__tests__/theme.spec.ts`

**Interfaces:**
- Produces:
  - CSS tokens（后续所有组件消费）：`--bg --bg-2 --text --text-2 --text-3 --border --accent(#d97757) --accent-blue(#6a9bcc) --accent-green(#788c5d) --c-up --c-down --c-buy --c-sell --c-pass --c-fail --font-display --font-body --font-mono --dur-fast(120ms) --dur-base(240ms) --ease-out(cubic-bezier(.22,1,.36,1))`，日间/夜间两档由 `:root[data-theme=...]` 切换。
  - `useThemeStore()`: `{ theme: Ref<'dark'|'light'>, toggle(): void, naiveTheme: ComputedRef<GlobalTheme|null>, naiveOverrides: ComputedRef<GlobalThemeOverrides> }`——写 localStorage(`ghq-theme`) 并同步 `documentElement.dataset.theme`。
  - 路由名：`overview backtests explorer verdicts live jobs`（live 带 `:view?` 参数）+ `shadow` 占位重定向 overview。
  - 导航锚点：`data-testid="nav-<name>"`；页面容器 `data-testid="page-<name>"`。

- [ ] **Step 1: 写 tokens.css**（品牌值照设计 §4.2：日 `#faf9f5/#141413`、夜反转、强调三级、中性 `#b0aea5/#e8e6dc` 及夜间深色档；语义色砖红/橄榄绿系与品牌同族；`@media (prefers-reduced-motion: reduce)` 把 `--dur-*` 归零）+ base.css（reset、字体应用：标题 Poppins/正文 Lora+中文系统衬线栈/数字表格 JetBrains Mono、链接与滚动条、`.num{font-family:var(--font-mono);font-variant-numeric:tabular-nums}`）。fontsource 导入放 main.ts。
- [ ] **Step 2: 写 theme store 失败测试**（toggle 翻转 theme+dataset+localStorage；naiveTheme 在 dark 时为 darkTheme 对象、light 时 null）→ 跑 `npm run test` 确认 FAIL。
- [ ] **Step 3: 实现 theme.ts**——`naiveOverrides` 两套：共同 `common.primaryColor='#d97757'`、fontFamily 对齐 token；dark 档背景 `#141413` 系、light 档 `#faf9f5` 系（卡片/弹层/输入底色逐项对齐 tokens.css 同名值）。
- [ ] **Step 4: App 壳**——`n-config-provider :theme="themeStore.naiveTheme" :theme-overrides="themeStore.naiveOverrides"` 包裹 `router-view`；顶栏：品牌标题（Poppins）、导航（`data-testid="nav-*"`，活跃态 accent 下划线滑动动效 `--dur-base`）、任务徽章占位、ThemeToggle（☀/☾ 图标 + `aria-label` 沿旧版）。路由切换过渡：`<router-view v-slot="{ Component }"><transition name="page"><component :is="Component"/></transition></router-view>`，`.page-enter-active{transition:opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out)}` 位移 8px。main.ts 挂 router + 导入 fontsource 三族（400/600/700 需要的字重）+ styles。
- [ ] **Step 5: 跑 test 全绿 + dev server 双主题目测**（curl 确认 + 浏览器截图：Playwright 一次性脚本或等 Task 4 的 ui_smoke 适配后补），commit `feat(ui-v2): 品牌 tokens/主题双驱动/应用壳+路由`。

---

## Task 3: api 层 + jobs store + usePolling

**Files:**
- Create: `frontend/src/api/fetch.ts`, `frontend/src/api/types.ts`, `frontend/src/stores/jobs.ts`, `frontend/src/composables/usePolling.ts`, `frontend/src/components/ErrorBanner.vue`
- Test: `frontend/src/composables/__tests__/usePolling.spec.ts`, `frontend/src/api/__tests__/fetch.spec.ts`
- 参考旧实现: `src/interfaces/api/static/js/api.js`（55 行，全部行为对等）、`js/jobs.js` 的 `window.__activeJobs` 用法

**Interfaces:**
- Produces:
  - `fetchJSON<T>(url: string): Promise<T>`；`postJSON<T>(url: string, payload?: unknown): Promise<T>`——错误消息格式沿旧版：非 2xx 抛 `Error('${status} ${url}: ${body 前 200 字}')`；POST 422 时 detail 数组提取 `.msg` join '; ' 截 300 字；**503 且 jobsStore.activeCount>0 时**改抛 `Error('后台任务运行中，数据库写锁占用，稍后自动恢复')`。
  - `useJobsStore()`: `{ activeCount: Ref<number>, setActive(n: number): void }`（由 Jobs 页/JobCard 轮询回填；不自轮询——沿旧版由任务列表刷新时写入）。
  - `usePolling<T>(fetcher: () => Promise<T>, opts: { intervalMs: number; immediate?: boolean }): { data: Ref<T|null>, error: Ref<Error|null>, loading: Ref<boolean>, refresh: () => Promise<void>, stop: () => void }`——行为规格：immediate 默认 true；**首载失败置 error**、后续 tick 失败静默保留旧 data（error 不覆盖已有 data 的展示由调用方决定）；`document.visibilitychange` 隐藏时暂停、恢复时立即 refresh 再续；组件卸载自动 stop；refresh 带**过期响应守卫**（内部序号，迟到响应丢弃）。
  - `ErrorBanner.vue` props `{ msg: string }`，全站单横幅语义由各页 `error` 状态驱动（新错误覆盖旧错误、成功后清除——对等旧 showError/clearError 时机）。
  - types.ts：手写核心类型 `Job JobStatus BacktestRun Verdict LiveSnapshot Position Execution AuditRow CycleRow TicketPayload OverviewData` ——字段以各页任务通读路由代码时**补全**，本任务先定义 Job 族（jobs.py `to_dict` 已知字段）与公共分页壳。
- Consumes: Task 2 的 theme store（ErrorBanner 用 token 变量着色）。

- [ ] Step 1: usePolling 失败测试（fake timers：immediate 拉取/间隔触发/隐藏暂停恢复刷新/卸载停止/首载失败 error 置位/迟到响应丢弃——6 个用例，全部真实代码）→ FAIL → 实现 → PASS。
- [ ] Step 2: fetch.ts 测试（mock fetch：200 返 json/500 抛格式化错/422 detail 数组可读化/503+activeCount>0 转写锁文案）→ FAIL → 实现（内部 `import { useJobsStore }` 于调用点取 store，避免 Pinia 未初始化）→ PASS。
- [ ] Step 3: ErrorBanner（token 着色、role="alert"、`data-testid="error-banner"`）+ jobs store 实现与单测。
- [ ] Step 4: 全绿 + commit `feat(ui-v2): api 层/usePolling/jobs store — 旧 api.js 语义对等(503 条件友好化/过期守卫/隐藏暂停)`。

---

## Task 4: 基础组件族 + ui_smoke 适配

**Files:**
- Create: `frontend/src/components/{KpiCard,DataTable,GlossaryTip,JobCard,SubNav}.vue`, `frontend/src/composables/useChartTheme.ts`, `frontend/src/glossary.ts`
- Modify: `scripts/ui_smoke.py`
- Test: `frontend/src/components/__tests__/{DataTable,JobCard}.spec.ts`
- 参考旧实现: `js/jobs.js`（任务卡全行为）、`js/glossary.js`（98 行术语表+挂载机制）、`js/charts.js`（主题调色板）、`js/pages/live.js` 的 `renderBounded`

**Interfaces:**
- Produces:
  - `KpiCard.vue` props `{ label: string; value: string|number; tone?: 'up'|'down'|'neutral'; sub?: string; countUp?: boolean }`——countUp 时数字滚动（requestAnimationFrame，`--dur-base`×3，reduced-motion 直接终值；`.num` mono 字体）。
  - `DataTable.vue` props `{ rows: Record<string,unknown>[]; columns: { key: string; title: string; render?: (row)=>VNode|string; align?: 'right' }[]; rowKey: string; pageSize?: number(默认50) }`——超过 pageSize 显示"显示全部 N 条 ▾"展开按钮；**展开态组件内 ref 保持**（父级轮询重传 rows 不重置）；行入场 staggered（仅首次渲染，每行延迟 `index*24ms` 上限 12 行，reduced-motion 关闭）；`data-testid="data-table"`。
  - `JobCard.vue` props `{ job: Job }` emits `{ cancel: [id: string], done: [] }`——中文状态映射（queued 排队中/running 运行中/succeeded 已完成/failed 失败/canceled 已取消）、耗时人性化（<60s 秒/<1h 分秒/否则时分）、参数摘要拼装（沿旧版 join 规则）、日志 `<pre>` 文本插值（Vue 自动转义）、日志跟随轮询 tail、cancel 后 404 视为已终止停止轮询、**done 仅 status==='succeeded' 时 emit 一次**；`data-testid="job-card"`。
  - `GlossaryTip`：`glossary.ts` 导出术语字典（旧 glossary.js 全量平移）；组件用 Naive UI `n-popover`（appendTo body 等价），props `{ term: string }`，字典缺词时降级为纯文本（对等旧"vendor 缺失降级"）。
  - `SubNav.vue` props `{ items: { key: string; label: string; badge?: number }[]; modelValue: string }` emits update——活跃态样式 + 徽章。
  - `useChartTheme()`: 返回 `ComputedRef<{ palette: string[]; axisStyle; tooltipStyle; textColor; gridColor }>`——品牌 6 色序列（#d97757 #6a9bcc #788c5d + 派生浅/深档），随 theme store 变化；页面 watch 它重设 option（vue-echarts option 用 `shallowRef`）。
  - ui_smoke.py：`BASE = os.environ.get('UI_BASE', 'http://127.0.0.1:8501/ui/')`；页签点击选择器改 `[data-testid="nav-{name}"]`；等待锚点改 `[data-testid="page-{name}"]`；保留 console 错误白名单与 `--deep` 流程（其内部选择器 `#bt-submit`/`.job-card` 等改为对应 data-testid，新前端组件按本任务/页面任务的 testid 约定提供）。
- Consumes: Task 2 tokens/theme store、Task 3 usePolling/fetch。

- [ ] Step 1: DataTable 失败测试（50 行截断+展开按钮文案/展开后重传 rows 不回折/rowKey 渲染）→ 实现 → PASS。
- [ ] Step 2: JobCard 失败测试（状态映射/done 仅成功触发一次/cancel emit）→ 实现（轮询用 usePolling 3s 沿旧任务卡节奏）→ PASS。
- [ ] Step 3: 其余组件实现 + useChartTheme（palette 双主题对比度目测）。
- [ ] Step 4: ui_smoke.py 适配（UI_BASE + data-testid；`python3 -c "import ast; ast.parse(open('scripts/ui_smoke.py').read())"` 语法自检——完整跑通留待页面就位）。
- [ ] Step 5: commit `feat(ui-v2): 基础组件族(DataTable自研/JobCard/GlossaryTip)+图表主题+ui_smoke testid 适配`。

---

## Task 5–10: 页面迁移（六页，页间无依赖可并行；每页同一模板）

> **每页统一步骤模板**（以下只列各页差异契约）：
> - [ ] Step 1: 通读旧源文件与对应路由 handler，列完整行为清单（契约+清单外发现），补全 `api/types.ts` 该页类型；
> - [ ] Step 2: 写页面组件（消费 Task 2-4 接口；布局照旧版信息架构，视觉按品牌 v5；所有交互锚点带 `data-testid`）；
> - [ ] Step 3: 该页纯逻辑抽函数并 Vitest（各页契约中标注 ⚗ 的项）；
> - [ ] Step 4: dev server 双主题截图读图，对照契约逐条勾验；
> - [ ] Step 5: commit `feat(ui-v2): <页名>迁移 — 契约对等`。

### Task 5: Overview（旧 `js/pages/overview.js` 54 行 + `routes/research.py` overview handler）
契约：单次加载（无轮询）；数据库状态 KPI（KpiCard countUp）+ 最新回测/判决摘要卡；加载失败 ErrorBanner；卡片 hover 浮起动效。

### Task 6: Verdicts(+研究表单)（旧 `js/pages/verdicts.js` 178 行 + research.py verdicts/factor 目录 handlers）
契约：判决表（评分等级着色⚗、**grade F→D 映射**⚗、field_ready=false 因子 chip 禁用态虚线删除线）；详情钻取（过期响应守卫）；**objective 切换联动**（表头/指标列/格式化整体切换）⚗；因子检验提交表单（P0/P1/P2 分组 chip 可勾选、选中金填充→改 accent 填充、多重检验提示文案、QMT 在线标注）+ 数据刷新表单（日期区间默认值沿旧版）——两表单走 JobCard 闭环；前端复制的闸门阈值常量原样平移并注释债 D2。

### Task 7: Explorer（旧 `js/pages/explorer.js` 167 行 + research.py kline/features handlers）
契约：标的输入联想 chips（输入防抖、点击成 chip、`#load-symbol` 等价按钮 testid=`explorer-load`）；K 线图（**红涨绿跌**，`--c-up/--c-down`）；特征时序图（多序列 palette）；空态/加载态文案沿旧版；图表随主题重渲染。

### Task 8: Backtests（旧 `js/pages/backtests.js` 599 行——最大文件，边界语义最密）
契约：回测列表（DataTable，行点击进详情）；详情 meta 条结构化；净值图**全部边界语义**：基准兜底链（指定基准→缺失回退链沿旧代码）、超额收益同窗口径、多轮次叠加**重定基**、买卖标记 path 字形 ▲买(`--c-buy`)/▼卖(`--c-sell`) 带光环偏移与**聚合/截断规则**（沿旧代码阈值）、回撤子图渐变、切换详情**过期渲染丢弃**；提交表单（标的 chips 联想复用 Explorer 逻辑→抽 `composables/useSymbolChips.ts`、参数默认值/校验沿旧版、`data-testid="bt-submit"`）+ JobCard 闭环（成功后列表刷新）；⚗ 重定基/超额计算抽纯函数测试。

### Task 9: Live（旧 `js/pages/live.js` 346 行 + `routes/live.py` 全端点）
契约：SubNav 六子视图（概览/持仓/循环/执行/审计/Ticket，徽章=各表计数）；KPI 条 4 卡（总资产/累计收益——**≥2 快照才显示收益**、单快照显"—　需多次快照累计"、颜色 `--c-up/--c-down`/可用资金/持仓市值）；权益曲线（<2 点显提示文案非空图）；持仓表（现价/市值盯市/浮动盈亏——**现价缺失回退成本且不显盈亏**）；循环表钻取（mode 筛选**仅作用于既定两端点**沿旧版）；执行/审计 DataTable（50 行展开态跨轮询保持）；Ticket 键值面板（方向买红卖绿、状态 FILLED 绿、原始 JSON `<details>` 折叠）；**诚实空态**：db_exists:false 显示旧版同文案；多端点并行加载（Promise.all 等价，独立错误不互斥）；轮询节奏沿旧版间隔。

### Task 10: Jobs（旧 `js/jobs.js` 181 行任务中心页部分 + `routes/jobs.py`）
契约：任务列表轮询（活跃任务写回 jobs store→顶栏徽章联动）；JobCard 复用（列表页卡片态）；ML 训练/评估表单（参数域校验沿 job_commands 白名单语义、提交走 JobCard）；日志查看（tail 参数、pre 转义）；取消（409 已结束的可读提示）。

---

## Task 11: 终章——构建切换 + 漂移防线 + 验收链

**Files:**
- Create: `scripts/check_frontend_fresh.py`, `frontend/public/favicon.svg`
- Delete: `src/interfaces/api/static/{js/,style.css,index.html,vendor/}`（旧手写前端，由 build 产物替换）
- Modify: `CLAUDE.md`（前端开发命令段）

- [ ] Step 1: favicon（品牌橙圆点简标，`<link rel="icon">` 进 index.html——消旧版 404）。
- [ ] Step 2: `check_frontend_fresh.py`——对比 `frontend/src/**` 最新 mtime 与 `static/.build-stamp`（build 时由 vite 插件或 npm script `node -e` 写入 ISO 时间戳）；src 更新则退出码 1 提示"改了 frontend/src 未 build"。
- [ ] Step 3: 删除旧 static 手写文件 → 一次 `npm run build`（含 vue-tsc 门）→ 产物+删除同一提交入库。
- [ ] Step 4: 验收链全跑：`npm run lint`、`npm run test`、`python -m pytest tests/ --ignore=tests/infrastructure/gateway/`、`ruff check src/`、`python scripts/check_frontend_fresh.py`——全绿才 commit `feat(ui-v2): 构建切换 static/ — 旧前端退役, 漂移防线进验收链`。

## Task 12: 全量验收 + 文档收口

- [ ] Step 1: `quant dashboard` 起服（Windows 侧）→ `UI_BASE` 缺省跑 `$WIN_PYTHON scripts/ui_smoke.py --deep`：PASS + 0 console 错误。
- [ ] Step 2: 双主题 × 六页截图逐张读图：品牌色板/字体/语义色对号/动效存在性（hover 前后对比截图）/reduced-motion 降级（Playwright `emulate_media` 补拍一组）。对照设计 §5.3 契约与各页任务清单逐条勾验。
- [ ] Step 3: CLAUDE.md 补前端段（dev/build/test 命令 + powershell 包装纪律 + 版本矩阵位置）；设计文档追加"§7 实施记录"；MEMORY 按需更新。
- [ ] Step 4: 最终 commit + 向用户汇报（含截图路径、验收清单结果、已知偏差）。

---

## Self-Review 记录

- 覆盖核对：设计 §3（Task 1/11）、§4.1（Task 2/3/4）、§4.2（Task 2/4 + 各页 Step 2）、§5.2 顺序（Task 编号即顺序，页面并行）、§5.3 契约（Task 5-10 各页展开）、§5.4/5.5（Task 11/12）✓
- 占位扫描：package.json 版本号"<锁定>"为 Step 1 实测填入的显式流程，非 TBD ✓；页面模板代码不预写——以旧源文件为 source of truth + 契约清单约束，属刻意决策（见 Global Constraints 迁移对等原则）✓
- 类型一致性：usePolling/fetchJSON/DataTable/JobCard 签名在 Task 3/4 定义、Task 5-10 消费一致 ✓
