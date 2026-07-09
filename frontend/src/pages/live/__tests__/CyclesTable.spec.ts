import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { TradingCycle } from '@/api/types'

import CyclesTable from '../CyclesTable.vue'

function mkCycle(id: string, overrides: Partial<TradingCycle> = {}): TradingCycle {
  return {
    cycle_id: id,
    cycle_time: '2026-07-05T09:30:00',
    mode: 'dry_run',
    strategy: 'micro_value',
    signals_generated: 3,
    orders_submitted: 2,
    orders_rejected: 0,
    orders_failed: 0,
    notional_submitted: 5000,
    note: null,
    ...overrides,
  }
}

function cycles(n: number): TradingCycle[] {
  return Array.from({ length: n }, (_, i) => mkCycle(`c${i}`))
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ executions: [] }),
      text: () => Promise.resolve(''),
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CyclesTable', () => {
  it('不超过 50 条时不显示"显示全部"按钮', () => {
    const w = mount(CyclesTable, { props: { cycles: cycles(10) } })
    expect(w.findAll('[data-testid="cycle-row"]')).toHaveLength(10)
    expect(w.find('[data-testid="cycles-expand"]').exists()).toBe(false)
  })

  it('超过 50 条时默认只显示前 50 行, 按钮显示总数', () => {
    const w = mount(CyclesTable, { props: { cycles: cycles(80) } })
    expect(w.findAll('[data-testid="cycle-row"]')).toHaveLength(50)
    const btn = w.find('[data-testid="cycles-expand"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('显示全部 80 条')
  })

  /* confirmed-bug 回归(2026-07-05): 按钮点击后必须保持常驻(不消失), 不能让表格里
   * 新展开的某一行占据按钮原来的屏幕位置——那样会有被浏览器补发的幽灵点击命中新行、
   * 误触发行展开/收起的风险(同款问题已在 useSymbolChips.ts 的联想候选点选场景
   * 实测确认过机制)。 */
  it('点击"显示全部"后展示全部行, 按钮保持常驻并切换为"收起"(不消失)', async () => {
    const w = mount(CyclesTable, { props: { cycles: cycles(80) } })
    await w.find('[data-testid="cycles-expand"]').trigger('click')

    expect(w.findAll('[data-testid="cycle-row"]')).toHaveLength(80)
    const btn = w.find('[data-testid="cycles-expand"]')
    expect(btn.exists()).toBe(true) // 按钮必须还在, 不能因 v-if 消失
    expect(btn.text()).toContain('收起')
  })

  it('再次点击"收起"后恢复只显示前 50 行', async () => {
    const w = mount(CyclesTable, { props: { cycles: cycles(80) } })
    await w.find('[data-testid="cycles-expand"]').trigger('click')
    await w.find('[data-testid="cycles-expand"]').trigger('click')

    expect(w.findAll('[data-testid="cycle-row"]')).toHaveLength(50)
    expect(w.find('[data-testid="cycles-expand"]').text()).toContain('显示全部 80 条')
  })

  it('点首列展开钮钻取明细', async () => {
    const w = mount(CyclesTable, { props: { cycles: cycles(3) } })
    await w.findAll('[data-testid="cycle-toggle"]')[0]!.trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="cycle-detail"]').exists()).toBe(true)
  })

  /* C2 键盘可达(WCAG 2.1.1/4.1.2): 展开须由真 <button> 承载并标注 aria-expanded,
   * 而非 <tr @click>(键盘不可达)。 */
  it('展开由真 button 承载并标注 aria-expanded', async () => {
    const w = mount(CyclesTable, { props: { cycles: cycles(1) } })
    const btn = w.find('[data-testid="cycle-toggle"]')
    expect(btn.element.tagName).toBe('BUTTON')
    expect(btn.attributes('aria-expanded')).toBe('false')
    expect(btn.attributes('aria-label')).toContain('展开')

    await btn.trigger('click')
    const after = w.find('[data-testid="cycle-toggle"]')
    expect(after.attributes('aria-expanded')).toBe('true')
    expect(after.attributes('aria-label')).toContain('收起')
  })

  /* 明细失败态是字符串 'error'(truthy) — 收起后重展开必须重拉(不能被 truthy 缓存跳过)。 */
  it('明细加载失败后收起再展开会重试拉取', async () => {
    const failing = vi.fn().mockRejectedValue(new Error('boom'))
    vi.stubGlobal('fetch', failing)
    const w = mount(CyclesTable, { props: { cycles: cycles(1) } })

    await w.find('[data-testid="cycle-toggle"]').trigger('click')
    await flushPromises()
    expect(w.find('.t-fail').exists()).toBe(true) // "明细加载失败"
    expect(failing).toHaveBeenCalledTimes(1)

    await w.find('[data-testid="cycle-toggle"]').trigger('click') // 收起
    await w.find('[data-testid="cycle-toggle"]').trigger('click') // 再展开 → 重试
    await flushPromises()
    expect(failing).toHaveBeenCalledTimes(2)
  })
})
