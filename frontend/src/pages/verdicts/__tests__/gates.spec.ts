import { describe, expect, it } from 'vitest'

import { gateClass, gradeClass } from '../gates'

describe('gateClass', () => {
  it('null/undefined → gate-na', () => {
    expect(gateClass('ic_mean', null)).toBe('gate-na')
    expect(gateClass('ic_mean', undefined)).toBe('gate-na')
  })

  it('闸门阈值判定 pass/fail (语义类, 非颜色类)', () => {
    expect(gateClass('ic_mean', 0.02)).toBe('t-pass')
    expect(gateClass('ic_mean', 0.019)).toBe('t-fail')
    expect(gateClass('excess_ir', 0.5)).toBe('t-pass')
    expect(gateClass('excess_positive_rate', 0.51)).toBe('t-fail')
    expect(gateClass('top_excess_return', 0.0001)).toBe('t-pass')
  })

  it('非闸门指标不着色', () => {
    expect(gateClass('oos_ic_mean', 0.5)).toBe('')
  })
})

describe('gradeClass', () => {
  it('F 映射到 D 档(红)', () => {
    expect(gradeClass('F')).toBe('grade-d')
    expect(gradeClass('f')).toBe('grade-d')
  })

  it('ABCD 各归其档, 未知回退 B 档', () => {
    expect(gradeClass('A')).toBe('grade-a')
    expect(gradeClass('D')).toBe('grade-d')
    expect(gradeClass(null)).toBe('grade-b')
    expect(gradeClass('X')).toBe('grade-b')
  })
})
