import { defineComponent } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { NModal } from 'naive-ui'

import type { VerdictFactor } from '@/api/types'

import FactorDetailModal from '../FactorDetailModal.vue'

/* P8 孤儿词条接线验收: oos_ic/oos_ir/ls_oos/score/verdict_badge 五个此前 0 引用的词条
 * 是否已用焦点可达的 GlossaryTip 接到 FactorDetailModal 对应 UI。用 term 捕获版 stub
 * 把每处 GlossaryTip 的 term 落到 data-term, 断言词条确实被渲染(即接线且可达)。 */

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

const GlossaryTipSpy = defineComponent({
  props: { term: { type: String, required: true }, plain: Boolean },
  template: '<span class="gloss-spy" :data-term="term"><slot /></span>',
})

const stubs = {
  [NModal.name as string]: defineComponent({
    props: { show: Boolean },
    template: '<div v-if="show"><slot /></div>',
  }),
  GlossaryTip: GlossaryTipSpy,
}

function terms(w: VueWrapper): string[] {
  return w.findAll('.gloss-spy').map((g) => g.attributes('data-term') ?? '')
}

function mountModal(props: Record<string, unknown>) {
  return mount(FactorDetailModal, {
    props: { show: true, factors: [mkFactor()], index: 0, longOnly: false, hasSplit: true, runTitle: 'r', ...props },
    global: { stubs },
  })
}

describe('FactorDetailModal 术语接线(P8 孤儿词条)', () => {
  it('多空 + 切分: oos_ic/oos_ir/ls_oos/score/verdict_badge 五个词条全部接线且焦点可达', () => {
    const t = terms(mountModal({ longOnly: false, hasSplit: true }))
    expect(t).toContain('oos_ic')
    expect(t).toContain('oos_ir')
    expect(t).toContain('ls_oos')
    expect(t).toContain('score')
    expect(t).toContain('verdict_badge')
  })

  it('长多 + 切分: OOS 列接 oos_ic 与 ls_oos(长多无 IR OOS 列)', () => {
    const t = terms(mountModal({ longOnly: true, hasSplit: true }))
    expect(t).toContain('oos_ic')
    expect(t).toContain('ls_oos')
    expect(t).toContain('score')
    expect(t).toContain('verdict_badge')
  })

  it('未切分: OOS 列显 — 不挂 oos_* tip; 徽章类词条(score/verdict_badge)与切分无关仍在', () => {
    const t = terms(mountModal({ hasSplit: false }))
    expect(t).not.toContain('oos_ic')
    expect(t).not.toContain('oos_ir')
    expect(t).not.toContain('ls_oos')
    expect(t).toContain('score')
    expect(t).toContain('verdict_badge')
  })

  it('score 缺失 → grade 徽章不渲染, 不接 score 词条(避免空徽章/无值 tip)', () => {
    const t = terms(mountModal({ factors: [mkFactor({ score: null, grade: null })] }))
    expect(t).not.toContain('score')
    expect(t).toContain('verdict_badge')
  })
})
