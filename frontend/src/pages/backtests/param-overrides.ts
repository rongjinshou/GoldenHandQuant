/* 回测策略参数编辑 — 纯逻辑（BacktestForm 参数区的可测内核）。
 *
 * 契约对齐后端 BacktestJobRequest.params: dict[策略名, dict[参数名, float|int|str]]
 * (src/interfaces/api/job_commands.py)。提交时只发「用户改过(≠默认)」的键——
 * 全默认则整个 params 字段不发, 与不改参数的旧行为逐字节等价。 */

export type ParamValue = number | string

/** 编辑态单值 — null = 用默认（NInputNumber 清空即回 null） */
export type ParamEditValue = ParamValue | null

/** 编辑态: 策略名 → { 参数名 → 当前编辑值 } */
export type ParamEdits = Record<string, Record<string, ParamEditValue>>

/** 默认值表: 策略名 → { 参数名 → 归一化默认值 }（与 editableParams 同一归一化） */
export type ParamDefaults = Record<string, Record<string, ParamValue>>

/** 可编辑参数描述 — numeric 决定控件（NInputNumber vs NInput） */
export interface EditableParam {
  key: string
  def: ParamValue
  numeric: boolean
}

/**
 * default_params → 可编辑参数列表（归一化）:
 * - null / 嵌套对象（dict、数组）不生成输入行（对等旧版 typeof null === 'object' 过滤）
 * - 数值保持数值（走 NInputNumber, 提交为 number）
 * - 其余（字符串、布尔）转字符串（走 NInput, 提交为 str, 布尔编辑为 "true"/"false"）
 */
export function editableParams(defaultParams: Record<string, unknown>): EditableParam[] {
  const out: EditableParam[] = []
  for (const [key, val] of Object.entries(defaultParams)) {
    if (val === null || val === undefined || typeof val === 'object') continue
    if (typeof val === 'number') out.push({ key, def: val, numeric: true })
    else out.push({ key, def: String(val), numeric: false })
  }
  return out
}

/**
 * 单键「已改」判定 — paramOverrides 的逐键语义抽出复用（单一事实源:
 * 表单"已改"高亮与提交 diff 永远同判）:
 * - null（InputNumber 清空）/ 空白字符串 = 用默认 → false
 * - 字符串 trim 后与默认严格相等 → false（"close " ≡ "close"）
 * - 其余（含 0 等 falsy 数值）≠ 默认 → true
 */
export function isOverridden(edited: ParamEditValue, def: ParamValue): boolean {
  if (edited === null) return false
  const val = typeof edited === 'string' ? edited.trim() : edited
  return val !== '' && val !== def
}

/**
 * 逐键 diff 出「用户改过」的参数覆盖（单键判定 = isOverridden, 见上）:
 * - 字符串 trim 后提交（"open " → "open", 不发尾随空格）
 * - 无默认值的未知键、defaults 缺失的策略一律忽略（不发后端不认的东西）
 * - 一个覆盖都没有 → undefined（调用方据此不带 params 字段）
 */
export function paramOverrides(
  edited: ParamEdits,
  defaults: ParamDefaults,
): Record<string, Record<string, ParamValue>> | undefined {
  const out: Record<string, Record<string, ParamValue>> = {}
  for (const [strat, kv] of Object.entries(edited)) {
    const defs = defaults[strat]
    if (!defs) continue
    for (const [key, raw] of Object.entries(kv)) {
      if (raw === null || !(key in defs) || !isOverridden(raw, defs[key])) continue
      ;(out[strat] ??= {})[key] = typeof raw === 'string' ? raw.trim() : raw
    }
  }
  return Object.keys(out).length ? out : undefined
}
