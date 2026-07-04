# 前端框架化改造设计 — Vue 3 + Vite + Anthropic 品牌视觉 v5

日期：2026-07-04（v2，吸收 4 视角对抗评审 25 条 findings）
状态：设计定稿（A/B 节用户逐节确认，C 节经"一路干下去"授权定稿；v2 修订经评审 workflow）
前置：`docs/feat/0612-interactive-dashboard/`（§1–§12，原生 JS 驾驶舱完成态）

## 1. 背景与动机

投研驾驶舱现为原生 JS ES modules（11 个模块约 1840 行 + 711 行 style.css），FastAPI 单进程托管，零构建。0612 设计 D1 当时的取舍（零构建/单进程交付）已达成使命；用户明确提出引入框架，动机四项：

1. **新功能复杂度**——影子盘视图、更复杂的交互式分析界面，手写 DOM 方式撑不住；
2. **工程化升级**——组件化、TypeScript 类型检查、HMR、测试；
3. **界面品质上限**——目标"Claude 官网质感 + 动效花活"；
4. **精进项目**——把项目做得更专业。

维护痛点**不是**动机（现有代码尚可维护）——这是前瞻与品质驱动的升级，不是止血。

## 2. 选型决策

### 2.1 框架：Vue 3（用户拍板）

三候选对比（均以 Vite + TypeScript 为共识底座）：

| 维度 | Vue 3 | React 19 | Svelte 5 |
|---|---|---|---|
| 迁移连续性（模板 vs 现有 HTML/CSS） | **最好**（模板即增强 HTML） | 最差（JSX 重写思维） | 中 |
| ECharts 集成 | **vue-echarts 官方级** | 社区 wrapper | 社区 |
| 组件库生态（品质上限） | Naive UI/Element Plus 成熟 | 最大 | 薄（与品质诉求冲突） |
| 轮询/副作用场景 | watch/composable 直观 | useEffect 依赖数组易错 | $effect 直观 |
| AI 生成质量/资料 | 高 | 最高 | 略逊（runes 较新） |
| 中文生态 | **最好** | 好 | 少 |

拍板：**Vue 3.5 Composition API，全部 `<script setup lang="ts">`，TypeScript strict**。React 唯一胜项（技能通用性）与本项目规模轨迹（10 页以内单用户工具）不相关。

### 2.2 视觉：整体转 Anthropic 品牌语言（用户拍板）

三方向（双主题分路 / 整体转官网风 / 保持暗金只借花活）中用户选**整体转官网风**：日夜两套全部重建为 Anthropic 品牌语言，放弃 gold-leaf 暗金终端美学。含义：711 行 style.css 基本重写而非平移，ui_smoke 截图基线全部重建——已向用户明示并获确认。

### 2.3 环境：Windows 侧 node（用户拍板）

项目在 `/mnt/c`（Windows 文件系统），WSL 侧 node 跨文件系统 I/O 极慢。Windows node v24.15.0 + npm 11.12.1 已验证可用。与既有 `$WIN_PYTHON` 模式一致；WSL 侧 Claude 经 mirrored 网络访问 dev server 做读图自查。

**环境纪律（评审新增）**：npm/npx 命令**一律经 `powershell.exe -NoProfile -Command` 包装在 Windows 侧执行**——从 WSL 直跑会以 Linux 平台解析 esbuild/rollup 等原生二进制，毒化 node_modules。防线双保险：`frontend/package.json` 加 `preinstall` 脚本断言 `process.platform === 'win32'`。

## 3. 工程骨架与运行形态（A 节）

```
GoldenHandQuant/
├── frontend/                    # 新增: Vite 工程（源码, 与 python src/ 平级）
│   ├── package.json  vite.config.ts  tsconfig.json
│   └── src/
│       ├── pages/  components/  composables/  stores/  api/  styles/
│       └── main.ts
├── src/interfaces/api/static/   # 构建产物落点（替换手写 JS; vendor/ 退役）
└── src/interfaces/api/app.py    # 不动: 仍挂 /ui/
```

