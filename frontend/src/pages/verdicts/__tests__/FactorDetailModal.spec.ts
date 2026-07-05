import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { VerdictFactor } from '@/api/types'
import { NModal } from 'naive-ui'

import FactorDetailModal from '../FactorDetailModal.vue'

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
    reasons: ['IC=0.0300 >= 0.02 ✓', '单调性=0.70 >= 0.6 ✓'],
    ...o,
  }
}

const stubs = {
  [NModal.name]: defineComponent({
    props: ['show'],
    template: '<div v-if="show"><slot /></div>',
  }),
}

describe('FactorDetailModal', () => {
  it('show=false 不渲染内容', () => {
    const w = mount(FactorDetailModal, {
      props: { show: false, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('[data-testid="verdict-modal"]').exists()).toBe(false)
  })

  it('展示身份/表达式/轮次上下文/逐关判定, OOS 未切分时显 —', () => {
    const w = mount(FactorDetailModal, {
      props: {
        show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false,
        runTitle: '3 因子 · 多空 · 未切分',
      },
      global: { stubs },
    })
    expect(w.text()).toContain('F01')
    expect(w.text()).toContain('20日动量')
    expect(w.text()).toContain('rank(close/delay(close,20))')
    expect(w.text()).toContain('3 因子 · 多空 · 未切分')
    expect(w.text()).toContain('IC=0.0300 >= 0.02 ✓')
    const rows = w.findAll('.vm-metrics tbody tr')
    expect(rows[0].text()).toContain('—') // IC均值行 OOS 列: 未切分显 —
  })

  it('设切分后 OOS 列显真实数值', () => {
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: true, runTitle: 'r' },
      global: { stubs },
    })
    const rows = w.findAll('.vm-metrics tbody tr')
    expect(rows[0].text()).toContain('0.0200') // oos_ic_mean
  })

  it('首个因子禁用上一个, 点下一个 emit navigate(1)', async () => {
    const factors = [mkFactor({ factor_id: 'A' }), mkFactor({ factor_id: 'B' }), mkFactor({ factor_id: 'C' })]
    const w = mount(FactorDetailModal, {
      props: { show: true, factors, index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('[data-testid="verdict-modal-prev"]').attributes('disabled')).toBeDefined()
    await w.find('[data-testid="verdict-modal-next"]').trigger('click')
    expect(w.emitted('navigate')?.[0]).toEqual([1])
  })

  it('末个因子禁用下一个', () => {
    const factors = [mkFactor({ factor_id: 'A' }), mkFactor({ factor_id: 'B' })]
    const w = mount(FactorDetailModal, {
      props: { show: true, factors, index: 1, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('[data-testid="verdict-modal-next"]').attributes('disabled')).toBeDefined()
  })

  it('→ 键盘导航等效点击下一个', async () => {
    const factors = [mkFactor({ factor_id: 'A' }), mkFactor({ factor_id: 'B' })]
    const w = mount(FactorDetailModal, {
      props: { show: true, factors, index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    await w.find('[data-testid="verdict-modal"]').trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('navigate')?.[0]).toEqual([1])
  })

  it('✕ 关闭钮 emit update:show(false)', async () => {
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    await w.find('.vm-close').trigger('click')
    expect(w.emitted('update:show')?.[0]).toEqual([false])
  })
})
