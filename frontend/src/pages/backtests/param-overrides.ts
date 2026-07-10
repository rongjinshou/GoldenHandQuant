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
 * 逐键 diff 出「用户改过」的参数覆盖:
 * - null（InputNumber 清空）/ 空白字符串 = 用默认, 不算覆盖
 * - 字符串 trim 后再比较与提交（"close " ≡ "close", 不发尾随空格）
 * - 与默认严格相等（number===number / string===string）的键不发
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
      if (!(key in defs)) continue
      if (raw === null) continue
      const val = typeof raw === 'string' ? raw.trim() : raw
      if (val === '' || val === defs[key]) continue
      ;(out[strat] ??= {})[key] = val
    }
  }
  return Object.keys(out).length ? out : undefined
}
