/* ML 训练/评估载荷构建(R7, 同 overview/refresh-form.ts 样板) — 纯函数便于单测。
 *
 * 后端事实(src/interfaces/api/job_commands.py, 只读核实):
 * - MlTrainJobRequest: start_date/end_date 必填无默认(pattern ^\d{4}-\d{2}-\d{2}$),
 *   空串/省键均 422; model_name 有后端默认但带 pattern ^[A-Za-z0-9_\-]{1,64}$ —
 *   旧实现总是显式发送, 清空后空串必撞 pattern 422, 且模型名是训练↔评估的衔接键,
 *   静默回落默认会训到用户不想要的名字下 → 必填拦截而非省键。
 * - MlEvaluateJobRequest: model_name/eval_start/eval_end 三者必填无默认。
 * - symbols(默认 000300.SH)/n_trials(默认 50, ge=1) 有后端默认 → 留空省键让默认生效
 *   (R2 判决表单「留空省键」同款); 旧实现清空后发 symbols:'' / Number(null)=0 也都是 422。
 * 通过校验的载荷永不携带空串。 */

export type MlRequest<P> = { ok: true; payload: P } | { ok: false; error: string }

export interface MlTrainInput {
  start: string | null
  end: string | null
  symbols: string
  model: string
  trials: number | null
}

export interface MlTrainPayload {
  start_date: string
  end_date: string
  model_name: string
  symbols?: string
  n_trials?: number
}

const MODEL_REQUIRED = '模型名必填 — 决定模型与数据集的落盘路径（models/<名>）'

export function buildTrainRequest(i: MlTrainInput): MlRequest<MlTrainPayload> {
  const s = i.start?.trim() ?? ''
  const e = i.end?.trim() ?? ''
  if (!s || !e) {
    return { ok: false, error: '训练起止日期均必填 — ML 训练接口要求明确区间' }
  }
  const model = i.model.trim()
  if (!model) return { ok: false, error: MODEL_REQUIRED }
  const payload: MlTrainPayload = { start_date: s, end_date: e, model_name: model }
  const symbols = i.symbols.trim()
  if (symbols) payload.symbols = symbols // 留空省键 → 后端默认 000300.SH
  if (i.trials !== null) payload.n_trials = i.trials // 清空省键 → 后端默认 50(不再发 0)
  return { ok: true, payload }
}

export interface MlEvalPayload {
  model_name: string
  eval_start: string
  eval_end: string
}

export function buildEvalRequest(
  model: string,
  start: string | null,
  end: string | null,
): MlRequest<MlEvalPayload> {
  const s = start?.trim() ?? ''
  const e = end?.trim() ?? ''
  if (!s || !e) {
    return { ok: false, error: '评估起止日期均必填 — ML 评估接口要求明确区间' }
  }
  const m = model.trim()
  if (!m) return { ok: false, error: MODEL_REQUIRED }
  return { ok: true, payload: { model_name: m, eval_start: s, eval_end: e } }
}
