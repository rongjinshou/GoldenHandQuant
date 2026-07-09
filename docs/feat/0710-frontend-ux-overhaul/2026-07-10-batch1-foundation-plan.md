# 批一·地基（P0-P3）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为投研驾驶舱前端建立设计令牌地基、消除三源调色板漂移、统一涨跌色与导航顺序、抽出共享组件，作为后续无障碍/交互/基础设施整改的依赖底座。

**Architecture:** 地基优先。先在 `tokens.css` 建字号/间距/行高/层级标尺与状态色三件套并整改亮色对比度，再在 `base.css` 落全局焦点/按压/sr-only 原语，`theme.ts` 联动主按钮文字色；用断言 spec 锁死三源同值；语义层统一涨跌色（收益行情色/质量指标中性/判定色保留）与导航流水线顺序；最后抽 PageHeader/AppBadge 组件并加固 DataTable/ErrorBanner。

**Tech Stack:** Vue 3 `<script setup>` + TypeScript + Vite + naive-ui + ECharts + Pinia + Vitest。设计文档：`docs/feat/0710-frontend-ux-overhaul/2026-07-10-frontend-ux-overhaul-design.md`。

## Global Constraints

- **npm 铁律**：所有 npm/vitest/build 一律 Windows 侧 powershell 包装，WSL 直跑会毒化 node_modules。命令模板：`powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run <script>"`。
- **WIN_PYTHON**：`/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`，用于 `scripts/check_frontend_fresh.py`、`scripts/ui_smoke.py`。
- **Python 版本**：前端无关；后端 3.13（本批不碰后端）。
- **对比度门槛**：正文/图标文字 ≥4.5:1，UI 组件/大字 ≥3:1（WCAG 2.2 AA）。
- **色值权威**：P0 所有色值已在设计 §4.6 用 WCAG 公式复算，本计划直接采用，不得凭感觉改动。
- **令牌语义正名**：`--c-up/down/buy/sell` = 行情/委托方向；`--c-pass/fail` = 闸门判定。迁移按语义对号，禁按颜色对号（tokens.css 顶注铁律）。
- **保留标杆项**：glossary、金融披露、实盘只读、竞态守卫、reduced-motion 令牌归零、买卖 ▲▼ 形状区分——整改中不得破坏。
- **提交规范**：提交信息末尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。当前已在分支 `feat/frontend-ux-overhaul`。
- **每个 Task 收尾**：先跑 `npm run typecheck` + `npm run test` 绿灯再 commit；涉及视觉的 Task 额外跑 `npm run build` + `ui_smoke.py` 并读图自查。

## File Structure（批一触及）

- `frontend/src/styles/tokens.css` — 令牌单一真相源（改）
- `frontend/src/styles/base.css` — 全局原语（改）
- `frontend/src/styles/__tests__/tokens.contrast.spec.ts` — 对比度守卫（新）
- `frontend/src/stores/theme.ts` — naive 覆盖，主按钮文字色（改）
- `frontend/src/stores/__tests__/palette-sync.spec.ts` — 三源同值断言（新）
- `frontend/src/composables/useChartTheme.ts` — ECharts 调色板（改：无）；`EquityChart.vue` 去重（改）
- `frontend/src/router.ts` — 导航顺序（改）
- `frontend/src/router.__tests__` → `frontend/src/__tests__/router.spec.ts` — 导航顺序断言（新）
- `frontend/src/pages/Backtests.vue` — 涨跌色统一 + 图例（改）
- `frontend/src/pages/backtests/__tests__/metric-cell.spec.ts` — cell 配色单测（新，需先抽纯函数）
- `frontend/src/pages/backtests/metric-cell.ts` — 抽出的纯函数（新）
- `frontend/src/components/PageHeader.vue` — 页头组件（新）+ 6 页迁移
- `frontend/src/components/AppBadge.vue` — 徽章组件（新）+ 状态徽章迁移
- `frontend/src/components/__tests__/PageHeader.spec.ts`、`AppBadge.spec.ts` — 组件测试（新）
- `frontend/src/components/DataTable.vue` — scope + clickable 加固（改）
- `frontend/src/components/ErrorBanner.vue` — 配色修正 + 关闭/重试（改）

## 迁移范围说明（诚实边界）

- **P0 建标尺，非全量迁移**：`--fs-*`/`--space-*` 在本批建立并被新/改动组件消费（PageHeader/AppBadge/ErrorBanner/DataTable/KpiCard/base.css .card 作示范）。146 处裸字号 + 169 处裸间距的**全量 px→token 机械迁移是低风险增量清理，不阻塞本批验收**，留作滚动清理。`--gap/--gap-lg` 保留为 `--space-4/--space-5` 别名，存量零破坏。
- **DataTable 归口**：本批仅加固 DataTable 自身（scope/clickable/token）。Jobs/Backtests/PositionsTable/CyclesTable 四张手写表的归口与键盘可达（C1/C2）强耦合，**移到批二**与无障碍一起做。
- **AppBadge 迁移面**：本批建组件 + 迁移状态徽章（JobCard running/failed、Jobs 表状态、App 顶栏任务徽章）。grade 徽章（A/B/C/D 自有色逻辑）与 LvBadge 归并留批二。
- **三源同源**：本批落**断言 spec + EquityChart 去重**（设计 §5 明列的兜底防线）。运行时 getComputedStyle 注入改造留作可选增量。

---

### Task 1: tokens.css 令牌地基 + 对比度守卫测试

