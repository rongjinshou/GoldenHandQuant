import { describe, expect, it } from 'vitest'

import { buildRefreshRequest } from '../refresh-form'

describe('buildRefreshRequest(R6-03a 数据刷新载荷)', () => {
  it('两端齐备 → ok, 载荷恰含 start_date/end_date 两键且无空值', () => {
    const r = buildRefreshRequest('2021-01-01', '2025-12-31')
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.payload).toEqual({ start_date: '2021-01-01', end_date: '2025-12-31' })
    expect(Object.keys(r.payload).sort()).toEqual(['end_date', 'start_date'])
    expect(Object.values(r.payload).every((v) => v !== '')).toBe(true)
  })

  it.each([
    ['start 缺', null, '2025-12-31'],
    ['end 缺', '2021-01-01', null],
    ['双缺', null, null],
    ['空串(旧 bug 输入形态)', '', ''],
    ['纯空白', '  ', '2025-12-31'],
  ])('%s → 不放行(不再发出会撞 422 的载荷), 给中文提示', (_name, s, e) => {
    const r = buildRefreshRequest(s, e)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('必填')
  })

  it('trim 后入荷: 带空白的合法日期净化为纯日期串', () => {
    const r = buildRefreshRequest(' 2021-01-01 ', '2025-12-31')
    expect(r).toEqual({
      ok: true,
      payload: { start_date: '2021-01-01', end_date: '2025-12-31' },
    })
  })
})
