import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// 读 CSS 源做正则断言(lint 式守卫); vitest 对 .css?raw 不可靠, 走 fs
const tokensCss = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8')
const baseCss = readFileSync(resolve(process.cwd(), 'src/styles/base.css'), 'utf8')

/** 提取 :root 顶层某 CSS 变量的声明值(取首个匹配) */
function rootVar(css: string, name: string): string {
  return css.match(new RegExp(`${name}:\\s*([^;]+);`))?.[1]?.trim() ?? ''
}

describe('P9 CJK 字体栈系统回退 (tokens.css)', () => {
  it('--font-body 补系统常驻 CJK 回退(Microsoft YaHei / PingFang SC), 不裸退默认宋', () => {
    const v = rootVar(tokensCss, '--font-body')
    expect(v).toContain('Microsoft YaHei')
    expect(v).toContain('PingFang SC')
  })

  it('--font-body 仍以思源 serif 优先(Noto Serif SC), 系统回退置于其后', () => {
    const v = rootVar(tokensCss, '--font-body')
    expect(v).toContain('Noto Serif SC')
    expect(v.indexOf('Noto Serif SC')).toBeLessThan(v.indexOf('Microsoft YaHei'))
  })

  it('--font-display 补系统常驻 CJK 回退(Noto Sans SC / Microsoft YaHei / PingFang SC)', () => {
    const v = rootVar(tokensCss, '--font-display')
    expect(v).toContain('Noto Sans SC')
    expect(v).toContain('Microsoft YaHei')
    expect(v).toContain('PingFang SC')
  })
})

describe('P9 表格横滚工具类 (base.css)', () => {
  it('定义 .table-scroll 且 overflow-x:auto', () => {
    expect(baseCss).toMatch(/\.table-scroll\s*{[^}]*overflow-x:\s*auto/s)
  })
})
