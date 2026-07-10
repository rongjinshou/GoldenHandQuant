/* 「最近查看」标的组合 — localStorage 读写纯函数（识别优于回忆; R3 升级: 逐标的 → 组合记忆）。
 *
 * 单一职责: 只做「最近成功加载过的标的组合」在 localStorage 里的持久化, 不碰路由/响应式 ——
 * Explorer.vue 在 loadAll 成功路径调 pushRecentSet 记入本轮组合（手动点"加载"、点最近组合
 * chip、?symbols= 深链恢复三条路径都汇到 loadAll, 天然一并记入）。
 *
 * 存储结构: RECENT_SETS_KEY 下存 string[][] —— 每个元素是一次加载的标的组合（单标的 =
 * 长度 1 组合）, 最新在前, 上限 RECENT_SETS_LIMIT 组; 组内经 parseSymbolsQuery 规范化
 * （大写/去重/保序/丢非法, 与 ?symbols= 深链同口径）, 规范化后为空的组合整条丢弃。
 *
 * 去重语义（顺序不敏感, 关键决策）: 组合的身份 = 标的集合, 与组内顺序无关 —— 用户心智里
 * "上次那组对比"指的是同一批标的, 顺序只影响赋色序数; 若顺序敏感, 同一组的不同排列会把
 * 6 个席位吃满。碰撞时新推入的条目胜出（保留它的组内顺序）并置于最前, 恢复时得到的是
 * "最近一次查看该组"的顺序与配色。
 *
 * 迁移兼容: 读路径发现旧 key LEGACY_RECENT_SYMBOLS_KEY（R1 逐标的 string[]）时, 把旧列表
 * 转成 N 个单标的组合, 排在新结构既有条目之后（新结构条目更新）, 合并去重截断后写入新 key
 * 并删除旧 key。写失败（隐私模式/配额满）时保留旧 key 待下次读取重试, 本次仍返回合并结果
 * 供会话 UI 用。
 *
 * 容错保证（绝不抛）:
 * - 新旧 key 任一 JSON 坏值 / 非数组 / 元素非数组 / 组内含非字符串或非法代码 → 过滤后返回,
 *   loadRecentSets 永远给合法 string[][];
 * - localStorage 读写失败 → 静默, pushRecentSet 仍返回合并结果供本会话 UI 用。 */

import { parseSymbolsQuery } from './deep-link'

export const RECENT_SETS_KEY = 'ghq-recent-symbol-sets'
/** R1 逐标的方案的旧 key（string[]）— 只在迁移与清空时触碰, 不再写入。 */
export const LEGACY_RECENT_SYMBOLS_KEY = 'ghq-recent-symbols'
export const RECENT_SETS_LIMIT = 6

/* unknown[] → 一个规范化组合: 只留 string、大写、组内去重保序、丢非法（复用 deep-link 口径） */
function normalizeSet(entry: readonly unknown[]): string[] {
  const strs = entry.filter((x): x is string => typeof x === 'string')
  return parseSymbolsQuery(strs.join(','))
}

/* 顺序不敏感的组合身份键: 排序后 join。同一标的集合的任意排列 → 同一键。 */
function setIdentity(set: readonly string[]): string {
  return [...set].sort().join(',')
}

/* unknown → 合法组合列表: 元素须为数组、组内规范化、空组丢弃、跨组按集合身份去重
 * （保留首次出现 = 最新一条）、截断上限。 */
function normalizeSets(entries: unknown): string[][] {
  if (!Array.isArray(entries)) return []
  const out: string[][] = []
  const seen = new Set<string>()
  for (const entry of entries) {
    if (!Array.isArray(entry)) continue
    const set = normalizeSet(entry)
    if (!set.length) continue
    const key = setIdentity(set)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(set)
    if (out.length >= RECENT_SETS_LIMIT) break
  }
  return out
}

/* 只读新 key（不触发迁移）; 任何坏值/读失败 → 空数组, 绝不抛。 */
function readStoredSets(): string[][] {
  try {
    const raw = localStorage.getItem(RECENT_SETS_KEY)
    if (!raw) return []
    return normalizeSets(JSON.parse(raw))
  } catch {
    return []
  }
}

/**
 * 旧 key（R1 逐标的 string[]）→ 新结构的一次性迁移。
 *
 * 旧 key 不存在 → 返回 null（未发生迁移）; 存在 → 旧列表逐标的转为长度 1 组合, 排在新结构
 * 既有条目之后合并（新结构条目更新）, 写入新 key 后删除旧 key, 返回合并结果。旧值坏 JSON /
 * 非数组 → 迁移不出条目但旧 key 照删（垃圾无保留价值）; 写失败 → 保留旧 key 待下次重试,
 * 仍返回合并结果供本会话用。
 */
export function migrateLegacyRecent(): string[][] | null {
  let rawLegacy: string | null
  try {
    rawLegacy = localStorage.getItem(LEGACY_RECENT_SYMBOLS_KEY)
  } catch {
    return null
  }
  if (rawLegacy === null) return null
  let singles: string[][] = []
  try {
    const parsed: unknown = JSON.parse(rawLegacy)
    if (Array.isArray(parsed)) singles = normalizeSet(parsed).map((sym) => [sym])
  } catch {
    /* 旧值坏 JSON → 迁移不出任何组合, 下方仍删旧 key */
  }
  const merged = normalizeSets([...readStoredSets(), ...singles])
  try {
    if (merged.length) localStorage.setItem(RECENT_SETS_KEY, JSON.stringify(merged))
    localStorage.removeItem(LEGACY_RECENT_SYMBOLS_KEY)
  } catch {
    /* 写失败（隐私模式/配额满）静默: 旧 key 保留, 下次读取重试迁移 */
  }
  return merged
}

/** 读「最近查看」组合列表（最新在前）, 顺带完成旧 key 迁移; 坏值/读失败 → 空数组, 绝不抛。 */
export function loadRecentSets(): string[][] {
  return migrateLegacyRecent() ?? readStoredSets()
}

/**
 * 把本轮加载的组合（组内保序）记到最前: 按集合身份去重（同集合的旧条目被移除, 新条目
 * 连同它的顺序置前）、截断上限, 落盘并返回新列表。组合规范化后为空 → 不记不写, 返回现状。
 */
export function pushRecentSet(syms: readonly string[]): string[][] {
  const set = normalizeSet(syms)
  const prev = loadRecentSets() // 先走读路径: 旧 key 若还在, 迁移合并后再置前, 不丢历史
  if (!set.length) return prev
  const next = normalizeSets([set, ...prev])
  try {
    localStorage.setItem(RECENT_SETS_KEY, JSON.stringify(next))
  } catch {
    /* 写失败（隐私模式/配额满）静默 —— 本次会话内仍返回合并结果供 UI 展示 */
  }
  return next
}

/** 清空「最近查看」记录（新旧 key 一并删, 防旧 key 迁移复活）; 失败静默。 */
export function clearRecentSets(): void {
  try {
    localStorage.removeItem(RECENT_SETS_KEY)
    localStorage.removeItem(LEGACY_RECENT_SYMBOLS_KEY)
  } catch {
    /* 静默 */
  }
}

/**
 * 组合 chip 文案: 单标的组合显代码本身; 多标的组合截断为「首标的 +N」（如 `000021.SZ +2`）,
 * 完整列表由调用方放 title/aria-label。空组（防御, 规范化列表不会出现）→ 空串。
 */
export function formatSetLabel(set: readonly string[]): string {
  if (set.length <= 1) return set[0] ?? ''
  return `${set[0]} +${set.length - 1}`
}
