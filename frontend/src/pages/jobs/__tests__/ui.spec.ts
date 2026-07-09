import { describe, expect, it } from 'vitest'

import { isNearBottom, jobBadgeKind, terminalNotification } from '../ui'

describe('jobBadgeKind', () => {
  it('五态映射到 AppBadge kind(设计 §7)', () => {
    expect(jobBadgeKind('queued')).toBe('info')
    expect(jobBadgeKind('running')).toBe('accent')
    expect(jobBadgeKind('succeeded')).toBe('pass')
    expect(jobBadgeKind('failed')).toBe('fail')
    expect(jobBadgeKind('canceled')).toBe('warn')
  })

  it('未知状态回退 info', () => {
    expect(jobBadgeKind('weird')).toBe('info')
    expect(jobBadgeKind('')).toBe('info')
  })
})

describe('isNearBottom', () => {
  it('距底 <40px 视为在底部附近(应跟随滚底)', () => {
    // scrollHeight-scrollTop-clientHeight = 300-260-40 = 0 < 40
    expect(isNearBottom(300, 260, 40)).toBe(true)
    // = 39 < 40
    expect(isNearBottom(300, 221, 40)).toBe(true)
  })

  it('距底 ≥40px 视为离底(不抢滚)', () => {
    // = 40, 不小于 40
    expect(isNearBottom(300, 220, 40)).toBe(false)
    // 用户滚到顶部
    expect(isNearBottom(1000, 0, 200)).toBe(false)
  })

  it('jsdom 无布局(全 0)时视为在底部附近, 保持既有自动滚底语义', () => {
    expect(isNearBottom(0, 0, 0)).toBe(true)
  })

  it('阈值可覆盖', () => {
    expect(isNearBottom(300, 250, 40, 10)).toBe(false) // 距底 10, 不小于 10
    expect(isNearBottom(300, 255, 40, 10)).toBe(true) // 距底 5 < 10
  })
})

describe('terminalNotification', () => {
  it('succeeded → success 通知', () => {
    expect(terminalNotification('succeeded')).toEqual({ type: 'success', title: '任务完成' })
  })

  it('failed → error 通知', () => {
    expect(terminalNotification('failed')).toEqual({ type: 'error', title: '任务失败' })
  })

  it('canceled/运行中态不打扰(null)', () => {
    expect(terminalNotification('canceled')).toBeNull()
    expect(terminalNotification('running')).toBeNull()
    expect(terminalNotification('queued')).toBeNull()
  })
})
