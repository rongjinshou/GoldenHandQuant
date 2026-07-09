export interface Cell {
  text: string
  cls: string
}

/** 带符号收益/盈亏 → A股行情色（涨/正=红 t-up, 跌/负=绿 t-down） */
export function marketCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: 't-muted' }
  return { text: fmt(v), cls: v > 0 ? 't-up' : v < 0 ? 't-down' : '' }
}

/** 质量指标（夏普/Calmar/胜率等）→ 中性，不上红绿（越大越好但非涨跌） */
export function qualityCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: '' }
}

/** 最大回撤 → 超 20% 标失败红，否则中性 */
export function ddCell(v: number | null | undefined, fmt: (x: number) => string): Cell {
  if (v === null || v === undefined) return { text: '-', cls: '' }
  return { text: fmt(v), cls: v > 0.2 ? 't-fail' : '' }
}
