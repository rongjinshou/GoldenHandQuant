import { describe, expect, it } from 'vitest'

import { NAV_ITEMS, pageTitle } from '@/router'

describe('导航顺序按流水线心智', () => {
  it('总览→行情→判决→回测→实盘→任务', () => {
    expect(NAV_ITEMS.map((i) => i.name)).toEqual([
      'overview', 'explorer', 'verdicts', 'backtests', 'live', 'jobs',
    ])
  })
})

describe('pageTitle(document.title 随路由)', () => {
  it('已知路由名 → 「{页名} · GoldenHandQuant」', () => {
    expect(pageTitle('overview')).toBe('总览 · GoldenHandQuant')
    expect(pageTitle('backtests')).toBe('回测 · GoldenHandQuant')
    expect(pageTitle('jobs')).toBe('任务 · GoldenHandQuant')
  })
  it('未知/空名退化为纯品牌名', () => {
    expect(pageTitle('unknown')).toBe('GoldenHandQuant')
    expect(pageTitle(undefined)).toBe('GoldenHandQuant')
    expect(pageTitle(null)).toBe('GoldenHandQuant')
  })
})
