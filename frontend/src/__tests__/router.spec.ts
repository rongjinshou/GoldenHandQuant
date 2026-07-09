import { describe, expect, it } from 'vitest'

import { NAV_ITEMS } from '@/router'

describe('导航顺序按流水线心智', () => {
  it('总览→行情→判决→回测→实盘→任务', () => {
    expect(NAV_ITEMS.map((i) => i.name)).toEqual([
      'overview', 'explorer', 'verdicts', 'backtests', 'live', 'jobs',
    ])
  })
})
