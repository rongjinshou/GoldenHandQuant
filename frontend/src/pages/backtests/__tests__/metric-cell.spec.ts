import { describe, expect, it } from 'vitest'

import { bestByColumn, ddCell, marketCell, qualityCell } from '../metric-cell'

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

describe('bestByColumn 多策略对比每列最优', () => {
  // 9 列全宽行, 列序与 METRIC_DIRECTIONS 一致:
  // [总收益, 年化, 回撤, 夏普, 索提诺, Calmar, 胜率, 交易数, 换手]
  const rowA = [0.3, 0.12, 0.15, 1.2, 1.5, 0.8, 0.55, 40, 2.1]
  const rowB = [0.1, 0.08, 0.25, 0.9, 1.1, 0.4, 0.6, 80, 1.4]

  it('默认方向表整表评优: 大优 6 列 + 小优 2 列全中, 交易数列缺席', () => {
    expect(bestByColumn([rowA, rowB])).toEqual(
      new Set(['0-0', '0-1', '0-2', '0-3', '0-4', '0-5', '1-6', '1-8']),
    )
  })

  it('越大越优列(总收益/夏普/胜率)标最大行', () => {
    const best = bestByColumn([rowA, rowB])
    expect(best.has('0-0')).toBe(true) // 总收益 A 高
    expect(best.has('1-0')).toBe(false)
    expect(best.has('0-3')).toBe(true) // 夏普 A 高
    expect(best.has('1-6')).toBe(true) // 胜率 B 高
  })

  it('越小越优列(最大回撤/换手)标最小行', () => {
    const best = bestByColumn([rowA, rowB])
    expect(best.has('0-2')).toBe(true) // 回撤 A 浅
    expect(best.has('1-2')).toBe(false)
    expect(best.has('1-8')).toBe(true) // 换手 B 低
  })

  it('交易数列(方向 null)不评优', () => {
    const best = bestByColumn([rowA, rowB])
    expect(best.has('0-7')).toBe(false)
    expect(best.has('1-7')).toBe(false)
  })

  it('null 跳过不参赛: 余者照常评优, 全 null 列不标', () => {
    const best = bestByColumn(
      [
        [null, null],
        [0.05, null],
      ],
      ['max', 'max'],
    )
    expect(best.has('1-0')).toBe(true) // 该列仅剩 1 个有效值 → 即最优
    expect(best.has('0-0')).toBe(false)
    expect([...best].some((k) => k.endsWith('-1'))).toBe(false) // 全 null 列无人得标
  })

  it('并列最优全标', () => {
    const best = bestByColumn([[0.2], [0.2], [0.1]], ['max'])
    expect(best.has('0-0')).toBe(true)
    expect(best.has('1-0')).toBe(true)
    expect(best.has('2-0')).toBe(false)
  })

  it('单行/空表不评优(非对比场景)返回空集', () => {
    expect(bestByColumn([rowA]).size).toBe(0)
    expect(bestByColumn([]).size).toBe(0)
  })

  it('方向表可注入: min 方向标最小行', () => {
    const best = bestByColumn([[3], [1], [2]], ['min'])
    expect([...best]).toEqual(['1-0'])
  })
})
