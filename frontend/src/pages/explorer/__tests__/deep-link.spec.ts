import { describe, expect, it } from 'vitest'

import { parseSymbolsQuery, symbolsToQuery } from '../deep-link'

/* 行情页 P7 URL 深链纯逻辑(?symbols= ↔ 标的列表) — 解析健壮性 + 序列化规范化 + 往返幂等。
 * 挂载侧(useRoute/useRouter/watch)由 explorer-aria.spec.ts 读文件契约守, 这里只测纯函数。 */

describe('parseSymbolsQuery — ?symbols= 原始值 → 合法标的有序列表', () => {
  it('单个合法代码', () => {
    expect(parseSymbolsQuery('000021.SZ')).toEqual(['000021.SZ'])
  })

  it('逗号分隔多个, 保序', () => {
    expect(parseSymbolsQuery('000021.SZ,600000.SH')).toEqual(['000021.SZ', '600000.SH'])
    // 顺序即输入顺序, 不排序
    expect(parseSymbolsQuery('600000.SH,000021.SZ')).toEqual(['600000.SH', '000021.SZ'])
  })

  it('小写交易所后缀大写化', () => {
    expect(parseSymbolsQuery('000021.sz,600000.sh')).toEqual(['000021.SZ', '600000.SH'])
  })

  it('token 首尾空白 trim', () => {
    expect(parseSymbolsQuery('  000021.SZ , 600000.SH  ')).toEqual(['000021.SZ', '600000.SH'])
  })

  it('去重(保留首次出现位置)', () => {
    expect(parseSymbolsQuery('000021.SZ,000021.SZ,600000.SH')).toEqual(['000021.SZ', '600000.SH'])
    // 大小写归一后再去重
    expect(parseSymbolsQuery('000021.SZ,000021.sz')).toEqual(['000021.SZ'])
  })

  it('丢弃非法 token, 保留合法 token(不崩)', () => {
    expect(parseSymbolsQuery('000021.SZ,foo,600000.SH')).toEqual(['000021.SZ', '600000.SH'])
  })

  it('丢弃空 token(连续逗号/首尾逗号)', () => {
    expect(parseSymbolsQuery('000021.SZ,,600000.SH')).toEqual(['000021.SZ', '600000.SH'])
    expect(parseSymbolsQuery(',000021.SZ,')).toEqual(['000021.SZ'])
  })

  it('全非法 → 空数组', () => {
    expect(parseSymbolsQuery('foo,bar')).toEqual([])
  })

  it('格式细节: 非 6 位/未知交易所/缺后缀 一律拒', () => {
    expect(parseSymbolsQuery('12345.SH')).toEqual([]) // 5 位
    expect(parseSymbolsQuery('1234567.SH')).toEqual([]) // 7 位
    expect(parseSymbolsQuery('000021.NYSE')).toEqual([]) // 未知交易所
    expect(parseSymbolsQuery('000021')).toEqual([]) // 缺后缀
    expect(parseSymbolsQuery('000021.SZ.SH')).toEqual([]) // 多后缀
    expect(parseSymbolsQuery('60000A.SH')).toEqual([]) // 含字母
  })

  it('BJ 交易所受支持', () => {
    expect(parseSymbolsQuery('430047.BJ')).toEqual(['430047.BJ'])
  })

  it('空串 / 纯空白 / 纯逗号 → 空数组', () => {
    expect(parseSymbolsQuery('')).toEqual([])
    expect(parseSymbolsQuery('   ')).toEqual([])
    expect(parseSymbolsQuery(',,,')).toEqual([])
  })

  it('健壮: 非字符串输入(vue-router 可能给 null/数组/undefined)一律 → 空数组, 不抛', () => {
    expect(parseSymbolsQuery(null)).toEqual([])
    expect(parseSymbolsQuery(undefined)).toEqual([])
    expect(parseSymbolsQuery(['000021.SZ', '600000.SH'])).toEqual([]) // 重复 query key → 数组, 不支持
    expect(parseSymbolsQuery(123)).toEqual([])
    expect(parseSymbolsQuery({})).toEqual([])
  })
})

describe('symbolsToQuery — 标的列表 → ?symbols= 值', () => {
  it('空列表 → 空串(调用方据此删除 query key)', () => {
    expect(symbolsToQuery([])).toBe('')
  })

  it('单个 / 多个逗号连接, 保序', () => {
    expect(symbolsToQuery(['000021.SZ'])).toBe('000021.SZ')
    expect(symbolsToQuery(['000021.SZ', '600000.SH'])).toBe('000021.SZ,600000.SH')
  })

  it('规范化: 大写/去重/丢非法(与 parse 同口径, 保证 query 始终规范)', () => {
    expect(symbolsToQuery(['000021.sz', 'foo', '000021.SZ', '600000.SH'])).toBe('000021.SZ,600000.SH')
  })
})

describe('往返幂等 — parse(toQuery(x)) 与 toQuery(parse(raw)) 稳定', () => {
  it('规范列表往返不变', () => {
    const list = ['000021.SZ', '600000.SH', '430047.BJ']
    expect(parseSymbolsQuery(symbolsToQuery(list))).toEqual(list)
  })

  it('脏输入一次规范后再往返稳定(防 URL↔状态同步死循环的地基)', () => {
    const raw = ' 000021.sz , foo , 000021.SZ ,600000.SH '
    const once = parseSymbolsQuery(raw)
    expect(once).toEqual(['000021.SZ', '600000.SH'])
    // 再序列化再解析应与 once 完全一致(不再变化 → 同步判等可收敛)
    expect(parseSymbolsQuery(symbolsToQuery(once))).toEqual(once)
    expect(symbolsToQuery(once)).toBe(symbolsToQuery(parseSymbolsQuery(raw)))
  })
})
