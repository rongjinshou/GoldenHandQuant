# 因子判决页卡片化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把因子判决页(`frontend/src/pages/Verdicts.vue`)的表格重构成卡片网格 + 排序/过滤工具条 + 详情弹框，并把因子检验表单挪到页面最上方。

**Architecture:** 拆出 4 个新组件(`FactorCard`/`FactorDetailModal`/`FactorTestForm` + 2 个纯逻辑文件 `sort.ts`/扩展 `gates.ts`)，`Verdicts.vue` 收敛为编排层(数据加载 + 过滤排序状态 + 弹框开关)。详情弹框用 naive-ui `NModal`(全站首例，参数已逐条核对源码确认默认行为)。零后端改动。

**Tech Stack:** Vue 3.5 `<script setup lang="ts">` + Composition API、naive-ui 2.44.1、TypeScript 5.9、Vitest 4 + @vue/test-utils 2.4(jsdom)。

**设计依据:** `docs/feat/0705-verdict-cards/2026-07-05-verdict-cards-design.md`(已批准)。本计划中任何与设计文档措辞不一致之处（如事件命名、组件契约细节）以本计划为准——这些是设计落地时才需要钉死的实现细节，不构成对设计的偏离。

## Global Constraints

- Vue 3.5 `<script setup lang="ts">` + Composition API，与现有代码风格一致；不引入新 npm 依赖(naive-ui 已是运行时依赖)。
- TypeScript 严格模式，不用 `any`；类型沿用 `@/api/types` 现有手写类型(`VerdictFactor`/`VerdictRun`)，本次不改动这两个接口。
- 测试栈 Vitest 4 + @vue/test-utils 2.4，`environment: 'jsdom'`。**约定**：页面级/组件级测试一律 stub naive-ui 组件(参照 `src/pages/__tests__/Jobs.spec.ts` 的 `NDatePicker: true` 等写法)，不在 jsdom 下挂载真实 naive-ui 组件——项目里现有测试无一例外都这样做，为的是绕开 naive-ui 内部 ResizeObserver/matchMedia 在 jsdom 下的兼容性摩擦。
- `data-testid` 沿用 kebab-case 约定；同类重复元素共用同一个 testid，测试用 `findAll`(参照 `job-row`/`job-card` 先例)。
- 零后端改动；不改 `/api/research/verdicts` 返回契约。
- `ft-factor-chip` 等既有 testid（`scripts/ui_smoke.py` 依赖）必须原样保留。
- 前端命令一律走 Windows 侧：`powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run <script>"`；构建产物需入库 `static/` 且过 `check_frontend_fresh.py`。
- 每个任务完成后直接提交到 `main`(项目既有工作方式，本会话设计文档已如此提交)，中文提交信息，风格参照 `git log` 现状(`feat(ui): ...`/`refactor(ui): ...`/`test(ui): ...`)。

---

## 背景速览(供任务内引用，不重复贴设计文档全文)

- 现状表格文件：`frontend/src/pages/Verdicts.vue`(710 行)。表格列逻辑(`columns`/`gcell`)、reasons 折叠展开(`expanded`/`toggleExpand`/`failedReasons`/`passedCount`)、因子检验表单(chips/字段/提交/JobCard)全部混在一个文件里。
- 闸门阈值权威源：`src/domain/strategy/factor_test/verdict.py`(后端)；前端阈值副本在 `frontend/src/pages/verdicts/gates.ts`(**既有债 D2**：两处需手动保持同步，本次不收敛，只维持现状口径)。
- **现存 bug**(本次顺手修)：`gates.ts` 的 `GATES` 表缺 `ic_positive_rate` 键，导致现表格「IC正率」列从未着色。阈值应为 `>= 0.52`(对齐 `verdict.py:110`)。
- `VerdictFactor`/`VerdictRun` 类型定义在 `frontend/src/api/types/research.ts`，本次不改动。
- 因子判决的 `objective`(记分牌口径：`long_short`/`long_only`)是**轮次级**参数(`run.params.objective`)，不是逐因子字段——现有 `Verdicts.vue` 用 `longOnly = computed(() => run.value?.params?.objective === 'long_only')` 联动整表列定义。本计划所有新函数/组件延续这个约定：`longOnly: boolean` 由父层算好逐层传下去，不去读 `VerdictFactor` 上并不存在于 TS 类型里的字段。
- IS/OOS 切分同理是轮次级：`run.params.split`。当某轮判决未设置切分时，后端 OOS 相关数值字段(`oos_ic_mean`/`oos_ir`/`oos_long_short_return`/`oos_top_excess_return`)全部存 `0.0`(见 `verdict.py:138-141`)——**不能**靠"数值是否为 0"反推"有没有切分"，必须显式传 `hasSplit: boolean`(来自 `!!run.params.split`)。

---

### Task 1: gates.ts 扩展 — 补闸键 + 抽取公用函数 + 新增闸门轨道

**Files:**
- Modify: `frontend/src/pages/verdicts/gates.ts`
- Test: `frontend/src/pages/verdicts/__tests__/gates.spec.ts` (新建)

**Interfaces:**
- Consumes: `VerdictFactor`(来自 `@/api/types`，字段见下方 mkFactor helper)
- Produces(后续任务都从这里 import)：
  - `GATES: Record<string, (v: number) => boolean>`(已有，新增 `ic_positive_rate` 键)
  - `gateClass(name: string, value: number | null | undefined): string`(已有，不变)
  - `gradeClass(grade: string | null | undefined): string`(已有，不变)
  - `f4/f3/f2/pct: (v: number) => string`(已有，不变)
  - `gcell(name: string, v: number | null | undefined, fmt: (x: number) => string): { text: string; cls: string }`(新增，从 `Verdicts.vue` 迁移)
  - `isPassReason(r: string): boolean`(新增，从 `Verdicts.vue` 迁移)
  - `type GateState = 'pass' | 'fail' | 'na'`
  - `interface GateCell { key: string; label: string; state: GateState; detail: string }`
  - `gateTrack(f: VerdictFactor, longOnly: boolean, hasSplit: boolean): GateCell[]`(新增，7 格固定顺序：IC → 稳定性 → 一致性 → 单调性 → 变现 → OOS符号 → OOS变现)

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/pages/verdicts/__tests__/gates.spec.ts`：

```ts
import { describe, expect, it } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import { f4, gateClass, gateTrack, gcell, gradeClass, isPassReason } from '../gates'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    ic_mean: 0.03,
    ir: 0.4,
    ic_positive_rate: 0.55,
    monotonicity_score: 0.7,
    long_short_return: 0.02,
    oos_ic_mean: 0.02,
    oos_ir: 0.35,
    oos_long_short_return: 0.01,
    excess_ir: 0.6,
    excess_positive_rate: 0.53,
    top_excess_return: 0.03,
    oos_top_excess_return: 0.02,
    score: 72,
    grade: 'B',
    passed: true,
    reasons: ['IC=0.0300 >= 0.02 ✓'],
    ...o,
  }
}

describe('gateClass', () => {
  it('无值 → gate-na', () => {
    expect(gateClass('ic_mean', null)).toBe('gate-na')
    expect(gateClass('ic_mean', undefined)).toBe('gate-na')
  })
  it('过闸 → t-pass, 未过 → t-fail', () => {
    expect(gateClass('ic_mean', 0.03)).toBe('t-pass')
    expect(gateClass('ic_mean', 0.01)).toBe('t-fail')
  })
  it('非闸门指标 → 空字符串(无着色)', () => {
    expect(gateClass('oos_ic_mean', 0.05)).toBe('')
  })
  it('ic_positive_rate 闸键存在(补齐前该列一直无着色)', () => {
    expect(gateClass('ic_positive_rate', 0.55)).toBe('t-pass')
    expect(gateClass('ic_positive_rate', 0.4)).toBe('t-fail')
  })
})

describe('gradeClass', () => {
  it('A/B/C/D 各档, F 映射到 D 档, 未知回落 B', () => {
    expect(gradeClass('A')).toBe('grade-a')
    expect(gradeClass('B')).toBe('grade-b')
    expect(gradeClass('C')).toBe('grade-c')
    expect(gradeClass('D')).toBe('grade-d')
    expect(gradeClass('F')).toBe('grade-d')
    expect(gradeClass(null)).toBe('grade-b')
    expect(gradeClass('X')).toBe('grade-b')
  })
})

describe('gcell', () => {
  it('null/undefined → 文本 "-", 类走 gate-na', () => {
    expect(gcell('ic_mean', null, f4)).toEqual({ text: '-', cls: 'gate-na' })
  })
  it('有值 → 格式化文本 + gateClass 结果', () => {
    expect(gcell('ic_mean', 0.03, f4)).toEqual({ text: '0.0300', cls: 't-pass' })
  })
})

describe('isPassReason', () => {
  it('含 ✓ 或 √ 判通过, 否则判未通过', () => {
    expect(isPassReason('IC=0.03 >= 0.02 ✓')).toBe(true)
    expect(isPassReason('IC=0.03 >= 0.02 √')).toBe(true)
    expect(isPassReason('单调性=0.52 < 0.6 (单调性不足)')).toBe(false)
  })
})

