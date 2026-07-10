/* 因子勾选集合运算(判决区·因子多选快捷组) — FactorTestForm「P 标签整组切换」与
 * 「上轮同款」共用的纯函数。两条不变量:
 *   - 禁用因子(field_ready=false)永不被勾上: 补全组时跳过, 套用上轮时跳过并计数;
 *   - 不就地修改输入集合(返回新 Set, 适配组件里 checked ref 整体替换的响应式写法)。 */

/** 组切换: 组内可用因子已全部勾选 → 整组清空; 否则补全该组(只补可用项)。
 * 全禁用组视为"无可全选也无可清空", 原样返回副本; 组外勾选永不受影响。 */
export function toggleGroup(
  current: ReadonlySet<string>,
  group: readonly string[],
  disabled: ReadonlySet<string>,
): Set<string> {
  const next = new Set(current)
  const enabled = group.filter((id) => !disabled.has(id))
  const full = enabled.length > 0 && enabled.every((id) => next.has(id))
  if (full) {
    // 清空时连组内异常残留的禁用 id 一起移除(自愈), 只动本组
    for (const id of group) next.delete(id)
  } else {
    for (const id of enabled) next.add(id)
  }
  return next
}

export interface ApplyLastRunResult {
  /** 应用后的勾选集(整体替换语义); 上轮无任何可用因子时 = current 副本(非破坏)。 */
  next: Set<string>
  /** 上轮集合中因未知(已下架/不在本期因子表)或禁用而跳过的个数(去重后计)。 */
  skipped: number
  /** 实际勾上的个数; 0 表示勾选未改动(供 UI 区分提示文案)。 */
  applied: number
}

/** 上轮同款: 把勾选集置为上轮判决的因子集合; 未知/禁用因子跳过并计数。
 * 上轮因子全部不可用时保持 current 不动 — 换来一个空表单没有任何价值。 */
export function applyLastRun(
  current: ReadonlySet<string>,
  lastRunIds: readonly string[],
  available: ReadonlySet<string>,
  disabled: ReadonlySet<string>,
): ApplyLastRunResult {
  const unique = [...new Set(lastRunIds)]
  const usable = unique.filter((id) => available.has(id) && !disabled.has(id))
  const skipped = unique.length - usable.length
  if (usable.length === 0) return { next: new Set(current), skipped, applied: 0 }
  return { next: new Set(usable), skipped, applied: usable.length }
}
