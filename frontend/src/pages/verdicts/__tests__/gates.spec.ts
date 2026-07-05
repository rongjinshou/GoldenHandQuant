import { describe, expect, it } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import { f4, gateClass, gateTrack, gcell, gradeClass, isPassReason } from '../gates'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    ic_mean: 0.03,
    ir: 0.4,
    ic_positive_rate: 0.55,
    monotonicity_score: 0.7,
    long_short_return: 0.02,
    oos_ic_mean: 0.02,
    oos_ir: 0.35,
    oos_long_short_return: 0.01,
    excess_ir: 0.6,
    excess_positive_rate: 0.53,
    top_excess_return: 0.03,
    oos_top_excess_return: 0.02,
    score: 72,
    grade: 'B',
    passed: true,
    reasons: ['IC=0.0300 >= 0.02 ✓'],
    ...o,
  }
}

describe('gateClass', () => {
  it('无值 → gate-na', () => {
    expect(gateClass('ic_mean', null)).toBe('gate-na')
    expect(gateClass('ic_mean', undefined)).toBe('gate-na')
  })
  it('过闸 → t-pass, 未过 → t-fail', () => {
    expect(gateClass('ic_mean', 0.03)).toBe('t-pass')
    expect(gateClass('ic_mean', 0.01)).toBe('t-fail')
  })
  it('非闸门指标 → 空字符串(无着色)', () => {
    expect(gateClass('oos_ic_mean', 0.05)).toBe('')
  })
  it('ic_positive_rate 闸键存在(补齐前该列一直无着色)', () => {
    expect(gateClass('ic_positive_rate', 0.55)).toBe('t-pass')
    expect(gateClass('ic_positive_rate', 0.4)).toBe('t-fail')
  })
})

describe('gradeClass', () => {
  it('A/B/C/D 各档, F 映射到 D 档, 未知回落 B', () => {
    expect(gradeClass('A')).toBe('grade-a')
    expect(gradeClass('B')).toBe('grade-b')
    expect(gradeClass('C')).toBe('grade-c')
    expect(gradeClass('D')).toBe('grade-d')
    expect(gradeClass('F')).toBe('grade-d')
    expect(gradeClass(null)).toBe('grade-b')
    expect(gradeClass('X')).toBe('grade-b')
  })
})

describe('gcell', () => {
  it('null/undefined → 文本 "-", 类走 gate-na', () => {
    expect(gcell('ic_mean', null, f4)).toEqual({ text: '-', cls: 'gate-na' })
  })
  it('有值 → 格式化文本 + gateClass 结果', () => {
    expect(gcell('ic_mean', 0.03, f4)).toEqual({ text: '0.0300', cls: 't-pass' })
  })
})

describe('isPassReason', () => {
  it('含 ✓ 或 √ 判通过, 否则判未通过', () => {
    expect(isPassReason('IC=0.03 >= 0.02 ✓')).toBe(true)
    expect(isPassReason('IC=0.03 >= 0.02 √')).toBe(true)
    expect(isPassReason('单调性=0.52 < 0.6 (单调性不足)')).toBe(false)
  })
})

describe('gateTrack', () => {
  it('long_short 口径: 5 道 IS 闸 + 未设切分 → 后 2 道 na, 顺序固定', () => {
    const track = gateTrack(mkFactor(), false, false)
    expect(track).toHaveLength(7)
    expect(track.map((c) => c.state)).toEqual(['pass', 'pass', 'pass', 'pass', 'pass', 'na', 'na'])
    expect(track.map((c) => c.key)).toEqual([
      'ic_mean', 'ir', 'ic_positive_rate', 'monotonicity_score',
      'long_short_return', 'oos_sign', 'oos_long_short_return',
    ])
  })

  it('long_only 口径: 稳定性/一致性/变现换成超额口径字段', () => {
    const track = gateTrack(mkFactor(), true, false)
    expect(track[1]).toMatchObject({ key: 'excess_ir', state: 'pass' })
    expect(track[2]).toMatchObject({ key: 'excess_positive_rate', state: 'pass' })
    expect(track[4]).toMatchObject({ key: 'top_excess_return', state: 'pass' })
    expect(track[6].key).toBe('oos_top_excess_return')
  })

  it('设切分且 OOS 符号一致 → 第6道 pass; 符号翻转 → fail', () => {
    const same = gateTrack(mkFactor({ ic_mean: 0.03, oos_ic_mean: 0.02 }), false, true)
    expect(same[5]).toMatchObject({ key: 'oos_sign', state: 'pass' })

    const flipped = gateTrack(mkFactor({ ic_mean: 0.03, oos_ic_mean: -0.01 }), false, true)
    expect(flipped[5]).toMatchObject({ key: 'oos_sign', state: 'fail' })
  })

  it('设切分后第7道读真实 OOS 数值', () => {
    const track = gateTrack(mkFactor({ oos_long_short_return: -0.01 }), false, true)
    expect(track[6]).toMatchObject({ key: 'oos_long_short_return', state: 'fail' })
  })

  it('无值字段 → na(不猜测)', () => {
    const track = gateTrack(mkFactor({ monotonicity_score: null }), false, false)
    expect(track[3]).toMatchObject({ key: 'monotonicity_score', state: 'na' })
  })
})
