/* 「最近查看」标的 — localStorage 读写纯函数（识别优于回忆，易用性迭代任务 1）。
 *
 * 单一职责: 只做「最近成功加载过的标的」在 localStorage 里的持久化（逐标的方案:
 * 去重、最新在前、上限 RECENT_SYMBOLS_LIMIT 个），不碰路由/响应式 —— Explorer.vue
 * 在 loadAll 成功路径调 pushRecent 记入（手动点"加载"、点最近 chip、?symbols= 深链
 * 恢复三条路径都汇到 loadAll，天然一并记入）。
 *
 * 容错保证（绝不抛）:
 * - 存量 JSON 坏值 / 非数组 / 含非字符串或非法代码 → 过滤后返回，loadRecent 永远给合法数组;
 * - localStorage 读写失败（隐私模式/配额满）→ 静默，pushRecent 仍返回合并结果供本会话 UI 用;
 * - 规范化（大写/去重/保序/丢非法）复用 deep-link.parseSymbolsQuery，与 ?symbols= 同口径。 */

import { parseSymbolsQuery } from './deep-link'

export const RECENT_SYMBOLS_KEY = 'ghq-recent-symbols'
export const RECENT_SYMBOLS_LIMIT = 8

/* unknown[] → 合法标的列表: 只留 string、大写、去重保序、丢非法、截断上限 */
function normalize(entries: readonly unknown[]): string[] {
  const strs = entries.filter((x): x is string => typeof x === 'string')
  return parseSymbolsQuery(strs.join(',')).slice(0, RECENT_SYMBOLS_LIMIT)
}

/** 读「最近查看」标的列表（最新在前）; 任何坏值/读失败 → 空数组，绝不抛。 */
export function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_SYMBOLS_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? normalize(parsed) : []
  } catch {
    return []
  }
}

/**
 * 把一个标的或一批标的（本轮加载的组合，批内保序）记到最前:
 * 去重（旧位置的同名项被提前）、截断上限，落盘并返回新列表。
 */
export function pushRecent(syms: string | readonly string[]): string[] {
  const batch = typeof syms === 'string' ? [syms] : syms
  const next = normalize([...batch, ...loadRecent()])
  try {
    localStorage.setItem(RECENT_SYMBOLS_KEY, JSON.stringify(next))
  } catch {
    /* 写失败（隐私模式/配额满）静默 —— 本次会话内仍返回合并结果供 UI 展示 */
  }
  return next
}

/** 清空「最近查看」记录; 失败静默。 */
export function clearRecent(): void {
  try {
    localStorage.removeItem(RECENT_SYMBOLS_KEY)
  } catch {
    /* 静默 */
  }
}
