/* 判决轮重载后的选中决策(设计 §9 交互「reload 保留选中」)。
 *
 * 旧口径: loadVerdicts 无条件 selectedIdx=0 → 表单完成/删除后一律跳最新轮,
 * 正在看的那轮被静默切走(且弹框强关)。新口径:
 *   - 原选中轮仍在 → 保留(定位到它在新列表里的下标), 不强切;
 *   - 原选中轮已不在(被删 / 被整体替换) → 回落到最新(0);
 *   - 无原选中(首次加载 / 空列表) → 最新(0)。
 * 附带: 若"最新轮"是此前列表里没有的新轮, 且我们停在了非最新轮上(keepIdx>0),
 * 返回其 run_id 供页面挂一条非侵入提示条(而非强切过去)。 */

export interface RunRef {
  run_id: string
}

export interface ReloadSelection {
  /** 重载后应选中的下标。 */
  selectedIdx: number
  /** 有新轮到达且未强切时其 run_id(供提示条); 否则 null。 */
  newRunId: string | null
}

export function resolveReloadSelection(
  prevRunId: string | null,
  prevRunIds: readonly string[],
  newRuns: readonly RunRef[],
): ReloadSelection {
  if (newRuns.length === 0) return { selectedIdx: 0, newRunId: null }

  const keepIdx = prevRunId ? newRuns.findIndex((r) => r.run_id === prevRunId) : -1
  const selectedIdx = keepIdx >= 0 ? keepIdx : 0

  // 提示条仅当: 保留在了非最新轮(keepIdx>0) 且 最新轮是旧列表没有的新轮。
  const prev = new Set(prevRunIds)
  const newest = newRuns[0]
  const newRunId = keepIdx > 0 && newest && !prev.has(newest.run_id) ? newest.run_id : null

  return { selectedIdx, newRunId }
}
