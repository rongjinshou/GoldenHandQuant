/* 回测轮选中 ↔ URL ?run= / 叠加 ↔ ?overlay= 深链的纯决策(设计 docs/feat/0710 §12 P7) —
 * 抽成纯函数便于单测, Backtests.vue 只做 useRoute/useRouter 接线。可深链/收藏/贴复盘笔记。
 *
 * 防死循环(关键): 状态→写 URL 与 URL→状态 是两向 watch, 必须靠"值相同不动"幂等互相刹车 ——
 *   selectionFromQuery 遇 (?run= === 当前选中) 返回 null(不改选中);
 *   shouldSyncRunToUrl 遇 (URL 已是选中值) 返回 false(不 replace);
 * 任一次往返到"两边一致"即静止, 不会 选中→replace→回读→再改选中 无限循环。
 * ?overlay= 同模式(overlayFromQuery 返回值与现值相同则调用方不赋值 + shouldSyncOverlayToUrl)。 */

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

/** URL ?overlay= → 叠加选择(overlaySel)应取的值。挂载首载恢复与前进/后退共用。
 *  两种 null 语义(务必区分, 批三坑):
 *  - 「缺席=清空」: 键不存在/无值/空串/数组 → null, URL 与状态一致地"无叠加";
 *  - 「非法=忽略」: 键存在但 run_id 不在列表 / 等于当前选中轮(自己叠自己无意义) → 也置 null,
 *    但 URL 里用户手输的原值必须保留 —— 不写回摘键的静默容错由 shouldSyncOverlayToUrl 负责,
 *    本函数只决定状态值。
 *  - 合法(在列表且非当前选中) → 采用。
 *  幂等刹车: 返回值 === 现值时调用方不赋值, 写URL→回读 的往返到此静止(与 ?run= 同模式)。 */
export function overlayFromQuery(
  raw: unknown,
  runs: readonly RunLike[],
  selectedRunId: string | null,
): string | null {
  if (typeof raw !== 'string' || raw === '') return null // 缺席(undefined/有键无值/数组/空串) → 清空
  if (raw === selectedRunId) return null // 等于当前选中轮 → 忽略
  return runs.some((r) => r.run_id === raw) ? raw : null // 在列表 → 采用; 否则忽略
}

/** 叠加选择 → URL: 是否需要 router.replace 写回 ?overlay=(null=摘除该键)。
 *  - URL 现值 === 选择值 → false(幂等刹车, 与 shouldSyncRunToUrl 同模式);
 *  - 选择为空 而 URL 值本就非法(不在列表 / 等于当前选中轮) → false: 静默容错,
 *    overlayFromQuery 忽略非法值置空后, 不许回写把用户手输的 URL 值抹掉;
 *  - 其余(写入新值 / 更新 / 用户清空合法叠加=摘键) → true。
 *  写方向不审查选择值合法性 —— 用户在下拉选了什么就写什么(选中自身轮的展示由图表层拦截)。 */
export function shouldSyncOverlayToUrl(
  currentUrlOverlay: string | null,
  overlaySel: string | null,
  runs: readonly RunLike[],
  selectedRunId: string | null,
): boolean {
  if (currentUrlOverlay === overlaySel) return false
  if (overlaySel === null && currentUrlOverlay !== null) {
    // 清空方向: 仅当 URL 值本是合法叠加(用户真清掉了它)才摘键; 非法值保留在地址栏
    return currentUrlOverlay !== selectedRunId && runs.some((r) => r.run_id === currentUrlOverlay)
  }
  return true
}
