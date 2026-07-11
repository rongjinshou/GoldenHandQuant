import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ErrorBanner from '../ErrorBanner.vue'

describe('ErrorBanner', () => {
  it('默认只渲染中文 msg, 无按钮无 title(既有 :msg 用法零破坏)', () => {
    const w = mount(ErrorBanner, { props: { msg: '记录不存在' } })
    const root = w.get('[data-testid="error-banner"]')
    expect(root.text()).toContain('记录不存在')
    expect(root.attributes('title')).toBeUndefined()
    expect(w.find('button').exists()).toBe(false)
  })

  it('technical 渲染为 title 悬停可见, 不进正文(R6-02)', () => {
    const w = mount(ErrorBanner, {
      props: { msg: '服务内部错误', technical: '500 /api/x: boom' },
    })
    const root = w.get('[data-testid="error-banner"]')
    expect(root.attributes('title')).toBe('500 /api/x: boom')
    expect(root.text()).not.toContain('500 /api/x')
  })

  it('dismissible 出 ✕ 且点击 emit close(R6-03b 恢复后可清横幅)', async () => {
    const w = mount(ErrorBanner, { props: { msg: 'x', dismissible: true } })
    await w.get('[aria-label="关闭"]').trigger('click')
    expect(w.emitted('close')).toHaveLength(1)
  })

  it('retryable 出重试钮且点击 emit retry', async () => {
    const w = mount(ErrorBanner, { props: { msg: 'x', retryable: true } })
    await w.get('button').trigger('click')
    expect(w.emitted('retry')).toHaveLength(1)
  })
})
