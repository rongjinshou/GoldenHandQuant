import { describe, expect, it } from 'vitest'

import type { VerdictFactor, VerdictRun } from '@/api/types'

import { buildVerdictRunLabel, objectiveLabel } from '../run-naming'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    ic_mean: null,
    ir: null,
    ic_positive_rate: null,
    monotonicity_score: null,
    long_short_return: null,
    oos_ic_mean: null,
    oos_ir: null,
    oos_long_short_return: null,
    excess_ir: null,
    excess_positive_rate: null,
    top_excess_return: null,
    oos_top_excess_return: null,
    score: null,
    grade: null,
    passed: false,
    reasons: null,
    ...o,
  }
}

function mkRun(o: Partial<VerdictRun> = {}): VerdictRun {
  return {
    run_id: 'MFCOMBO-20210101-20260613',
    created_at: '2026-06-14 10:02:00.100000',
    params: { objective: 'long_only', split: '2024-06-30' },
    factors: [mkFactor()],
    ...o,
  }
}

describe('objectiveLabel', () => {
  it('long_only→长多, long_short→多空, 未知/空→?', () => {
    expect(objectiveLabel('long_only')).toBe('长多')
    expect(objectiveLabel('long_short')).toBe('多空')
    expect(objectiveLabel(null)).toBe('?')
    expect(objectiveLabel(undefined)).toBe('?')
  })
})

describe('buildVerdictRunLabel', () => {
  it('因子数 · 口径 · 切分日 组成标题, 副行时间+run_id', () => {
    const run = mkRun({ factors: [mkFactor(), mkFactor({ factor_id: 'F02' })] })
    const label = buildVerdictRunLabel(run)
    expect(label.title).toBe('2 因子 · 长多 · 切分 2024-06-30')
    expect(label.subtitle).toBe('06-14 10:02 · MFCOMBO-20210101-20260613')
  })

  it('未设切分日 → "未切分"(而非空字符串或 undefined)', () => {
    const run = mkRun({ params: { objective: 'long_short', split: null } })
    expect(buildVerdictRunLabel(run).title).toBe('1 因子 · 多空 · 未切分')
  })

  it('params 为 null(异常数据) 不炸', () => {
    const run = mkRun({ params: null })
    expect(buildVerdictRunLabel(run).title).toBe('1 因子 · ? · 未切分')
  })
})
