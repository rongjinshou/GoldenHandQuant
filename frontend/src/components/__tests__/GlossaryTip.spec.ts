import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { GLOSSARY } from '@/glossary'

import GlossaryTip from '../GlossaryTip.vue'

describe('GlossaryTip 焦点可达(WCAG 1.4.13)', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('触发元素带 tabindex/role/aria-label', () => {
    const w = mount(GlossaryTip, { props: { term: 'sharpe' }, slots: { default: '夏普' } })
    const g = w.find('.gloss')
    expect(g.exists()).toBe(true)
    expect(g.attributes('tabindex')).toBe('0')
    expect(g.attributes('role')).toBe('button')
    expect(g.attributes('aria-label')).toBe('sharpe')
    expect(g.text()).toBe('夏普')
  })

  it('字典缺词降级为纯文本(无 popover 触发壳)', () => {
    const w = mount(GlossaryTip, { props: { term: '___missing___' }, slots: { default: '原文' } })
    expect(w.find('.gloss').exists()).toBe(false)
    expect(w.text()).toBe('原文')
  })

  it('focus 打开术语解释', async () => {
    const w = mount(GlossaryTip, {
      props: { term: 'sharpe' },
      slots: { default: '夏普' },
      attachTo: document.body,
    })
    expect(document.body.textContent).not.toContain(GLOSSARY.sharpe)
    await w.find('.gloss').trigger('focus')
    await nextTick()
    await nextTick()
    expect(document.body.textContent).toContain(GLOSSARY.sharpe)
    w.unmount()
  })
})
