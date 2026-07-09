import { describe, expect, it } from 'vitest'

import { normalizeRunParam, runQueryNeedsUpdate, selectionFromRunParam } from '../run-deeplink'

const runs = (...ids: string[]) => ids.map((run_id) => ({ run_id }))

describe('normalizeRunParam', () => {
  it('字符串去空白后返回, 空/纯空白→null', () => {
    expect(normalizeRunParam('MFCOMBO-1')).toBe('MFCOMBO-1')
    expect(normalizeRunParam('  MFCOMBO-1  ')).toBe('MFCOMBO-1')
    expect(normalizeRunParam('')).toBeNull()
    expect(normalizeRunParam('   ')).toBeNull()
  })

  it('数组(重复 query)取首个非空', () => {
    expect(normalizeRunParam(['A', 'B'])).toBe('A')
    expect(normalizeRunParam([''])).toBeNull()
  })

  it('非字符串(undefined/null/number)→null', () => {
    expect(normalizeRunParam(undefined)).toBeNull()
    expect(normalizeRunParam(null)).toBeNull()
    expect(normalizeRunParam(42)).toBeNull()
  })
})

describe('selectionFromRunParam', () => {
  it('?run= 命中某轮 → 其下标', () => {
    expect(selectionFromRunParam('B', runs('A', 'B', 'C'))).toBe(1)
    expect(selectionFromRunParam('A', runs('A', 'B', 'C'))).toBe(0)
  })

  it('数组形式命中', () => {
    expect(selectionFromRunParam(['C'], runs('A', 'B', 'C'))).toBe(2)
  })

  it('无 ?run= / 空 → -1(保持既有选中)', () => {
    expect(selectionFromRunParam(undefined, runs('A', 'B'))).toBe(-1)
    expect(selectionFromRunParam('', runs('A', 'B'))).toBe(-1)
  })

  it('?run= 指向不存在的轮 → -1(不跳转)', () => {
    expect(selectionFromRunParam('GONE', runs('A', 'B'))).toBe(-1)
  })

  it('空列表 → -1', () => {
    expect(selectionFromRunParam('A', [])).toBe(-1)
  })
})

describe('runQueryNeedsUpdate', () => {
  it('当前 query 与期望一致(归一化后) → 无需写(断死循环)', () => {
    expect(runQueryNeedsUpdate('B', 'B')).toBe(false)
    expect(runQueryNeedsUpdate(['B'], 'B')).toBe(false)
    expect(runQueryNeedsUpdate('  B  ', 'B')).toBe(false)
  })

  it('当前 query 与期望不同 → 需写', () => {
    expect(runQueryNeedsUpdate('A', 'B')).toBe(true)
    expect(runQueryNeedsUpdate(undefined, 'B')).toBe(true)
  })

  it('期望为 null 且当前无 query → 无需写', () => {
    expect(runQueryNeedsUpdate(undefined, null)).toBe(false)
    expect(runQueryNeedsUpdate('', null)).toBe(false)
  })

  it('期望为 null 但当前有 query → 需写(清除)', () => {
    expect(runQueryNeedsUpdate('B', null)).toBe(true)
  })
})
