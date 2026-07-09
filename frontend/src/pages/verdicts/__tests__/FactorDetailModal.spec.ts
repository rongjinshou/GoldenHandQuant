import { defineComponent, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
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
  // NModal.name 的静态类型是 string | undefined(DefineComponent 的 name 字段可选) —— 计算属性名
  // 不接受含 undefined 的联合类型, 但运行时 naive-ui 组件恒有 name, 用 as string 收窄即可, 不影响任何
  // 运行时行为(纯类型断言, 编译后代码不变); 与 Jobs.spec.ts 现状 stub 命名习惯保持一致(按组件名字符串)。
  [NModal.name as string]: defineComponent({
    props: { show: Boolean },
    template: '<div v-if="show"><slot /></div>',
  }),
  // 同 Jobs.spec.ts 既有惯例: GlossaryTip 内部按术语查字典渲染 NPopover, 测试里只关心插槽文本本身。
  GlossaryTip: { template: '<span><slot /></span>' },
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

  it('标题用 <h3>(消除 h2→h4 跳级, a11y)', () => {
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    expect(w.find('h3#vm-title').exists()).toBe(true)
  })

  it('指标表表头带 scope=col, 空表头补 sr-only 文本', () => {
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
    })
    const ths = w.findAll('.vm-metrics thead th')
    expect(ths).toHaveLength(3)
    ths.forEach((th) => expect(th.attributes('scope')).toBe('col'))
    expect(ths[0].find('.sr-only').text()).toBe('指标')
  })

  it('Top超额行(带符号收益)上A股行情色, IC均值行中性(设计 §6.1)', () => {
    // longOnly + hasSplit: 行序 IC均值 / 超额信息比 / 超额正率 / 单调性 / Top超额
    const w = mount(FactorDetailModal, {
      props: { show: true, factors: [mkFactor()], index: 0, longOnly: true, hasSplit: true, runTitle: 'r' },
      global: { stubs },
    })
    const rows = w.findAll('.vm-metrics tbody tr')
    const icCells = rows[0]!.findAll('td.num')
    expect(icCells[0]!.classes()).not.toContain('t-up') // IC均值 IS 中性
    expect(icCells[1]!.classes()).not.toContain('t-up') // OOS IC均值 中性
    const topCells = rows[4]!.findAll('td.num')
    expect(topCells[0]!.classes()).toContain('t-up') // IS top_excess_return=0.03 → 红
    expect(topCells[1]!.classes()).toContain('t-up') // OOS oos_top_excess_return=0.02 → 红
  })

  it('Top超额为负 → t-down(A股绿)', () => {
    const w = mount(FactorDetailModal, {
      props: {
        show: true,
        factors: [mkFactor({ top_excess_return: -0.03, oos_top_excess_return: -0.02 })],
        index: 0, longOnly: true, hasSplit: true, runTitle: 'r',
      },
      global: { stubs },
    })
    const topCells = w.findAll('.vm-metrics tbody tr')[4]!.findAll('td.num')
    expect(topCells[0]!.classes()).toContain('t-down')
    expect(topCells[1]!.classes()).toContain('t-down')
  })

  it('打开后焦点落到弹框容器(修 ←/→ 方向键首次失灵)', async () => {
    const w = mount(FactorDetailModal, {
      props: { show: false, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: false, runTitle: 'r' },
      global: { stubs },
      attachTo: document.body,
    })
    await w.setProps({ show: true })
    await flushPromises()
    await nextTick()
    expect(document.activeElement).toBe(w.find('[data-testid="verdict-modal"]').element)
    w.unmount()
  })
})
