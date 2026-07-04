# 前端框架化改造设计 — Vue 3 + Vite + Anthropic 品牌视觉 v5

日期：2026-07-04
状态：设计定稿（A/B 节用户逐节确认，C 节经"一路干下去"授权定稿）
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

## 3. 工程骨架与运行形态（A 节，已确认）

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

- **技术栈钉死**：Vue 3.5 + `<script setup lang="ts">` + TS strict + Vite + Pinia + vue-router（hash 模式，静态托管零配置）+ vue-echarts + Naive UI。
- **开发流**：Windows 侧 `npm run dev` 起 Vite dev server（:5173），`/api` proxy → :8501；后端照常 `quant dashboard`；HMR 毫秒级。
- **构建与交付（DD-1）**：`npm run build` 产物输出 `src/interfaces/api/static/` 并**提交入库**。理由：运行机只需 Python（clone 即跑不变、生产零 node 依赖）、FastAPI 挂载/访问路径/CLI 全不变。代价：产物 diff 噪音——单用户仓库可接受。ECharts/Tippy 改走 npm 打包（Tippy 退役由 Naive UI 接替），无 CDN 依赖性质保持。
- **API 类型自动生成（DD-2）**：`openapi-typescript` 从 FastAPI `/openapi.json` 生成 TS 类型，前后端契约进编译期。生成文件入库，`npm run gen:api` 手动刷新（后端路由改动时）。

## 4. 应用架构与视觉策略（B 节，修订版已确认）

### 4.1 应用架构

