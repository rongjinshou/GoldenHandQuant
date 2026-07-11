/* 回测表单日期收口(R7, 同 overview/refresh-form.ts 样板) — 纯函数便于单测。
 *
 * 后端事实(src/interfaces/api/job_commands.py BacktestJobRequest, 只读核实):
 * start_date/end_date 均为必填、无默认(Field(pattern=^\d{4}-\d{2}-\d{2}$))。
 * 表单日期有默认值但 clearable — 清空后提交, 旧实现以 `?? ''` 兜底发出空串,
 * 必撞 pattern 422(R6 总览刷新同型缺陷)。故必填校验前置: 缺任一日期不发请求,
 * 表单内就地中文提示; 通过校验的日期恰为两个非空 trim 串。 */

export type BacktestDates =
  | { ok: true; start: string; end: string }
  | { ok: false; error: string }

export function requireBacktestDates(start: string | null, end: string | null): BacktestDates {
  const s = start?.trim() ?? ''
  const e = end?.trim() ?? ''
  if (!s || !e) {
    return { ok: false, error: '起止日期均必填 — 回测接口要求明确区间' }
  }
  return { ok: true, start: s, end: e }
}
