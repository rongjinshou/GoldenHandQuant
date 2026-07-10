import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearRecentSets,
  formatSetLabel,
  LEGACY_RECENT_SYMBOLS_KEY,
  loadRecentSets,
  migrateLegacyRecent,
  pushRecentSet,
  RECENT_SETS_KEY,
  RECENT_SETS_LIMIT,
} from '../recent-symbols'

/* 「最近查看」组合记忆 localStorage 纯逻辑 — 组合去重(顺序不敏感)/最新在前/上限截断 +
 * 旧 key(R1 逐标的)迁移 + 坏值容错(绝不抛) + label 截断格式化。
 * jsdom 自带 localStorage, 每例清空隔离; 挂载侧接线(loadAll 成功记入/模板锚点)由
 * explorer-aria.spec.ts 读文件契约守, 这里只测纯函数。 */

beforeEach(() => {
  localStorage.clear()
})

function seedSets(sets: unknown): void {
  localStorage.setItem(RECENT_SETS_KEY, JSON.stringify(sets))
}

function storedSets(): unknown {
  const raw = localStorage.getItem(RECENT_SETS_KEY)
  return raw === null ? null : JSON.parse(raw)
}

describe('loadRecentSets — 读取与容错', () => {
  it('无记录 → 空数组', () => {
    expect(loadRecentSets()).toEqual([])
  })

  it('正常组合列表按存储顺序返回(最新在前由 pushRecentSet 落盘时保证)', () => {
    seedSets([['600000.SH', '000001.SZ'], ['430047.BJ']])
    expect(loadRecentSets()).toEqual([['600000.SH', '000001.SZ'], ['430047.BJ']])
  })

  it('JSON 坏值 → 空数组, 不抛', () => {
    localStorage.setItem(RECENT_SETS_KEY, '{oops')
    expect(loadRecentSets()).toEqual([])
  })

  it('合法 JSON 但非数组(对象/字符串/数字/null/布尔) → 空数组', () => {
    for (const bad of ['{"a":1}', '"600000.SH"', '42', 'null', 'true']) {
      localStorage.setItem(RECENT_SETS_KEY, bad)
      expect(loadRecentSets()).toEqual([])
    }
  })

  it('元素非数组(裸字符串/数字/null/对象) → 丢弃该元素, 其余保留', () => {
    seedSets([['600000.SH'], '000001.SZ', 42, null, { a: 1 }, ['430047.BJ']])
    expect(loadRecentSets()).toEqual([['600000.SH'], ['430047.BJ']])
  })

  it('组内含非字符串/非法代码/重复/小写 → 组内规范化(与 ?symbols= 深链同口径)', () => {
    seedSets([['600000.sh', 42, null, 'foo', '600000.SH', '000001.SZ']])
    expect(loadRecentSets()).toEqual([['600000.SH', '000001.SZ']])
  })

  it('规范化后为空的组合(全非法/空数组) → 整条丢弃', () => {
    seedSets([[], ['foo', 'bar'], ['600000.SH']])
    expect(loadRecentSets()).toEqual([['600000.SH']])
  })

  it('跨组去重顺序不敏感: 同一标的集合的不同排列视为同一组, 保留最前(最新)一条', () => {
    seedSets([
      ['600000.SH', '000001.SZ'],
      ['000001.SZ', '600000.SH'],
      ['600000.SH'],
    ])
    expect(loadRecentSets()).toEqual([['600000.SH', '000001.SZ'], ['600000.SH']])
  })

  it('存量超上限 → 截断到 RECENT_SETS_LIMIT 组', () => {
    const many = Array.from({ length: RECENT_SETS_LIMIT + 3 }, (_, i) => [`${600000 + i}.SH`])
    seedSets(many)
    expect(loadRecentSets()).toEqual(many.slice(0, RECENT_SETS_LIMIT))
  })
})

