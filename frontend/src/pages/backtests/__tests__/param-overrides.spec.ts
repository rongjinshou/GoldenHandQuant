import { describe, expect, it } from 'vitest'

import { editableParams, isOverridden, type ParamDefaults, paramOverrides } from '../param-overrides'

/* 参数覆盖 diff — 提交体只带「改过(≠默认)」的键; 全默认不发 params 字段。
 * 契约对齐后端 BacktestJobRequest.params: dict[str, dict[str, float|int|str]]。 */

const DEFAULTS: ParamDefaults = {
  dual_ma: { fast_period: 5, slow_period: 20, price_field: 'close' },
  micro_value: { top_n: 20 },
}

describe('paramOverrides(编辑态 vs 默认 → 只发改过的键)', () => {
  it('未改（编辑态=默认） → undefined（不带 params 字段, 与旧行为等价）', () => {
    const edited = {
      dual_ma: { fast_period: 5, slow_period: 20, price_field: 'close' },
      micro_value: { top_n: 20 },
    }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('改一个数值 → 只含该策略该键, 且保持 number 类型', () => {
    const edited = { dual_ma: { fast_period: 7, slow_period: 20, price_field: 'close' } }
    expect(paramOverrides(edited, DEFAULTS)).toEqual({ dual_ma: { fast_period: 7 } })
  })

  it('改过再改回默认 → undefined（不残留覆盖）', () => {
    // 用户 5 → 7 → 5, 编辑态最终等于默认
    const edited = { dual_ma: { fast_period: 5, slow_period: 20, price_field: 'close' } }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('InputNumber 清空（null） = 用默认, 不算覆盖', () => {
    const edited = { dual_ma: { fast_period: null, slow_period: 20, price_field: 'close' } }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('字符串参数改动 → 提交 trim 后的字符串', () => {
    const edited = { dual_ma: { fast_period: 5, slow_period: 20, price_field: ' open ' } }
    expect(paramOverrides(edited, DEFAULTS)).toEqual({ dual_ma: { price_field: 'open' } })
  })

  it('字符串仅加了首尾空白（trim 后=默认） → 不算覆盖', () => {
    const edited = { dual_ma: { fast_period: 5, slow_period: 20, price_field: 'close ' } }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('字符串清成空白 = 用默认', () => {
    const edited = { dual_ma: { fast_period: 5, slow_period: 20, price_field: '  ' } }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('同策略数值+字符串都改 → 两键并存', () => {
    const edited = { dual_ma: { fast_period: 8, slow_period: 20, price_field: 'open' } }
    expect(paramOverrides(edited, DEFAULTS)).toEqual({
      dual_ma: { fast_period: 8, price_field: 'open' },
    })
  })

  it('多策略: 一个改了一个全默认 → 只含改过的策略', () => {
    const edited = {
      dual_ma: { fast_period: 5, slow_period: 20, price_field: 'close' },
      micro_value: { top_n: 30 },
    }
    expect(paramOverrides(edited, DEFAULTS)).toEqual({ micro_value: { top_n: 30 } })
  })

  it('多策略都改 → 各自成组', () => {
    const edited = {
      dual_ma: { fast_period: 3, slow_period: 20, price_field: 'close' },
      micro_value: { top_n: 10 },
    }
    expect(paramOverrides(edited, DEFAULTS)).toEqual({
      dual_ma: { fast_period: 3 },
      micro_value: { top_n: 10 },
    })
  })

  it('无默认值的未知键忽略（不发后端不认的键）', () => {
    const edited = { dual_ma: { ghost_param: 99, fast_period: 5, slow_period: 20, price_field: 'close' } }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('defaults 缺失整个策略 → 该策略忽略', () => {
    const edited = { unknown_strategy: { x: 1 } }
    expect(paramOverrides(edited, DEFAULTS)).toBeUndefined()
  })

  it('空编辑态 → undefined', () => {
    expect(paramOverrides({}, DEFAULTS)).toBeUndefined()
  })

  it('0 是合法覆盖值（不与 null/空混淆）', () => {
    const edited = { micro_value: { top_n: 0 } }
    expect(paramOverrides(edited, DEFAULTS)).toEqual({ micro_value: { top_n: 0 } })
  })
})

describe('isOverridden(单键「已改」判定 — 表单高亮与提交 diff 同语义)', () => {
  it('null(InputNumber 清空) = 用默认 → false', () => {
    expect(isOverridden(null, 5)).toBe(false)
  })

  it('空串 / 纯空白串 = 用默认 → false', () => {
    expect(isOverridden('', 'close')).toBe(false)
    expect(isOverridden('   ', 'close')).toBe(false)
  })

  it('数值等于默认 → false; 改成别的数 → true', () => {
    expect(isOverridden(5, 5)).toBe(false)
    expect(isOverridden(7, 5)).toBe(true)
  })

  it('0 是真实改动(falsy 数值不与"空"混淆) → true; 默认本就是 0 → false', () => {
    expect(isOverridden(0, 20)).toBe(true)
    expect(isOverridden(0, 0)).toBe(false)
  })

  it('字符串 trim 后与默认相等("close " ≡ "close") → false', () => {
    expect(isOverridden('close ', 'close')).toBe(false)
    expect(isOverridden(' close', 'close')).toBe(false)
  })

  it('字符串改成别的值 → true(含仅由 trim 归一后的不同值)', () => {
    expect(isOverridden('open', 'close')).toBe(true)
    expect(isOverridden(' open ', 'close')).toBe(true)
  })

  it('类型不同(字符串 "5" vs 数值 5)严格比较 → true(与提交 diff 一致)', () => {
    expect(isOverridden('5', 5)).toBe(true)
  })
})

describe('editableParams(default_params → 可编辑参数归一化)', () => {
  it('数值保持 number 且 numeric=true（走 NInputNumber）', () => {
    expect(editableParams({ fast_period: 5, ratio: 0.5 })).toEqual([
      { key: 'fast_period', def: 5, numeric: true },
      { key: 'ratio', def: 0.5, numeric: true },
    ])
  })

  it('字符串 numeric=false（走 NInput）', () => {
    expect(editableParams({ price_field: 'close' })).toEqual([
      { key: 'price_field', def: 'close', numeric: false },
    ])
  })

  it('布尔转字符串编辑（"true"/"false", 对等旧版文本框行为）', () => {
    expect(editableParams({ enabled: true })).toEqual([
      { key: 'enabled', def: 'true', numeric: false },
    ])
  })

  it('null / 嵌套 dict / 数组 不生成输入行（对等旧版过滤）', () => {
    expect(editableParams({ a: null, b: { x: 1 }, c: [1, 2], d: 5 })).toEqual([
      { key: 'd', def: 5, numeric: true },
    ])
  })
})
