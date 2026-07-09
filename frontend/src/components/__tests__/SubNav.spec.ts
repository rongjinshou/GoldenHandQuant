import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SubNav from '../SubNav.vue'

const items = [
  { key: 'a', label: 'A' },
  { key: 'b', label: 'B' },
  { key: 'c', label: 'C' },
]

describe('SubNav aria-current', () => {
  it('仅激活项带 aria-current=page', () => {
    const w = mount(SubNav, { props: { items, modelValue: 'b' } })
    expect(w.find('[data-testid="subnav-b"]').attributes('aria-current')).toBe('page')
    expect(w.find('[data-testid="subnav-a"]').attributes('aria-current')).toBeUndefined()
    expect(w.find('[data-testid="subnav-c"]').attributes('aria-current')).toBeUndefined()
  })

  it('点击发出 update:modelValue', async () => {
    const w = mount(SubNav, { props: { items, modelValue: 'a' } })
    await w.find('[data-testid="subnav-c"]').trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['c'])
  })
})
