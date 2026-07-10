import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { hotkeyIndex, shouldHandleHotkey, usePageHotkeys } from '../usePageHotkeys'
import { NAV_ITEMS } from '@/router'

/* R2-D 数字键 1-6 切页签: 两个纯函数(键→下标 / 守卫)直接断言;
 * 挂载侧用最小 host + memory 路由验证 push 接线与 onUnmounted 卸载干净(window 监听不残留)。 */

describe('hotkeyIndex(键名 → 页签下标)', () => {
  it("'1'..'6' → 0..5(主键盘与小键盘 NumLock 开时 e.key 同为数字字符)", () => {
    expect(hotkeyIndex('1')).toBe(0)
    expect(hotkeyIndex('2')).toBe(1)
    expect(hotkeyIndex('3')).toBe(2)
    expect(hotkeyIndex('4')).toBe(3)
    expect(hotkeyIndex('5')).toBe(4)
    expect(hotkeyIndex('6')).toBe(5)
  })

  it('范围外/非数字/多字符/空串 → null', () => {
    expect(hotkeyIndex('0')).toBeNull()
    expect(hotkeyIndex('7')).toBeNull()
    expect(hotkeyIndex('a')).toBeNull()
    expect(hotkeyIndex('')).toBeNull()
    expect(hotkeyIndex('12')).toBeNull() // 多字符不得因字典序误判
    expect(hotkeyIndex('F1')).toBeNull()
    expect(hotkeyIndex('Escape')).toBeNull()
  })
})

/** 守卫用例的 e-like 工厂: 默认"正常场景"(无修饰/非合成/目标无输入语境), 用例只覆写关心的字段。 */
function makeEvent(overrides: Partial<Parameters<typeof shouldHandleHotkey>[0]> = {}) {
  return {
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    shiftKey: false,
    isComposing: false,
    target: null,
    ...overrides,
  }
}

describe('shouldHandleHotkey(守卫纯函数)', () => {
  it('正常场景放行: 无修饰键 + 非合成 + 目标/焦点均非输入', () => {
    expect(shouldHandleHotkey(makeEvent())).toBe(true)
    expect(shouldHandleHotkey(makeEvent({ target: document.createElement('div') }))).toBe(true)
    // activeElement 为 body(未聚焦任何控件)不拦
    expect(shouldHandleHotkey(makeEvent(), document.body)).toBe(true)
  })

  it('任一修饰键按下即忽略(不劫持 Ctrl+1 等系统习惯)', () => {
    expect(shouldHandleHotkey(makeEvent({ ctrlKey: true }))).toBe(false)
    expect(shouldHandleHotkey(makeEvent({ metaKey: true }))).toBe(false)
    expect(shouldHandleHotkey(makeEvent({ altKey: true }))).toBe(false)
    expect(shouldHandleHotkey(makeEvent({ shiftKey: true }))).toBe(false)
  })

  it('输入法合成中(isComposing)忽略: 拼音敲数字选字不切页', () => {
    expect(shouldHandleHotkey(makeEvent({ isComposing: true }))).toBe(false)
  })

  it('事件目标在输入场景(input/textarea/select/contenteditable 及其后代)忽略', () => {
    expect(shouldHandleHotkey(makeEvent({ target: document.createElement('input') }))).toBe(false)
    expect(shouldHandleHotkey(makeEvent({ target: document.createElement('textarea') }))).toBe(false)
    expect(shouldHandleHotkey(makeEvent({ target: document.createElement('select') }))).toBe(false)

    const editable = document.createElement('div')
    editable.setAttribute('contenteditable', 'true')
    const inner = document.createElement('span')
    editable.appendChild(inner)
    expect(shouldHandleHotkey(makeEvent({ target: editable }))).toBe(false)
    expect(shouldHandleHotkey(makeEvent({ target: inner }))).toBe(false) // closest 沿祖先命中
  })

  it('contenteditable="false" 不算输入场景(选择器只认 "true")', () => {
    const notEditable = document.createElement('div')
    notEditable.setAttribute('contenteditable', 'false')
    expect(shouldHandleHotkey(makeEvent({ target: notEditable }))).toBe(true)
  })

  it('activeElement 在输入场景也忽略(事件从 window 派发时 target 非焦点元素的双保险)', () => {
    const input = document.createElement('input')
    expect(shouldHandleHotkey(makeEvent(), input)).toBe(false)
  })

  it('非 Element 目标(window/document 无 closest)不崩且放行', () => {
    expect(shouldHandleHotkey(makeEvent({ target: window }))).toBe(true)
  })
})

describe('usePageHotkeys(挂载接线)', () => {
  const Stub = defineComponent({ render: () => h('div') })
  const Host = defineComponent({
    setup() {
      usePageHotkeys()
      return () => h('div')
    },
  })

  function makeRouter(): Router {
    return createRouter({
      history: createMemoryHistory(),
      // 只需路由名与 NAV_ITEMS 对齐; 组件用 Stub, 不拖真实页面(重且慢)
      routes: NAV_ITEMS.map((n) => ({ path: `/${n.name}`, name: n.name, component: Stub })),
    })
  }

  async function mountHost() {
    const router = makeRouter()
    await router.push({ name: NAV_ITEMS[0].name })
    const wrapper = mount(Host, { global: { plugins: [router] } })
    return { router, wrapper }
  }

  function press(key: string, init: KeyboardEventInit = {}): void {
    window.dispatchEvent(new KeyboardEvent('keydown', { key, ...init }))
  }

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it("按 '3' → 跳第 3 个页签(verdicts); 范围外键不动", async () => {
    const { router, wrapper } = await mountHost()
    press('3')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(NAV_ITEMS[2].name)

    press('9')
    press('0')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(NAV_ITEMS[2].name)
    wrapper.unmount()
  })

  it('带修饰键不切页(Ctrl+1 留给浏览器)', async () => {
    const { router, wrapper } = await mountHost()
    press('2', { ctrlKey: true })
    press('2', { metaKey: true })
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(NAV_ITEMS[0].name)
    wrapper.unmount()
  })

  it('焦点在输入框时数字键不切页(activeElement 守卫)', async () => {
    const { router, wrapper } = await mountHost()
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()
    expect(document.activeElement).toBe(input)

    press('2') // window 派发, target 非 input, 靠 activeElement 拦
    input.dispatchEvent(new KeyboardEvent('keydown', { key: '2', bubbles: true })) // target=input 路径
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(NAV_ITEMS[0].name)
    wrapper.unmount()
  })

  it('卸载后监听移除干净: 再按数字键不再触发导航', async () => {
    const { router, wrapper } = await mountHost()
    press('4')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe(NAV_ITEMS[3].name)

    // app 卸载时 vue-router 会把 currentRoute 重置回 START(name=undefined),
    // 故不能拿路由值断言"没动"; 改盯 push: 监听若残留会继续调 router.push。
    wrapper.unmount()
    const push = vi.spyOn(router, 'push')
    press('6')
    await flushPromises()
    expect(push).not.toHaveBeenCalled() // 零调用 → window 监听已卸干净
  })
})