describe('migrateLegacyRecent — 旧 key(R1 逐标的)迁移', () => {
  it('无旧 key → 返回 null, 不动新 key', () => {
    seedSets([['600000.SH']])
    expect(migrateLegacyRecent()).toBeNull()
    expect(storedSets()).toEqual([['600000.SH']])
  })

  it('纯旧用户: 旧列表转 N 个单标的组合(保序), 写入新 key 并删除旧 key', () => {
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(['600000.SH', '000001.SZ']))
    expect(loadRecentSets()).toEqual([['600000.SH'], ['000001.SZ']])
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
    expect(storedSets()).toEqual([['600000.SH'], ['000001.SZ']])
  })

  it('新旧并存: 新结构条目在前(更新), 旧单标的在后; 与既有组合同集合的旧单标的被去重', () => {
    seedSets([['600000.SH', '000001.SZ'], ['430047.BJ']])
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(['430047.BJ', '600519.SH']))
    expect(loadRecentSets()).toEqual([
      ['600000.SH', '000001.SZ'],
      ['430047.BJ'], // 新结构里的单标的组合胜出, 旧 key 里的同集合条目被去重
      ['600519.SH'],
    ])
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
  })

  it('旧 key 坏 JSON / 非数组 → 迁移不出条目(容错返回空), 旧 key 照删', () => {
    for (const bad of ['{oops', '"600000.SH"', '{"a":1}']) {
      localStorage.clear()
      localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, bad)
      expect(loadRecentSets()).toEqual([])
      expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
      expect(storedSets()).toBeNull() // 空结果不写新 key
    }
  })

  it('旧列表含非法/小写/重复 → 规范化后再转组合', () => {
    localStorage.setItem(
      LEGACY_RECENT_SYMBOLS_KEY,
      JSON.stringify(['600000.sh', 'foo', 42, '600000.SH', '000001.SZ']),
    )
    expect(loadRecentSets()).toEqual([['600000.SH'], ['000001.SZ']])
  })

  it('旧列表超长(R1 上限 8 > 新上限 6) → 合并后截断到 RECENT_SETS_LIMIT', () => {
    const legacy = Array.from({ length: 8 }, (_, i) => `${600000 + i}.SH`)
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(legacy))
    const out = loadRecentSets()
    expect(out).toHaveLength(RECENT_SETS_LIMIT)
    expect(out).toEqual(legacy.slice(0, RECENT_SETS_LIMIT).map((s) => [s]))
  })

  it('迁移只发生一次: 第二次读取时旧 key 已不在, 结果稳定', () => {
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(['600000.SH']))
    const first = loadRecentSets()
    expect(loadRecentSets()).toEqual(first)
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
  })

  it('写失败(隐私模式/配额满): 本次仍返回合并结果, 旧 key 保留待下次重试', () => {
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(['600000.SH']))
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      expect(loadRecentSets()).toEqual([['600000.SH']]) // 会话内可见
    } finally {
      spy.mockRestore()
    }
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).not.toBeNull() // 未删, 可重试
    expect(loadRecentSets()).toEqual([['600000.SH']]) // 恢复后重试迁移成功
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
  })
})

