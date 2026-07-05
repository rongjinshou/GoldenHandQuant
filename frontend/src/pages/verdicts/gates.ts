/* 判决闸门与评分等级 — 旧 pages/verdicts.js 纯逻辑抽取。
 * 阈值与 verdict.py 同步; 单一真相源收敛留作债 D2(前端复制沿现状)。 */

import type { VerdictFactor } from '@/api/types'

export const GATES: Record<string, (v: number) => boolean> = {
  ic_mean: (v) => v >= 0.02,
  ir: (v) => v >= 0.3,
  ic_positive_rate: (v) => v >= 0.52,
  monotonicity_score: (v) => v >= 0.6,
  long_short_return: (v) => v > 0,
  oos_long_short_return: (v) => v > 0,
  // long-only 记分牌门槛
  excess_ir: (v) => v >= 0.5,
  excess_positive_rate: (v) => v >= 0.52,
  top_excess_return: (v) => v > 0,
  oos_top_excess_return: (v) => v > 0,
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
