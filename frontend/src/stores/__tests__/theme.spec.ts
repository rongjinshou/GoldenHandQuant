import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useThemeStore } from '../theme'

describe('theme store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    document.documentElement.dataset.theme = 'dark'
  })

  it('默认 dark, toggle 翻转 theme/dataset/localStorage', () => {
    const store = useThemeStore()
    expect(store.theme).toBe('dark')

    store.toggle()
    expect(store.theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('ghq-theme')).toBe('light')

    store.toggle()
    expect(store.theme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('ghq-theme')).toBe('dark')
  })

  it('从 localStorage 恢复 light', () => {
    localStorage.setItem('ghq-theme', 'light')
    const store = useThemeStore()
    expect(store.theme).toBe('light')
  })

  it('naiveTheme: dark 时为 darkTheme 对象, light 时为 null', () => {
    const store = useThemeStore()
    expect(store.naiveTheme).not.toBeNull()
    store.toggle()
    expect(store.naiveTheme).toBeNull()
  })

  it('naiveOverrides 主色恒为品牌橙', () => {
    const store = useThemeStore()
    expect(store.naiveOverrides.common?.primaryColor).toBe('#d97757')
    store.toggle()
    expect(store.naiveOverrides.common?.primaryColor).toBe('#d97757')
  })
})