describe('gateTrack', () => {
  it('long_short 口径: 5 道 IS 闸 + 未设切分 → 后 2 道 na, 顺序固定', () => {
    const track = gateTrack(mkFactor(), false, false)
    expect(track).toHaveLength(7)
    expect(track.map((c) => c.state)).toEqual(['pass', 'pass', 'pass', 'pass', 'pass', 'na', 'na'])
    expect(track.map((c) => c.key)).toEqual([
      'ic_mean', 'ir', 'ic_positive_rate', 'monotonicity_score',
      'long_short_return', 'oos_sign', 'oos_long_short_return',
    ])
  })

  it('long_only 口径: 稳定性/一致性/变现换成超额口径字段', () => {
    const track = gateTrack(mkFactor(), true, false)
    expect(track[1]).toMatchObject({ key: 'excess_ir', state: 'pass' })
    expect(track[2]).toMatchObject({ key: 'excess_positive_rate', state: 'pass' })
    expect(track[4]).toMatchObject({ key: 'top_excess_return', state: 'pass' })
    expect(track[6].key).toBe('oos_top_excess_return')
  })

  it('设切分且 OOS 符号一致 → 第6道 pass; 符号翻转 → fail', () => {
    const same = gateTrack(mkFactor({ ic_mean: 0.03, oos_ic_mean: 0.02 }), false, true)
    expect(same[5]).toMatchObject({ key: 'oos_sign', state: 'pass' })

    const flipped = gateTrack(mkFactor({ ic_mean: 0.03, oos_ic_mean: -0.01 }), false, true)
    expect(flipped[5]).toMatchObject({ key: 'oos_sign', state: 'fail' })
  })

  it('设切分后第7道读真实 OOS 数值', () => {
    const track = gateTrack(mkFactor({ oos_long_short_return: -0.01 }), false, true)
    expect(track[6]).toMatchObject({ key: 'oos_long_short_return', state: 'fail' })
  })

  it('无值字段 → na(不猜测)', () => {
    const track = gateTrack(mkFactor({ monotonicity_score: null }), false, false)
    expect(track[3]).toMatchObject({ key: 'monotonicity_score', state: 'na' })
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/gates.spec.ts"`
Expected: FAIL — `gcell`/`isPassReason`/`gateTrack` 未导出("does not provide an export named...")。

- [ ] **Step 3: 实现 — 用以下完整内容替换 `frontend/src/pages/verdicts/gates.ts`**

```ts
/* 判决闸门与评分等级 — 旧 pages/verdicts.js 纯逻辑抽取。
 * 阈值与 verdict.py 同步; 单一真相源收敛留作债 D2(前端复制沿现状)。 */

import type { VerdictFactor } from '@/api/types'

export const GATES: Record<string, (v: number) => boolean> = {
  ic_mean: (v) => v >= 0.02,
  ir: (v) => v >= 0.3,
  ic_positive_rate: (v) => v >= 0.52,
  monotonicity_score: (v) => v >= 0.6,
  long_short_return: (v) => v > 0,
  oos_long_short_return: (v) => v > 0,
  // long-only 记分牌门槛
  excess_ir: (v) => v >= 0.5,
  excess_positive_rate: (v) => v >= 0.52,
  top_excess_return: (v) => v > 0,
  oos_top_excess_return: (v) => v > 0,
}

/* 闸门单元格语义类: 无值 na / 过闸 pass / 未过 fail; 非闸门指标无着色 */
export function gateClass(name: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return 'gate-na'
  const gate = GATES[name]
  if (!gate) return ''
  return gate(value) ? 't-pass' : 't-fail'
}

/* 评分等级着色: A 绿 / B 中性 / C 琥珀 / D 红; F 映射到 D 档 */
export function gradeClass(grade: string | null | undefined): string {
  const g = (grade ?? '').toUpperCase()
  const map: Record<string, string> = {
    A: 'grade-a',
    B: 'grade-b',
    C: 'grade-c',
    D: 'grade-d',
    F: 'grade-d',
  }
  return map[g] ?? 'grade-b'
}

export const f4 = (v: number): string => v.toFixed(4)
export const f3 = (v: number): string => v.toFixed(3)
export const f2 = (v: number): string => v.toFixed(2)
export const pct = (v: number): string => `${(v * 100).toFixed(2)}%`

export function gcell(
  name: string,
  v: number | null | undefined,
  fmt: (x: number) => string,
): { text: string; cls: string } {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: gateClass(name, v) }
}

/* 判定符号: 后端 verdict.py 用 '✓'(U+2713); 兼容 '√'(U+221A) 防历史数据 */
export function isPassReason(r: string): boolean {
  return r.includes('✓') || r.includes('√')
}

export type GateState = 'pass' | 'fail' | 'na'

export interface GateCell {
  key: string
  label: string
  state: GateState
  detail: string
}

function trackCell(
  key: string,
  label: string,
  value: number | null | undefined,
  fmt: (v: number) => string,
): GateCell {
  if (value === null || value === undefined) {
    return { key, label, state: 'na', detail: `${label}: 无数据` }
  }
  const gate = GATES[key]
  const state: GateState = gate ? (gate(value) ? 'pass' : 'fail') : 'na'
  return { key, label, state, detail: `${label}=${fmt(value)}` }
}

/* 闸门轨道(设计 0705-verdict-cards §4.2) — 7 道硬闸门, 顺序对齐 verdict.py 判定顺序:
 * ①IC ②稳定性 ③一致性 ④单调性 ⑤变现 ⑥OOS符号一致 ⑦OOS变现。
 * ⑥⑦只信 run.params.split 有无(hasSplit), 不用 OOS 数值反猜——无切分时后端存 0.0,
 * 会跟"真实为 0"混淆。 */
export function gateTrack(f: VerdictFactor, longOnly: boolean, hasSplit: boolean): GateCell[] {
  const cells: GateCell[] = [
    trackCell('ic_mean', 'IC', f.ic_mean, f4),
    longOnly
      ? trackCell('excess_ir', '超额信息比', f.excess_ir, f2)
      : trackCell('ir', 'IR', f.ir, f3),
    longOnly
      ? trackCell('excess_positive_rate', '超额正率', f.excess_positive_rate, pct)
      : trackCell('ic_positive_rate', 'IC正率', f.ic_positive_rate, pct),
    trackCell('monotonicity_score', '单调性', f.monotonicity_score, f2),
    longOnly
      ? trackCell('top_excess_return', 'Top超额', f.top_excess_return, pct)
      : trackCell('long_short_return', '多空收益', f.long_short_return, pct),
  ]

  if (!hasSplit) {
    cells.push({ key: 'oos_sign', label: '样本外符号一致', state: 'na', detail: '未设 IS/OOS 切分' })
    cells.push(
      longOnly
        ? { key: 'oos_top_excess_return', label: '样本外Top超额', state: 'na', detail: '未设 IS/OOS 切分' }
        : { key: 'oos_long_short_return', label: '样本外多空', state: 'na', detail: '未设 IS/OOS 切分' },
    )
    return cells
  }

  const icSign = Math.sign(f.ic_mean ?? 0)
  const oosSign = Math.sign(f.oos_ic_mean ?? 0)
  const signOk = icSign === 0 || oosSign === 0 || icSign === oosSign
  cells.push({
    key: 'oos_sign',
    label: '样本外符号一致',
    state: signOk ? 'pass' : 'fail',
    detail: `IS=${f4(f.ic_mean ?? 0)} vs OOS=${f4(f.oos_ic_mean ?? 0)}`,
  })
  cells.push(
    longOnly
      ? trackCell('oos_top_excess_return', '样本外Top超额', f.oos_top_excess_return, pct)
      : trackCell('oos_long_short_return', '样本外多空', f.oos_long_short_return, pct),
  )
  return cells
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/gates.spec.ts"`
Expected: PASS，全部用例通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/verdicts/gates.ts frontend/src/pages/verdicts/__tests__/gates.spec.ts
git commit -m "$(cat <<'EOF'
refactor(ui): 判决闸门逻辑抽取 gcell/isPassReason + 新增闸门轨道 gateTrack

补 ic_positive_rate 闸键(此前表格该列一直无着色); 为卡片化重构准备可复用的
7 道闸门判定(gateTrack), 与 verdict.py 判定顺序对齐。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: sort.ts — 排序与过滤纯函数

**Files:**
- Create: `frontend/src/pages/verdicts/sort.ts`
- Test: `frontend/src/pages/verdicts/__tests__/sort.spec.ts`

**Interfaces:**
- Consumes: `VerdictFactor`(来自 `@/api/types`)
- Produces(Task 6 会 import)：
  - `type SortKey = 'verdict' | 'score' | 'ic' | 'oos_realize' | 'submitted'`
  - `SORT_OPTIONS: { label: string; value: SortKey }[]`(顺序固定，Task 6 测试依赖此顺序)
  - `type FilterKey = 'all' | 'pass' | 'fail'`
  - `sortFactors(factors: VerdictFactor[], key: SortKey, longOnly: boolean): VerdictFactor[]`(不修改入参，返回新数组)
  - `filterFactors(factors: VerdictFactor[], filter: FilterKey): VerdictFactor[]`

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/pages/verdicts/__tests__/sort.spec.ts`：

```ts
import { describe, expect, it } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import { filterFactors, sortFactors } from '../sort'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    ic_mean: null,
    ir: null,
    ic_positive_rate: null,
    monotonicity_score: null,
    long_short_return: null,
    oos_ic_mean: null,
    oos_ir: null,
    oos_long_short_return: null,
    excess_ir: null,
    excess_positive_rate: null,
    top_excess_return: null,
    oos_top_excess_return: null,
    score: null,
    grade: null,
    passed: false,
    reasons: null,
    ...o,
  }
}

describe('filterFactors', () => {
  const factors = [
    mkFactor({ factor_id: 'A', passed: true }),
    mkFactor({ factor_id: 'B', passed: false }),
    mkFactor({ factor_id: 'C', passed: true }),
  ]
  it('all 原样返回, pass/fail 各自过滤', () => {
    expect(filterFactors(factors, 'all').map((f) => f.factor_id)).toEqual(['A', 'B', 'C'])
    expect(filterFactors(factors, 'pass').map((f) => f.factor_id)).toEqual(['A', 'C'])
    expect(filterFactors(factors, 'fail').map((f) => f.factor_id)).toEqual(['B'])
  })
})

describe('sortFactors', () => {
  it('verdict: passed 降序, 同组按 score 降序(默认"放榜序")', () => {
    const factors = [
      mkFactor({ factor_id: 'low-pass', passed: true, score: 40 }),
      mkFactor({ factor_id: 'fail', passed: false, score: 90 }),
      mkFactor({ factor_id: 'high-pass', passed: true, score: 80 }),
    ]
    expect(sortFactors(factors, 'verdict', false).map((f) => f.factor_id)).toEqual([
      'high-pass', 'low-pass', 'fail',
    ])
  })

  it('score: 降序, null 排最后', () => {
    const factors = [
      mkFactor({ factor_id: 'null', score: null }),
      mkFactor({ factor_id: 'mid', score: 50 }),
      mkFactor({ factor_id: 'top', score: 90 }),
    ]
    expect(sortFactors(factors, 'score', false).map((f) => f.factor_id)).toEqual([
      'top', 'mid', 'null',
    ])
  })

  it('ic: 按 ic_mean 降序', () => {
    const factors = [
      mkFactor({ factor_id: 'a', ic_mean: 0.01 }),
      mkFactor({ factor_id: 'b', ic_mean: 0.05 }),
    ]
    expect(sortFactors(factors, 'ic', false).map((f) => f.factor_id)).toEqual(['b', 'a'])
  })

  it('oos_realize: long_short 用 oos_long_short_return, long_only 用 oos_top_excess_return', () => {
    const factors = [
      mkFactor({ factor_id: 'a', oos_long_short_return: 0.01, oos_top_excess_return: 0.05 }),
      mkFactor({ factor_id: 'b', oos_long_short_return: 0.03, oos_top_excess_return: 0.02 }),
    ]
    expect(sortFactors(factors, 'oos_realize', false).map((f) => f.factor_id)).toEqual(['b', 'a'])
    expect(sortFactors(factors, 'oos_realize', true).map((f) => f.factor_id)).toEqual(['a', 'b'])
  })

  it('submitted: 保持原序', () => {
    const factors = [mkFactor({ factor_id: 'z' }), mkFactor({ factor_id: 'a' })]
    expect(sortFactors(factors, 'submitted', false).map((f) => f.factor_id)).toEqual(['z', 'a'])
  })

  it('不修改入参数组(纯函数)', () => {
    const factors = [mkFactor({ factor_id: 'b', score: 1 }), mkFactor({ factor_id: 'a', score: 9 })]
    const original = [...factors]
    sortFactors(factors, 'score', false)
    expect(factors).toEqual(original)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/sort.spec.ts"`
Expected: FAIL — 找不到模块 `../sort`。

- [ ] **Step 3: 实现 — 创建 `frontend/src/pages/verdicts/sort.ts`**

```ts
/* 判决因子排序/过滤(设计 0705-verdict-cards §5) — 纯函数, 供卡片网格工具条使用。 */

import type { VerdictFactor } from '@/api/types'

export type SortKey = 'verdict' | 'score' | 'ic' | 'oos_realize' | 'submitted'

export const SORT_OPTIONS: { label: string; value: SortKey }[] = [
  { label: '判决 + 评分', value: 'verdict' },
  { label: '评分', value: 'score' },
  { label: 'IC 均值', value: 'ic' },
  { label: '样本外变现', value: 'oos_realize' },
  { label: '提交顺序', value: 'submitted' },
]

export type FilterKey = 'all' | 'pass' | 'fail'

function nn(v: number | null | undefined): number {
  return v === null || v === undefined ? Number.NEGATIVE_INFINITY : v
}

function oosRealizeValue(f: VerdictFactor, longOnly: boolean): number {
  return longOnly ? nn(f.oos_top_excess_return) : nn(f.oos_long_short_return)
}

export function sortFactors(
  factors: VerdictFactor[],
  key: SortKey,
  longOnly: boolean,
): VerdictFactor[] {
  const arr = [...factors]
  switch (key) {
    case 'verdict':
      return arr.sort((a, b) => Number(b.passed) - Number(a.passed) || nn(b.score) - nn(a.score))
    case 'score':
      return arr.sort((a, b) => nn(b.score) - nn(a.score))
    case 'ic':
      return arr.sort((a, b) => nn(b.ic_mean) - nn(a.ic_mean))
    case 'oos_realize':
      return arr.sort((a, b) => oosRealizeValue(b, longOnly) - oosRealizeValue(a, longOnly))
    case 'submitted':
      return arr
    default:
      return arr
  }
}

export function filterFactors(factors: VerdictFactor[], filter: FilterKey): VerdictFactor[] {
  if (filter === 'pass') return factors.filter((f) => f.passed)
  if (filter === 'fail') return factors.filter((f) => !f.passed)
  return factors
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/sort.spec.ts"`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/verdicts/sort.ts frontend/src/pages/verdicts/__tests__/sort.spec.ts
git commit -m "$(cat <<'EOF'
feat(ui): 判决因子排序/过滤纯函数(sortFactors/filterFactors)

默认"放榜序"(passed 降序 + 评分降序), 另支持按评分/IC/样本外变现/提交顺序;
oos_realize 按 objective 切键(long_only→Top超额, long_short→多空)。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: FactorCard.vue — 因子判决卡片

**Files:**
- Create: `frontend/src/pages/verdicts/FactorCard.vue`
- Test: `frontend/src/pages/verdicts/__tests__/FactorCard.spec.ts`

**Interfaces:**
- Consumes: `gateTrack`/`gcell`/`gradeClass`/`isPassReason`/`f2`/`f3`/`f4`/`pct` (Task 1, `./gates`)；`VerdictFactor` 类型 (`@/api/types`)
- Produces(Task 6 会用)：组件 props `{ factor: VerdictFactor; longOnly: boolean; hasSplit: boolean }`；**无自定义 emit** — 根元素是原生 `<button>`，父层直接用 `@click` 走 Vue 3 attrs fallthrough(非 prop/emit 的监听器自动落到唯一根元素上，键盘 Enter/Space 触发 `<button>` 原生 click 也随之免费获得，不需要自定义 keydown 处理)。`data-testid="verdict-card"`(重复，每卡一个，测试用 `findAll`)。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/pages/verdicts/__tests__/FactorCard.spec.ts`：

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import FactorCard from '../FactorCard.vue'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    factor_name: '20日动量',
    expression: 'rank(close/delay(close,20))',
    ic_mean: 0.03,
    ir: 0.4,
    ic_positive_rate: 0.55,
    monotonicity_score: 0.7,
    long_short_return: 0.02,
    oos_ic_mean: 0.02,
    oos_ir: 0.35,
    oos_long_short_return: 0.01,
    excess_ir: 0.6,
    excess_positive_rate: 0.53,
    top_excess_return: 0.03,
    oos_top_excess_return: 0.02,
    score: 72,
    grade: 'B',
    passed: true,
    reasons: ['IC=0.0300 >= 0.02 ✓'],
    ...o,
  }
}

describe('FactorCard', () => {
  it('渲染因子身份/评分等级/PASS 徽章, 无死因行', () => {
    const w = mount(FactorCard, { props: { factor: mkFactor(), longOnly: false, hasSplit: false } })
    expect(w.text()).toContain('F01')
    expect(w.text()).toContain('20日动量')
    expect(w.find('[data-testid="verdict-card-grade"]').text()).toBe('B 72')
    expect(w.text()).toContain('PASS')
    expect(w.find('[data-testid="verdict-card-fail-reason"]').exists()).toBe(false)
  })

  it('FAIL 因子显示首要死因(reasons 中第一条未通过项)', () => {
    const f = mkFactor({
      passed: false,
      reasons: ['IC=0.0300 >= 0.02 ✓', '单调性=0.52 < 0.6 (单调性不足)', 'IR=0.10 < 0.3 (IR门槛)'],
    })
    const w = mount(FactorCard, { props: { factor: f, longOnly: false, hasSplit: false } })
    expect(w.text()).toContain('FAIL')
    expect(w.find('[data-testid="verdict-card-fail-reason"]').text()).toBe('单调性=0.52 < 0.6 (单调性不足)')
  })

  it('score 为 null 时评分徽章显示 —', () => {
    const w = mount(FactorCard, {
      props: { factor: mkFactor({ score: null, grade: null }), longOnly: false, hasSplit: false },
    })
    expect(w.find('[data-testid="verdict-card-grade"]').text()).toBe('—')
  })

  it('点击时触发外部绑定的原生 click 监听(attrs fallthrough, 无需自定义 emit)', async () => {
    const onClick = vi.fn()
    const w = mount(FactorCard, {
      props: { factor: mkFactor(), longOnly: false, hasSplit: false },
      attrs: { onClick },
    })
    await w.trigger('click')
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('闸门轨道渲染 7 格, aria-label 统计通过数', () => {
    const w = mount(FactorCard, { props: { factor: mkFactor(), longOnly: false, hasSplit: true } })
    const track = w.find('[data-testid="verdict-card-track"]')
    expect(track.findAll('.gate-cell')).toHaveLength(7)
    expect(track.attributes('aria-label')).toBe('7 道闸门通过 7 道')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/FactorCard.spec.ts"`
Expected: FAIL — 找不到 `../FactorCard.vue`。

- [ ] **Step 3: 实现 — 创建 `frontend/src/pages/verdicts/FactorCard.vue`**

```vue
<script setup lang="ts">
import { computed } from 'vue'

import type { VerdictFactor } from '@/api/types'

import { f2, f3, f4, gateTrack, gcell, gradeClass, isPassReason, pct } from './gates'

/* 因子判决卡片(设计 0705-verdict-cards §4) — 表格行的替代品:
 * 左缘判决色条 → id+中文名+评分等级 → 三项关键指标 → 闸门轨道(签名元素) → PASS/FAIL徽章
 * (+FAIL 首要死因)。根元素是原生 <button>: 点击/回车/空格触发原生 click,
 * 无需自定义 emit 或 keydown 处理(父层用 @click 走 attrs fallthrough)。 */
const props = defineProps<{ factor: VerdictFactor; longOnly: boolean; hasSplit: boolean }>()

const track = computed(() => gateTrack(props.factor, props.longOnly, props.hasSplit))
const passCount = computed(() => track.value.filter((c) => c.state === 'pass').length)

const metrics = computed(() => {
  const f = props.factor
  return props.longOnly
    ? [
        { label: 'IC均值', ...gcell('ic_mean', f.ic_mean, f4) },
        { label: '超额IR', ...gcell('excess_ir', f.excess_ir, f2) },
        { label: 'OOS超额', ...gcell('oos_top_excess_return', f.oos_top_excess_return, pct) },
      ]
    : [
        { label: 'IC均值', ...gcell('ic_mean', f.ic_mean, f4) },
        { label: 'IR', ...gcell('ir', f.ir, f3) },
        { label: 'OOS多空', ...gcell('oos_long_short_return', f.oos_long_short_return, pct) },
      ]
})

const firstFailReason = computed(() => {
  if (props.factor.passed) return null
  return (props.factor.reasons ?? []).find((r) => !isPassReason(r)) ?? null
})
</script>

<template>
  <button
    type="button"
    class="factor-card card card--hoverable"
    :class="factor.passed ? 'verdict-pass' : 'verdict-fail'"
    data-testid="verdict-card"
  >
    <div class="fc-head">
      <span class="fc-id-name">
        <span class="fid num">{{ factor.factor_id }}</span>
        <span class="fname">{{ factor.factor_name ?? '' }}</span>
      </span>
      <span
        v-if="factor.score !== null && factor.score !== undefined"
        class="grade-badge"
        :class="gradeClass(factor.grade)"
        data-testid="verdict-card-grade"
      >{{ (factor.grade ?? '?').toUpperCase() }} {{ factor.score.toFixed(0) }}</span>
      <span v-else class="grade-badge grade-na" data-testid="verdict-card-grade">—</span>
    </div>

    <div class="fc-metrics">
      <span v-for="m in metrics" :key="m.label" class="fc-metric">
        <i>{{ m.label }}</i>
        <b class="num" :class="m.cls">{{ m.text }}</b>
      </span>
    </div>

    <div class="fc-track" data-testid="verdict-card-track" :aria-label="`7 道闸门通过 ${passCount} 道`">
      <span v-for="c in track" :key="c.key" class="gate-cell" :class="c.state" :title="c.detail" />
    </div>

    <div class="fc-foot">
      <span class="badge" :class="factor.passed ? 'pass' : 'fail'">{{ factor.passed ? 'PASS' : 'FAIL' }}</span>
    </div>
    <p
      v-if="firstFailReason"
      class="fc-fail-reason"
      :title="firstFailReason"
      data-testid="verdict-card-fail-reason"
    >{{ firstFailReason }}</p>
  </button>
</template>

<style scoped>
.factor-card {
  animation: card-in var(--dur-base) var(--ease-out) backwards;
  appearance: none;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  font: inherit;
  gap: 10px;
  min-height: 152px;
  text-align: left;
  width: 100%;
}

.factor-card.verdict-pass {
  border-left-color: var(--c-pass);
  border-left-width: 3px;
}

.factor-card.verdict-fail {
  border-left-color: var(--c-fail);
  border-left-width: 3px;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .factor-card {
    animation: none;
  }
}

.fc-head {
  align-items: flex-start;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.fc-id-name {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.fid {
  font-size: 13px;
  font-weight: 600;
}

.fname {
  color: var(--text-3);
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grade-badge {
  border-radius: var(--radius-sm);
  flex-shrink: 0;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  white-space: nowrap;
}

.grade-badge.grade-na {
  background: var(--bg-3);
  color: var(--text-3);
}

.grade-a {
  background: color-mix(in srgb, var(--c-pass) 18%, transparent);
  color: var(--c-pass);
}

.grade-b {
  background: var(--bg-3);
  color: var(--text-2);
}

.grade-c {
  background: color-mix(in srgb, var(--c-warn) 18%, transparent);
  color: var(--c-warn);
}

.grade-d {
  background: color-mix(in srgb, var(--c-fail) 18%, transparent);
  color: var(--c-fail);
}

.fc-metrics {
  display: flex;
  justify-content: space-between;
}

.fc-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.fc-metric i {
  color: var(--text-3);
  font-size: 10.5px;
  font-style: normal;
}

.fc-metric b {
  font-size: 13px;
  font-weight: 600;
}

.fc-track {
  display: flex;
  gap: 3px;
}

.gate-cell {
  border-radius: 2px;
  height: 10px;
  width: 10px;
}

.gate-cell.pass {
  background: color-mix(in srgb, var(--c-pass) 72%, transparent);
}

.gate-cell.fail {
  background: var(--c-fail);
}

.gate-cell.na {
  background: transparent;
  border: 1px solid var(--border);
}

.fc-foot {
  margin-top: auto;
}

.badge {
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 10px;
}

.badge.pass {
  background: color-mix(in srgb, var(--c-pass) 16%, transparent);
  color: var(--c-pass);
}

.badge.fail {
  background: color-mix(in srgb, var(--c-fail) 16%, transparent);
  color: var(--c-fail);
}

.fc-fail-reason {
  color: var(--c-fail);
  font-size: 11px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/FactorCard.spec.ts"`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/verdicts/FactorCard.vue frontend/src/pages/verdicts/__tests__/FactorCard.spec.ts
git commit -m "$(cat <<'EOF'
feat(ui): 因子判决卡片组件 FactorCard — 闸门轨道签名元素替代表格行

三级视线: 判决色条→身份+评分→关键指标, 签名元素为 7 格闸门轨道(一眼看出
挂在第几关); FAIL 卡附首要死因。原生 button 根元素靠 attrs fallthrough
免费获得点击+键盘可达性。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: FactorDetailModal.vue — 详情弹框(全站首个 modal)

**Files:**
- Create: `frontend/src/pages/verdicts/FactorDetailModal.vue`
- Test: `frontend/src/pages/verdicts/__tests__/FactorDetailModal.spec.ts`

**Interfaces:**
- Consumes: `gcell`/`gradeClass`/`isPassReason`/`f2`/`f3`/`f4`/`pct` (Task 1, `./gates`)；`VerdictFactor` (`@/api/types`)；naive-ui `NModal`。
- Produces(Task 6 会用)：props `{ show: boolean; factors: VerdictFactor[]; index: number; longOnly: boolean; hasSplit: boolean; runTitle: string }`；emits `{ 'update:show': [boolean]; navigate: [number] }`(父层用 `v-model:show` + `@navigate` 接线)。`factors`/`index` 是父层过滤排序后的**可见序列**，前后导航就是在这个序列里移动下标。

**已核实的 naive-ui NModal 行为(避免重复踩坑)：** 读取 `node_modules/naive-ui/es/modal/src/Modal.mjs` 源码确认 `maskClosable`/`closeOnEsc`/`autoFocus`/`trapFocus`/`blockScroll` 默认值均为 `true`，且遮罩点击与 Esc 两条路径都收敛到同一个 `doUpdateShow(false)` → 触发 `update:show`。所以**只需监听 `update:show`**，不需要分别接 `onEsc`/`onMaskClick`。但 naive-ui 的 Modal **不会**自动把焦点还给触发元素(已用 `grep activeElement/restoreFocus` 确认源码中无此逻辑)——焦点复原需要在 Task 6(父层)手动实现，本任务不需要处理。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/pages/verdicts/__tests__/FactorDetailModal.spec.ts`：

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import FactorDetailModal from '../FactorDetailModal.vue'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    factor_name: '20日动量',
    expression: 'rank(close/delay(close,20))',
    ic_mean: 0.03,
    ir: 0.4,
    ic_positive_rate: 0.55,
    monotonicity_score: 0.7,
    long_short_return: 0.02,
    oos_ic_mean: 0.02,
    oos_ir: 0.35,
    oos_long_short_return: 0.01,
    excess_ir: 0.6,
    excess_positive_rate: 0.53,
    top_excess_return: 0.03,
    oos_top_excess_return: 0.02,
    score: 72,
    grade: 'B',
    passed: true,
    reasons: ['IC=0.0300 >= 0.02 ✓', '单调性=0.70 >= 0.6 ✓'],
    ...o,
  }
}

const stubs = { NModal: { props: ['show'], template: '<div v-if="show"><slot /></div>' } }

describe('FactorDetailModal', () => {
  it('show=false 不渲染内容', () => {
    const w = mount(FactorDetailModal, {
      props: { show: false, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('[data-testid="verdict-modal"]').exists()).toBe(false)
  })

  it('展示身份/表达式/轮次上下文/逐关判定, OOS 未切分时显 —', () => {
    const w = mount(FactorDetailModal, {
      props: {
        show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false,
        runTitle: '3 因子 · 多空 · 未切分',
      },
      global: { stubs },
    })
    expect(w.text()).toContain('F01')
    expect(w.text()).toContain('20日动量')
    expect(w.text()).toContain('rank(close/delay(close,20))')
    expect(w.text()).toContain('3 因子 · 多空 · 未切分')
    expect(w.text()).toContain('IC=0.0300 >= 0.02 ✓')
    const rows = w.findAll('.vm-metrics tbody tr')
    expect(rows[0].text()).toContain('—') // IC均值行 OOS 列: 未切分显 —
  })

  it('设切分后 OOS 列显真实数值', () => {
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: true, runTitle: 'r' },
      global: { stubs },
    })
    const rows = w.findAll('.vm-metrics tbody tr')
    expect(rows[0].text()).toContain('0.0200') // oos_ic_mean
  })

  it('首个因子禁用上一个, 点下一个 emit navigate(1)', async () => {
    const factors = [mkFactor({ factor_id: 'A' }), mkFactor({ factor_id: 'B' }), mkFactor({ factor_id: 'C' })]
    const w = mount(FactorDetailModal, {
      props: { show: true, factors, index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('[data-testid="verdict-modal-prev"]').attributes('disabled')).toBeDefined()
    await w.find('[data-testid="verdict-modal-next"]').trigger('click')
    expect(w.emitted('navigate')?.[0]).toEqual([1])
  })

  it('末个因子禁用下一个', () => {
    const factors = [mkFactor({ factor_id: 'A' }), mkFactor({ factor_id: 'B' })]
    const w = mount(FactorDetailModal, {
      props: { show: true, factors, index: 1, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('[data-testid="verdict-modal-next"]').attributes('disabled')).toBeDefined()
  })

  it('→ 键盘导航等效点击下一个', async () => {
    const factors = [mkFactor({ factor_id: 'A' }), mkFactor({ factor_id: 'B' })]
    const w = mount(FactorDetailModal, {
      props: { show: true, factors, index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    await w.find('[data-testid="verdict-modal"]').trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('navigate')?.[0]).toEqual([1])
  })

  it('✕ 关闭钮 emit update:show(false)', async () => {
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    await w.find('.vm-close').trigger('click')
    expect(w.emitted('update:show')?.[0]).toEqual([false])
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/FactorDetailModal.spec.ts"`
Expected: FAIL — 找不到 `../FactorDetailModal.vue`。

- [ ] **Step 3: 实现 — 创建 `frontend/src/pages/verdicts/FactorDetailModal.vue`**

```vue
<script setup lang="ts">
import { NModal } from 'naive-ui'
import { computed } from 'vue'

import type { VerdictFactor } from '@/api/types'

import { f2, f3, f4, gcell, gradeClass, isPassReason, pct } from './gates'

/* 因子详情弹框(设计 0705-verdict-cards §6) — 全站首个 modal, 规范:
 * 尺寸 min(760px,92vw)/84vh 滚动, 遮罩 rgba(0,0,0,.4)+blur(2px)。
 * Esc/遮罩点击/✕ 三途径关闭均由 naive-ui NModal 默认行为覆盖(maskClosable/closeOnEsc
 * 默认 true, 已读源码确认两者都收敛到 update:show(false)), 本组件只需监听 update:show。
 * factors/index 是父层过滤排序后的可见序列 — 上一个/下一个即在这个序列里移动。 */
const props = defineProps<{
  show: boolean
  factors: VerdictFactor[]
  index: number
  longOnly: boolean
  hasSplit: boolean
  runTitle: string
}>()

const emit = defineEmits<{ 'update:show': [boolean]; navigate: [number] }>()

const factor = computed<VerdictFactor | null>(() => props.factors[props.index] ?? null)

interface MetricCell {
  text: string
  cls: string
}

interface MetricRow {
  label: string
  is: MetricCell
  oos: MetricCell
}

const NA_CELL: MetricCell = { text: '—', cls: '' }

const metricRows = computed<MetricRow[]>(() => {
  const f = factor.value
  if (!f) return []
  const oosOr = (name: string, v: number | null, fmt: (x: number) => string): MetricCell =>
    props.hasSplit ? gcell(name, v, fmt) : NA_CELL

  if (props.longOnly) {
    return [
      { label: 'IC均值', is: gcell('ic_mean', f.ic_mean, f4), oos: oosOr('oos_ic_mean', f.oos_ic_mean, f4) },
      { label: '超额信息比', is: gcell('excess_ir', f.excess_ir, f2), oos: NA_CELL },
      { label: '超额正率', is: gcell('excess_positive_rate', f.excess_positive_rate, pct), oos: NA_CELL },
      { label: '单调性', is: gcell('monotonicity_score', f.monotonicity_score, f2), oos: NA_CELL },
      {
        label: 'Top超额',
        is: gcell('top_excess_return', f.top_excess_return, pct),
        oos: oosOr('oos_top_excess_return', f.oos_top_excess_return, pct),
      },
    ]
  }
  return [
    { label: 'IC均值', is: gcell('ic_mean', f.ic_mean, f4), oos: oosOr('oos_ic_mean', f.oos_ic_mean, f4) },
    { label: 'IR', is: gcell('ir', f.ir, f3), oos: oosOr('oos_ir', f.oos_ir, f3) },
    { label: 'IC正率', is: gcell('ic_positive_rate', f.ic_positive_rate, pct), oos: NA_CELL },
    { label: '单调性', is: gcell('monotonicity_score', f.monotonicity_score, f2), oos: NA_CELL },
    {
      label: '多空收益',
      is: gcell('long_short_return', f.long_short_return, pct),
      oos: oosOr('oos_long_short_return', f.oos_long_short_return, pct),
    },
  ]
})

function go(delta: number): void {
  const next = props.index + delta
  if (next < 0 || next >= props.factors.length) return
  emit('navigate', next)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    go(-1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    go(1)
  }
}
</script>

<template>
  <NModal
    :show="show"
    :overlay-style="{ background: 'rgba(0,0,0,.4)', backdropFilter: 'blur(2px)' }"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div v-if="factor" class="verdict-modal" data-testid="verdict-modal" @keydown="onKeydown">
      <header class="vm-head">
        <span class="fid num">{{ factor.factor_id }}</span>
        <span class="fname">{{ factor.factor_name ?? '' }}</span>
        <span
          v-if="factor.score !== null && factor.score !== undefined"
          class="grade-badge"
          :class="gradeClass(factor.grade)"
        >{{ (factor.grade ?? '?').toUpperCase() }} {{ factor.score.toFixed(0) }}</span>
        <span class="badge" :class="factor.passed ? 'pass' : 'fail'">{{ factor.passed ? 'PASS' : 'FAIL' }}</span>
        <button type="button" class="vm-close" aria-label="关闭" @click="emit('update:show', false)">✕</button>
      </header>
      <p class="vm-context t-muted">{{ runTitle }}</p>

      <code v-if="factor.expression" class="vm-expr num">{{ factor.expression }}</code>

      <h4 class="vm-section">指标对照</h4>
      <table class="vm-metrics">
        <thead>
          <tr>
            <th></th>
            <th class="th-num">IS</th>
            <th class="th-num">OOS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in metricRows" :key="row.label">
            <td>{{ row.label }}</td>
            <td class="num" :class="row.is.cls">{{ row.is.text }}</td>
            <td class="num" :class="row.oos.cls">{{ row.oos.text }}</td>
          </tr>
        </tbody>
      </table>

      <h4 class="vm-section">逐关判定</h4>
      <ul class="vm-reasons">
        <li v-for="(r, i) in factor.reasons ?? []" :key="i" :class="isPassReason(r) ? 'r-pass' : 'r-fail'">{{ r }}</li>
      </ul>

      <footer class="vm-nav">
        <button type="button" :disabled="index === 0" data-testid="verdict-modal-prev" @click="go(-1)">
          ‹ 上一个<template v-if="factors[index - 1]"> ({{ factors[index - 1].factor_id }})</template>
        </button>
        <span class="vm-pos num">{{ index + 1 }} / {{ factors.length }}</span>
        <button
          type="button"
          :disabled="index === factors.length - 1"
          data-testid="verdict-modal-next"
          @click="go(1)"
        >下一个<template v-if="factors[index + 1]"> ({{ factors[index + 1].factor_id }})</template> ›</button>
      </footer>
    </div>
  </NModal>
</template>

<style scoped>
.verdict-modal {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-pop);
  max-height: 84vh;
  overflow-y: auto;
  padding: var(--gap-lg);
  width: min(760px, 92vw);
}

.vm-head {
  align-items: center;
  display: flex;
  gap: 10px;
}

.vm-head .fid {
  font-size: 15px;
  font-weight: 700;
}

.vm-head .fname {
  color: var(--text-3);
  flex: 1;
  font-size: 13px;
}

.vm-context {
  font-size: 12px;
  margin: 4px 0 0;
}

.vm-close {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 4px 8px;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.vm-close:hover {
  background: var(--bg-3);
  color: var(--text);
}

.vm-expr {
  color: var(--accent-blue);
  display: block;
  font-size: 12px;
  margin: 14px 0;
  white-space: pre-wrap;
}

.vm-section {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 18px 0 8px;
}

.vm-metrics {
  border-collapse: collapse;
  width: 100%;
}

.vm-metrics th {
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
  font-size: 11px;
  padding: 4px 8px;
  text-align: left;
}

.vm-metrics th.th-num {
  text-align: right;
}

.vm-metrics td {
  font-size: 13px;
  padding: 5px 8px;
}

.vm-metrics td.num {
  text-align: right;
}

.vm-reasons {
  list-style: none;
  margin: 0;
  padding: 0;
}

.vm-reasons li {
  border-radius: var(--radius-sm);
  font-size: 12px;
  margin-bottom: 4px;
  padding: 4px 9px;
}

.r-pass {
  background: var(--bg-3);
  color: var(--text-3);
}

.r-fail {
  background: color-mix(in srgb, var(--c-fail) 12%, transparent);
  color: var(--c-fail);
}

.vm-nav {
  align-items: center;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  margin-top: 18px;
  padding-top: 14px;
}

.vm-nav button {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  cursor: pointer;
  font-size: 12.5px;
  padding: 6px 12px;
  transition: border-color var(--dur-fast) var(--ease-out);
}

.vm-nav button:hover:not(:disabled) {
  border-color: var(--accent);
}

.vm-nav button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.vm-pos {
  color: var(--text-3);
  font-size: 12px;
}

.grade-badge {
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
}

.grade-a { background: color-mix(in srgb, var(--c-pass) 18%, transparent); color: var(--c-pass); }
.grade-b { background: var(--bg-3); color: var(--text-2); }
.grade-c { background: color-mix(in srgb, var(--c-warn) 18%, transparent); color: var(--c-warn); }
.grade-d { background: color-mix(in srgb, var(--c-fail) 18%, transparent); color: var(--c-fail); }

.badge {
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 10px;
}

.badge.pass { background: color-mix(in srgb, var(--c-pass) 16%, transparent); color: var(--c-pass); }
.badge.fail { background: color-mix(in srgb, var(--c-fail) 16%, transparent); color: var(--c-fail); }
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/FactorDetailModal.spec.ts"`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/verdicts/FactorDetailModal.vue frontend/src/pages/verdicts/__tests__/FactorDetailModal.spec.ts
git commit -m "$(cat <<'EOF'
feat(ui): 因子详情弹框 FactorDetailModal — 全站首个 modal 规范

IS/OOS 双列指标对照替代原 8 列横排表格; 逐关判定渲染后端 reasons 原文
(权威留痕); 前后导航跟随父层过滤排序后的可见序列, 支持 ←/→ 键盘。
NModal 参数(maskClosable/closeOnEsc/trapFocus 等)已读组件库源码确认默认
行为, 未额外配置冗余 prop。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: FactorTestForm.vue — 因子检验表单抽取

**Files:**
- Create: `frontend/src/pages/verdicts/FactorTestForm.vue`
- Test: `frontend/src/pages/verdicts/__tests__/FactorTestForm.spec.ts`
- (下个任务会从 `frontend/src/pages/Verdicts.vue` 删除对应代码，本任务不动 Verdicts.vue)

**Interfaces:**
- Consumes: `fetchJSON`/`postJSON` (`@/api/fetch`)；`Job`/`MetaFactor` 类型 (`@/api/types`)；`ErrorBanner`/`GlossaryTip`/`JobCard` 组件(均已存在，零改动)。
- Produces(Task 6 会用)：props `{ lastSplitHint: string | null }`；emits `{ refresh: [] }`(JobCard 终态成功后触发，语义"数据已变化，请重新加载"，替代原来内联在 Verdicts.vue 里的 `@done="() => loadVerdicts()"`)。**保留的 data-testid**(ui_smoke.py 依赖，不可改名): `ft-factors`、`ft-factor-chip`、`ft-submit`、`ft-job-area`。

**行为对照(与现状的唯一差异)：**
1. `ftSplit` 预填逻辑从"读同文件里的 `runs.value[0]?.params?.split`"改成"读 `props.lastSplitHint`"，效果不变(父层 `Verdicts.vue` 会把同一个值算好传下来)。
2. 表单自己的错误(chips 加载失败/未勾选校验/提交失败)有独立的 `ErrorBanner`，不再和"判决结果加载失败"共用一个 error 状态——两者本来就是不同来源的错误，拆开后各自离出错的地方更近，是本次抽取顺带的小改善(设计文档已备注)。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/pages/verdicts/__tests__/FactorTestForm.spec.ts`：

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import FactorTestForm from '../FactorTestForm.vue'

const META_RESPONSE = {
  factors: [
    { factor_id: 'F01', name: 'ROA', field_ready: true },
    { factor_id: 'F02', name: '停牌因子', field_ready: false },
    { factor_id: 'F03', name: 'PE', field_ready: true },
  ],
  groups: { P0: ['F01', 'F02'], P1: ['F03'] },
}

function jsonResp(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body), text: () => Promise.resolve('') })
}

const stubs = {
  NDatePicker: true,
  NInputNumber: true,
  NSelect: true,
  NButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
}

function mountForm(lastSplitHint: string | null = null) {
  return mount(FactorTestForm, { props: { lastSplitHint }, global: { stubs } })
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock = vi.fn().mockImplementation((input: unknown, init?: { method?: string }) => {
    const url = String(input)
    if (url === '/api/meta/factors') return jsonResp(META_RESPONSE)
    if (url === '/api/jobs/factor-test') {
      expect(init?.method).toBe('POST')
      return jsonResp({ job_id: 'jt1', job_type: 'factor_test', status: 'queued' })
    }
    if (url === '/api/jobs/jt1?tail=120') {
      return jsonResp({
        job_id: 'jt1', job_type: 'factor_test', params: {}, status: 'succeeded',
        created_at: '2026-07-05T09:00:00', started_at: '2026-07-05T09:00:01',
        finished_at: '2026-07-05T09:00:30', return_code: 0, log_path: 'x.log', log_tail: [],
      })
    }
    return Promise.reject(new Error(`unexpected url: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('FactorTestForm', () => {
  it('P0 组默认勾选非禁用因子, 禁用项(field_ready=false)不勾选', async () => {
    const w = mountForm()
    await flushPromises()
    const chips = w.findAll('[data-testid="ft-factor-chip"]')
    expect(chips).toHaveLength(3)
    expect(chips[0]?.classes()).toContain('checked') // F01: P0 且非禁用
    expect(chips[1]?.classes()).toContain('disabled') // F02: field_ready=false
    expect(chips[1]?.classes()).not.toContain('checked')
    expect(chips[2]?.classes()).not.toContain('checked') // F03: P1 组不自动勾
  })

  it('点击禁用 chip 不改变勾选状态', async () => {
    const w = mountForm()
    await flushPromises()
    const disabledChip = w.findAll('[data-testid="ft-factor-chip"]')[1]!
    await disabledChip.trigger('click')
    expect(disabledChip.classes()).not.toContain('checked')
  })

  it('点击可用 chip 切换勾选', async () => {
    const w = mountForm()
    await flushPromises()
    const chip = w.findAll('[data-testid="ft-factor-chip"]')[2]!
    await chip.trigger('click')
    expect(chip.classes()).toContain('checked')
    await chip.trigger('click')
    expect(chip.classes()).not.toContain('checked')
  })

  it('取消全部勾选后提交报错, 不发请求', async () => {
    const w = mountForm()
    await flushPromises()
    await w.findAll('[data-testid="ft-factor-chip"]')[0]!.trigger('click') // 取消 F01(唯一默认勾选项)
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="error-banner"]').text()).toContain('至少勾选一个因子')
    expect(fetchMock.mock.calls.some((c) => String(c[0]) === '/api/jobs/factor-test')).toBe(false)
  })

  it('提交默认载荷含默认勾选因子与默认表单值', async () => {
    const w = mountForm()
    await flushPromises()
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find((c) => String(c[0]) === '/api/jobs/factor-test')
    expect(call).toBeTruthy()
    const body = JSON.parse((call?.[1] as { body: string }).body)
    expect(body).toEqual({
      factors: 'F01',
      start_date: '',
      end_date: '',
      objective: 'long_only',
      num_layers: 5,
      rebalance_days: 5,
      cost_rate: 0.003,
    })
    expect(w.find('[data-testid="ft-job-area"]').find('[data-testid="job-card"]').exists()).toBe(true)
  })

  it('lastSplitHint 预填切分日, 提交载荷带 split_date', async () => {
    const w = mountForm('2024-06-30')
    await flushPromises()
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()
    const call = fetchMock.mock.calls.find((c) => String(c[0]) === '/api/jobs/factor-test')
    const body = JSON.parse((call?.[1] as { body: string }).body)
    expect(body.split_date).toBe('2024-06-30')
  })

  it('勾选多因子且未设切分 → 显示多重检验提示', async () => {
    const w = mountForm()
    await flushPromises()
    await w.findAll('[data-testid="ft-factor-chip"]')[2]!.trigger('click') // 加勾 F03 → 2 个已勾, 无切分
    expect(w.find('.hint').exists()).toBe(true)
  })

  it('JobCard 真实终态(succeeded)后 emit refresh', async () => {
    const w = mountForm()
    await flushPromises()
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(w.emitted('refresh')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/FactorTestForm.spec.ts"`
Expected: FAIL — 找不到 `../FactorTestForm.vue`。

- [ ] **Step 3: 实现 — 创建 `frontend/src/pages/verdicts/FactorTestForm.vue`**

```vue
<script setup lang="ts">
import { NButton, NDatePicker, NInputNumber, NSelect } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job, MetaFactor } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'

/* 因子检验表单(设计 0705-verdict-cards §3) — 从 Verdicts.vue 抽取, 置顶页面第一屏;
 * 行为对旧版零改动: chips 分组/P0 默认勾/field_ready 禁用/多重检验提示/JobCard 闭环。
 * lastSplitHint: 父层最近一轮判决的切分日, 用于预填 IS/OOS 切分(消除进页即报
 * "多重检验风险"的常驻警告)。 */
const props = defineProps<{ lastSplitHint: string | null }>()
const emit = defineEmits<{ refresh: [] }>()

const error = ref('')

interface ChipGroup {
  group: string
  chips: { factor: MetaFactor; disabled: boolean }[]
}

const chipGroups = ref<ChipGroup[]>([])
const checked = ref<Set<string>>(new Set())

async function loadFactorMeta(): Promise<void> {
  try {
    const data = await fetchJSON<{ factors: MetaFactor[]; groups: Record<string, string[]> }>(
      '/api/meta/factors',
    )
    const byId = new Map(data.factors.map((f) => [f.factor_id, f]))
    chipGroups.value = Object.entries(data.groups).map(([group, ids]) => ({
      group,
      chips: ids
        .filter((id) => byId.has(id))
        .map((id) => ({ factor: byId.get(id)!, disabled: byId.get(id)!.field_ready === false })),
    }))
    const p0 = chipGroups.value.find((g) => g.group === 'P0')
    checked.value = new Set(p0?.chips.filter((c) => !c.disabled).map((c) => c.factor.factor_id))
  } catch (e) {
    error.value = (e as Error).message
  }
}

void loadFactorMeta()

function toggleChip(id: string, disabled: boolean): void {
  if (disabled) return
  const next = new Set(checked.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  checked.value = next
}

const ftStart = ref<string | null>(null)
const ftEnd = ref<string | null>(null)
const ftSplit = ref<string | null>(null)
const ftObjective = ref('long_only')
const ftLayers = ref(5)
const ftRebalance = ref(5)
const ftCost = ref(0.003)
const ftJobIds = ref<string[]>([])

watch(
  () => props.lastSplitHint,
  (hint) => {
    if (!ftSplit.value && hint) ftSplit.value = hint
  },
  { immediate: true },
)

const OBJECTIVE_OPTIONS = [
  { label: 'Top层纯多头超额 (long_only)', value: 'long_only' },
  { label: '多空价差 (long_short)', value: 'long_short' },
]

const ftHint = computed(() => checked.value.size > 1 && !ftSplit.value)

async function submitFactorTest(): Promise<void> {
  error.value = ''
  if (checked.value.size === 0) {
    error.value = '至少勾选一个因子'
    return
  }
  const payload: Record<string, unknown> = {
    factors: [...checked.value].join(','),
    start_date: ftStart.value ?? '',
    end_date: ftEnd.value ?? '',
    objective: ftObjective.value,
    num_layers: ftLayers.value,
    rebalance_days: ftRebalance.value,
    cost_rate: ftCost.value,
  }
  if (ftSplit.value) payload.split_date = ftSplit.value
  try {
    const job = await postJSON<Job>('/api/jobs/factor-test', payload)
    ftJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  }
}
</script>

<template>
  <details class="card form-card" open data-testid="factor-test-form">
    <summary>因子检验</summary>
    <ErrorBanner v-if="error" :msg="error" />
    <div v-for="g in chipGroups" :key="g.group" class="factor-group" data-testid="ft-factors">
      <GlossaryTip term="factor_group"><span class="group-title">{{ g.group }}</span></GlossaryTip>
      <div class="fchips">
        <button
          v-for="c in g.chips"
          :key="c.factor.factor_id"
          type="button"
          class="fchip"
          :class="{ checked: checked.has(c.factor.factor_id), disabled: c.disabled }"
          :title="(c.factor.expression ?? '') + (c.disabled ? '（数据管道缺字段，禁用）' : '')"
          data-testid="ft-factor-chip"
          @click="toggleChip(c.factor.factor_id, c.disabled)"
        >
          <span class="fchip-id">{{ c.factor.factor_id }}</span>
          <span class="fchip-name">{{ c.factor.name }}</span>
        </button>
      </div>
    </div>

    <div class="form-row">
      <label>起始 <NDatePicker v-model:formatted-value="ftStart" value-format="yyyy-MM-dd" type="date" clearable /></label>
      <label>结束 <NDatePicker v-model:formatted-value="ftEnd" value-format="yyyy-MM-dd" type="date" clearable /></label>
      <label><GlossaryTip term="split_date">IS/OOS 切分</GlossaryTip> <NDatePicker v-model:formatted-value="ftSplit" value-format="yyyy-MM-dd" type="date" clearable /></label>
      <label><GlossaryTip term="objective">记分牌</GlossaryTip> <NSelect v-model:value="ftObjective" :options="OBJECTIVE_OPTIONS" style="width: 220px" /></label>
      <label><GlossaryTip term="layers">分层</GlossaryTip> <NInputNumber v-model:value="ftLayers" :min="2" :max="10" style="width: 90px" /></label>
      <label><GlossaryTip term="rebalance">调仓(日)</GlossaryTip> <NInputNumber v-model:value="ftRebalance" :min="1" style="width: 90px" /></label>
      <label><GlossaryTip term="cost_rate">成本率</GlossaryTip> <NInputNumber v-model:value="ftCost" :step="0.001" style="width: 110px" /></label>
      <NButton type="primary" data-testid="ft-submit" @click="submitFactorTest">提交检验</NButton>
    </div>
    <p v-if="ftHint" class="t-warn hint">
      多因子批量检验未设 IS/OOS 切分——存在多重检验风险，建议保留切分日期。
    </p>
    <div data-testid="ft-job-area">
      <JobCard v-for="id in ftJobIds" :key="id" :job-id="id" @done="() => emit('refresh')" />
    </div>
  </details>
</template>

<style scoped>
.form-card summary {
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
}

.factor-group {
  align-items: baseline;
  display: flex;
  gap: 12px;
  margin: 12px 0;
}

.group-title {
  color: var(--accent);
  font-family: var(--font-display);
  font-size: 12.5px;
  font-weight: 700;
  min-width: 28px;
}

.fchips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fchip {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 16px;
  color: var(--text-2);
  cursor: pointer;
  font-size: 12px;
  padding: 4px 12px;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.fchip:hover:not(.disabled) {
  border-color: var(--accent);
}

.fchip.checked {
  background: var(--accent);
  border-color: var(--accent);
  color: #faf9f5;
}

.fchip.disabled {
  border-style: dashed;
  cursor: not-allowed;
  opacity: 0.55;
  text-decoration: line-through;
}

.fchip-id {
  font-family: var(--font-mono);
  font-weight: 600;
  margin-right: 5px;
}

.form-row {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin: 14px 0;
}

.form-row label {
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
}

.hint {
  font-size: 12.5px;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/verdicts/__tests__/FactorTestForm.spec.ts"`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/verdicts/FactorTestForm.vue frontend/src/pages/verdicts/__tests__/FactorTestForm.spec.ts
git commit -m "$(cat <<'EOF'
refactor(ui): 因子检验表单抽取为 FactorTestForm 组件

从 Verdicts.vue 平移(chips分组/P0默认勾/field_ready禁用/多重检验提示/
JobCard闭环行为不变), 为置顶布局与页面瘦身铺路。切分日预填逻辑改吃
lastSplitHint prop; 表单自身错误用独立 ErrorBanner(不再与判决加载错误共用)。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Verdicts.vue 重排 — 表单置顶 + 结果区过滤排序 + 卡片网格

**Files:**
- Modify: `frontend/src/pages/Verdicts.vue`(710 行 → 完整替换为编排层，预计 ~200 行)
- Test: `frontend/src/pages/__tests__/Verdicts.spec.ts`(新建 — 该页面此前无测试覆盖)

**Interfaces:**
- Consumes: `FactorCard`(Task 3)、`FactorDetailModal`(Task 4)、`FactorTestForm`(Task 5)、`sortFactors`/`filterFactors`/`SortKey`/`SORT_OPTIONS`/`FilterKey`(Task 2, `./verdicts/sort`)、`buildVerdictRunLabel`(既有 `./verdicts/run-naming`，不变)。
- Produces: 无(叶子任务，页面级)。

**关键设计决策(执行时需要知道的"为什么")：**
1. `run.params.objective`/`run.params.split` 是**轮次级**参数——`longOnly`/`hasSplit` 两个 computed 算一次，逐层往下传给 `FactorCard`/`FactorDetailModal`，不要在子组件里重新读取。
2. `visibleFactors` = 先 `filterFactors` 再 `sortFactors`(顺序对结果无影响，但保持这个顺序方便读)。
3. 过滤/排序/切换轮次都会让"下标 i 对应哪个因子"这件事失效——所以三者任一变化时直接关闭弹框，而不是尝试保持弹框开着并静默指向别的因子(设计文档未明确这个边界情况，这里选保守做法：关闭比"偷偷换目标"更不容易让人困惑)。
4. naive-ui `NModal` 不会自动把焦点还给触发弹框的元素(Task 4 已读源码确认)，所以这里手动记录 `document.activeElement` 并在弹框关闭时还原焦点。

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/pages/__tests__/Verdicts.spec.ts`：

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { VerdictFactor, VerdictRun } from '@/api/types'

import Verdicts from '../Verdicts.vue'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01', factor_name: 'f', ic_mean: 0.03, ir: 0.4, ic_positive_rate: 0.55,
    monotonicity_score: 0.7, long_short_return: 0.02, oos_ic_mean: null, oos_ir: null,
    oos_long_short_return: null, excess_ir: null, excess_positive_rate: null,
    top_excess_return: null, oos_top_excess_return: null, score: 70, grade: 'B',
    passed: true, reasons: ['✓'], ...o,
  }
}

function mkRun(o: Partial<VerdictRun> = {}): VerdictRun {
  return {
    run_id: 'MFCOMBO-1', created_at: '2026-07-05 09:00:00',
    params: { objective: 'long_short', split: null, start: '2021-01-01', end: '2026-06-30' },
    factors: [
      mkFactor({ factor_id: 'A', passed: true, score: 80 }),
      mkFactor({ factor_id: 'B', passed: false, score: 40 }),
    ],
    ...o,
  }
}

const stubs = {
  FactorTestForm: { props: ['lastSplitHint'], emits: ['refresh'], template: '<div data-testid="stub-form" />' },
  FactorCard: {
    props: ['factor', 'longOnly', 'hasSplit'],
    template: '<button type="button" class="stub-card" @click="$emit(\'click\')">{{ factor.factor_id }}</button>',
  },
  FactorDetailModal: {
    props: ['show', 'factors', 'index', 'longOnly', 'hasSplit', 'runTitle'],
    template: '<div v-if="show" data-testid="stub-modal">{{ factors[index]?.factor_id }} {{ index + 1 }}/{{ factors.length }}</div>',
  },
  NSelect: {
    props: ['value', 'options'],
    emits: ['update:value'],
    template:
      '<div class="stub-select"><button v-for="o in options" :key="o.value" type="button" @click="$emit(\'update:value\', o.value)">{{ o.label }}</button></div>',
  },
}

let runsResp: VerdictRun[]
let wrapper: { unmount(): void } | null = null

function mountPage() {
  const w = mount(Verdicts, { global: { stubs } })
  wrapper = w
  return w
}

beforeEach(() => {
  runsResp = [mkRun()]
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: unknown) => {
      const url = String(input)
      if (url === '/api/research/verdicts') {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ runs: runsResp }),
          text: () => Promise.resolve(''),
        })
      }
      return Promise.reject(new Error(`unexpected url: ${url}`))
    }),
  )
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('Verdicts 页面编排', () => {
  it('加载后渲染 run 选择器/meta 条/全部卡片', async () => {
    const w = mountPage()
    await flushPromises()
    expect(w.find('[data-testid="run-select"]').exists()).toBe(true)
    expect(w.findAll('.stub-card')).toHaveLength(2)
    expect(w.text()).toContain('2021-01-01 → 2026-06-30')
  })

  it('空轮次列表显示空态引导语(指向上方表单)', async () => {
    runsResp = []
    const w = mountPage()
    await flushPromises()
    expect(w.find('[data-testid="verdicts-empty"]').text()).toContain('用上方表单提交')
  })

  it('加载失败显示 ErrorBanner', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net down')))
    const w = mountPage()
    await flushPromises()
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(true)
  })

  it('过滤: PASS/FAIL 切换只渲染对应卡片, 计数正确', async () => {
    const w = mountPage()
    await flushPromises()
    const filter = w.find('[data-testid="verdict-filter"]')
    expect(filter.text()).toContain('全部 2')
    expect(filter.text()).toContain('PASS 1')
    expect(filter.text()).toContain('FAIL 1')

    await filter.findAll('button')[1]!.trigger('click') // PASS
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['A'])

    await filter.findAll('button')[2]!.trigger('click') // FAIL
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['B'])
  })

  it('过滤后无匹配显示清除入口, 点击后回到全部', async () => {
    runsResp = [mkRun({ factors: [mkFactor({ factor_id: 'A', passed: true })] })]
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="verdict-filter"]').findAll('button')[2]!.trigger('click') // FAIL, 无匹配
    expect(w.find('[data-testid="verdict-filter-empty"]').exists()).toBe(true)
    await w.find('[data-testid="verdict-filter-empty"] button').trigger('click')
    expect(w.findAll('.stub-card')).toHaveLength(1)
  })

  it('排序: 切到 IC 均值重新排列卡片', async () => {
    runsResp = [mkRun({
      factors: [
        mkFactor({ factor_id: 'LOW', ic_mean: 0.01, passed: true, score: 90 }),
        mkFactor({ factor_id: 'HIGH', ic_mean: 0.08, passed: true, score: 10 }),
      ],
    })]
    const w = mountPage()
    await flushPromises()
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['LOW', 'HIGH']) // 默认: 评分降序

    const sortButtons = w.find('[data-testid="verdict-sort"]').findAll('button')
    await sortButtons[2]!.trigger('click') // SORT_OPTIONS[2] = 'IC 均值'
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['HIGH', 'LOW'])
  })

  it('点击卡片按当前可见序列下标打开弹框', async () => {
    const w = mountPage()
    await flushPromises()
    await w.findAll('.stub-card')[1]!.trigger('click') // 默认排序: A(passed) 在前, B(fail) 在后
    expect(w.find('[data-testid="stub-modal"]').text()).toContain('B 2/2')
  })

  it('切换 run 时若弹框开着则关闭', async () => {
    runsResp = [
      mkRun({ run_id: 'run-1' }),
      mkRun({ run_id: 'run-2', factors: [mkFactor({ factor_id: 'X' })] }),
    ]
    const w = mountPage()
    await flushPromises()
    await w.findAll('.stub-card')[0]!.trigger('click')
    expect(w.find('[data-testid="stub-modal"]').exists()).toBe(true)

    await w.find('[data-testid="run-select"]').findAll('button')[1]!.trigger('click') // 切到 run-2
    await flushPromises()
    expect(w.find('[data-testid="stub-modal"]').exists()).toBe(false)
  })

  it('FactorTestForm refresh 事件触发重新加载', async () => {
    const w = mountPage()
    await flushPromises()
    runsResp = [mkRun({ run_id: 'run-2' })]
    await w.findComponent(stubs.FactorTestForm).vm.$emit('refresh')
    await flushPromises()
    expect(w.find('[data-testid="run-select"]').findAll('button')[0]!.text()).toContain('run-2')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/__tests__/Verdicts.spec.ts"`
Expected: FAIL — 当前 `Verdicts.vue` 还是表格版，找不到 `run-select`/`verdict-filter`/`verdict-sort`/卡片 stub 挂载点等测试锚点。

- [ ] **Step 3: 实现 — 用以下完整内容替换 `frontend/src/pages/Verdicts.vue`**

```vue
<script setup lang="ts">
import { NSelect } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { fetchJSON } from '@/api/fetch'
import type { VerdictRun } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'

import FactorCard from './verdicts/FactorCard.vue'
import FactorDetailModal from './verdicts/FactorDetailModal.vue'
import FactorTestForm from './verdicts/FactorTestForm.vue'
import { buildVerdictRunLabel } from './verdicts/run-naming'
import { SORT_OPTIONS, filterFactors, sortFactors, type FilterKey, type SortKey } from './verdicts/sort'

/* 因子判决页(设计 0705-verdict-cards) — 检验表单置顶 + 判决结果卡片化:
 * 卡片替代表格行, 闸门轨道为签名元素, 点击卡片开详情弹框, 排序+过滤工具条。 */

const error = ref('')
const loading = ref(true)
const runs = ref<VerdictRun[]>([])
const selectedIdx = ref(0)

async function loadVerdicts(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: VerdictRun[] }>('/api/research/verdicts')
    runs.value = data.runs
    selectedIdx.value = 0
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

void loadVerdicts()

const run = computed(() => runs.value[selectedIdx.value] ?? null)
const longOnly = computed(() => run.value?.params?.objective === 'long_only')
const hasSplit = computed(() => !!run.value?.params?.split)
const lastSplitHint = computed(() => runs.value[0]?.params?.split ?? null)

const runOptions = computed(() =>
  runs.value.map((r, i) => {
    const label = buildVerdictRunLabel(r)
    return { label: `${label.title}（${(r.created_at ?? '').slice(5, 16)} · ${r.run_id}）`, value: i }
  }),
)

const metaItems = computed(() => {
  const p = run.value?.params ?? {}
  return [
    { label: '区间', value: `${p.start ?? '?'} → ${p.end ?? '?'}` },
    { label: '切分', value: p.split ?? '无', gloss: 'split_date' },
    { label: '调仓', value: `${p.rebalance_days ?? 1} 日`, gloss: 'rebalance' },
    { label: '记分牌', value: longOnly.value ? '长多(Top超额)' : '多空', gloss: 'objective' },
    { label: '覆盖股票池', value: `${p.universe_count ?? '?'} 只`, gloss: 'universe_lineage' },
    { label: '特征', value: `v${p.feature_version ?? '?'}` },
  ]
})

// ---- 过滤 + 排序 ----
const filterKey = ref<FilterKey>('all')
const sortKey = ref<SortKey>('verdict')

const totalCount = computed(() => run.value?.factors.length ?? 0)
const passCount = computed(() => run.value?.factors.filter((f) => f.passed).length ?? 0)
const failCount = computed(() => totalCount.value - passCount.value)

const visibleFactors = computed(() => {
  if (!run.value) return []
  return sortFactors(filterFactors(run.value.factors, filterKey.value), sortKey.value, longOnly.value)
})

// ---- 详情弹框 ----
const modalOpen = ref(false)
const modalIndex = ref(0)
const lastFocusedEl = ref<HTMLElement | null>(null)

function openModal(i: number): void {
  lastFocusedEl.value = document.activeElement as HTMLElement | null
  modalIndex.value = i
  modalOpen.value = true
}

watch(modalOpen, (open) => {
  if (!open) lastFocusedEl.value?.focus()
})

// 过滤/排序或切换轮次时, 弹框下标语义会变 — 直接关闭而非静默指向别的因子
watch(() => run.value?.run_id, () => { modalOpen.value = false })
watch([filterKey, sortKey], () => { modalOpen.value = false })
</script>

<template>
  <section data-testid="page-verdicts">
    <header class="page-head">
      <h2>因子判决</h2>
    </header>
    <p class="guide t-muted">
      先检验因子，判决结果随后以卡片呈现——左缘色条与闸门轨道标出 PASS/FAIL，点击卡片看全部细节。
    </p>

    <ErrorBanner v-if="error" :msg="error" />

    <FactorTestForm :last-split-hint="lastSplitHint" @refresh="loadVerdicts" />

    <p v-if="loading" class="t-muted">加载判决轮次…</p>
    <p v-else-if="!runs.length" class="t-muted" data-testid="verdicts-empty">
      暂无判决轮次 — 用上方表单提交一次因子检验。
    </p>

    <template v-if="run">
      <div class="result-head">
        <span class="list-title">判决结果</span>
        <NSelect
          v-model:value="selectedIdx"
          :options="runOptions"
          size="small"
          style="width: 380px"
          data-testid="run-select"
        />
        <div class="filter-seg" role="group" aria-label="按判决过滤" data-testid="verdict-filter">
          <button type="button" :class="{ active: filterKey === 'all' }" @click="filterKey = 'all'">全部 {{ totalCount }}</button>
          <button type="button" :class="{ active: filterKey === 'pass' }" @click="filterKey = 'pass'">PASS {{ passCount }}</button>
          <button type="button" :class="{ active: filterKey === 'fail' }" @click="filterKey = 'fail'">FAIL {{ failCount }}</button>
        </div>
        <NSelect
          v-model:value="sortKey"
          :options="SORT_OPTIONS"
          size="small"
          style="width: 190px"
          data-testid="verdict-sort"
        />
      </div>

      <div class="meta-strip card">
        <span v-for="m in metaItems" :key="m.label" class="rm">
          <GlossaryTip v-if="m.gloss" :term="m.gloss"><i>{{ m.label }}</i></GlossaryTip>
          <i v-else>{{ m.label }}</i>
          <b>{{ m.value }}</b>
        </span>
      </div>

      <p v-if="!visibleFactors.length" class="t-muted" data-testid="verdict-filter-empty">
        无匹配因子 — <button type="button" class="link-btn" @click="filterKey = 'all'">清除过滤</button>
      </p>
      <div v-else class="factor-grid" data-testid="verdict-grid">
        <FactorCard
          v-for="(f, i) in visibleFactors"
          :key="f.factor_id"
          :factor="f"
          :long-only="longOnly"
          :has-split="hasSplit"
          @click="openModal(i)"
        />
      </div>
    </template>

    <FactorDetailModal
      v-model:show="modalOpen"
      :factors="visibleFactors"
      :index="modalIndex"
      :long-only="longOnly"
      :has-split="hasSplit"
      :run-title="run ? buildVerdictRunLabel(run).title : ''"
      @navigate="(i) => (modalIndex = i)"
    />
  </section>
</template>

<style scoped>
.page-head {
  align-items: center;
  display: flex;
  gap: 14px;
  margin-bottom: 6px;
}

.page-head h2 {
  margin: 0;
}

.guide {
  font-size: 13px;
  margin: 0 0 var(--gap);
}

.result-head {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin: var(--gap-lg) 0 10px;
}

.list-title {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.filter-seg {
  display: flex;
  gap: 4px;
}

.filter-seg button {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  font-size: 12px;
  padding: 5px 11px;
  transition:
    background var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.filter-seg button:hover {
  border-color: var(--accent);
}

.filter-seg button.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #faf9f5;
}

.meta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  margin-bottom: var(--gap);
  padding: 10px 16px;
}

.rm i {
  color: var(--text-3);
  font-size: 12px;
  font-style: normal;
  margin-right: 6px;
}

.rm b {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
}

.link-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: inherit;
  padding: 0;
  text-decoration: underline;
}

.factor-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  margin-bottom: var(--gap-lg);
}
</style>
```

- [ ] **Step 4: 运行测试确认通过**

Run: `powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npx vitest run src/pages/__tests__/Verdicts.spec.ts src/pages/verdicts/__tests__/run-naming.spec.ts"`
Expected: PASS(含既有 `run-naming.spec.ts`，确认未被波及)。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Verdicts.vue frontend/src/pages/__tests__/Verdicts.spec.ts
git commit -m "$(cat <<'EOF'
refactor(ui): Verdicts 页卡片化重排 — 表单置顶/结果区过滤排序/卡片网格替代表格

页面收敛为编排层: 数据加载 + 过滤排序状态 + 弹框开关, 表格/columns/gcell/
展开折叠等旧逻辑随表格一起删除(迁移到 FactorCard/FactorDetailModal/gates.ts)。
run 下拉从页头下沉到结果区头, 与新增的 PASS/FAIL 过滤、排序控件同组。
补充该页面首份测试覆盖(此前零覆盖)。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 收尾验证

**Files:** 无新增/修改(除非验证中发现需要小修的问题)。

**Interfaces:** 无。

- [ ] **Step 1: 全量前端检查**

```bash
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run typecheck"
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run lint"
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run test"
```
Expected: 三者全部 0 退出码。若 lint/typecheck 报错，就地修复后重跑，不进入下一步。

- [ ] **Step 2: 构建产物 + 漂移检查**

```bash
powershell.exe -NoProfile -Command "cd C:\Codes\GoldenHandQuant\frontend; npm run build"
```
Expected: 构建成功，`src/interfaces/api/static/` 与 `.build-stamp` 更新。

```bash
$WIN_PYTHON scripts/check_frontend_fresh.py
```
Expected: 退出码 0(无漂移)。

- [ ] **Step 3: 冒烟 + 截图**

先确认驾驶舱服务已起(若未起)：
```bash
$WIN_PYTHON -m src.interfaces.cli.quant dashboard
```

```bash
$WIN_PYTHON scripts/ui_smoke.py --deep
```
Expected: 退出码 0；`verdicts` 页签锚点 `[data-testid="ft-factor-chip"]` 命中(表单置顶后该锚点仍在，只是位置变了，不影响就绪判定)；无新增 console 错误/失败请求。

- [ ] **Step 4: 双主题读图自查**

```bash
python frontend/scripts/shot.py verdicts
```
Read 生成的两张(浅色/深色)截图，逐项核对设计文档 §9.6 交互验收清单中"可视觉判断"的部分：
- 卡片左缘判决色条、闸门轨道三态(pass/fail/na)在深浅主题下均清晰可辨，不会互相混淆。
- 评分等级徽章配色(A绿/B中性/C琥珀/D红)在两个主题下对比度足够。
- 因子检验表单在页面最顶部，判决结果区跟随其后，工具条(run选择/过滤/排序)一行布局无换行错位。
- 卡片网格在截图宽度下无异常挤压或大片留白。

- [ ] **Step 5: 手动交互验收(需要浏览器操作，非纯截图能覆盖)**

在浏览器打开 dashboard(或 `npm run dev` 的 :5173，二选一)，对 `/#/verdicts` 逐项确认：
1. 点击任意因子卡片 → 弹框打开，内容对应该因子。
2. 按 `Esc` → 弹框关闭，焦点回到刚才点击的卡片(可通过"关闭后按 Tab，确认下一个获得焦点的元素符合预期"间接验证焦点已回到该卡片)。
3. 重新打开弹框，点击遮罩(弹框外区域) → 关闭。
4. 重新打开弹框，点击右上角 ✕ → 关闭。
5. 打开弹框后按 `→`/`←` → 在可见序列内前后切换，首/尾两端对应按钮置灰。
6. 切换 PASS/FAIL 过滤或排序方式时，若弹框开着 → 自动关闭(不留一个指向错误因子的弹框)。
7. 系统设置"减少动态效果"(prefers-reduced-motion) 打开时，卡片入场动画应消失(浏览器 DevTools → Rendering → Emulate CSS media feature 可模拟，不必真的改系统设置)。

若发现任何一项不符，回到对应任务的组件文件修复，重新跑该任务的测试后再继续。

- [ ] **Step 6(如有修复): 提交收尾修复**

仅当 Step 1-5 发现需要修复的问题时执行；若全部一次通过，跳过本步骤。

```bash
git add -A
git status --short  # 检查 diff 范围符合预期后再提交
git commit -m "$(cat <<'EOF'
fix(ui): 判决页卡片化收尾验证修复(typecheck/lint/交互验收发现项)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review 记录

**Spec coverage 核对**(对照设计文档逐节)：
- §3 页面结构重排 → Task 6(表单置顶、run 下拉下沉、空态文案改"上方")。
- §4.1/4.2 卡片信息层级 + 闸门轨道 → Task 1(gateTrack) + Task 3(FactorCard)。
- §4.3 卡片状态(hover/focus/进场动效/reduced-motion) → Task 3 样式 + Task 7 Step 5-7 人工验收。
- §5 排序与过滤 → Task 2(sortFactors/filterFactors) + Task 6(工具条接线)。
- §6 详情弹框(尺寸/遮罩/关闭途径/内容结构/键盘导航) → Task 4，naive-ui 实际默认行为已读源码核实(非按文档假设照抄)。
- §7 数据与兼容(零后端改动/防御性判空/'√'兼容) → 贯穿 Task 1/4/5，均延续原逻辑。
- §8 组件拆分表 → 对应 Task 1-6 一一落地；额外把 `gcell`/`isPassReason` 也一并从 Verdicts.vue 移入 gates.ts(设计文档表格未逐字列出，但属于"扩展 gates.ts"这一行的合理延伸，Task 1 已注明)。
- §9 测试与验收 → Task 1-6 各自的 Vitest + Task 7 的 typecheck/lint/build/check_frontend_fresh/ui_smoke/shot.py/人工交互清单，一一对应。
- §11 风险(阈值双源债/NModal 覆盖成本) → 阈值口径在 Task 1 头注释重申维持现状；NModal 覆盖成本通过 Task 4 读源码核实降为已知量，非未知风险。

**Placeholder 扫描：** 全文检索确认无 "TBD"/"待定"/"后续补充" 等占位表述；每个 Step 3 均为完整可运行代码，无"仿照上面"式引用。

**类型一致性核对：**
- `gateTrack(f: VerdictFactor, longOnly: boolean, hasSplit: boolean): GateCell[]` — Task 1 定义、Task 3 `FactorCard.vue` 调用、Task 1 测试断言，三处签名/字段名(`key`/`label`/`state`/`detail`)一致。
- `sortFactors(factors, key, longOnly)` / `filterFactors(factors, filter)` — Task 2 定义、Task 6 `visibleFactors` 调用、Task 2/6 测试，参数顺序与类型(`SortKey`/`FilterKey`)一致。
- `FactorCard` props `{ factor, longOnly, hasSplit }` — Task 3 定义与 Task 6 使用处(`:factor="f" :long-only="longOnly" :has-split="hasSplit"`)一致；无自定义 emit，Task 6 用原生 `@click` 一致。
- `FactorDetailModal` props `{ show, factors, index, longOnly, hasSplit, runTitle }` + emits `{ 'update:show', navigate }` — Task 4 定义与 Task 6 `v-model:show`/`@navigate` 用法一致。
- `FactorTestForm` props `{ lastSplitHint }` + emits `{ refresh }` — Task 5 定义与 Task 6 `:last-split-hint="lastSplitHint" @refresh="loadVerdicts"` 一致。
- `gcell`/`isPassReason`/`gradeClass`/`f2`/`f3`/`f4`/`pct` 的 import 列表在 Task 3/4 中均只列出实际用到的函数(逐一核对过，未导入未使用的 `gateClass`，避免 lint unused-import 报错)。

**Scope 检查：** 单一 spec 对应单一实现计划，7 个任务全部服务同一个页面重构目标，无需再拆子项目。