describe('pushRecentSet — 入列语义(组合去重、最新在前、上限)', () => {
  it('单标的组合入列并落盘, 返回新列表', () => {
    expect(pushRecentSet(['600000.SH'])).toEqual([['600000.SH']])
    expect(storedSets()).toEqual([['600000.SH']])
  })

  it('最新在前: 后推的组合排前面', () => {
    pushRecentSet(['600000.SH'])
    expect(pushRecentSet(['000001.SZ', '600000.SH'])).toEqual([
      ['000001.SZ', '600000.SH'],
      ['600000.SH'],
    ])
  })

  it('组内保序: 推入顺序即存储顺序(恢复时配色序数一致)', () => {
    expect(pushRecentSet(['000001.SZ', '600000.SH'])).toEqual([['000001.SZ', '600000.SH']])
  })

  it('同集合不同顺序 → 视为同一组: 旧条目被移除, 新条目连同新顺序置前', () => {
    pushRecentSet(['600000.SH', '000001.SZ'])
    pushRecentSet(['430047.BJ'])
    expect(pushRecentSet(['000001.SZ', '600000.SH'])).toEqual([
      ['000001.SZ', '600000.SH'],
      ['430047.BJ'],
    ])
  })

  it('子集/超集不去重: 单标的组合与含它的多标的组合是两条记录', () => {
    pushRecentSet(['600000.SH'])
    expect(pushRecentSet(['600000.SH', '000001.SZ'])).toEqual([
      ['600000.SH', '000001.SZ'],
      ['600000.SH'],
    ])
  })

  it('超上限挤出最旧一组, 长度封顶 RECENT_SETS_LIMIT', () => {
    for (let i = 0; i < RECENT_SETS_LIMIT; i++) pushRecentSet([`${600000 + i}.SH`])
    const out = pushRecentSet(['000001.SZ'])
    expect(out).toHaveLength(RECENT_SETS_LIMIT)
    expect(out[0]).toEqual(['000001.SZ'])
    expect(out).not.toContainEqual(['600000.SH']) // 最早入列的被挤出
  })

  it('组内规范化: 大小写归一 + 非法丢弃(与 deep-link 同口径)', () => {
    expect(pushRecentSet(['600000.sh', 'foo', '000001.SZ'])).toEqual([['600000.SH', '000001.SZ']])
  })

  it('全非法组合 → 不记不写, 返回现状', () => {
    pushRecentSet(['600000.SH'])
    expect(pushRecentSet(['foo', 'bar'])).toEqual([['600000.SH']])
    expect(storedSets()).toEqual([['600000.SH']])
  })

  it('存量是坏 JSON 时 push 从空开始, 不抛', () => {
    localStorage.setItem(RECENT_SETS_KEY, '{oops')
    expect(pushRecentSet(['600000.SH'])).toEqual([['600000.SH']])
  })

  it('旧 key 尚存时 push 先迁移合并再置前, 不丢 R1 历史', () => {
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(['430047.BJ']))
    expect(pushRecentSet(['600000.SH', '000001.SZ'])).toEqual([
      ['600000.SH', '000001.SZ'],
      ['430047.BJ'],
    ])
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
  })

  it('写失败(隐私模式/配额满)静默不抛, 仍返回合并结果; 存量保持原值', () => {
    pushRecentSet(['600000.SH'])
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })
    try {
      expect(pushRecentSet(['000001.SZ'])).toEqual([['000001.SZ'], ['600000.SH']])
    } finally {
      spy.mockRestore()
    }
    expect(loadRecentSets()).toEqual([['600000.SH']])
  })
})

describe('clearRecentSets', () => {
  it('清空后新旧 key 都移除(防旧 key 迁移复活), loadRecentSets → 空数组', () => {
    localStorage.setItem(LEGACY_RECENT_SYMBOLS_KEY, JSON.stringify(['430047.BJ']))
    pushRecentSet(['600000.SH'])
    clearRecentSets()
    expect(localStorage.getItem(RECENT_SETS_KEY)).toBeNull()
    expect(localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)).toBeNull()
    expect(loadRecentSets()).toEqual([])
  })
})

describe('formatSetLabel — 组合 chip 文案截断', () => {
  it('单标的组合 → 代码本身', () => {
    expect(formatSetLabel(['000021.SZ'])).toBe('000021.SZ')
  })

  it('多标的组合 → 首标的 +N(N=其余标的数)', () => {
    expect(formatSetLabel(['000021.SZ', '600000.SH'])).toBe('000021.SZ +1')
    expect(formatSetLabel(['000021.SZ', '600000.SH', '430047.BJ'])).toBe('000021.SZ +2')
  })

  it('空组(防御) → 空串', () => {
    expect(formatSetLabel([])).toBe('')
  })
})
