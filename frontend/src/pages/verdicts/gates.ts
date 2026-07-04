/* 判决闸门与评分等级 — 旧 pages/verdicts.js 纯逻辑抽取。
 * 阈值与 verdict.py 同步; 单一真相源收敛留作债 D2(前端复制沿现状)。 */

export const GATES: Record<string, (v: number) => boolean> = {
  ic_mean: (v) => v >= 0.02,
  ir: (v) => v >= 0.3,
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
