import { describe, expect, it } from 'vitest'

import { ddCell, marketCell, qualityCell } from '../metric-cell'

const id = (x: number) => String(x)

describe('回测指标 cell 配色', () => {
  it('收益正号=行情涨色 t-up(A股红)', () => {
    expect(marketCell(0.07, id).cls).toBe('t-up')
  })
  it('收益负号=行情跌色 t-down(A股绿)', () => {
    expect(marketCell(-0.03, id).cls).toBe('t-down')
  })
  it('收益为 0 无色', () => {
    expect(marketCell(0, id).cls).toBe('')
  })
  it('null → t-muted 破折号', () => {
    expect(marketCell(null, id)).toEqual({ text: '-', cls: 't-muted' })
  })
  it('质量指标恒中性(好夏普不显红/绿)', () => {
    expect(qualityCell(0.53, id).cls).toBe('')
    expect(qualityCell(-0.1, id).cls).toBe('')
  })
  it('回撤 >20% 标 t-fail, 否则无色', () => {
    expect(ddCell(0.25, id).cls).toBe('t-fail')
    expect(ddCell(0.15, id).cls).toBe('')
  })
})
