import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { splitSymbolTokens, useSymbolChips } from '../useSymbolChips'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-07-05T10:00:00.000Z'))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('splitSymbolTokens', () => {
  it('按分隔符切分并大写化, 区分合法/非法 token', () => {
    expect(splitSymbolTokens('000021.sz, 600519.SH;贵州')).toEqual({
      ok: ['000021.SZ', '600519.SH'],
      bad: ['贵州'],
    })
  })
})

describe('useSymbolChips', () => {
  it('commitText 追加合法 symbol, 去重, 返回非法 token', () => {
    const chips = useSymbolChips()
    const bad = chips.commitText('000021.SZ,000021.SZ,foo')
    expect(chips.symbols.value).toEqual(['000021.SZ'])
    expect(bad).toEqual(['FOO'])
  })

  it('pickSuggestion 即时成 chip 并清空输入与候选', () => {
    const chips = useSymbolChips()
    chips.input.value = '000021'
    chips.suggestions.value = [{ symbol: '000021.SZ', name: '深科技' }]
    chips.pickSuggestion({ symbol: '000021.SZ', name: '深科技' })
    expect(chips.symbols.value).toEqual(['000021.SZ'])
    expect(chips.input.value).toBe('')
    expect(chips.suggestions.value).toEqual([])
  })

  /* 幽灵点击防护回归测试(2026-07-05 confirmed-bug): 点选联想候选后, 浏览器对该候选的
   * mouseup 会命中同一屏幕坐标新插入的×按钮, 补发一次原生 click 触发 remove——同一次
   * 点击手势里"选中"与"删除"背靠背发生, 表现为点联想候选 chip 秒加秒删, 搜索选中彻底
   * 不可用。防护: 250ms 内对刚加入的同一 symbol 的 remove() 视为幽灵点击, 忽略。 */
  it('幽灵点击防护: 刚 pickSuggestion 加入的 symbol, 250ms 内 remove() 是空操作', () => {
    const chips = useSymbolChips()
    chips.pickSuggestion({ symbol: '000021.SZ', name: '深科技' })
    expect(chips.symbols.value).toEqual(['000021.SZ'])

    chips.remove('000021.SZ') // 模拟同一手势里紧随其后的幽灵点击
    expect(chips.symbols.value).toEqual(['000021.SZ']) // 未被误删
  })

  it('幽灵点击防护窗口过后, remove() 恢复正常生效(不会永久锁死删除)', () => {
    const chips = useSymbolChips()
    chips.pickSuggestion({ symbol: '000021.SZ', name: '深科技' })

    vi.advanceTimersByTime(251)
    chips.remove('000021.SZ')
    expect(chips.symbols.value).toEqual([])
  })

  it('防护窗口只保护"刚加入"那一刻, 对已存在较久的 symbol 立即 remove() 正常生效', () => {
    const chips = useSymbolChips()
    chips.commitText('000021.SZ')
    vi.advanceTimersByTime(1000)
    chips.commitText('600519.SH') // 新加入另一个 symbol, 不影响 000021.SZ 的防护状态(早已过期)

    chips.remove('000021.SZ')
    expect(chips.symbols.value).toEqual(['600519.SH'])
  })

  it('remove 移除指定 symbol, 不影响其余', () => {
    const chips = useSymbolChips()
    chips.commitText('000021.SZ,600519.SH')
    vi.advanceTimersByTime(1000)
    chips.remove('000021.SZ')
    expect(chips.symbols.value).toEqual(['600519.SH'])
  })

  it('onBackspace: 输入框为空时回删最后一个 chip', () => {
    const chips = useSymbolChips()
    chips.commitText('000021.SZ,600519.SH')
    chips.input.value = ''
    chips.onBackspace()
    expect(chips.symbols.value).toEqual(['000021.SZ'])
  })

  it('onBackspace: 输入框非空时不回删', () => {
    const chips = useSymbolChips()
    chips.commitText('000021.SZ')
    chips.input.value = '6005'
    chips.onBackspace()
    expect(chips.symbols.value).toEqual(['000021.SZ'])
  })
})

/* combobox 键盘导航(WCAG 2.1.1/4.1.2): 联想候选 ↑↓ 高亮 + Enter 取高亮 + Esc 关闭。
 * activeIndex=-1 表示无高亮(ARIA aria-activedescendant 空), 首次 ↓ 落首项、↑ 落末项, 到边回绕。 */
describe('useSymbolChips 键盘导航(combobox)', () => {
  function withSuggestions(): ReturnType<typeof useSymbolChips> {
    const chips = useSymbolChips()
    chips.suggestions.value = [
      { symbol: '000021.SZ', name: '深科技' },
      { symbol: '600519.SH', name: '贵州茅台' },
      { symbol: '300750.SZ', name: '宁德时代' },
    ]
    return chips
  }

  it('初始 activeIndex 为 -1(无高亮)', () => {
    const chips = withSuggestions()
    expect(chips.activeIndex.value).toBe(-1)
  })

  it('onArrowDown 从 -1 高亮首项, 逐步下移', () => {
    const chips = withSuggestions()
    chips.onArrowDown()
    expect(chips.activeIndex.value).toBe(0)
    chips.onArrowDown()
    expect(chips.activeIndex.value).toBe(1)
  })

  it('onArrowDown 到末项再下移回绕到首项', () => {
    const chips = withSuggestions()
    chips.onArrowDown() // 0
    chips.onArrowDown() // 1
    chips.onArrowDown() // 2
    chips.onArrowDown() // 回绕 → 0
    expect(chips.activeIndex.value).toBe(0)
  })

  it('onArrowUp 从 -1 高亮末项', () => {
    const chips = withSuggestions()
    chips.onArrowUp()
    expect(chips.activeIndex.value).toBe(2)
  })

  it('onArrowUp 从首项回绕到末项', () => {
    const chips = withSuggestions()
    chips.onArrowDown() // 0
    chips.onArrowUp() // 回绕 → 2
    expect(chips.activeIndex.value).toBe(2)
  })

  it('无候选时方向键是空操作(不越界)', () => {
    const chips = useSymbolChips()
    chips.onArrowDown()
    expect(chips.activeIndex.value).toBe(-1)
    chips.onArrowUp()
    expect(chips.activeIndex.value).toBe(-1)
  })

  it('onEscape 关闭候选并清高亮', () => {
    const chips = withSuggestions()
    chips.onArrowDown()
    chips.onEscape()
    expect(chips.suggestions.value).toEqual([])
    expect(chips.activeIndex.value).toBe(-1)
  })

  it('onEnter 提交当前高亮候选(非首项), 清空输入/候选/高亮', () => {
    const chips = withSuggestions()
    chips.input.value = '600'
    chips.onArrowDown() // 0
    chips.onArrowDown() // 1 → 600519.SH
    chips.onEnter()
    expect(chips.symbols.value).toEqual(['600519.SH'])
    expect(chips.input.value).toBe('')
    expect(chips.activeIndex.value).toBe(-1)
    expect(chips.suggestions.value).toEqual([])
  })

  it('无高亮时 onEnter 维持既有行为(完整代码直接成 chip)', () => {
    const chips = useSymbolChips()
    chips.input.value = '000021.SZ'
    chips.onEnter()
    expect(chips.symbols.value).toEqual(['000021.SZ'])
  })
})
