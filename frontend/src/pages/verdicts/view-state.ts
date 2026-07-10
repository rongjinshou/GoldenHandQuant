/* 判决结果视图(过滤+排序)会话记忆 — sessionStorage 读写纯函数。
 *
 * 动机: 研究期反复进出判决页, 过滤(全部/PASS/FAIL)与排序每次进页都重置, 得重新设。
 * 本模块记住"用什么视角看结果", Verdicts.vue 只做接线: setup 恢复初值、变更即写。
 *
 * 刻意 sessionStorage 而非 localStorage(关键决策): 视角是"本次研究会话"的工作状态,
 * 跨天/新开会话重置回默认反而符合"新会话新起点"; 与 Explorer「最近查看」
 * (localStorage, 长期资产)的语义划清界线。
 *
 * 与 ?run= 深链(run-deeplink.ts)不同关注点: 深链记"看哪一轮"(可分享的 URL 状态),
 * 本模块记"用什么视角看"(个人工作状态), 互不读写对方, 无冲突。
 *
 * 容错保证(绝不抛):
 * - 坏 JSON / 非对象 → 整体回默认(filter='all' + 默认排序键 'verdict');
 * - 字段级非法枚举(如 filter:'nope' / 大小写不符) → 只该字段回默认, 合法字段保留;
 * - sessionStorage 读写失败(隐私模式/配额满/无 storage 环境) → load 回默认 / save 静默。 */

import { FILTER_KEYS, SORT_OPTIONS, type FilterKey, type SortKey } from './sort'

export const VERDICTS_VIEW_KEY = 'ghq-verdicts-view'

export interface VerdictsView {
  filter: FilterKey
  sort: SortKey
}

/** 进页默认视角: 全部因子 + "判决 + 评分"放榜序(原 Verdicts.vue 硬编码初值, 收敛到此)。 */
export const DEFAULT_VERDICTS_VIEW: Readonly<VerdictsView> = { filter: 'all', sort: 'verdict' }

function isFilterKey(v: unknown): v is FilterKey {
  return (FILTER_KEYS as readonly unknown[]).includes(v)
}

/* SORT_OPTIONS 即排序下拉的可选项 — "能被恢复的值"与"能被选中的值"同一口径, 不另列清单。 */
function isSortKey(v: unknown): v is SortKey {
  return SORT_OPTIONS.some((o) => o.value === v)
}

/** 读会话记忆; 无记录/坏值/读失败 → 默认(字段级容错: 非法枚举只丢该字段)。绝不抛。 */
export function loadVerdictsView(): VerdictsView {
  try {
    const raw = sessionStorage.getItem(VERDICTS_VIEW_KEY)
    if (!raw) return { ...DEFAULT_VERDICTS_VIEW }
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return { ...DEFAULT_VERDICTS_VIEW }
    const rec = parsed as Record<string, unknown>
    return {
      filter: isFilterKey(rec.filter) ? rec.filter : DEFAULT_VERDICTS_VIEW.filter,
      sort: isSortKey(rec.sort) ? rec.sort : DEFAULT_VERDICTS_VIEW.sort,
    }
  } catch {
    return { ...DEFAULT_VERDICTS_VIEW }
  }
}

/** 变更即写(整对象覆盖); 写失败静默 — 记忆是增强, 不打断研究流。 */
export function saveVerdictsView(view: VerdictsView): void {
  try {
    sessionStorage.setItem(VERDICTS_VIEW_KEY, JSON.stringify(view))
  } catch {
    /* 静默(隐私模式/配额满) */
  }
}
