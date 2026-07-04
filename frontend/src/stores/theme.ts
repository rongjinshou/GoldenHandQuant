import { darkTheme, type GlobalTheme, type GlobalThemeOverrides } from 'naive-ui'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type ThemeName = 'dark' | 'light'

const STORAGE_KEY = 'ghq-theme'

/* Naive UI 是 prop 驱动、不感知 data-theme attribute(设计 §4.1) —
 * 本 store 双驱动: dataset 供自有 CSS token, naiveTheme/naiveOverrides 供 n-config-provider。 */

const common = {
  primaryColor: '#d97757',
  primaryColorHover: '#e08a6d',
  primaryColorPressed: '#c0563c',
  borderRadius: '10px',
  fontFamily: "'Lora', Georgia, 'Noto Serif SC', serif",
} as const

const DARK_OVERRIDES: GlobalThemeOverrides = {
  common: {
    ...common,
    bodyColor: '#141413',
    cardColor: '#1f1e1c',
    modalColor: '#1f1e1c',
    popoverColor: '#2a2926',
    inputColor: '#2a2926',
    borderColor: '#3a3833',
    textColorBase: '#faf9f5',
    textColor1: '#faf9f5',
    textColor2: '#d6d4cb',
    textColor3: '#9d9b92',
  },
}

const LIGHT_OVERRIDES: GlobalThemeOverrides = {
  common: {
    ...common,
    bodyColor: '#faf9f5',
    cardColor: '#f2f0e9',
    modalColor: '#faf9f5',
    popoverColor: '#faf9f5',
    inputColor: '#ffffff',
    borderColor: '#dcd9cd',
    textColorBase: '#141413',
    textColor1: '#141413',
    textColor2: '#4a4945',
    textColor3: '#75736b',
  },
}

function readInitial(): ThemeName {
  return localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<ThemeName>(readInitial())

  function apply(next: ThemeName): void {
    theme.value = next
    document.documentElement.dataset.theme = next
    localStorage.setItem(STORAGE_KEY, next)
  }

  function toggle(): void {
    apply(theme.value === 'dark' ? 'light' : 'dark')
  }

  const naiveTheme = computed<GlobalTheme | null>(() => (theme.value === 'dark' ? darkTheme : null))
  const naiveOverrides = computed<GlobalThemeOverrides>(() =>
    theme.value === 'dark' ? DARK_OVERRIDES : LIGHT_OVERRIDES,
  )

  return { theme, toggle, naiveTheme, naiveOverrides }
})
