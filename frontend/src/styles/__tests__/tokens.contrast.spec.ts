import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// 读 CSS 源做正则断言(lint 式守卫); vitest 对 .css?raw 不可靠, 走 fs
const css = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8')

/** 提取某主题块内的 --var: #hex / rgba() 声明 */
function themeVars(theme: 'dark' | 'light'): Record<string, string> {
  const re = new RegExp(`:root\\[data-theme='${theme}'\\]\\s*{([^}]*)}`, 'm')
  const body = css.match(re)?.[1] ?? ''
  const out: Record<string, string> = {}
  for (const m of body.matchAll(/(--[\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}

function lin(c: number): number {
  const s = c / 255
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
function L(hex: string): number {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}
function ratio(fg: string, bg: string): number {
  const a = L(fg)
  const b = L(bg)
  const [hi, lo] = a > b ? [a, b] : [b, a]
  return (hi + 0.05) / (lo + 0.05)
}

// 主背景常量（tokens.css 顶部权威值）
const BG = { dark: '#141413', bg2Dark: '#1f1e1c', light: '#faf9f5', bg2Light: '#f2f0e9' }
const ACCENT = '#d97757'

describe('tokens 对比度守卫 (WCAG 2.2 AA)', () => {
  it('主按钮文字 --text-on-accent 压 accent ≥4.5:1（双主题）', () => {
    for (const t of ['dark', 'light'] as const) {
      const v = themeVars(t)['--text-on-accent']
      expect(ratio(v, ACCENT), `${t} text-on-accent`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('亮色语义文字色压 bg-2 ≥4.5:1', () => {
    const v = themeVars('light')
    const bg = BG.bg2Light
    for (const key of ['--text-3', '--accent-strong', '--c-up', '--c-down', '--c-warn', '--accent-blue']) {
      expect(ratio(v[key], bg), `light ${key}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('输入框边框 --border-input 压 bg-2 ≥3:1（双主题，UI 组件门槛）', () => {
    expect(ratio(themeVars('dark')['--border-input'], BG.bg2Dark), 'dark border-input').toBeGreaterThanOrEqual(3)
    expect(ratio(themeVars('light')['--border-input'], BG.bg2Light), 'light border-input').toBeGreaterThanOrEqual(3)
  })
})
