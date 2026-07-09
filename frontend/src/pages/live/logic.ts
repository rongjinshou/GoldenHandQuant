/* Live 页纯展示逻辑 — 自旧 static/js/pages/live.js 逐条对等抽取, 可单测。
 * 语义色正名(设计 §4.1): 旧 CSS 涨/买复用 gate-bad(红)、跌/卖复用 gate-good(绿)是
 * 类名反用 — 此处按语义对号: 涨=t-up 跌=t-down(行情), 买=t-buy 卖=t-sell(委托,
 * A 股买红卖绿), FILLED=t-pass REJECT/FAIL=t-fail(判定)。 */

import type { AccountSnapshot, LiveConfig, PositionSnapshot, TicketContent } from '@/api/types'

/* 旧 api.js num(): null/undefined → '-', 其余千分位 */
export function num(v: number | null | undefined): string {
  return v === null || v === undefined ? '-' : Number(v).toLocaleString()
}

/* 收益率类百分比的唯一口径(精度统一): 统一 2 位小数 + 带符号 + %。
 * 全站收益率(KPI 累计收益 / 持仓浮盈 %)一律走此函数, 消除"累计 2 位 vs 持仓 1 位"漂移。 */
const RETURN_PCT_DP = 2
export function returnPct(ratio: number): string {
  return `${ratio >= 0 ? '+' : ''}${(ratio * 100).toFixed(RETURN_PCT_DP)}%`
}

/* 时间戳截到秒(旧 .slice(0, 19)) */
export function sliceTime(s: string | null | undefined): string {
  return (s ?? '').slice(0, 19)
}

/* 权益 Y 轴刻度: 绝对值 ≥1 万显示 x.x万 */
export function wan(v: number): string {
  return Math.abs(v) >= 10000 ? `${(v / 10000).toFixed(1)}万` : `${v}`
}

export type BadgeKind = 'info' | 'pass' | 'warn' | 'fail'

/* 执行状态 → 徽章语义(对等旧 STATUS_BADGE; 未知状态回退 info) */
const STATUS_BADGE: Record<string, BadgeKind> = {
  DRY_RUN: 'info',
  SUBMITTED: 'info',
  FILLED: 'pass',
  PARTIAL: 'warn',
  ALIVE: 'warn',
  TIMEOUT_CANCELED: 'warn',
  TIMEOUT_UNCANCELED: 'fail',
  CANCELED: 'warn',
  REJECTED: 'fail',
  FAILED: 'fail',
}

export function statusBadge(status: string): BadgeKind {
  return STATUS_BADGE[status] ?? 'info'
}

/* 累计收益 KPI — equity 快照 ≥2 才有"累计"口径(单快照无从谈累计):
 * 现值优先取最新账户快照, 回退权益序列末条; 起点无效(空/0)同样显示占位。
 * series 须为单一模式(调用方按 latest.mode 预过滤) — 混合序列的 series[0] 起点
 * 与 latest 现值可能分属不同 mode, 相除即跨模式串账; sub 标注模式便于核对。 */
export interface CumReturnView {
  text: string
  tone: 'up' | 'down' | 'neutral'
  sub: string
}

export function cumReturn(
  series: AccountSnapshot[],
  latest: AccountSnapshot | null,
): CumReturnView {
  const first = series.length ? series[0].total_asset : null
  const lastTotal =
    latest?.total_asset ?? (series.length ? series[series.length - 1].total_asset : null)
  if (series.length >= 2 && first !== null && first > 0 && lastTotal !== null && lastTotal !== undefined) {
    const ret = lastTotal / first - 1
    return {
      text: returnPct(ret),
      tone: ret >= 0 ? 'up' : 'down', // A股: 涨红跌绿
      sub: `起点 ${num(first)} (${series[0].mode})`,
    }
  }
  return {
    text: '—',
    tone: 'neutral',
    sub: series.length === 1 ? '需多次快照累计' : '暂无权益快照',
  }
}

/* 守护活性徽章: 按执行槽位与今日循环数推断(对等旧 daemonBadge); now 可注入便于测试 */
export interface DaemonBadgeView {
  kind: BadgeKind
  text: string
}

export function daemonBadge(
  cfg: LiveConfig,
  now: string = new Date().toTimeString().slice(0, 5),
): DaemonBadgeView {
  const slots = cfg.today.expected_slots ?? []
  const due = slots.filter((s) => s <= now).length
  const n = cfg.today.cycles_today
  if (!slots.length) return { kind: 'info', text: '未配置槽位' }
  if (due === 0) return { kind: 'info', text: '今日未到执行时刻' }
  if (n >= due) return { kind: 'pass', text: `槽位已覆盖 ${n}/${due}` }
  return { kind: 'warn', text: `槽位缺口 ${n}/${due} — 守护可能未运行` }
}

