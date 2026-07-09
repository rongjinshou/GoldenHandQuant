import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import type { VerdictFactor } from '@/api/types'

import FactorCard from '../FactorCard.vue'

function mkFactor(o: Partial<VerdictFactor> = {}): VerdictFactor {
  return {
    factor_id: 'F01',
    factor_name: '20日动量',
    expression: 'rank(close/delay(close,20))',
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

describe('FactorCard', () => {
  it('渲染因子身份/评分等级/PASS 徽章, 无死因行', () => {
    const w = mount(FactorCard, { props: { factor: mkFactor(), longOnly: false, hasSplit: false } })
    expect(w.text()).toContain('F01')
    expect(w.text()).toContain('20日动量')
    expect(w.find('[data-testid="verdict-card-grade"]').text()).toBe('B 72')
    expect(w.text()).toContain('PASS')
    expect(w.find('[data-testid="verdict-card-fail-reason"]').exists()).toBe(false)
  })

  it('FAIL 因子显示首要死因(reasons 中第一条未通过项)', () => {
    const f = mkFactor({
      passed: false,
      reasons: ['IC=0.0300 >= 0.02 ✓', '单调性=0.52 < 0.6 (单调性不足)', 'IR=0.10 < 0.3 (IR门槛)'],
    })
    const w = mount(FactorCard, { props: { factor: f, longOnly: false, hasSplit: false } })
    expect(w.text()).toContain('FAIL')
    expect(w.find('[data-testid="verdict-card-fail-reason"]').text()).toBe('单调性=0.52 < 0.6 (单调性不足)')
  })

  it('score 为 null 时评分徽章显示 —', () => {
    const w = mount(FactorCard, {
      props: { factor: mkFactor({ score: null, grade: null }), longOnly: false, hasSplit: false },
    })
    expect(w.find('[data-testid="verdict-card-grade"]').text()).toBe('—')
  })

  it('点击时触发外部绑定的原生 click 监听(attrs fallthrough, 无需自定义 emit)', async () => {
    const onClick = vi.fn()
    const w = mount(FactorCard, {
      props: { factor: mkFactor(), longOnly: false, hasSplit: false },
      attrs: { onClick },
    })
    await w.trigger('click')
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('闸门轨道渲染 7 格, aria-label 统计通过数', () => {
    const w = mount(FactorCard, { props: { factor: mkFactor(), longOnly: false, hasSplit: true } })
    const track = w.find('[data-testid="verdict-card-track"]')
    expect(track.findAll('.gate-cell')).toHaveLength(7)
    expect(track.attributes('aria-label')).toBe('7 道闸门通过 7 道')
  })

  it('OOS超额上A股行情色(正=t-up), IC均值/超额IR 转中性不再上闸门判定色(设计 §6.1)', () => {
    // longOnly 指标序: IC均值 / 超额IR / OOS超额
    const w = mount(FactorCard, { props: { factor: mkFactor(), longOnly: true, hasSplit: true } })
    const cells = w.findAll('.fc-metric b')
    expect(cells[0]!.classes()).not.toContain('t-up')
    expect(cells[0]!.classes()).not.toContain('t-pass') // 不再走闸门判定色
    expect(cells[1]!.classes()).not.toContain('t-up')
    expect(cells[2]!.classes()).toContain('t-up') // OOS超额 0.02 → A股红
  })

  it('OOS超额为负 → t-down(A股绿)', () => {
    const w = mount(FactorCard, {
      props: { factor: mkFactor({ oos_top_excess_return: -0.02 }), longOnly: true, hasSplit: true },
    })
    expect(w.findAll('.fc-metric b')[2]!.classes()).toContain('t-down')
  })

  it('非长多口径 OOS多空(带符号收益)上行情色', () => {
    // 非 longOnly 指标序: IC均值 / IR / OOS多空
    const w = mount(FactorCard, {
      props: { factor: mkFactor({ oos_long_short_return: 0.01 }), longOnly: false, hasSplit: true },
    })
    expect(w.findAll('.fc-metric b')[2]!.classes()).toContain('t-up')
  })
})
