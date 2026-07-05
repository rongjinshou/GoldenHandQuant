/* 判决闸门与评分等级 — D2 单一真相源修复。
 *
 * 阈值从 /api/meta/gates 动态获取（后端 gates_config.py 是唯一定义处），
 * 启动时 fetch 一次并缓存；API 不可用时回退到硬编码默认值（防御性）。
 */

import type { VerdictFactor } from '@/api/types'

/** 闸门阈值结构 — 与后端 get_all_gates() 返回值对齐。 */
interface GatesConfig {
  ic_min: number
  ir_min: number
  ic_positive_rate_min: number
  monotonicity_min: number
  long_short_min: number
  excess_ir_min: number
  excess_positive_rate_min: number
  top_excess_min: number
}

/** 硬编码回退值 — 仅在 API 不可达时使用，修改请同步 gates_config.py。 */
const FALLBACK: GatesConfig = {
  ic_min: 0.02,
  ir_min: 0.30,
  ic_positive_rate_min: 0.52,
  monotonicity_min: 0.6,
  long_short_min: 0.0,
  excess_ir_min: 0.50,
  excess_positive_rate_min: 0.52,
  top_excess_min: 0.0,
}

let _cached: GatesConfig | null = null

/** 获取闸门阈值（启动时 fetch 一次，后续走缓存）。 */
export async function loadGates(): Promise<GatesConfig> {
  if (_cached) return _cached
  try {
    const res = await fetch('/api/meta/gates')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    _cached = {
      ic_min: data.ic_min,
      ir_min: data.ir_min,
      ic_positive_rate_min: data.ic_positive_rate_min,
      monotonicity_min: data.monotonicity_min,
      long_short_min: data.long_short_min,
      excess_ir_min: data.excess_ir_min,
      excess_positive_rate_min: data.excess_positive_rate_min,
      top_excess_min: data.top_excess_min,
    }
    return _cached
  } catch {
    console.warn('[gates] API 不可达，使用回退阈值')
    _cached = { ...FALLBACK }
    return _cached
  }
}

/** 同步获取已缓存的阈值（必须先调用 loadGates）。 */
function getGates(): GatesConfig {
  if (!_cached) {
    console.warn('[gates] loadGates() 尚未完成，使用回退阈值')
    return FALLBACK
  }
  return _cached
}

/** 供测试用：重置缓存。 */
export function _resetGatesCache(): void {
  _cached = null
}

export const GATES: Record<string, (v: number) => boolean> = {
  ic_mean: (v) => v >= getGates().ic_min,
  ir: (v) => v >= getGates().ir_min,
  ic_positive_rate: (v) => v >= getGates().ic_positive_rate_min,
  monotonicity_score: (v) => v >= getGates().monotonicity_min,
  long_short_return: (v) => v > getGates().long_short_min,
  oos_long_short_return: (v) => v > getGates().long_short_min,
  // long-only 记分牌门槛
  excess_ir: (v) => v >= getGates().excess_ir_min,
  excess_positive_rate: (v) => v >= getGates().excess_positive_rate_min,
  top_excess_return: (v) => v > getGates().top_excess_min,
  oos_top_excess_return: (v) => v > getGates().top_excess_min,
}

/* 闸门单元格语义类: 无值 na / 过闸 pass / 未过 fail; 非闸门指标无着色 */
export function gateClass(name: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return 'gate-na'
  const gate = GATES[name]
  if (!gate) return ''
  return gate(value) ? 't-pass' : 't-fail'
}

/* 评分等级着色: A 绿 / B 中性 / C 琥珀 / D 红; F 映射到 D 档 */
export function gradeClass(grade: string | null | undefined): string {
  const g = (grade ?? '').toUpperCase()
  const map: Record<string, string> = {
    A: 'grade-a',
    B: 'grade-b',
    C: 'grade-c',
    D: 'grade-d',
    F: 'grade-d',
  }
  return map[g] ?? 'grade-b'
}

