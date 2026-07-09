import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/styles/base.css'), 'utf8')

describe('base.css 全局无障碍原语', () => {
  it('定义 .sr-only 工具类', () => {
    expect(css).toMatch(/\.sr-only\s*{/)
  })
  it('定义全局 :focus-visible 焦点环', () => {
    expect(css).toMatch(/:focus-visible\s*{[^}]*outline/)
  })
  it('骨架动画有 reduced-motion 归零', () => {
    expect(css).toMatch(/kpi-skeleton[^}]*animation:\s*none/s)
  })
  it('链接文字用 accent-strong 回退', () => {
    expect(css).toMatch(/color:\s*var\(--accent-strong,\s*var\(--accent\)\)/)
  })
})
