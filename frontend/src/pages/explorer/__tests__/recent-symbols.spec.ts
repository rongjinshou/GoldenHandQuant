import { beforeEach, describe, expect, it, vi } from 'vitest'

import { clearRecent, loadRecent, pushRecent, RECENT_SYMBOLS_KEY, RECENT_SYMBOLS_LIMIT } from '../recent-symbols'

/* 「最近查看」localStorage 纯逻辑 — 去重/最新在前/上限截断 + 坏值容错(绝不抛)。
 * jsdom 自带 localStorage, 每例清空隔离; 挂载侧接线(loadAll 成功记入/模板锚点)由
 * explorer-aria.spec.ts 读文件契约守, 这里只测纯函数。 */

beforeEach(() => {
  localStorage.clear()
})

describe('loadRecent — 读取与容错', () => {
  it('无记录 → 空数组', () => {
    expect(loadRecent()).toEqual([])
  })

  it('正常记录按存储顺序返回(最新在前的顺序由 pushRecent 落盘时保证)', () => {
    localStorage.setItem(RECENT_SYMBOLS_KEY, JSON.stringify(['600000.SH', '000001.SZ']))
    expect(loadRecent()).toEqual(['600000.SH', '000001.SZ'])
  })

  it('JSON 坏值 → 空数组, 不抛', () => {
    localStorage.setItem(RECENT_SYMBOLS_KEY, '{oops')
    expect(loadRecent()).toEqual([])
  })

  it('合法 JSON 但非数组(对象/字符串/数字/null/布尔) → 空数组', () => {
    for (const bad of ['{"a":1}', '"600000.SH"', '42', 'null', 'true']) {
      localStorage.setItem(RECENT_SYMBOLS_KEY, bad)
      expect(loadRecent()).toEqual([])
    }
  })

  it('数组含非字符串/非法代码/重复/小写 → 过滤规范化(与 ?symbols= 深链同口径)', () => {
    localStorage.setItem(
      RECENT_SYMBOLS_KEY,
      JSON.stringify(['600000.sh', 42, null, 'foo', '600000.SH', '000001.SZ']),
    )
    expect(loadRecent()).toEqual(['600000.SH', '000001.SZ'])
  })

  it('存量超上限 → 截断到 RECENT_SYMBOLS_LIMIT', () => {
    const many = Array.from({ length: RECENT_SYMBOLS_LIMIT + 4 }, (_, i) => `${600000 + i}.SH`)
    localStorage.setItem(RECENT_SYMBOLS_KEY, JSON.stringify(many))
    expect(loadRecent()).toEqual(many.slice(0, RECENT_SYMBOLS_LIMIT))
  })
})

describe('pushRecent — 入列语义(去重、最新在前、上限)', () => {
  it('单个标的入列并落盘, 返回新列表', () => {
    expect(pushRecent('600000.SH')).toEqual(['600000.SH'])
    expect(JSON.parse(localStorage.getItem(RECENT_SYMBOLS_KEY)!)).toEqual(['600000.SH'])
  })

  it('最新在前: 后推的排前面', () => {
    pushRecent('600000.SH')
    expect(pushRecent('000001.SZ')).toEqual(['000001.SZ', '600000.SH'])
  })

  it('重复推同一标的 → 去重并提到最前', () => {
    pushRecent(['600000.SH', '000001.SZ'])
    expect(pushRecent('000001.SZ')).toEqual(['000001.SZ', '600000.SH'])
  })

  it('一批组合(数组)整批置前且批内保序 — 对应一次多标的加载', () => {
    pushRecent('430047.BJ')
    expect(pushRecent(['600000.SH', '000001.SZ'])).toEqual(['600000.SH', '000001.SZ', '430047.BJ'])
  })

  it('超上限挤出最旧的, 长度封顶 RECENT_SYMBOLS_LIMIT', () => {
    for (let i = 0; i < RECENT_SYMBOLS_LIMIT; i++) pushRecent(`${600000 + i}.SH`)
    const out = pushRecent('000001.SZ')
    expect(out).toHaveLength(RECENT_SYMBOLS_LIMIT)
    expect(out[0]).toBe('000001.SZ')
    expect(out).not.toContain('600000.SH') // 最早入列的被挤出
  })

  it('大小写归一 + 非法代码丢弃(与 deep-link 同口径)', () => {
    expect(pushRecent(['600000.sh', 'foo'])).toEqual(['600000.SH'])
  })

  it('存量是坏 JSON 时 push 从空开始, 不抛', () => {
    localStorage.setItem(RECENT_SYMBOLS_KEY, '{oops')
    expect(pushRecent('600000.SH')).toEqual(['600000.SH'])
  })

  it('写失败(隐私模式/配额满)静默不抛, 仍返回合并结果; 存量保持原值', () => {
    pushRecent('600000.SH')
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      expect(pushRecent('000001.SZ')).toEqual(['000001.SZ', '600000.SH'])
    } finally {
      spy.mockRestore()
    }
    expect(loadRecent()).toEqual(['600000.SH'])
  })
})

describe('clearRecent', () => {
  it('清空后 key 移除, loadRecent → 空数组', () => {
    pushRecent('600000.SH')
    clearRecent()
    expect(localStorage.getItem(RECENT_SYMBOLS_KEY)).toBeNull()
    expect(loadRecent()).toEqual([])
  })
})