**Files:**
- Create: `frontend/src/styles/__tests__/tokens.contrast.spec.ts`
- Modify: `frontend/src/styles/tokens.css`

**Interfaces:**
- Produces: CSS 自定义属性 `--fs-{xs,sm,base,md,lg,xl}`、`--lh-{xs,sm,base,md,lg,xl}`、`--space-{1..6}`、`--z-{bg,base,sticky,popover,modal}`、`--text-on-accent`、`--border-input`、`--accent-strong`(仅 light)、`--c-info`、`--c-{pass,fail,warn,info}-{soft,border}`；亮色整改后的 `--text-3/--accent-blue/--c-up/down/buy/sell/pass/fail/warn`；暗色 `--border-input`。后续所有 Task 消费这些令牌。

- [ ] **Step 1: 写对比度守卫测试（先失败）**

Create `frontend/src/styles/__tests__/tokens.contrast.spec.ts`：

```ts
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const css = readFileSync(fileURLToPath(new URL('../tokens.css', import.meta.url)), 'utf8')

/** 提取某主题块内的 --var: #hex / rgba() 声明 */
function themeVars(theme: 'dark' | 'light'): Record<string, string> {
  const re = new RegExp(`:root\\[data-theme='${theme}'\\]\\s*{([^}]*)}`, 'm')
  const body = css.match(re)?.[1] ?? ''
  const out: Record<string, string> = {}
  for (const m of body.matchAll(/(--[\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

function lin(c: number): number {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
function L(hex: string): number {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}
function ratio(fg: string, bg: string): number {
  const a = L(fg)
  const b = L(bg)
  const [hi, lo] = a > b ? [a, b] : [b, a]
  return (hi + 0.05) / (lo + 0.05)
}

// 主背景常量（tokens.css 顶部权威值）
const BG = { dark: '#141413', bg2Dark: '#1f1e1c', light: '#faf9f5', bg2Light: '#f2f0e9' }
const ACCENT = '#d97757'

describe('tokens 对比度守卫 (WCAG 2.2 AA)', () => {
  it('主按钮文字 --text-on-accent 压 accent ≥4.5:1（双主题）', () => {
    for (const t of ['dark', 'light'] as const) {
      const v = themeVars(t)['--text-on-accent']
      expect(ratio(v, ACCENT), `${t} text-on-accent`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('亮色语义文字色压 bg-2 ≥4.5:1', () => {
    const v = themeVars('light')
    const bg = BG.bg2Light
    for (const key of ['--text-3', '--accent-strong', '--c-up', '--c-down', '--c-warn', '--accent-blue']) {
      expect(ratio(v[key], bg), `light ${key}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('输入框边框 --border-input 压 bg-2 ≥3:1（双主题，UI 组件门槛）', () => {
    expect(ratio(themeVars('dark')['--border-input'], BG.bg2Dark), 'dark border-input').toBeGreaterThanOrEqual(3)
    expect(ratio(themeVars('light')['--border-input'], BG.bg2Light), 'light border-input').toBeGreaterThanOrEqual(3)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- tokens.contrast"`
Expected: FAIL — 现 tokens.css 无 `--text-on-accent`/`--accent-strong`/`--border-input`（取值 undefined → `ratio` NaN 断言失败），亮色 `--c-warn`(#b98a3a) 实测 2.72:1 < 4.5。

- [ ] **Step 3: 改 tokens.css — 新增标尺令牌**

在 `:root { ... }` 块内（现 `--radius` 附近）追加：

```css
  /* 字号 6 档 + 配套行高（取代 15 档散值） */
  --fs-xs: 11px;   --lh-xs: 1.5;
  --fs-sm: 12.5px; --lh-sm: 1.5;
  --fs-base: 14px; --lh-base: 1.6;
  --fs-md: 15px;   --lh-md: 1.65;
  --fs-lg: 20px;   --lh-lg: 1.3;
  --fs-xl: 26px;   --lh-xl: 1.2;

  /* 间距 4px 基网格；--gap/--gap-lg 保留为别名，存量零破坏 */
  --space-1: 4px; --space-2: 8px; --space-3: 12px;
  --space-4: 16px; --space-5: 24px; --space-6: 32px;

  /* 层级阶梯（取代魔数 100/50/-1） */
  --z-bg: -1; --z-base: 1; --z-sticky: 100; --z-popover: 200; --z-modal: 300;
```

- [ ] **Step 4: 改 tokens.css — 暗色块新增/整改**

在 `:root[data-theme='dark'] { ... }` 块内追加（保留现有声明）：

```css
  --text-on-accent: #141413;   /* 5.90:1 on accent */
  --border-input: #726f68;     /* 3.32:1 on bg-2 */
  --c-info: #6a9bcc;
  --c-pass-soft: rgba(139,163,107,.16); --c-pass-border: rgba(139,163,107,.42);
  --c-fail-soft: rgba(229,115,90,.16);  --c-fail-border: rgba(229,115,90,.42);
  --c-warn-soft: rgba(217,169,87,.16);  --c-warn-border: rgba(217,169,87,.42);
  --c-info-soft: rgba(106,155,204,.16); --c-info-border: rgba(106,155,204,.42);
```

- [ ] **Step 5: 改 tokens.css — 亮色块整改对比度 + 新增**

在 `:root[data-theme='light'] { ... }` 块内，**替换**这些行的值并**追加**新令牌：

```css
  /* 整改：以下 6 组文字色替换为达标值 */
  --text-3: #64625a;        /* 4.17 → 5.36:1 */
  --accent-blue: #46708f;   /* 2.57 → 4.63:1 */
  --c-up: #ab4530;   --c-buy: #ab4530;
  --c-down: #5a6b40; --c-sell: #5a6b40;
  --c-pass: #5a6b40; --c-fail: #ab4530;
  --c-warn: #8a6626;        /* 2.72 → 4.59:1 */
  /* 新增 */
  --accent-strong: #a8462e; /* 5.14:1；文字级 accent，--accent 保留给填充/边框 */
  --text-on-accent: #141413;
  --border-input: #827f78;  /* 3.50:1 on bg-2 */
  --c-info: #46708f;
  --c-pass-soft: rgba(90,107,64,.12);  --c-pass-border: rgba(90,107,64,.38);
  --c-fail-soft: rgba(171,69,48,.12);  --c-fail-border: rgba(171,69,48,.38);
  --c-warn-soft: rgba(138,102,38,.12); --c-warn-border: rgba(138,102,38,.38);
  --c-info-soft: rgba(70,112,143,.12); --c-info-border: rgba(70,112,143,.38);
```

> 注意：亮色 `--c-up` 现值 `#c0563c`（3.97:1）→ 改 `#ab4530`。暗色 `--c-up`(#e5735a) 等**不改**（暗色本达标）。

- [ ] **Step 6: 跑测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- tokens.contrast"`
Expected: PASS（3 个 it 全绿）。

- [ ] **Step 7: 独立复算兜底（WSL Python，防测试自身写错）**

Run:
```bash
python3 -c "
def lin(c):
 c/=255; return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
def L(h):
 h=h.lstrip('#');return 0.2126*lin(int(h[0:2],16))+0.7152*lin(int(h[2:4],16))+0.0722*lin(int(h[4:6],16))
def r(f,b):
 a,b=L(f),L(b);h,l=max(a,b),min(a,b);return (h+.05)/(l+.05)
print('warn', round(r('#8a6626','#f2f0e9'),2), 'up', round(r('#ab4530','#f2f0e9'),2), 'border-d', round(r('#726f68','#1f1e1c'),2))
"
```
Expected: `warn 4.59 up 5.08 border-d 3.32`（与设计 §4.6 一致）。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/styles/__tests__/tokens.contrast.spec.ts
git commit -m "feat(tokens): P0令牌地基+亮色12组对比度整改+对比度守卫测试

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: base.css 全局原语（焦点/按压/sr-only/骨架/accent-strong 文字）

**Files:**
- Modify: `frontend/src/styles/base.css`

**Interfaces:**
- Consumes: Task 1 的 `--accent`、`--accent-strong`（仅 light 定义，dark 回退）、`--text-3`。
- Produces: 全局 `:focus-visible` 焦点环、`button:active` 按压、`.sr-only` 工具类、骨架 reduced-motion 归零；链接/导航文字用 `--accent-strong` 回退。

- [ ] **Step 1: 写 sr-only 存在性测试（先失败）**

Create `frontend/src/styles/__tests__/base-primitives.spec.ts`：

```ts
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const css = readFileSync(fileURLToPath(new URL('../base.css', import.meta.url)), 'utf8')

describe('base.css 全局无障碍原语', () => {
  it('定义 .sr-only 工具类', () => {
    expect(css).toMatch(/\.sr-only\s*{/)
  })
  it('定义全局 :focus-visible 焦点环', () => {
    expect(css).toMatch(/:focus-visible\s*{[^}]*outline/)
  })
  it('骨架动画有 reduced-motion 归零', () => {
    expect(css).toMatch(/prefers-reduced-motion[^}]*kpi-skeleton|kpi-skeleton[^}]*animation:\s*none/s)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- base-primitives"`
Expected: FAIL（base.css 现无这些规则）。

- [ ] **Step 3: 改 base.css — 追加全局原语**

在 `base.css` 末尾追加：

```css
/* 全局焦点环: 键盘可见, 与品牌色一致(2.4.7) */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* 按压态: 全站自定义按钮统一微缩(reduced-motion 下 --dur-fast=0 不影响 transform, 单独关) */
button:active {
  transform: scale(0.98);
}
@media (prefers-reduced-motion: reduce) {
  button:active { transform: none; }
  .kpi-skeleton { animation: none; opacity: 0.7; }
}

/* 仅读屏可见文本(表头 sr-only、skip link 等) */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

- [ ] **Step 4: 改 base.css — 链接文字改 accent-strong 回退**

将现有 `a { color: var(--accent); ... }`（约 63-67 行）的 color 改为：

```css
a {
  color: var(--accent-strong, var(--accent));
  text-decoration: none;
  transition: opacity var(--dur-fast) var(--ease-out);
}
```

> `--accent-strong` 只在 light 定义；dark 未定义 → 回退 `--accent`（暗色 accent 文字本达标 5.34:1）。

- [ ] **Step 5: 跑测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- base-primitives"`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/base.css frontend/src/styles/__tests__/base-primitives.spec.ts
git commit -m "feat(base): 全局焦点环/按压/sr-only/骨架reduced-motion + 链接accent-strong

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: theme.ts 主按钮墨黑文字 + 三源同值断言

**Files:**
- Modify: `frontend/src/stores/theme.ts:12-18`（common 块）
- Create: `frontend/src/stores/__tests__/palette-sync.spec.ts`

**Interfaces:**
- Consumes: —
- Produces: naive 主按钮四态文字色 `#141413`；三源关键色断言防线。

- [ ] **Step 1: 写三源同值断言测试（先失败）**

Create `frontend/src/stores/__tests__/palette-sync.spec.ts`：

```ts
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const tokens = readFileSync(fileURLToPath(new URL('../../styles/tokens.css', import.meta.url)), 'utf8')
const chart = readFileSync(fileURLToPath(new URL('../../composables/useChartTheme.ts', import.meta.url)), 'utf8')

function tokenVar(theme: 'dark' | 'light', name: string): string {
  const body = tokens.match(new RegExp(`:root\\[data-theme='${theme}'\\]\\s*{([^}]*)}`, 'm'))?.[1] ?? ''
  return body.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1].trim() ?? ''
}

describe('三源调色板同值防线', () => {
  it('theme.ts primaryColor 与 tokens --accent 同值', () => {
    // primaryColor 是主题无关品牌橙, 两主题 --accent 都应等于它
    expect(tokenVar('dark', '--accent')).toBe('#d97757')
    expect(tokenVar('light', '--accent')).toBe('#d97757')
    expect(theme).toContain("primaryColor: '#d97757'")
  })
  it('ECharts brand 与 tokens --accent 同值', () => {
    expect(chart).toMatch(/brand:\s*'#d97757'/)
  })
  it('ECharts 暗色 up/down 与 tokens 暗色行情色同值', () => {
    expect(tokenVar('dark', '--c-up')).toBe('#e5735a')
    expect(tokenVar('dark', '--c-down')).toBe('#8ba36b')
    expect(chart).toMatch(/up:\s*'#e5735a'/)
    expect(chart).toMatch(/down:\s*'#8ba36b'/)
  })
})
```
（顶部补 `const theme = readFileSync(fileURLToPath(new URL('../theme.ts', import.meta.url)), 'utf8')`）

- [ ] **Step 2: 跑测试确认状态**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- palette-sync"`
Expected: PASS（现值本就同源——本测试是**防线**，锁死未来漂移；若某条已 FAIL 说明已有漂移，按 tokens.css 权威值对齐 theme.ts/useChartTheme.ts）。

- [ ] **Step 3: 改 theme.ts — 主按钮文字墨黑**

将 `common` 块（12-18 行）改为追加 Button 覆盖。把 `DARK_OVERRIDES`/`LIGHT_OVERRIDES` 各加 `Button` 段。在 `common` 后、`DARK_OVERRIDES` 定义处修改为：

```ts
const BUTTON_PRIMARY_TEXT = {
  textColorPrimary: '#141413',
  textColorHoverPrimary: '#141413',
  textColorPressedPrimary: '#141413',
  textColorFocusPrimary: '#141413',
} as const

const DARK_OVERRIDES: GlobalThemeOverrides = {
  common: {
    ...common,
    bodyColor: '#141413',
    cardColor: '#1f1e1c',
    modalColor: '#1f1e1c',
    popoverColor: '#2a2926',
    inputColor: '#2a2926',
    borderColor: '#3a3833',
    textColorBase: '#faf9f5',
    textColor1: '#faf9f5',
    textColor2: '#d6d4cb',
    textColor3: '#9d9b92',
  },
  Button: BUTTON_PRIMARY_TEXT,
}
```

同样给 `LIGHT_OVERRIDES` 加 `Button: BUTTON_PRIMARY_TEXT,`。

- [ ] **Step 4: 跑 typecheck + 测试**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck; npm run test -- palette-sync"`
Expected: typecheck 无错；palette-sync PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/theme.ts frontend/src/stores/__tests__/palette-sync.spec.ts
git commit -m "feat(theme): 主按钮文字墨黑(2.96→5.90:1) + 三源调色板同值断言防线

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: EquityChart tooltip 去重（消除逐字重抄）

**Files:**
- Modify: `frontend/src/pages/backtests/EquityChart.vue`（import 与 tooltip option）

**Interfaces:**
- Consumes: `useChartTheme.ts` 的 `tooltipStyle(t)` 助手（已存在，签名 `(t: ChartPalette) => {...}`）。
- Produces: —

- [ ] **Step 1: 定位重抄处**

Run: `grep -n "backdrop-filter\|tooltipStyle\|import.*useChartTheme\|box-shadow: 0 10px" frontend/src/pages/backtests/EquityChart.vue`
Expected: 看到 tooltip option 内逐字重抄的 `backdrop-filter: blur... box-shadow: 0 10px 30px rgba(0,0,0,.28); padding: 8px 11px;`，且 import 只取了 `vGradient`。

- [ ] **Step 2: 改 import**

将 EquityChart.vue 顶部对 useChartTheme 的 import 补上 `tooltipStyle`：

```ts
import { axisStyle, tooltipStyle, useChartTheme, vGradient } from '@/composables/useChartTheme'
```
（若原来没 import `axisStyle` 则按实际现有项增补，只需确保含 `tooltipStyle`；用 grep 结果确认当前 import 列表后精确编辑。）

- [ ] **Step 3: 替换 tooltip option**

将 EquityChart 内手写的 `tooltip: { backgroundColor: ..., extraCssText: 'backdrop-filter... padding: 8px 11px;' }` 的**样式字段**替换为展开 `tooltipStyle(t)`，保留 tooltip 的 `trigger`/`axisPointer`/`formatter` 等行为字段。形如：

```ts
tooltip: {
  trigger: 'axis',
  ...tooltipStyle(t),        // 毛玻璃样式统一走助手
  axisPointer: { /* 原有值保留 */ },
  formatter: /* 原有 formatter 保留 */,
},
```
（`t` 为 `useChartTheme()` 的当前调色板；按文件内现有变量名对齐。）

- [ ] **Step 4: typecheck + 组件测试 + build**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck; npm run test; npm run build"`
Expected: 全绿；build 产出 static/。

- [ ] **Step 5: 读图自查回归**

Run: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe scripts/ui_smoke.py`
然后 Read `data/ui_screenshots/04-backtests.png` 双主题确认净值图 tooltip 无视觉回归（需 hover 才见 tooltip，主要确认图表整体未破）。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/backtests/EquityChart.vue
git commit -m "refactor(chart): EquityChart tooltip 改用 tooltipStyle 助手, 消除逐字重抄

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 导航流水线重排

**Files:**
- Modify: `frontend/src/router.ts:18-25`（NAV_ITEMS 数组顺序）
- Create: `frontend/src/__tests__/router.spec.ts`

**Interfaces:**
- Consumes: —
- Produces: `NAV_ITEMS` 顺序 = overview/explorer/verdicts/backtests/live/jobs。

- [ ] **Step 1: 写顺序断言测试（先失败）**

Create `frontend/src/__tests__/router.spec.ts`：

```ts
import { describe, expect, it } from 'vitest'

import { NAV_ITEMS } from '@/router'

describe('导航顺序按流水线心智', () => {
  it('总览→行情→判决→回测→实盘→任务', () => {
    expect(NAV_ITEMS.map((i) => i.name)).toEqual([
      'overview', 'explorer', 'verdicts', 'backtests', 'live', 'jobs',
    ])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- router"`
Expected: FAIL（现顺序为 overview/backtests/explorer/verdicts/live/jobs）。

- [ ] **Step 3: 改 router.ts — 重排 NAV_ITEMS**

将 `NAV_ITEMS` 改为：

```ts
export const NAV_ITEMS = [
  { name: 'overview', label: '总览' },
  { name: 'explorer', label: '行情' },
  { name: 'verdicts', label: '判决' },
  { name: 'backtests', label: '回测' },
  { name: 'live', label: '实盘' },
  { name: 'jobs', label: '任务' },
] as const
```
（`routes` 定义不动，仅 NAV_ITEMS 顺序变。）

- [ ] **Step 4: 跑测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- router"`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router.ts frontend/src/__tests__/router.spec.ts
git commit -m "feat(nav): 导航按流水线重排(总览/行情/判决/回测/实盘/任务)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 涨跌色统一（收益行情色 / 质量指标中性 / 判定色保留）+ 图例

**Files:**
- Create: `frontend/src/pages/backtests/metric-cell.ts`
- Create: `frontend/src/pages/backtests/__tests__/metric-cell.spec.ts`
- Modify: `frontend/src/pages/Backtests.vue:199-231`（抽函数）、图例模板

**Interfaces:**
- Consumes: —
- Produces: `marketCell(v, fmt)`（收益/盈亏→行情色 t-up/t-down）、`qualityCell(v, fmt)`（质量指标→中性）、`ddCell(v, fmt)`（回撤→超阈红）；`Cell = { text: string; cls: string }`。

- [ ] **Step 1: 写纯函数测试（先失败）**

Create `frontend/src/pages/backtests/__tests__/metric-cell.spec.ts`：

```ts
import { describe, expect, it } from 'vitest'

import { ddCell, marketCell, qualityCell } from '../metric-cell'

const id = (x: number) => String(x)

describe('回测指标 cell 配色', () => {
  it('收益正号=行情涨色 t-up(A股红)', () => {
    expect(marketCell(0.07, id).cls).toBe('t-up')
  })
  it('收益负号=行情跌色 t-down(A股绿)', () => {
    expect(marketCell(-0.03, id).cls).toBe('t-down')
  })
  it('收益为 0 无色', () => {
    expect(marketCell(0, id).cls).toBe('')
  })
  it('null → t-muted 破折号', () => {
    expect(marketCell(null, id)).toEqual({ text: '-', cls: 't-muted' })
  })
  it('质量指标恒中性(好夏普不显红/绿)', () => {
    expect(qualityCell(0.53, id).cls).toBe('')
    expect(qualityCell(-0.1, id).cls).toBe('')
  })
  it('回撤 >20% 标 t-fail, 否则无色', () => {
    expect(ddCell(0.25, id).cls).toBe('t-fail')
    expect(ddCell(0.15, id).cls).toBe('')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- metric-cell"`
Expected: FAIL（`metric-cell.ts` 不存在）。

- [ ] **Step 3: 写 metric-cell.ts**

Create `frontend/src/pages/backtests/metric-cell.ts`：

```ts
export interface Cell {
  text: string
  cls: string
}

/** 带符号收益/盈亏 → A股行情色（涨/正=红 t-up, 跌/负=绿 t-down） */
export function marketCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: 't-muted' }
  return { text: fmt(v), cls: v > 0 ? 't-up' : v < 0 ? 't-down' : '' }
}

/** 质量指标（夏普/Calmar/胜率等）→ 中性，不上红绿（越大越好但非涨跌） */
export function qualityCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: '' }
}

/** 最大回撤 → 超 20% 标失败红，否则中性 */
export function ddCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: '' }
  return { text: fmt(v), cls: v > 0.2 ? 't-fail' : '' }
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- metric-cell"`
Expected: PASS（6 个 it 全绿）。

- [ ] **Step 5: 改 Backtests.vue — 接入纯函数**

删除 199-210 行的内联 `interface Cell` / `signedCell` / `plainCell`（`plainCell` 若他处仍用则保留；grep 确认），改为 import：

```ts
import { ddCell, marketCell, qualityCell, type Cell } from './backtests/metric-cell'
```
（Backtests.vue 在 pages/ 下，相对路径为 `./backtests/metric-cell`。）

将 `metricRows`（211-231 行）的 cells 改为：

```ts
    cells: [
      marketCell(s.total_return, pct),
      marketCell(s.annualized_return, pct),
      ddCell(s.max_drawdown, pct),
      qualityCell(s.sharpe_ratio, f3),
      qualityCell(s.sortino_ratio, f3),
      qualityCell(s.calmar_ratio, f3),
      qualityCell(s.win_rate, pct),
      { text: s.trade_count == null ? '-' : String(s.trade_count), cls: '' },
      qualityCell(s.turnover_rate, pct),
    ] as Cell[],
```

将 361 行基准超额 alpha 的配色由 `t-pass/t-fail` 改为行情色：

```html
<b class="num" :class="benchInfo.stats.alpha >= 0 ? 't-up' : 't-down'">{{ pct(Math.abs(benchInfo.stats.alpha)) }}</b>
```

- [ ] **Step 6: 改 Backtests.vue — 净值图区加图例**

在净值与回撤图表卡标题旁（图表容器上方）加一次性图例。定位「净值与回撤」标题所在模板处，追加：

```html
<span class="chart-legend-note t-muted">红=正收益/涨，绿=负收益/跌（A股行情色）</span>
```

配套 scoped 样式（用令牌）：

```css
.chart-legend-note {
  font-size: var(--fs-xs);
  margin-left: var(--space-2);
}
```

- [ ] **Step 7: typecheck + 全量测试 + build + 读图**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck; npm run test; npm run build"`
Expected: 全绿。
Run: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe scripts/ui_smoke.py`
Read `data/ui_screenshots/04-backtests.png`：确认总收益/年化正号显**红**、负显绿；夏普等**无色**；图例可见。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/backtests/metric-cell.ts frontend/src/pages/backtests/__tests__/metric-cell.spec.ts frontend/src/pages/Backtests.vue
git commit -m "feat(backtests): 涨跌色统一A股行情色(收益红涨/质量中性)+表图例

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: PageHeader 组件 + 六页迁移

**Files:**
- Create: `frontend/src/components/PageHeader.vue`
- Create: `frontend/src/components/__tests__/PageHeader.spec.ts`
- Modify: `Overview.vue`、`Backtests.vue`、`Explorer.vue`、`Verdicts.vue`、`Live.vue`、`Jobs.vue`（各 page-head/guide 块 + scoped 样式删除）

**Interfaces:**
- Consumes: `--fs-*`/`--space-*`/`--text-3`。
- Produces: `<PageHeader title meta? guide?>` + 默认插槽（复杂 guide 用插槽）。

- [ ] **Step 1: 写组件测试（先失败）**

Create `frontend/src/components/__tests__/PageHeader.spec.ts`：

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PageHeader from '../PageHeader.vue'

describe('PageHeader', () => {
  it('渲染标题 h2', () => {
    const w = mount(PageHeader, { props: { title: '回测' } })
    expect(w.find('h2').text()).toBe('回测')
  })
  it('meta 存在时渲染 meta 行', () => {
    const w = mount(PageHeader, { props: { title: 'X', meta: '判决轮次 1' } })
    expect(w.text()).toContain('判决轮次 1')
  })
  it('guide prop 渲染引导句', () => {
    const w = mount(PageHeader, { props: { title: 'X', guide: '一句话说明' } })
    expect(w.text()).toContain('一句话说明')
  })
  it('默认插槽覆盖 guide（复杂引导）', () => {
    const w = mount(PageHeader, { props: { title: 'X' }, slots: { default: '<a>链接引导</a>' } })
    expect(w.find('a').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- PageHeader"`
Expected: FAIL（组件不存在）。

- [ ] **Step 3: 写 PageHeader.vue**

Create `frontend/src/components/PageHeader.vue`：

```vue
<script setup lang="ts">
defineProps<{ title: string; meta?: string; guide?: string }>()
</script>

<template>
  <div class="page-header">
    <header class="page-head">
      <h2>{{ title }}</h2>
      <span v-if="meta" class="meta-line t-muted num">{{ meta }}</span>
    </header>
    <p v-if="$slots.default || guide" class="guide t-muted">
      <slot>{{ guide }}</slot>
    </p>
  </div>
</template>

<style scoped>
.page-head {
  align-items: baseline;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.page-head h2 {
  font-size: var(--fs-xl);
  line-height: var(--lh-xl);
  margin: 0;
}

.meta-line {
  font-size: var(--fs-sm);
}

.guide {
  font-size: var(--fs-base);
  line-height: var(--lh-base);
  margin: 0 0 var(--space-5);
  max-width: 74ch;
}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- PageHeader"`
Expected: PASS。

- [ ] **Step 5: 迁移 Overview.vue**

import：`import PageHeader from '@/components/PageHeader.vue'`。
将模板 93-99 行的 `<header class="page-head">...</header>` + `<p class="guide">...</p>` 替换为：

```html
<PageHeader title="数据资产总览" :meta="metaLine">
  本系统的研究工作是一条流水线：数据资产喂给因子判决，过闸因子组成策略去回测，回测通过的策略上纸面（实盘 dry_run）验证。下方四步即对应四个页签，点击可直接跳转。
</PageHeader>
```
删除 Overview.vue scoped 样式中的 `.page-head`、`.page-head h2`、`.guide`、`.meta-line`（若有）块。

- [ ] **Step 6: 迁移其余五页**

对 `Backtests.vue`/`Explorer.vue`/`Verdicts.vue`/`Live.vue`/`Jobs.vue` 重复：import PageHeader → 替换 page-head/guide 模板 → 删除对应 scoped 样式。各页标题与 guide 文案照原样搬入（Backtests「回测」、Explorer「个股查看」含副标、Verdicts「因子判决」、Live「实盘 / 纸面前向」、Jobs「任务中心」）。含内联链接的 guide（如 Explorer/Backtests 的「时序策略」「截面策略」GlossaryTip）用**默认插槽**搬入以保留 GlossaryTip 组件。

> 逐页迁移后立即 `npm run typecheck` 验证该页无残留引用，再进下一页，避免批量出错难定位。

- [ ] **Step 7: 全量 typecheck + 测试 + build + 读图**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck; npm run test; npm run build"`
Expected: 全绿。
Run: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe scripts/ui_smoke.py`
Read 六页截图，确认页头视觉与迁移前一致（标题字号、guide 间距）。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/PageHeader.vue frontend/src/components/__tests__/PageHeader.spec.ts frontend/src/pages/
git commit -m "refactor(ui): 抽 PageHeader 组件, 六页 page-head/guide 去重

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: AppBadge 组件 + 状态徽章迁移 + DataTable/ErrorBanner 加固

**Files:**
- Create: `frontend/src/components/AppBadge.vue`
- Create: `frontend/src/components/__tests__/AppBadge.spec.ts`
- Modify: `frontend/src/components/DataTable.vue`（th scope + clickable）
- Modify: `frontend/src/components/ErrorBanner.vue`（配色 + 关闭 + 重试）
- Modify: `frontend/src/components/JobCard.vue`、`frontend/src/pages/Jobs.vue`、`frontend/src/App.vue`（状态徽章迁移）

**Interfaces:**
- Consumes: Task 1 的 `--c-{pass,fail,warn,info}-{soft,border}`、`--fs-xs`、`--text-on-accent`、`--accent`。
- Produces: `<AppBadge kind size?>`（kind: 'info'|'pass'|'warn'|'fail'|'accent'；size: 'sm'|'md'）；`ErrorBanner` 加 `@retry`/`@close` 可选事件与 `dismissible`/`retryable` prop。

- [ ] **Step 1: 写 AppBadge 测试（先失败）**

Create `frontend/src/components/__tests__/AppBadge.spec.ts`：

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppBadge from '../AppBadge.vue'

describe('AppBadge', () => {
  it('渲染插槽内容', () => {
    const w = mount(AppBadge, { props: { kind: 'pass' }, slots: { default: 'PASS' } })
    expect(w.text()).toBe('PASS')
  })
  it('kind 映射到 badge--{kind} 类', () => {
    const w = mount(AppBadge, { props: { kind: 'fail' }, slots: { default: 'x' } })
    expect(w.classes()).toContain('badge--fail')
  })
  it('默认 size=md, 传 sm 加 badge--sm', () => {
    const w = mount(AppBadge, { props: { kind: 'info', size: 'sm' }, slots: { default: 'x' } })
    expect(w.classes()).toContain('badge--sm')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- AppBadge"`
Expected: FAIL。

- [ ] **Step 3: 写 AppBadge.vue**

Create `frontend/src/components/AppBadge.vue`：

```vue
<script setup lang="ts">
withDefaults(defineProps<{ kind: 'info' | 'pass' | 'warn' | 'fail' | 'accent'; size?: 'sm' | 'md' }>(), {
  size: 'md',
})
</script>

<template>
  <span class="badge" :class="[`badge--${kind}`, { 'badge--sm': size === 'sm' }]" data-testid="app-badge">
    <slot />
  </span>
</template>

<style scoped>
.badge {
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 2px 8px;
}
.badge--sm { padding: 1px 6px; }

.badge--pass { background: var(--c-pass-soft); border-color: var(--c-pass-border); color: var(--c-pass); }
.badge--fail { background: var(--c-fail-soft); border-color: var(--c-fail-border); color: var(--c-fail); }
.badge--warn { background: var(--c-warn-soft); border-color: var(--c-warn-border); color: var(--c-warn); }
.badge--info { background: var(--c-info-soft); border-color: var(--c-info-border); color: var(--c-info); }
.badge--accent { background: var(--accent); color: var(--text-on-accent); }
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- AppBadge"`
Expected: PASS。

- [ ] **Step 5: 迁移状态徽章**

- `App.vue:132-140` 顶栏任务徽章：改用 `<AppBadge kind="accent" size="sm">{{ jobsStore.activeCount }}</AppBadge>`，删除本地 `.badge` 样式（白字问题一并消除，改由 `--text-on-accent` 承接）。
- `JobCard.vue` running/failed 状态徽章：running → `<AppBadge kind="accent" size="sm">`；failed → `<AppBadge kind="fail" size="sm">`；其余状态按语义映射（queued→info、done→pass）。删除本地 badge 样式块。
- `Jobs.vue` 表内状态徽章同上映射。

> 逐文件迁移后即刻 typecheck，确认状态→kind 映射覆盖全部枚举（queued/running/done/failed/canceled/dead）。canceled→warn、dead→fail。

- [ ] **Step 6: DataTable 加固（scope + clickable）**

改 `DataTable.vue`：
- props 增 `clickable?: boolean`（默认 false）：

```ts
const props = withDefaults(
  defineProps<{
    rows: Record<string, unknown>[]
    columns: Column[]
    rowKey: string
    pageSize?: number
    clickable?: boolean
  }>(),
  { pageSize: 50, clickable: false },
)
```

- th 加 `scope="col"`（61 行）：

```html
<th v-for="column in columns" :key="column.key" scope="col" :class="{ right: column.align === 'right' }">
```

- 行 hover 高亮与 rowClick 仅在 clickable 时启用。将 67-71 行 `<tr>` 改为：

```html
<tr
  v-for="record in visible"
  :key="String(record[rowKey])"
  :class="{ 'row-clickable': clickable }"
  @click="clickable && emit('rowClick', record)"
>
```

- 样式：把 131-133 行 `tbody tr:hover` 限定到 `.row-clickable`：

```css
tbody tr.row-clickable { cursor: pointer; }
tbody tr.row-clickable:hover { background: var(--accent-soft); }
```

> 这样堵住「hover 高亮暗示可点但无消费者」的幽灵隐患（DataTable 现无 clickable 消费者 → 默认无 hover 高亮）。

- [ ] **Step 7: ErrorBanner 配色修正 + 关闭/重试**

改 `ErrorBanner.vue` 为：

```vue
<script setup lang="ts">
withDefaults(defineProps<{ msg: string; retryable?: boolean; dismissible?: boolean }>(), {
  retryable: false,
  dismissible: false,
})
defineEmits<{ retry: []; close: [] }>()
</script>

<template>
  <div class="error-banner" role="alert" data-testid="error-banner">
    <span class="eb-msg">⚠ {{ msg }}</span>
    <span class="eb-actions">
      <button v-if="retryable" type="button" class="eb-btn" @click="$emit('retry')">重试</button>
      <button v-if="dismissible" type="button" class="eb-btn eb-close" aria-label="关闭" @click="$emit('close')">✕</button>
    </span>
  </div>
</template>

<style scoped>
.error-banner {
  align-items: center;
  background: var(--c-fail-soft);
  border: 1px solid var(--c-fail-border);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  display: flex;
  font-size: var(--fs-base);
  gap: var(--space-3);
  justify-content: space-between;
  margin-bottom: var(--space-4);
  padding: 10px 14px;
}
.eb-actions { display: inline-flex; gap: var(--space-2); }
.eb-btn {
  background: transparent;
  border: 1px solid var(--c-fail-border);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  cursor: pointer;
  font-size: var(--fs-xs);
  min-height: 24px;
  min-width: 24px;
  padding: 2px 8px;
}
.eb-close { border-color: transparent; }
</style>
```

> 现有 6 处 `<ErrorBanner :msg="..."/>` 用法不传新 prop 时行为不变（retry/close 默认关），零破坏。retry 实际接线在批二。

- [ ] **Step 8: 全量 typecheck + 测试 + build + 读图**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck; npm run test; npm run build"`
Expected: 全绿。
Run: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe scripts/ui_smoke.py`
Read `01-overview.png`(顶栏徽章)、`06-jobs.png`(状态徽章)、`05-live.png`：确认徽章配色达标、ErrorBanner 若出现为失败红底、无回归。

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/
git commit -m "refactor(ui): 抽 AppBadge + 状态徽章迁移; DataTable scope/clickable 加固; ErrorBanner 失败红配色+关闭/重试

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 批一验收（全部 Task 完成后）

- [ ] **Step A: 全量绿灯**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck; npm run lint; npm run test; npm run build"`
Expected: 四项全绿；build 写入 `src/interfaces/api/static/`。

- [ ] **Step B: 漂移防线**

Run: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe scripts/check_frontend_fresh.py`
Expected: 退出 0（frontend/src 已 build）。

- [ ] **Step C: 冒烟 + 双主题读图**

Run: `/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe scripts/ui_smoke.py`
Expected: 六页锚点命中，console 零错（gates 404 属陈旧进程，若仍现忽略并记录）。
读 `data/ui_screenshots/` 六页 + 切亮色主题重跑读图，确认：亮色语义色不再发灰、主按钮墨黑字、导航新顺序、回测涨跌色红涨绿跌、徽章达标。

- [ ] **Step D: 对比度终算**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test -- contrast"`
Expected: PASS。

- [ ] **Step E: 更新台账**

在设计文档同目录追加 `batch1-done.md` 记录：完成项、截图前后、遗留（px→token 全量迁移、DataTable 四表归口移批二）。提交。

## Self-Review 覆盖核对

- P0 令牌地基 → Task 1/2/3 ✓（字号/间距/行高/层级/状态色三件套/对比度整改/焦点/按压/sr-only/主按钮墨黑）
- P1 三源同源 → Task 3（断言）+ Task 4（EquityChart 去重）✓
- P2 语义横扫 → Task 5（导航）+ Task 6（涨跌色）✓
- P3 组件抽象 → Task 7（PageHeader）+ Task 8（AppBadge/DataTable/ErrorBanner）✓
- 类型一致：`Cell` 类型在 metric-cell.ts 定义并被 Backtests.vue import，未双定义 ✓
- 边界诚实：px→token 全量迁移、四表归口、grade/LvBadge 归并、运行时读令牌——均明列移出本批 ✓
