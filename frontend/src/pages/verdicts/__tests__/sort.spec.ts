import { describe, expect, it } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import { filterFactors, sortFactors } from '../sort'

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

describe('filterFactors', () => {
  const factors = [
    mkFactor({ factor_id: 'A', passed: true }),
    mkFactor({ factor_id: 'B', passed: false }),
    mkFactor({ factor_id: 'C', passed: true }),
  ]
  it('all 原样返回, pass/fail 各自过滤', () => {
    expect(filterFactors(factors, 'all').map((f) => f.factor_id)).toEqual(['A', 'B', 'C'])
    expect(filterFactors(factors, 'pass').map((f) => f.factor_id)).toEqual(['A', 'C'])
    expect(filterFactors(factors, 'fail').map((f) => f.factor_id)).toEqual(['B'])
  })
})

describe('sortFactors', () => {
  it('verdict: passed 降序, 同组按 score 降序(默认"放榜序")', () => {
    const factors = [
      mkFactor({ factor_id: 'low-pass', passed: true, score: 40 }),
      mkFactor({ factor_id: 'fail', passed: false, score: 90 }),
      mkFactor({ factor_id: 'high-pass', passed: true, score: 80 }),
    ]
    expect(sortFactors(factors, 'verdict', false).map((f) => f.factor_id)).toEqual([
      'high-pass', 'low-pass', 'fail',
    ])
  })

  it('score: 降序, null 排最后', () => {
    const factors = [
      mkFactor({ factor_id: 'null', score: null }),
      mkFactor({ factor_id: 'mid', score: 50 }),
      mkFactor({ factor_id: 'top', score: 90 }),
    ]
    expect(sortFactors(factors, 'score', false).map((f) => f.factor_id)).toEqual([
      'top', 'mid', 'null',
    ])
  })

  it('ic: 按 ic_mean 降序', () => {
    const factors = [
      mkFactor({ factor_id: 'a', ic_mean: 0.01 }),
      mkFactor({ factor_id: 'b', ic_mean: 0.05 }),
    ]
    expect(sortFactors(factors, 'ic', false).map((f) => f.factor_id)).toEqual(['b', 'a'])
  })

  it('oos_realize: long_short 用 oos_long_short_return, long_only 用 oos_top_excess_return', () => {
    const factors = [
      mkFactor({ factor_id: 'a', oos_long_short_return: 0.01, oos_top_excess_return: 0.05 }),
      mkFactor({ factor_id: 'b', oos_long_short_return: 0.03, oos_top_excess_return: 0.02 }),
    ]
    expect(sortFactors(factors, 'oos_realize', false).map((f) => f.factor_id)).toEqual(['b', 'a'])
    expect(sortFactors(factors, 'oos_realize', true).map((f) => f.factor_id)).toEqual(['a', 'b'])
  })

  it('submitted: 保持原序', () => {
    const factors = [mkFactor({ factor_id: 'z' }), mkFactor({ factor_id: 'a' })]
    expect(sortFactors(factors, 'submitted', false).map((f) => f.factor_id)).toEqual(['z', 'a'])
  })

  it('不修改入参数组(纯函数)', () => {
    const factors = [mkFactor({ factor_id: 'b', score: 1 }), mkFactor({ factor_id: 'a', score: 9 })]
    const original = [...factors]
    sortFactors(factors, 'score', false)
    expect(factors).toEqual(original)
  })
})