export const f4 = (v: number): string => v.toFixed(4)
export const f3 = (v: number): string => v.toFixed(3)
export const f2 = (v: number): string => v.toFixed(2)
export const pct = (v: number): string => `${(v * 100).toFixed(2)}%`

export function gcell(
  name: string,
  v: number | null | undefined,
  fmt: (x: number) => string,
): { text: string; cls: string } {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: gateClass(name, v) }
}

/* 判定符号: 后端 verdict.py 用 '✓'(U+2713); 兼容 '√'(U+221A) 防历史数据 */
export function isPassReason(r: string): boolean {
  return r.includes('✓') || r.includes('√')
}

export type GateState = 'pass' | 'fail' | 'na'

export interface GateCell {
  key: string
  label: string
  state: GateState
  detail: string
}

function trackCell(
  key: string,
  label: string,
  value: number | null | undefined,
  fmt: (v: number) => string,
): GateCell {
  if (value === null || value === undefined) {
    return { key, label, state: 'na', detail: `${label}: 无数据` }
  }
  const gate = GATES[key]
  const state: GateState = gate ? (gate(value) ? 'pass' : 'fail') : 'na'
  return { key, label, state, detail: `${label}=${fmt(value)}` }
}

/* 闸门轨道(设计 0705-verdict-cards §4.2) — 7 道硬闸门, 顺序对齐 verdict.py 判定顺序:
 * ①IC ②稳定性 ③一致性 ④单调性 ⑤变现 ⑥OOS符号一致 ⑦OOS变现。
 * ⑥⑦只信 run.params.split 有无(hasSplit), 不用 OOS 数值反猜——无切分时后端存 0.0,
 * 会跟"真实为 0"混淆。 */
export function gateTrack(f: VerdictFactor, longOnly: boolean, hasSplit: boolean): GateCell[] {
  const cells: GateCell[] = [
    trackCell('ic_mean', 'IC', f.ic_mean, f4),
    longOnly
      ? trackCell('excess_ir', '超额信息比', f.excess_ir, f2)
      : trackCell('ir', 'IR', f.ir, f3),
    longOnly
      ? trackCell('excess_positive_rate', '超额正率', f.excess_positive_rate, pct)
      : trackCell('ic_positive_rate', 'IC正率', f.ic_positive_rate, pct),
    trackCell('monotonicity_score', '单调性', f.monotonicity_score, f2),
    longOnly
      ? trackCell('top_excess_return', 'Top超额', f.top_excess_return, pct)
      : trackCell('long_short_return', '多空收益', f.long_short_return, pct),
  ]

  if (!hasSplit) {
    cells.push({ key: 'oos_sign', label: '样本外符号一致', state: 'na', detail: '未设 IS/OOS 切分' })
    cells.push(
      longOnly
        ? { key: 'oos_top_excess_return', label: '样本外Top超额', state: 'na', detail: '未设 IS/OOS 切分' }
        : { key: 'oos_long_short_return', label: '样本外多空', state: 'na', detail: '未设 IS/OOS 切分' },
    )
    return cells
  }

  const icSign = Math.sign(f.ic_mean ?? 0)
  const oosSign = Math.sign(f.oos_ic_mean ?? 0)
  const signOk = icSign === 0 || oosSign === 0 || icSign === oosSign
  cells.push({
    key: 'oos_sign',
    label: '样本外符号一致',
    state: signOk ? 'pass' : 'fail',
    detail: `IS=${f4(f.ic_mean ?? 0)} vs OOS=${f4(f.oos_ic_mean ?? 0)}`,
  })
  cells.push(
    longOnly
      ? trackCell('oos_top_excess_return', '样本外Top超额', f.oos_top_excess_return, pct)
      : trackCell('oos_long_short_return', '样本外多空', f.oos_long_short_return, pct),
  )
  return cells
}