- **技术栈钉死**：Vue 3.5 + `<script setup lang="ts">` + TS strict + Vite + Pinia + vue-router（hash 模式，与 StaticFiles(html=True) 托管兼容已确认）+ vue-echarts + Naive UI（范围见 4.1）。
- **版本矩阵（DD-5，评审新增）**：实施首步用 `npm info` 锁定并记录精确版本进 package.json（无 `^`）：Vue 3.5.x、Vite 8.x、vue-router 5.x、Pinia 3.x、Naive UI 2.x、echarts 6.x 与 vue-echarts 配对版本（**硬 peer 配对，装前核对**）、openapi-typescript、Vitest 4.x。禁止裸 `npm install <pkg>` 追最新。
- **Vite 关键配置（评审新增）**：`base: '/ui/'`（挂载点对齐，漏配即资源 404）、`build.outDir` 指向 `../src/interfaces/api/static`、`emptyOutDir: true`（终章构建时清旧产物）。
- **开发流**：Windows 侧 `npm run dev` 起 Vite dev server（:5173，`host: true` 保证 WSL 可达），`/api` proxy → `127.0.0.1:8501`；后端照常 `quant dashboard`；HMR 毫秒级。**迁移期读图走 dev server，不碰 static/**。
- **构建与交付（DD-1）**：`npm run build` 产物输出 `src/interfaces/api/static/` 并**提交入库**。理由：运行机只需 Python（clone 即跑不变、生产零 node 依赖）、FastAPI 挂载/访问路径/CLI 全不变。代价：产物 diff 噪音——单用户仓库可接受。ECharts/Tippy 改走 npm 打包（Tippy 退役由 Naive UI 接替），无 CDN 依赖性质保持。**构建时机纪律：迁移期间只在终章执行一次 build 落 static/；并行迁移 agent 只写 frontend/src，禁止触碰 static/**（评审：防并行产物冲突 + 防迁移期砸掉 main 上仍在用的旧版）。
- **API 类型（DD-2，评审后降级）**：现有后端仅 7 个 pydantic schema，多数路由返回裸 dict——openapi-typescript 生成类型对本期价值有限。策略改为：**前端手写类型为主**（`api/types.ts`，按各页实际消费字段定义），openapi 生成仅做路径/方法骨架参考；后端零改动原则不破。待未来后端逐步补 `response_model` 再切换到生成为主。
- **漂移防线（DD-4，评审新增）**：产物入库必然伴生两条漂移路径，各配机器校验：①改 frontend/src 忘 build——`scripts/check_frontend_fresh.py`（比对 frontend/src 最新 mtime 与 static/ 构建时间戳，验收链强制跑）；②改后端路由忘同步前端类型——手写类型为主后此风险降为普通接口回归，由 ui_smoke 兜底。

## 4. 应用架构与视觉策略（B 节）

### 4.1 应用架构

- **路由**（vue-router hash）：`/#/overview` `/#/backtests` `/#/explorer` `/#/verdicts` `/#/live/:view?` `/#/jobs`；为未来影子盘页留 `/#/shadow`（本期不实现，仅路由与菜单占位，YAGNI 守住）。
- **components/**：JobCard（任务卡：提交/日志轮询/取消）、KpiCard、**DataTable（自研，评审裁定）**——分页长表收敛 `renderBounded` 语义（默认 50 行 + "显示全部 N 条"展开、**展开态内存跨轮询保持**）+ 行 staggered 入场动效；ErrorBanner、SubNav（Live 页子导航）、GlossaryTip（术语教学，收敛 glossary.js：幂等挂载、动态取词、body 挂载）、ThemeToggle。
- **Naive UI 范围收窄（评审裁定）**：只用表单族（input/select/date-picker/校验）、弹层族（modal/popover/tooltip）、反馈族（message/notification）。**不用 NDataTable**（DataTable 自研）。
- **Naive UI 主题接线（评审纠正）**：Naive UI 是 prop 驱动、不感知 `data-theme` attribute。theme store 双驱动：①`document.documentElement.dataset.theme` 供自有 CSS token；②`n-config-provider` 的 `:theme`（null/darkTheme）+ 日夜两套 `themeOverrides` 对象。组件树外的消息（fetch 层 503 提示）用 `createDiscreteApi` 且同步传主题，避免半黑半白 UI。
- **composables/**：`usePolling`（统一轮询）——**轮询矩阵成文（评审新增）**：间隔参数化沿用现状各页节奏（实施时照源码逐页核对登记）；页签隐藏暂停、恢复立即刷一次；错误语义保留现状——首载失败显示 ErrorBanner，后续 tick 失败静默保留旧数据；卸载自停；**过期响应守卫**（切换钻取目标后丢弃迟到响应，沿用现状三处语义）。`useChartTheme`（ECharts 主题权威，品牌色板；vue-echarts 用 `shallowRef` 持 option 防深层响应式开销）。
- **stores/**（Pinia）：`theme`（localStorage 键沿用 `ghq-theme`、默认 dark、首屏防闪内联脚本保留）、`jobs`（活跃任务数——`window.__activeJobs` 正经化；**503 写锁友好化是条件行为**：仅活跃任务>0 时把 503 转为"后台任务运行中，数据库写锁占用"提示，语义照旧）。
- **api/**：手写类型 `types.ts` + 薄 fetch 封装（fetchJSON/postJSON 平移成 TS：422 detail 数组可读化、错误截断、**单横幅错误兜底语义**——新错误覆盖旧错误、成功清除时机沿用现状）。
- **语义色 token 正名（评审新增）**：现状 CSS 里涨/买复用 `gate-bad`(红)、跌/卖复用 `gate-good`(绿)——类名语义反用是迁移陷阱。新 token 分离命名：`--c-up/--c-down`（行情涨跌）、`--c-buy/--c-sell`（委托方向，A 股惯例买红卖绿）、`--c-pass/--c-fail`（闸门/判定）。迁移时逐处按语义对号，禁止按颜色对号。

### 4.2 视觉系统 v5：Anthropic 品牌语言

- **色板**（brand-guidelines 官方值）：
  - 日间：`#faf9f5` 暖米白底 / `#141413` 墨黑字；夜间反转 `#141413` 底 / `#faf9f5` 字。
  - 强调三级：Claude 橙 `#d97757`（主：CTA/高亮/活跃态）、蓝 `#6a9bcc`（次）、绿 `#788c5d`（三）。
  - 中性：`#b0aea5` / `#e8e6dc` 做分隔线与次级背景（夜间取等效深色档）。
  - 双主题机制保留：`data-theme` attribute + 首屏防闪内联脚本 + localStorage（`ghq-theme`）。
- **排版（评审后修订——CJK vendored 不可行，实测 40MB/四字重）**：
  - 拉丁族 vendored（@fontsource，合计数百 KB）：Poppins（标题）、Lora（正文）、JetBrains Mono（数字/表格/代码——量化对齐刚需）。
  - 中文走系统字体栈不 vendored：正文 `Lora, Georgia, 'Noto Serif SC', 'Source Han Serif SC', serif`；标题 `Poppins, 'Noto Sans SC', 'Microsoft YaHei', sans-serif`。Windows 端默认可得雅黑/宋体族，质感由拉丁主字体 + 间距排版承担。
- **金融语义色**：A 股红涨绿跌保留，饱和度调至与品牌协调的砖红/橄榄绿系（与 `#d97757`/`#788c5d` 同族）。买=红/卖=绿的委托方向惯例不变。
- **图表**：ECharts 主题按品牌色板重做；数据系列色由品牌三色扩展出 6-8 色可区分序列；日夜随 theme store 响应式换肤。**既有图表边界语义全部保留**（见 5.3 契约）。
- **动效（"花活"，节制原则：服务信息层级）**：路由切换过渡、KPI 数字滚动（count-up）、表格行 staggered 入场、hover 微交互（卡片浮起/按钮反馈）、任务卡状态流转动效；曲线与时长遵循 ui-ux-pro-max 动效规范；`prefers-reduced-motion` 全局尊重（媒体查询下全部动效退化为瞬时）。
- **实施工具链**：frontend-design（方法论）+ brand-guidelines（配方）+ ui-ux-pro-max（细节规范）三 skill 协同；ui_smoke 读图闭环验收。

## 5. 迁移策略与质量保障（C 节）

### 5.1 迁移方式：一次到位整体迁移（DD-3）

不做渐进双栈。理由：①1840 行规模小，整体迁移可控；②双栈共存需维护两套主题/路由/错误兜底，分裂成本高于收益；③git 历史即回滚。**迁移期 main 可用性保障**：并行迁移只写 frontend/src（不影响 main 上旧版 static/ 正常服务），终章一次 build 切换——不可用窗口≈0。

### 5.2 迁移顺序（依赖驱动，评审修订）

1. **骨架**：版本矩阵锁定 → Vite 工程（base/outDir/preinstall 守卫）+ TS + 路由 + Pinia + 设计系统 token（styles/tokens.css：品牌色板/字体/间距/语义色正名/日夜双档）+ api 层（手写类型 + fetch 封装）+ theme store 双驱动；**ui_smoke.py 适配同步做**——BASE_URL 参数化（可指 :5173 dev server），选择器改为 data-testid 锚点约定，使迁移全期读图闭环可用。
2. **基础组件**：ThemeToggle / ErrorBanner / KpiCard / DataTable（自研）/ GlossaryTip / JobCard / SubNav（组件测试随写）。
3. **页面迁移**（功能对等为准，页面间无依赖可并行）：Overview → Verdicts → Explorer → Backtests → Live → Jobs。**并行纪律：agent 只写 frontend/src + 对应组件测试；禁碰 static/、禁跑 build**。每页完成即在 dev server 读图对照 5.3 契约。
4. **终章**：一次 `npm run build` 落 static/ + 产物入库；ui_smoke 指回 :8501 全量跑（--deep）；CLAUDE.md 更新（前端开发命令）；旧手写 JS/CSS/vendor 删除；favicon 补齐（顺手消 404）。

### 5.3 功能对等契约（迁移验收基线，评审后照代码事实修订）

> 以下为各页**必须对等**的行为契约（评审逐文件核对后修正：删除不存在的"覆盖率图/top_n 对比"，修正表单归属）。实施计划为每页展开完整契约清单，来源=现有源码逐行核对。

- **Overview**：数据库状态 KPI + 最新回测/判决摘要卡；
- **Verdicts**：判决表（评分等级着色、grade F→D 映射、field_ready 禁用 chip）+ 详情钻取 + objective 切换联动（表头/指标/格式化随切换）+ 因子检验/数据刷新提交表单（多重检验提示、QMT 在线标注）；前端复制的闸门阈值沿现状（债 D2 本期不修）；
- **Explorer**：标的 chips 联想 + K 线（红涨绿跌）+ 特征时序图 + 加载按钮语义；
- **Backtests**：回测列表 + 详情图表**含全部边界语义**（基准兜底链、超额收益同窗口径、多轮次叠加重定基、买卖标记 ▲买红/▼卖绿 path 字形 + 聚合/截断规则、切换详情时过期渲染丢弃）+ 回测提交表单 + 任务卡闭环；
- **Live**：六子视图（概览/持仓/循环/执行/审计/Ticket）+ KPI 条（累计收益 **≥2 快照才显示**、单/零快照占位文案）+ 权益曲线 + 盯市持仓（现价缺失回退成本不显盈亏）+ 循环钻取 + mode 筛选（**仅作用于既定两端点**）+ DataTable 分页长表（展开态内存跨轮询保持）+ 诚实空态（db_exists:false 文案）+ ticket 键值面板（买红卖绿、原始 JSON details 折叠）+ 多端点并行加载；
- **Jobs**：任务列表（中文状态映射、耗时人性化、参数摘要拼装）+ 实时日志（pre 转义）+ 取消（404 终止轮询）+ ML 训练/评估表单 + onDone 仅成功触发刷新；
- **全站**：日夜主题切换无闪烁、术语 tips（幂等/动态取词/body 挂载/缺失降级）、错误条单横幅兜底语义、503 写锁条件友好化、任务运行中徽章联动、favicon。

### 5.4 质量保障

- **类型**：`vue-tsc --noEmit` 进验收链。
- **测试**：Vitest + Vue Testing Library——JobCard 状态流转、usePolling（隐藏暂停/卸载清理/过期响应丢弃）、DataTable（分页/展开态保持）、theme store 双驱动；页面级冒烟由 ui_smoke 承担。
- **Lint**：ESLint + eslint-plugin-vue + typescript-eslint。
- **读图闭环**：迁移期每页在 dev server 截图逐张读图（双主题）；对照 5.3 契约核对。
- **后端零改动**：API/DB 层完全不动，pytest 全量回归证明。
- **产物新鲜度**：`scripts/check_frontend_fresh.py` 进验收链（DD-4）。

### 5.5 验收标准（Definition of Done，评审后可执行化）

1. `npm run build` 产物入库，`quant dashboard` 起服后 `:8501/ui/` 全功能可用（访问路径/CLI 零变化）；
2. 5.3 契约逐页核对通过（实施计划展开的逐条清单打勾）；
3. `vue-tsc` 0 error、ESLint 0 error、Vitest 全绿、pytest 全量 0 失败、ruff 0、check_frontend_fresh 通过；
4. ui_smoke PASS（0 console 错误，白名单沿用）+ 双主题 × 全页截图逐张读图：品牌色板/字体正确、双主题一致性、**动效验收=逐项代码核对存在 + hover 前后对比截图 + prefers-reduced-motion 降级核对**（截图无法验动画过程，以此三项替代）；
5. CLAUDE.md 补前端开发命令（dev/build/test/环境纪律）；
6. 设计文档 + 实施计划留痕于 docs/feat/0704-frontend-framework/。

### 5.6 风险与回滚（评审后扩充）

| 风险 | 应对 |
|---|---|
| 产物/源码漂移（改 src 忘 build） | DD-4 新鲜度检查进验收链 |
| 并行迁移 agent 误 build 制造冲突/砸旧版 | 5.2 并行纪律：只写 frontend/src；build 仅终章一次 |
| WSL 侧误跑 npm 毒化 node_modules | powershell 包装纪律 + preinstall 平台守卫双保险 |
| 版本兼容（echarts×vue-echarts 硬配对等） | DD-5 版本矩阵锁定，禁裸装最新 |
| CJK 字体体积 | 已消：中文系统栈不 vendored |
| Naive UI 换肤达不到品牌质感 | themeOverrides 日夜两套 + 局部 CSS 补；核心组件本就自研（DataTable） |
| Naive UI 与自有 CSS 样式冲突 | Naive 收窄到表单/弹层/反馈族；自有 token 优先级由 CSS layer 控制 |
| 迁移期主线要用驾驶舱 | main 上旧版 static/ 全期可用，终章才切换 |
| 回滚 | `git revert` 产物提交即回旧版 |

## 6. 阶段划分

- **本期（阶段 1）**：第 3–5 节全部内容——骨架、六页迁移、品牌视觉 v5、验收链。
- **阶段 2（另立设计）**：影子盘页（signal_snapshots 决策快照视图 + shadow_consistency_check 比对历史）——依赖本期新架构，是新架构的第一个增量页面。

## 附：评审记录

4 视角（架构/前端技术/迁移完整性/YAGNI 一致性）并行评审产出 25 条去重 findings；对抗验证阶段因 session 限额未完成，改由主循环逐条批判性吸收：约 20 条成立并已并入上文（DD-2 降级、DD-4/DD-5 新增、DataTable 裁定自研、Naive UI 接线纠正、字体方案重定、5.2 流程纪律、5.3 契约修正、语义色正名等），2 条为正面确认（hash 路由兼容、清单方向正确），其余为实施级细节移交实施计划展开。
