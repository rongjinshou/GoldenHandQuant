import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NButton, NPopconfirm, NSelect } from 'naive-ui'

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
  // naive-ui 组件运行时 `.name` 不带 N 前缀(NSelect.name === 'Select', 详见
  // FactorDetailModal.spec.ts 对 NModal/'Modal' 的同类记录) — 字符串字面量 key 对不上,
  // 会导致真实组件穿透渲染; 用 [Component.name] 收窄成运行时准确值。
  // `.name` 静态类型是 string | undefined, 计算属性名不接受 undefined 联合类型 —
  // `as string` 收窄(纯类型断言, 不影响运行时行为), 同 FactorDetailModal.spec.ts 写法。
  [NSelect.name as string]: {
    props: ['value', 'options'],
    emits: ['update:value'],
    template:
      '<div class="stub-select"><button v-for="o in options" :key="o.value" type="button" @click="$emit(\'update:value\', o.value)">{{ o.label }}</button></div>',
  },
  // 判决页轮次删除入口(commit 8dc2558, 与本次卡片化重排并行落地于同一文件) — 本页测试
  // 前此前从未覆盖过它, 这里仍按仓库既有惯例(FactorTestForm.spec.ts/FactorDetailModal.spec.ts)
  // stub 掉 naive-ui 组件, 只保留可断言的最小结构(trigger 插槽 + 一个确认按钮触发 positive-click)。
  [NButton.name as string]: {
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
  [NPopconfirm.name as string]: {
    emits: ['positive-click'],
    template:
      '<div class="stub-popconfirm"><slot name="trigger" /><button type="button" data-testid="verdict-delete-confirm" @click="$emit(\'positive-click\')">confirm</button></div>',
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
    vi.fn().mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (url === '/api/research/verdicts' && (init?.method ?? 'GET') === 'GET') {
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ runs: runsResp }),
          text: () => Promise.resolve(''),
        })
      }
      // 删除入口(见上 NPopconfirm/NButton stub 注释): 就地从 runsResp 摘除, 模拟后端硬删除
      if (url.startsWith('/api/research/verdicts/') && init?.method === 'DELETE') {
        const id = url.split('/').pop()
        runsResp = runsResp.filter((r) => r.run_id !== id)
        return Promise.resolve({
          ok: true, status: 200,
          json: () => Promise.resolve({ deleted: 1 }),
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

  // 判决页轮次删除入口(commit 8dc2558)在本次重排里原样保留(移到结果区头) — 补一条行为测试,
  // 不只是"存在性"断言: 确认点击→触发 DELETE 请求→重新加载后列表反映删除结果。
  it('删除本轮确认后调用 DELETE 接口, 列表刷新为空态', async () => {
    const w = mountPage()
    await flushPromises()
    await w.find('[data-testid="verdict-delete"]').trigger('click')
    await w.find('[data-testid="verdict-delete-confirm"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="verdicts-empty"]').exists()).toBe(true)
  })
})
