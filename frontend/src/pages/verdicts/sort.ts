/* 判决因子排序/过滤(设计 0705-verdict-cards §5) — 纯函数, 供卡片网格工具条使用。 */

import type { VerdictFactor } from '@/api/types'

export type SortKey = 'verdict' | 'score' | 'ic' | 'oos_realize' | 'submitted'

export const SORT_OPTIONS: { label: string; value: SortKey }[] = [
  { label: '判决 + 评分', value: 'verdict' },
  { label: '评分', value: 'score' },
  { label: 'IC 均值', value: 'ic' },
  { label: '样本外变现', value: 'oos_realize' },
  { label: '提交顺序', value: 'submitted' },
]

export type FilterKey = 'all' | 'pass' | 'fail'

function nn(v: number | null | undefined): number {
  return v === null || v === undefined ? Number.NEGATIVE_INFINITY : v
}

function oosRealizeValue(f: VerdictFactor, longOnly: boolean): number {
  return longOnly ? nn(f.oos_top_excess_return) : nn(f.oos_long_short_return)
}

export function sortFactors(
  factors: VerdictFactor[],
  key: SortKey,
  longOnly: boolean,
): VerdictFactor[] {
  const arr = [...factors]
  switch (key) {
    case 'verdict':
      return arr.sort((a, b) => Number(b.passed) - Number(a.passed) || nn(b.score) - nn(a.score))
    case 'score':
      return arr.sort((a, b) => nn(b.score) - nn(a.score))
    case 'ic':
      return arr.sort((a, b) => nn(b.ic_mean) - nn(a.ic_mean))
    case 'oos_realize':
      return arr.sort((a, b) => oosRealizeValue(b, longOnly) - oosRealizeValue(a, longOnly))
    case 'submitted':
      return arr
    default:
      return arr
  }
}

export function filterFactors(factors: VerdictFactor[], filter: FilterKey): VerdictFactor[] {
  if (filter === 'pass') return factors.filter((f) => f.passed)
  if (filter === 'fail') return factors.filter((f) => !f.passed)
  return factors
}
