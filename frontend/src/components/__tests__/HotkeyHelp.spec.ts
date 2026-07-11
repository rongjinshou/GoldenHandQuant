import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'

import { NModal } from 'naive-ui'

import { NAV_ITEMS } from '@/router'

import HotkeyHelp from '../HotkeyHelp.vue'

/* NModal stub 沿 FactorDetailModal.spec.ts 既有惯例(按组件名字符串注册):
 * 只保留 show 开关语义 + 透传 update:show, 不拖 naive-ui teleport/遮罩重逻辑;
 * 额外声明 title 供断言弹层标题接到了 preset=card 的 title prop。 */
const ModalStub = defineComponent({
  props: { show: Boolean, title: { type: String, default: '' }, closable: Boolean },
  emits: ['update:show'],
  template: '<div v-if="show"><slot /></div>',
})

const stubs = { [NModal.name as string]: ModalStub }

describe('HotkeyHelp(快捷键帮助浮层)', () => {
  it('show=false 不渲染内容', () => {
    const w = mount(HotkeyHelp, { props: { show: false }, global: { stubs } })
    expect(w.find('[data-testid="hotkey-help-body"]').exists()).toBe(false)
  })

  it('show=true 列出全部 6 个页签 label 及对应数字键(NAV_ITEMS 动态生成)', () => {
    const w = mount(HotkeyHelp, { props: { show: true }, global: { stubs } })
    const rows = w.findAll('[data-testid="hotkey-help-nav"]')
    expect(NAV_ITEMS).toHaveLength(6) // 页签数变动时本用例应同步审视帮助文案
    expect(rows).toHaveLength(NAV_ITEMS.length)
    NAV_ITEMS.forEach((item, i) => {
      expect(rows[i].find('kbd').text()).toBe(String(i + 1))
      expect(rows[i].text()).toContain(item.label)
    })
  })

  it("列出 '?' 打开帮助与 Esc 关闭两条通用项, 标题为「键盘快捷键」", () => {
    const w = mount(HotkeyHelp, { props: { show: true }, global: { stubs } })
    const keys = w.findAll('kbd').map((k) => k.text())
    expect(keys).toContain('?')
    expect(keys).toContain('Esc')
    expect(keys).toHaveLength(NAV_ITEMS.length + 2) // 6 页签 + ? + Esc, 无冗余行
    expect(w.text()).toContain('打开本帮助')
    expect(w.text()).toContain('关闭弹层')
    expect(w.findComponent(ModalStub).props('title')).toBe('键盘快捷键')
  })

  it('closable 开启(R6 F 节): 纯静态浮层由 ✕ 提供焦点落点与显式关闭途径', () => {
    const w = mount(HotkeyHelp, { props: { show: true }, global: { stubs } })
    expect(w.findComponent(ModalStub).props('closable')).toBe(true)
  })

  it('NModal 关闭(Esc/遮罩/✕ 收敛的 update:show(false)) → 向上透传 update:show', () => {
    const w = mount(HotkeyHelp, { props: { show: true }, global: { stubs } })
    w.findComponent(ModalStub).vm.$emit('update:show', false)
    expect(w.emitted('update:show')).toEqual([[false]])
  })
})