/* 持仓行盯市: 现价缺失(null/0)回退成本估市值, 且不显示盈亏 */
export interface PositionRowView {
  symbol: string
  totalVolume: number
  available: number | string
  costText: string
  lastText: string
  mktValText: string
  pnlText: string
  pnlCls: '' | 't-up' | 't-down'
}

export function positionRow(r: PositionSnapshot): PositionRowView {
  const vol = r.total_volume || 0
  const cost = r.average_cost ?? 0
  const last = r.last_price
  const hasLast = last !== null && last !== undefined && last > 0
  const mktPx = hasLast ? last : cost
  const pnl = hasLast ? (last - cost) * vol : null
  let pnlText = '-'
  let pnlCls: PositionRowView['pnlCls'] = ''
  if (pnl !== null) {
    // 浮盈 % 与 KPI 累计收益同口径(returnPct, 2 位); mktPx/cost-1 与 pnl 同号(cost>0,vol>0)
    const pct = cost > 0 ? ` (${returnPct(mktPx / cost - 1)})` : ''
    pnlText = `${pnl >= 0 ? '+' : ''}${num(pnl)}${pct}`
    pnlCls = pnl >= 0 ? 't-up' : 't-down' // A股: 涨红跌绿
  }
  return {
    symbol: r.symbol,
    totalVolume: vol,
    available: r.available_volume ?? '-',
    costText: cost.toFixed(3),
    lastText: hasLast ? last.toFixed(3) : '-',
    mktValText: num(vol * mktPx),
    pnlText,
    pnlCls,
  }
}

/* 权益曲线无障碍替代文本(WCAG 1.1.1) — ECharts 容器 role="img" 的 aria-label:
 * 概述曲线条数(按 mode)、每条最新总资产、时间区间, 让读屏用户不看图也能获取要点。
 * <2 快照(不成曲线)时返回未绘制说明。时间中的 'T' 换空格便于读屏断句。 */
export function equityAriaLabel(series: AccountSnapshot[]): string {
  if (series.length < 2) return '账户权益曲线，快照不足暂未绘制'
  const fmt = (s: string): string => sliceTime(s).replace('T', ' ')
  const sorted = [...series].sort((a, b) => (a.snapshot_time < b.snapshot_time ? -1 : 1))
  const modes = [...new Set(sorted.map((r) => r.mode))]
  const start = fmt(sorted[0].snapshot_time)
  const end = fmt(sorted[sorted.length - 1].snapshot_time)
  const parts = modes.map((m) => {
    const rows = sorted.filter(
      (r) => r.mode === m && r.total_asset !== null && r.total_asset !== undefined,
    )
    const last = rows.length ? rows[rows.length - 1].total_asset : null
    return `${m} 最新总资产 ${num(last)}`
  })
  return `账户权益曲线，${modes.length} 条：${parts.join('；')}；区间 ${start} 至 ${end}`
}

/* ticket 键值面板: content 非对象 → null(渲染"内容不可读"); 空值字段跳过。
 * 方向买红卖绿(t-buy/t-sell), 终态含 FILLED 绿(t-pass)、REJECT/FAIL 红(t-fail)。 */
export interface TicketCell {
  k: string
  v: string
  cls: string
}

export function ticketCells(c: unknown): TicketCell[] | null {
  if (!c || typeof c !== 'object') return null
  const t = c as TicketContent
  const cells: TicketCell[] = []
  const push = (k: string, v: unknown, cls = ''): void => {
    if (v === undefined || v === null || v === '') return
    cells.push({ k, v: String(v), cls })
  }
  const dirCls = t.direction === 'BUY' ? 't-buy' : t.direction === 'SELL' ? 't-sell' : ''
  const dirText =
    t.direction === 'BUY' ? '买入 BUY' : t.direction === 'SELL' ? '卖出 SELL' : (t.direction ?? '-')
  const fin = t.final_status || t.status
  const finCls = /FILLED/.test(fin || '') ? 't-pass' : /REJECT|FAIL/.test(fin || '') ? 't-fail' : ''
  push('标的', t.symbol)
  push('方向', dirText, dirCls)
  push('委托价', t.price)
  push('数量', t.volume)
  push('金额', t.notional !== null && t.notional !== undefined ? Number(t.notional).toLocaleString() : null)
  push('状态', fin, finCls)
  push('委托号', t.order_id)
  push('提交时刻', (t.submitted_at || t.requested_at || '').slice(0, 19))
  return cells
}