- **路由**（vue-router hash）：`/#/overview` `/#/backtests` `/#/explorer` `/#/verdicts` `/#/live/:view?` `/#/jobs`；为未来影子盘页留 `/#/shadow`（本期不实现，仅路由与菜单占位，YAGNI 守住）。
- **components/**：JobCard（任务卡：提交/日志轮询/取消）、KpiCard、DataTable（分页长表，收敛 `renderBounded` 模式）、ErrorBanner、SubNav（Live 页子导航）、GlossaryTip（术语教学，收敛 glossary.js）、ThemeToggle。
- **composables/**：`usePolling`（统一轮询：错误兜底、卸载自停、**页签隐藏暂停**）、`useChartTheme`（ECharts 主题权威，charts.js 调色板逻辑迁移并换品牌色板）。
- **stores/**（Pinia）：`theme`（替代 `gh:theme` 事件广播）、`jobs`（活跃任务数，`window.__activeJobs` 正经化；503 写锁提示逻辑随迁——DuckDB 单写者约束的前端表达）。
- **api/**：openapi-typescript 生成类型 + 薄 fetch 封装（fetchJSON/postJSON 平移成 TS，422 detail 可读化等既有修复保留）。

### 4.2 视觉系统 v5：Anthropic 品牌语言

- **色板**（brand-guidelines 官方值）：
  - 日间：`#faf9f5` 暖米白底 / `#141413` 墨黑字；夜间反转 `#141413` 底 / `#faf9f5` 字。
  - 强调三级：Claude 橙 `#d97757`（主：CTA/高亮/活跃态）、蓝 `#6a9bcc`（次）、绿 `#788c5d`（三）。
  - 中性：`#b0aea5` / `#e8e6dc` 做分隔线与次级背景（夜间取等效深色档）。
  - 双主题**机制**保留：`data-theme` attribute + 首屏防闪内联脚本 + localStorage 持久化。
- **排版**：Poppins 标题 + Lora 正文（官方配方），两处扩展：
  - 中文：正文配 Noto Serif SC（衬线，保编辑部气质），标题配 Noto Sans SC 中黑档；
  - 数字/表格/代码：保留 JetBrains Mono（量化数字对齐刚需）。
  - 字体全部本地 vendored（npm 包或字体文件入 frontend/src/assets，无 CDN）。
- **金融语义色**：A 股红涨绿跌保留，饱和度调至与品牌协调的砖红/橄榄绿系（与 `#d97757`/`#788c5d` 同族）。买=红/卖=绿的委托方向惯例不变。
- **图表**：ECharts 主题按品牌色板重做；数据系列色由品牌三色扩展出 6-8 色可区分序列；日夜随 `data-theme` 响应式换肤（watch 自动重渲染，替代事件广播）。
- **动效（"花活"，节制原则：服务信息层级）**：路由切换过渡、KPI 数字滚动（count-up）、表格行 staggered 入场、hover 微交互（卡片浮起/按钮反馈）、任务卡状态流转动效；曲线与时长遵循 ui-ux-pro-max 动效规范；`prefers-reduced-motion` 全局尊重。
- **组件库**：Naive UI 按需引入，`n-config-provider` themeOverrides 对齐 Anthropic token；覆盖：数据表格/表单校验/日期区间/弹窗/消息/气泡（Tippy 退役）。
- **实施工具链**：frontend-design（方法论）+ brand-guidelines（配方）+ ui-ux-pro-max（细节规范）三 skill 协同；ui_smoke 读图闭环验收。

## 5. 迁移策略与质量保障（C 节）

### 5.1 迁移方式：一次到位整体迁移（DD-3）

不做渐进双栈。理由：①1840 行规模小，整体迁移可控；②双栈共存需维护两套主题/路由/错误兜底，分裂成本高于收益；③git 历史即回滚（旧 static/ 完整在 `1b8e0ed` 之前的树里）。

### 5.2 迁移顺序（依赖驱动）

1. **骨架**：Vite 工程 + TS + 路由 + Pinia + 设计系统 token（styles/tokens.css：品牌色板/字体/间距/日夜双档）+ api 层（类型生成 + fetch 封装）；
2. **基础组件**：ThemeToggle / ErrorBanner / KpiCard / DataTable / GlossaryTip / JobCard / SubNav（组件测试随写）；
3. **页面迁移**（简单→复杂，功能对等为准）：Overview → Verdicts → Explorer → Backtests → Live → Jobs；
4. **收尾**：构建产物入库、CLAUDE.md 更新（前端开发命令）、ui_smoke.py 选择器适配、旧 static 手写文件删除。

页面迁移彼此独立，可多智能体并行（骨架与基础组件先行完成后 fan-out）。

### 5.3 功能对等清单（迁移验收基线）

- Overview：数据概览 KPI + 覆盖率图；
- Verdicts：因子判决表 + 详情钻取 + 评分等级着色 + 因子 chip；
- Explorer：标的 chips 联想 + K 线（红涨绿跌）+ 特征时序图；
- Backtests：回测列表 + 详情（净值/回撤/基准对照/买卖标记/轮次叠加）+ 交互提交表单 + 任务卡闭环 + top_n 对比；
- Live：六子视图（概览/持仓/循环/执行/审计/Ticket）+ KPI 条 + 权益曲线 + 盯市持仓 + 循环钻取 + mode 筛选 + 分页长表 + 诚实空态（db_exists:false）；
- Jobs：任务列表 + 实时日志 + 取消 + 五种任务表单（回测/因子/刷新/ML 训练/评估）+ 多重检验提示 + QMT 标注；
- 全站：日夜主题切换无闪烁、术语教学 tips、错误条统一兜底、503 写锁可读提示、任务运行中徽章。

### 5.4 质量保障

- **类型**：`vue-tsc --noEmit` 进验收链；API 类型自动生成杜绝字段漂移。
- **测试**：Vitest + Vue Testing Library——组件测试覆盖 JobCard 状态流转、usePolling（含隐藏暂停/卸载清理）、DataTable 分页、theme store；页面级冒烟由 ui_smoke 承担（Playwright 已有资产）。
- **Lint**：ESLint + eslint-plugin-vue + typescript-eslint。
- **读图闭环**：每页迁移完 ui_smoke 截图逐张读图（双主题 × 六页）；对照 5.3 清单核对功能对等。
- **后端零改动**：API/DB 层完全不动，pytest 全量回归作为"后端未被波及"的证明。

### 5.5 验收标准（Definition of Done）

1. `npm run build` 产物入库，`quant dashboard` 起服后 `:8501/ui/` 全功能可用（访问路径/CLI 零变化）；
2. 5.3 功能对等清单逐项核对通过；
3. `vue-tsc` 0 error、ESLint 0 error、Vitest 全绿、pytest 全量 0 失败、ruff 0；
4. ui_smoke PASS（0 console 错误）+ 双主题逐页读图确认（Anthropic 品牌视觉落地、动效可感知且不干扰）；
5. CLAUDE.md 补前端开发命令（dev/build/gen:api/test）；
6. 设计文档 + 实施计划留痕于 docs/feat/0704-frontend-framework/。

### 5.6 风险与回滚

| 风险 | 应对 |
|---|---|
| 中文衬线字体文件体积大（Noto Serif SC 全量数 MB） | 子集化（仅常用字 + 界面用字）或降级方案：中文用系统衬线栈 `Georgia, 'Noto Serif SC', serif` 不 vendored；实施期实测定夺 |
| Naive UI 换肤达不到品牌质感 | themeOverrides 覆盖不足处用局部 CSS 补；极端情况该组件手写（DataTable 等核心组件本就自研倾向） |
| 一次到位迁移期间主线需要看驾驶舱 | 迁移在 git 分支/工作树进行也可，但按用户"直推 main"偏好：迁移期 main 上旧版仍可用（构建产物最后一步才替换 static/） |
| 回滚 | `git revert` 构建产物提交即回旧版（旧 static/ 在历史树中完整） |

## 6. 阶段划分

- **本期（阶段 1）**：第 3–5 节全部内容——骨架、六页迁移、品牌视觉 v5、验收链。
- **阶段 2（另立设计）**：影子盘页（signal_snapshots 决策快照视图 + shadow_consistency_check 比对历史）——依赖本期新架构，是新架构的第一个增量页面。
