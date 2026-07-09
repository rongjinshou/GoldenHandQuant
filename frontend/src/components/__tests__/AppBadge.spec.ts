import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppBadge from '../AppBadge.vue'

describe('AppBadge', () => {
  it('渲染插槽内容', () => {
    const w = mount(AppBadge, { props: { kind: 'pass' }, slots: { default: 'PASS' } })
    expect(w.text()).toBe('PASS')
  })
  it('kind 映射到 badge--{kind} 类', () => {
    const w = mount(AppBadge, { props: { kind: 'fail' }, slots: { default: 'x' } })
    expect(w.classes()).toContain('badge--fail')
  })
  it('默认 size=md, 传 sm 加 badge--sm', () => {
    const w = mount(AppBadge, { props: { kind: 'info', size: 'sm' }, slots: { default: 'x' } })
    expect(w.classes()).toContain('badge--sm')
  })
})
