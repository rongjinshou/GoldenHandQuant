/* 判决轮 URL 深链纯逻辑(设计 0710 批三 P7) — 选中判决轮 ↔ `?run=` query。
 *
 * 纯函数便于单测; Verdicts.vue 只做 route/router 接线(挂载读 query 恢复、watch query
 * 支持前进后退、幂等 replace 写回)。所有"是否写/写什么/恢复到哪"的判定都在此收敛,
 * 组件侧不再散落条件, 也便于与批二「reload 保留选中 + 新轮提示条」协调不打架。 */

export interface RunRef {
  run_id: string
}

/** route.query.run 归一化: 数组(重复 query)取首个, 去空白; 空串/非字符串 → null。 */
export function normalizeRunParam(raw: unknown): string | null {
  const v = Array.isArray(raw) ? raw[0] : raw
  if (typeof v !== 'string') return null
  const s = v.trim()
  return s === '' ? null : s
}

/**
 * 深链恢复: `?run=` 命中的轮返回其下标; 无参 / 未命中 / 空列表 → -1
 * (调用方保持既有选中, 不强跳)。
 */
export function selectionFromRunParam(raw: unknown, runs: readonly RunRef[]): number {
  const id = normalizeRunParam(raw)
  if (id === null) return -1
  return runs.findIndex((r) => r.run_id === id)
}

/**
 * 幂等写回判定: 期望的 run 值与当前 query 值(归一化后)一致 → 返回 false(无需写)。
 * 这是断"恢复→写回→再恢复"死循环的关键闸: query 已经是目标值就绝不再 replace。
 */
export function runQueryNeedsUpdate(currentRaw: unknown, desired: string | null): boolean {
  return normalizeRunParam(currentRaw) !== desired
}
