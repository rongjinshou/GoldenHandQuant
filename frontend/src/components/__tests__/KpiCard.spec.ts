import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import KpiCard, { rollFrom } from '../KpiCard.vue'

describe('rollFrom(缓动插值纯函数)', () => {
  it('t=0 返回旧值(prev), 不归零', () => {
    expect(rollFrom(100, 200, 0)).toBe(100)
    expect(rollFrom(646, 999, 0)).toBe(646)
  })
  it('t=1 返回目标值', () => {
    expect(rollFrom(100, 200, 1)).toBe(200)
  })
  it('中间进度在 prev 与 target 之间(缓出)', () => {
    const v = rollFrom(100, 200, 0.5)
    expect(v).toBeGreaterThan(100)
    expect(v).toBeLessThan(200)
    expect(v).toBeCloseTo(187.5, 4)
  })
})

describe('KpiCard', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('reduced-motion / 无动画时长: 直接显示终值', async () => {
    // jsdom 下 --dur-base 取不到 → durMs=0 → 直接终值
    const w = mount(KpiCard, { props: { label: 'X', value: 42, countUp: true } })
    await nextTick()
    expect(w.find('.kpi-value').text()).toContain('42')
    await w.setProps({ value: 99 })
    await nextTick()
    expect(w.find('.kpi-value').text()).toContain('99')
  })

  it('刷新时从旧值滚动而非归零', async () => {
    vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      getPropertyValue: () => '200ms',
    } as unknown as CSSStyleDeclaration)
    let now = 0
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const frames: FrameRequestCallback[] = []
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => frames.push(cb))

    const w = mount(KpiCard, { props: { label: 'X', value: 100, countUp: true } })
    // 完成首次动画 0→100
    now = 600
    while (frames.length) frames.shift()!(now)
    await nextTick()
    expect(w.find('.kpi-value').text()).toContain('100')

    // 刷新到 200: 第一帧应从旧值 100 起滚, 而非从 0
    await w.setProps({ value: 200 })
    expect(frames.length).toBeGreaterThan(0)
    now = 600 // t=0
    frames[0](now)
    await nextTick()
    const shown = parseFloat(w.find('.kpi-value').text().replace(/[^0-9.]/g, ''))
    expect(shown).toBeGreaterThanOrEqual(100) // 从 100 起, 旧代码从 0 起会 <100
  })
})
