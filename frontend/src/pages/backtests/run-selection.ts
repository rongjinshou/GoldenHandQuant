/* 回测轮选中 ↔ URL ?run= 深链的纯决策(设计 docs/feat/0710 §12 P7) — 抽成纯函数便于单测,
 * Backtests.vue 只做 useRoute/useRouter 接线。研究结果可深链/收藏/贴复盘笔记。
 *
 * 防死循环(关键): 选中→写 URL 与 URL→选中 是两向 watch, 必须靠"值相同不动"幂等互相刹车 ——
 *   selectionFromQuery 遇 (?run= === 当前选中) 返回 null(不改选中);
 *   shouldSyncRunToUrl 遇 (URL 已是选中值) 返回 false(不 replace);
 * 任一次往返到"两边一致"即静止, 不会 选中→replace→回读→再改选中 无限循环。 */

export interface RunLike {
  run_id: string
}

/** 载入/重载后该选哪一轮(优先级由高到低):
 *  1. 原选中仍在列表 → 保留(删他轮/新回测完成后台刷新时, 不弹走用户正看的详情)
 *  2. 否则 URL ?run= 命中列表 → 用它(深链打开/刷新/收藏恢复)
 *  3. 都不命中 → 落最新一条(倒序首条); 空列表 → null */
export function resolveSelection(
  runs: readonly RunLike[],
  urlRun: string | null,
  current: string | null,
): string | null {
  if (current !== null && runs.some((r) => r.run_id === current)) return current
  if (urlRun !== null && runs.some((r) => r.run_id === urlRun)) return urlRun
  return runs[0]?.run_id ?? null
}

/** URL → 选中: 浏览器前进/后退令 ?run= 变化时该切到哪轮。
 *  命中列表且非当前选中 → 返回它; 否则(缺省/数组/无效/与当前相同) → null 表示"不动"。
 *  返回 null 即幂等刹车点: 写 URL 触发的回读会命中"=== current"而止步。 */
export function selectionFromQuery(
  queryRun: unknown,
  runs: readonly RunLike[],
  current: string | null,
): string | null {
  const id = typeof queryRun === 'string' ? queryRun : null
  if (id === null || id === current) return null
  return runs.some((r) => r.run_id === id) ? id : null
}

/** 选中 → URL: 是否需要 router.replace 写回 ?run=。
 *  URL 现值与选中不同才写(含"URL 无而选中有"=写入、"URL 有而选中清空"=清除);
 *  相同则 false —— 幂等刹车点: 回读 URL 触发的回写会命中"相同"而止步。 */
export function shouldSyncRunToUrl(currentUrlRun: string | null, selectedId: string | null): boolean {
  return currentUrlRun !== selectedId
}
