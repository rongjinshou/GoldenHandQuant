import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { formatClockTime } from '../logic'
import StaleIndicator from '../StaleIndicator.vue'

/* R6-01 断连陈旧指示 — 文案切换契约:
 * Live.vue 把 overview 轮询器(5s 主节拍)的 isStale/lastSuccessAt 原样喂进来,
 * 这里以 props 直接驱动(等价于 mock 轮询器状态), 断言两态渲染与恢复回切。 */

const T = new Date(2026, 6, 9, 14, 30, 5).getTime() // 本地 14:30:05

describe('StaleIndicator(Live 连接状态行)', () => {
  it('从未成功(lastSuccessAt=null)不渲染 — 首载失败交给 ErrorBanner', () => {
    const w = mount(StaleIndicator, { props: { isStale: false, lastSuccessAt: null } })
    expect(w.find('[data-testid="live-conn-status"]').exists()).toBe(false)
  })

  it('正常态: 低调「数据更新于 HH:mm:ss」, 无 live region', () => {
    const w = mount(StaleIndicator, { props: { isStale: false, lastSuccessAt: T } })
    const ok = w.get('[data-testid="live-conn-ok"]')
    expect(ok.text()).toContain(`数据更新于 ${formatClockTime(T)}`)
    expect(w.find('[data-testid="live-conn-stale"]').exists()).toBe(false)
    expect(w.find('[role="status"]').exists()).toBe(false)
  })

  it('isStale: 转「⚠ 连接中断，显示 HH:mm:ss 前数据，重试中…」+ role=status/aria-live=polite', () => {
    const w = mount(StaleIndicator, { props: { isStale: true, lastSuccessAt: T } })
    const stale = w.get('[data-testid="live-conn-stale"]')
    expect(stale.text()).toContain('连接中断')
    expect(stale.text()).toContain(`显示 ${formatClockTime(T)} 前数据`)
    expect(stale.text()).toContain('重试中')
    expect(stale.attributes('role')).toBe('status')
    expect(stale.attributes('aria-live')).toBe('polite')
    expect(w.find('[data-testid="live-conn-ok"]').exists()).toBe(false)
  })

  it('恢复(isStale 复位 + lastSuccessAt 前进)自动回正常态且时间刷新', async () => {
    const w = mount(StaleIndicator, { props: { isStale: true, lastSuccessAt: T } })
    expect(w.find('[data-testid="live-conn-stale"]').exists()).toBe(true)

    const T2 = T + 65_000
    await w.setProps({ isStale: false, lastSuccessAt: T2 })
    expect(w.find('[data-testid="live-conn-stale"]').exists()).toBe(false)
    expect(w.get('[data-testid="live-conn-ok"]').text()).toContain(formatClockTime(T2))
  })
})
