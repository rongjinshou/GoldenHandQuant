import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { FILTER_KEYS, SORT_OPTIONS } from '../sort'
import {
  DEFAULT_VERDICTS_VIEW,
  VERDICTS_VIEW_KEY,
  loadVerdictsView,
  saveVerdictsView,
} from '../view-state'

/* 视图会话记忆纯逻辑 — 默认回退/往返恢复/坏值容错(整体 + 字段级)/storage 故障不抛。
 * jsdom 自带 sessionStorage, 每例清空隔离; 挂载侧接线(setup 恢复 + 变更即写)见
 * Verdicts.view-memory.spec.ts。 */

beforeEach(() => {
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('loadVerdictsView', () => {
  it('无记录 → 默认视角(all + verdict 放榜序)', () => {
    expect(loadVerdictsView()).toEqual({ filter: 'all', sort: 'verdict' })
  })

  it('默认值本身合法: filter 在 FILTER_KEYS、sort 在 SORT_OPTIONS 内(防未来枚举漂移)', () => {
    expect(FILTER_KEYS).toContain(DEFAULT_VERDICTS_VIEW.filter)
    expect(SORT_OPTIONS.map((o) => o.value)).toContain(DEFAULT_VERDICTS_VIEW.sort)
  })

  it('save→load 往返: 每个合法 filter × sort 组合均按原样恢复', () => {
    for (const filter of FILTER_KEYS) {
      for (const { value: sort } of SORT_OPTIONS) {
        saveVerdictsView({ filter, sort })
        expect(loadVerdictsView()).toEqual({ filter, sort })
      }
    }
  })

  it.each(['{oops', '"fail"', '42', 'null', 'true'])(
    '坏 JSON/非对象 %s → 整体回默认',
    (raw) => {
      sessionStorage.setItem(VERDICTS_VIEW_KEY, raw)
      expect(loadVerdictsView()).toEqual(DEFAULT_VERDICTS_VIEW)
    },
  )

  it('数组虽是 object 但无同名字段 → 回默认(不抛)', () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, '[{"filter":"pass"}]')
    expect(loadVerdictsView()).toEqual(DEFAULT_VERDICTS_VIEW)
  })

  it('非法 filter 枚举 → 仅 filter 回默认, 合法 sort 保留(字段级容错)', () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 'nope', sort: 'ic' }))
    expect(loadVerdictsView()).toEqual({ filter: 'all', sort: 'ic' })
  })

  it('非法 sort 枚举 → 仅 sort 回默认, 合法 filter 保留', () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 'fail', sort: 'nope' }))
    expect(loadVerdictsView()).toEqual({ filter: 'fail', sort: 'verdict' })
  })

  it('大小写不符(UI 文案 "PASS" ≠ 枚举 "pass") → 该字段回默认', () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 'PASS', sort: 'ic' }))
    expect(loadVerdictsView()).toEqual({ filter: 'all', sort: 'ic' })
  })

  it('字段缺失 → 缺的回默认, 在的保留', () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 'pass' }))
    expect(loadVerdictsView()).toEqual({ filter: 'pass', sort: 'verdict' })
  })

  it('字段非字符串(数字/数组) → 全回默认', () => {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify({ filter: 3, sort: ['ic'] }))
    expect(loadVerdictsView()).toEqual(DEFAULT_VERDICTS_VIEW)
  })

  it('读失败(隐私模式等) → 默认, 绝不抛', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(loadVerdictsView()).toEqual(DEFAULT_VERDICTS_VIEW)
  })

  it('每次返回新对象 — 调用方原地改动不污染默认常量与后续读取', () => {
    const a = loadVerdictsView()
    a.filter = 'fail'
    expect(loadVerdictsView().filter).toBe('all')
    expect(DEFAULT_VERDICTS_VIEW.filter).toBe('all')
  })
})

describe('saveVerdictsView', () => {
  it('写入约定 key 下的 JSON 整对象', () => {
    saveVerdictsView({ filter: 'pass', sort: 'score' })
    expect(JSON.parse(sessionStorage.getItem(VERDICTS_VIEW_KEY)!)).toEqual({
      filter: 'pass',
      sort: 'score',
    })
  })

  it('写失败(配额满等)静默不抛', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => saveVerdictsView({ filter: 'fail', sort: 'ic' })).not.toThrow()
  })
})
