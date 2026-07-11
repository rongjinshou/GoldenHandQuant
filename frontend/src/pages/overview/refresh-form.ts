/* 数据刷新表单载荷构建(R6-03a) — 纯函数便于单测。
 *
 * 后端事实(src/interfaces/api/job_commands.py DataRefreshJobRequest, 只读核实):
 * start_date/end_date 均为必填、无默认(Field(pattern=^\d{4}-\d{2}-\d{2}$)) — 发空串撞
 * pattern 422, 省键撞 Field required 422("留空=自动补齐"仅 CLI 版 quant data refresh
 * 有默认, Web 通道从未走通)。故前端把必填校验前置: 缺任一日期不发请求, 就地中文提示。
 * 通过校验的载荷恰含两个非空键, 永不携带空串。 */

export type RefreshRequest =
  | { ok: true; payload: { start_date: string; end_date: string } }
  | { ok: false; error: string }

export function buildRefreshRequest(start: string | null, end: string | null): RefreshRequest {
  const s = start?.trim() ?? ''
  const e = end?.trim() ?? ''
  if (!s || !e) {
    return { ok: false, error: '起始与结束日期均必填 — 数据刷新接口要求明确区间（区间内只补库内缺口）' }
  }
  return { ok: true, payload: { start_date: s, end_date: e } }
}
