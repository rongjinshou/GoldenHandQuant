import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// 读源文件断言三源关键色同值 (防漂移)
const read = (p: string) => readFileSync(resolve(process.cwd(), p), 'utf8')
const chart = read('src/composables/useChartTheme.ts')
const tokens = read('src/styles/tokens.css')
const theme = read('src/stores/theme.ts')

function tokenVar(t: 'dark' | 'light', name: string): string {
  const body = tokens.match(new RegExp(`:root\\[data-theme='${t}'\\]\\s*{([^}]*)}`, 'm'))?.[1] ?? ''
  return body.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1].trim() ?? ''
}

describe('三源调色板同值防线', () => {
  it('theme.ts primaryColor 与 tokens --accent 同值', () => {
    expect(tokenVar('dark', '--accent')).toBe('#d97757')
    expect(tokenVar('light', '--accent')).toBe('#d97757')
    expect(theme).toContain("primaryColor: '#d97757'")
  })
  it('ECharts brand 与 tokens --accent 同值', () => {
    expect(chart).toMatch(/brand:\s*'#d97757'/)
  })
  it('ECharts 暗色 up/down 与 tokens 暗色行情色同值', () => {
    expect(tokenVar('dark', '--c-up')).toBe('#e5735a')
    expect(tokenVar('dark', '--c-down')).toBe('#8ba36b')
    expect(chart).toMatch(/up:\s*'#e5735a'/)
    expect(chart).toMatch(/down:\s*'#8ba36b'/)
  })
})
