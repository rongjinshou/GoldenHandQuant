import { describe, expect, it } from 'vitest'

import { requireBacktestDates } from '../form-dates'

describe('requireBacktestDates(R7 回测日期收口, 同 R6 刷新表单样板)', () => {
  it('两端齐备 → ok, 返回 trim 后的非空日期串', () => {
    const r = requireBacktestDates('2024-01-01', '2025-12-31')
    expect(r).toEqual({ ok: true, start: '2024-01-01', end: '2025-12-31' })
  })

  it.each([
    ['start 清空(clearable 置 null)', null, '2025-12-31'],
    ['end 清空', '2024-01-01', null],
    ['双清空', null, null],
    ['空串(旧实现 ?? 兜底的 422 输入形态)', '', ''],
    ['纯空白', '  ', '2025-12-31'],
  ])('%s → 不放行(不再发出会撞 422 的载荷), 给中文必填提示', (_name, s, e) => {
    const r = requireBacktestDates(s, e)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('起止日期均必填')
  })

  it('trim 净化: 带空白的合法日期收敛为纯日期串', () => {
    const r = requireBacktestDates(' 2024-01-01 ', '2025-12-31 '.trim())
    expect(r).toEqual({ ok: true, start: '2024-01-01', end: '2025-12-31' })
  })
})
