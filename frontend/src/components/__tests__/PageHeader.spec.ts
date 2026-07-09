import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PageHeader from '../PageHeader.vue'

describe('PageHeader', () => {
  it('渲染标题 h2', () => {
    const w = mount(PageHeader, { props: { title: '回测' } })
    expect(w.find('h2').text()).toBe('回测')
  })
  it('meta 存在时渲染 meta 行', () => {
    const w = mount(PageHeader, { props: { title: 'X', meta: '判决轮次 1' } })
    expect(w.text()).toContain('判决轮次 1')
  })
  it('guide prop 渲染引导句', () => {
    const w = mount(PageHeader, { props: { title: 'X', guide: '一句话说明' } })
    expect(w.text()).toContain('一句话说明')
  })
  it('默认插槽覆盖 guide（复杂引导）', () => {
    const w = mount(PageHeader, { props: { title: 'X' }, slots: { default: '<a>链接引导</a>' } })
    expect(w.find('a').exists()).toBe(true)
  })
  it('无 guide 无插槽时不渲染引导段', () => {
    const w = mount(PageHeader, { props: { title: 'X' } })
    expect(w.find('.guide').exists()).toBe(false)
  })
})
