import { describe, expect, it } from 'vitest'

import { filterLogLines, isNearBottom, jobBadgeKind, terminalNotification } from '../ui'

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

describe('filterLogLines', () => {
  it('q 为空串返回原数组引用(零开销直通)', () => {
    const lines = ['a', 'b']
    expect(filterLogLines(lines, '')).toBe(lines)
    const empty: string[] = []
    expect(filterLogLines(empty, '')).toBe(empty)
  })

  it('大小写不敏感子串匹配, 保持原行序', () => {
    const lines = ['Epoch 1 loss=0.52', 'saving checkpoint', 'EPOCH 2 loss=0.41', 'epoch 3 loss=0.38']
    expect(filterLogLines(lines, 'epoch')).toEqual([
      'Epoch 1 loss=0.52',
      'EPOCH 2 loss=0.41',
      'epoch 3 loss=0.38',
    ])
    expect(filterLogLines(lines, 'POCH 2')).toEqual(['EPOCH 2 loss=0.41'])
    expect(filterLogLines(lines, 'LOSS=0.4')).toEqual(['EPOCH 2 loss=0.41'])
  })

  it('无命中返回空数组; 空行集非空 q 亦空数组', () => {
    expect(filterLogLines(['a', 'b'], 'zz')).toEqual([])
    expect(filterLogLines([], 'x')).toEqual([])
  })

  it('空白字符按字面子串处理(不 trim, 可精确定位含空格片段)', () => {
    expect(filterLogLines(['a b', 'ab'], ' ')).toEqual(['a b'])
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
