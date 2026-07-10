import { flushPromises, mount } from '@vue/test-utils'
import { NButton, NPopconfirm, NSelect } from 'naive-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { VerdictFactor, VerdictRun } from '@/api/types'

import Verdicts from '../../Verdicts.vue'
import { VERDICTS_VIEW_KEY } from '../view-state'

/* 视图会话记忆的挂载接线 — 只测本迭代新增的两条线: setup 恢复 sessionStorage 里的
 * 过滤+排序、变更即写回。纯读写/容错语义在 view-state.spec.ts, 页面其余编排在
 * pages/__tests__/Verdicts.spec.ts(stub 手法与其一致, 见该文件注释)。 */

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01', factor_name: 'f', ic_mean: null, ir: null, ic_positive_rate: null,
    monotonicity_score: null, long_short_return: null, oos_ic_mean: null, oos_ir: null,
    oos_long_short_return: null, excess_ir: null, excess_positive_rate: null,
    top_excess_return: null, oos_top_excess_return: null, score: null, grade: null,
    passed: false, reasons: null, ...o,
  }
}

/* 三因子刻意让「verdict 放榜序」「ic 序」「fail 过滤」三者可区分:
 * 默认视角 → [A, C, B](passed 前置, 组内 score 降序); fail+ic → [B, C](非 [C, B])。 */
const runsResp: VerdictRun[] = [{
  run_id: 'MFCOMBO-1', created_at: '2026-07-05 09:00:00',
  params: { objective: 'long_short', split: null, start: '2021-01-01', end: '2026-06-30' },
  factors: [
    mkFactor({ factor_id: 'A', passed: true, score: 90, ic_mean: 0.01 }),
    mkFactor({ factor_id: 'B', passed: false, score: 10, ic_mean: 0.08 }),
    mkFactor({ factor_id: 'C', passed: false, score: 50, ic_mean: 0.02 }),
  ],
}]

const stubs = {
  FactorTestForm: { template: '<div data-testid="stub-form" />' },
  FactorCard: {
    props: ['factor', 'longOnly', 'hasSplit'],
    template: '<button type="button" class="stub-card">{{ factor.factor_id }}</button>',
  },
  FactorDetailModal: { props: ['show'], template: '<div v-if="show" data-testid="stub-modal" />' },
  [NSelect.name as string]: {
    props: ['value', 'options'],
    emits: ['update:value'],
    template:
      '<div class="stub-select"><button v-for="o in options" :key="o.value" type="button" @click="$emit(\'update:value\', o.value)">{{ o.label }}</button></div>',
  },
  [NButton.name as string]: { template: '<button type="button"><slot /></button>' },
  [NPopconfirm.name as string]: { template: '<div><slot name="trigger" /></div>' },
}

let wrapper: { unmount(): void } | null = null

async function mountPage() {
  const w = mount(Verdicts, { global: { stubs } })
  wrapper = w
  await flushPromises()
  return w
}

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: () => Promise.resolve({ runs: runsResp }),
      text: () => Promise.resolve(''),
    }),
  )
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('Verdicts 视图会话记忆接线', () => {
  it('无记忆时按默认视角渲染(全部 + 放榜序), 且挂载本身不写存储', async () => {
    const w = await mountPage()
    const filterBtns = w.find('[data-testid="verdict-filter"]').findAll('button')
    expect(filterBtns[0]!.attributes('aria-pressed')).toBe('true')
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['A', 'C', 'B'])
    expect(sessionStorage.getItem(VERDICTS_VIEW_KEY)).toBeNull()
  })

  it('挂载恢复: 预置 {fail, ic} → FAIL 段激活、卡片只剩 fail 且按 IC 降序', async () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 'fail', sort: 'ic' }))
    const w = await mountPage()
    const filterBtns = w.find('[data-testid="verdict-filter"]').findAll('button')
    expect(filterBtns[2]!.attributes('aria-pressed')).toBe('true')
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['B', 'C'])
  })

  it('变更即写: 点 PASS → 落盘 {pass, verdict}; 再切排序"评分" → 落盘 {pass, score}', async () => {
    const w = await mountPage()
    await w.find('[data-testid="verdict-filter"]').findAll('button')[1]!.trigger('click')
    expect(JSON.parse(sessionStorage.getItem(VERDICTS_VIEW_KEY)!)).toEqual({
      filter: 'pass', sort: 'verdict',
    })

    await w.find('[data-testid="verdict-sort"]').findAll('button')[1]!.trigger('click') // SORT_OPTIONS[1] = 评分
    expect(JSON.parse(sessionStorage.getItem(VERDICTS_VIEW_KEY)!)).toEqual({
      filter: 'pass', sort: 'score',
    })
  })

  it('存了非法枚举也能安然进页: 回默认视角渲染, 不抛不白屏', async () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 'PASS', sort: 'bogus' }))
    const w = await mountPage()
    expect(w.findAll('.stub-card').map((c) => c.text())).toEqual(['A', 'C', 'B'])
  })
})
