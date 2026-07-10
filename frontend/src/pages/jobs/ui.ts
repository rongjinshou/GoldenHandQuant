/* 任务中心纯 UI 逻辑(设计 §7 徽章抽象 / §9 交互状态) — 与模板解耦, 便于单测。 */

/** AppBadge 语义 kind(见 components/AppBadge.vue) */
export type BadgeKind = 'info' | 'pass' | 'warn' | 'fail' | 'accent'

/* 任务状态 → AppBadge kind: queued=排队(info) / running=运行(accent 强调) /
 * succeeded=完成(pass 绿) / failed=失败(fail 红) / canceled=取消(warn 黄)。 */
const BADGE_KIND: Record<string, BadgeKind> = {
  queued: 'info',
  running: 'accent',
  succeeded: 'pass',
  failed: 'fail',
  canceled: 'warn',
}

export function jobBadgeKind(status: string): BadgeKind {
  return BADGE_KIND[status] ?? 'info'
}

/** 日志近底跟随判定(纯函数): 距底 <threshold(默认 40px) 即"在底部附近", 应自动跟随滚底。
 * jsdom 无布局(全 0)时结果为 true → 保持组件既有"始终滚底"语义, 既有测试不回归。 */
export function isNearBottom(
  scrollHeight: number,
  scrollTop: number,
  clientHeight: number,
  threshold = 40,
): boolean {
  return scrollHeight - scrollTop - clientHeight < threshold
}

/** 日志行过滤(纯函数): q 为空串返回原数组引用(零开销直通, 调用方可据此判断未过滤);
 * 非空则大小写不敏感子串匹配, 保持原行序。长日志(数千行)线性扫描足够, 配 computed 惰性求值。 */
export function filterLogLines(lines: string[], q: string): string[] {
  if (q === '') return lines
  const needle = q.toLowerCase()
  return lines.filter((line) => line.toLowerCase().includes(needle))
}

/** 任务终态通知决策(纯函数): succeeded→success / failed→error;
 * canceled(用户主动)与进行中态不打扰, 返回 null。type 对齐 naive useNotification 方法名。 */
export function terminalNotification(
  status: string,
): { type: 'success' | 'error'; title: string } | null {
  if (status === 'succeeded') return { type: 'success', title: '任务完成' }
  if (status === 'failed') return { type: 'error', title: '任务失败' }
  return null
}
