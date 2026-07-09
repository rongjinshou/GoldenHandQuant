import { describe, expect, it } from 'vitest'

import { mcell, metricCellClass, metricColorMode } from '../verdict-metric-cell'

const id = (x: number) => String(x)

/* 配色映射的单一真相源锁定(设计 §6.1) —— 哪些字段行情色 / 哪些中性,
 * 改一处坏一处的门。 */
describe('判决数值格子配色映射', () => {
  describe('metricColorMode: 带符号收益=行情, 其余=中性', () => {
    it.each([
      'top_excess_return',
      'oos_top_excess_return',
      'long_short_return',
      'oos_long_short_return',
    ])('%s → 行情色(market)', (name) => {
      expect(metricColorMode(name)).toBe('market')
    })

    it.each([
      'ic_mean',
      'ir',
      'excess_ir',
      'ic_positive_rate',
      'excess_positive_rate',
      'monotonicity_score',
      'oos_ic_mean',
      'oos_ir',
    ])('%s → 中性色(neutral)', (name) => {
      expect(metricColorMode(name)).toBe('neutral')
    })
  })

  describe('metricCellClass: 行情字段按符号上 A 股行情色', () => {
    it('OOS超额 正 → t-up(A股红)', () => {
      expect(metricCellClass('oos_top_excess_return', 0.03)).toBe('t-up')
    })
    it('OOS超额 负 → t-down(A股绿)', () => {
      expect(metricCellClass('oos_top_excess_return', -0.02)).toBe('t-down')
    })
    it('OOS多空 正 → t-up / 负 → t-down', () => {
      expect(metricCellClass('oos_long_short_return', 0.01)).toBe('t-up')
      expect(metricCellClass('oos_long_short_return', -0.01)).toBe('t-down')
    })
    it('IS 侧超额/多空同样上行情色', () => {
      expect(metricCellClass('top_excess_return', 0.05)).toBe('t-up')
      expect(metricCellClass('long_short_return', -0.04)).toBe('t-down')
    })
    it('行情字段值为 0 → 无色', () => {
      expect(metricCellClass('oos_top_excess_return', 0)).toBe('')
    })
    it('行情字段无值 → 无色', () => {
      expect(metricCellClass('oos_top_excess_return', null)).toBe('')
      expect(metricCellClass('oos_top_excess_return', undefined)).toBe('')
    })
  })

  describe('metricCellClass: 中性字段恒不上红绿(好夏普不显红同理)', () => {
    it('IC均值 无论正负都中性', () => {
      expect(metricCellClass('ic_mean', 0.08)).toBe('')
      expect(metricCellClass('ic_mean', -0.08)).toBe('')
    })
    it('超额IR 中性', () => {
      expect(metricCellClass('excess_ir', 1.2)).toBe('')
      expect(metricCellClass('excess_ir', -1.2)).toBe('')
    })
    it('IR 中性', () => {
      expect(metricCellClass('ir', 0.4)).toBe('')
    })
  })

  describe('mcell: 文本格式化 + 配色', () => {
    it('行情字段: 文本走 fmt, 类走行情色', () => {
      expect(mcell('oos_top_excess_return', 0.03, id)).toEqual({ text: '0.03', cls: 't-up' })
    })
    it('中性字段: 文本走 fmt, 无色', () => {
      expect(mcell('ic_mean', 0.03, id)).toEqual({ text: '0.03', cls: '' })
    })
    it('无值 → 破折号 + 无色', () => {
      expect(mcell('oos_top_excess_return', null, id)).toEqual({ text: '-', cls: '' })
      expect(mcell('ic_mean', undefined, id)).toEqual({ text: '-', cls: '' })
    })
  })
})
