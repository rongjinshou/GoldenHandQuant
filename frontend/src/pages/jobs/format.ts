import type { Job } from '@/api/types'

/* 任务格式化 — 旧 static/js/jobs.js STATUS_LABEL/durationOf/paramsSummary 对等移植。
 * 列表页与 JobCard 内嵌实现保持同一语义(契约: 一致但不改 JobCard, 故此处独立小实现)。 */

export const STATUS_LABEL: Record<string, string> = {
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
}

export const TERMINAL_STATUS: ReadonlySet<string> = new Set(['succeeded', 'failed', 'canceled'])

/* 耗时: 未开始 '-'; 结束取 finished_at 否则取现在; <90s 整秒, 否则一位小数分钟 */
export function durationOf(job: Pick<Job, 'started_at' | 'finished_at'>): string {
  if (!job.started_at) return '-'
  const end = job.finished_at ? new Date(job.finished_at) : new Date()
  const sec = Math.max(0, (end.getTime() - new Date(job.started_at).getTime()) / 1000)
  return sec < 90 ? `${sec.toFixed(0)}s` : `${(sec / 60).toFixed(1)}min`
}

/* 参数摘要: strategies/factors/model_name/symbols(>2 只缩写)/日期区间/objective,
 * ' · ' 连接后截 90 字 — 逐条对等旧版拼装顺序 */
export function paramsSummary(job: Pick<Job, 'params'>): string {
  const p = (job.params ?? {}) as Record<string, unknown>
  const parts: string[] = []
  if (Array.isArray(p.strategies)) parts.push((p.strategies as string[]).join(','))
  if (p.factors) parts.push(String(p.factors))
  if (p.model_name) parts.push(String(p.model_name))
  if (p.symbols) {
    const arr = Array.isArray(p.symbols) ? (p.symbols as string[]) : String(p.symbols).split(',')
    parts.push(arr.length <= 2 ? arr.join(',') : `${arr.slice(0, 2).join(',')}等${arr.length}只`)
  }
  if (p.start_date) parts.push(`${p.start_date}~${p.end_date ?? ''}`)
  if (p.objective) parts.push(String(p.objective))
  return parts.join(' · ').slice(0, 90)
}
