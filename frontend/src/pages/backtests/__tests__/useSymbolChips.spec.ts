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
