import { describe, expect, it } from 'vitest'

import { buildEvalRequest, buildTrainRequest, type MlTrainInput } from '../ml-forms'

const FULL: MlTrainInput = {
  start: '2021-01-01',
  end: '2024-12-31',
  symbols: '000300.SH',
  model: 'lgbm_return_5d',
  trials: 50,
}

describe('buildTrainRequest(R7 ML 训练载荷收口)', () => {
  it('全默认输入 → ok, 载荷五键齐备且无空值(与旧提交体等价, 行为不回归)', () => {
    const r = buildTrainRequest(FULL)
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.payload).toEqual({
      start_date: '2021-01-01',
      end_date: '2024-12-31',
      symbols: '000300.SH',
      model_name: 'lgbm_return_5d',
      n_trials: 50,
    })
    expect(Object.values(r.payload).every((v) => v !== '')).toBe(true)
  })

  it.each<[string, MlTrainInput]>([
    ['start 清空(clearable 置 null)', { ...FULL, start: null }],
    ['end 清空', { ...FULL, end: null }],
    ['双清空', { ...FULL, start: null, end: null }],
    ['空串(旧实现 ?? 兜底的 422 输入形态)', { ...FULL, start: '', end: '' }],
    ['纯空白', { ...FULL, start: '  ' }],
  ])('%s → 不放行(不再发出会撞 422 的载荷), 提示训练起止必填', (_name, input) => {
    const r = buildTrainRequest(input)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('训练起止日期均必填')
  })

  it.each([
    ['模型名清空', ''],
    ['模型名纯空白', '   '],
  ])('%s → 拦截(后端 pattern ^[A-Za-z0-9_\\-]{1,64}$ 空串必 422)', (_name, model) => {
    const r = buildTrainRequest({ ...FULL, model })
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('模型名必填')
  })

  it('symbols 留空省键 → 后端默认 000300.SH 生效(旧实现发空串必 422)', () => {
    const r = buildTrainRequest({ ...FULL, symbols: '  ' })
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect('symbols' in r.payload).toBe(false)
  })

  it('n_trials 清空省键 → 后端默认 50 生效(旧实现 Number(null)=0 撞 ge=1 必 422)', () => {
    const r = buildTrainRequest({ ...FULL, trials: null })
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect('n_trials' in r.payload).toBe(false)
  })

  it('trim 净化: 各串字段带空白时收敛为纯串入荷', () => {
    const r = buildTrainRequest({
      ...FULL,
      start: ' 2021-01-01 ',
      symbols: ' 000300.SH ',
      model: ' lgbm_return_5d ',
    })
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.payload.start_date).toBe('2021-01-01')
    expect(r.payload.symbols).toBe('000300.SH')
    expect(r.payload.model_name).toBe('lgbm_return_5d')
  })
})

describe('buildEvalRequest(R7 ML 评估载荷收口)', () => {
  it('三字段齐备 → ok, 载荷恰含三个非空键(与旧提交体等价)', () => {
    const r = buildEvalRequest('lgbm_return_5d', '2025-01-01', '2025-12-31')
    expect(r).toEqual({
      ok: true,
      payload: { model_name: 'lgbm_return_5d', eval_start: '2025-01-01', eval_end: '2025-12-31' },
    })
  })

  it.each<[string, string, string | null, string | null]>([
    ['eval_start 清空', 'lgbm_return_5d', null, '2025-12-31'],
    ['eval_end 清空', 'lgbm_return_5d', '2025-01-01', null],
    ['双清空', 'lgbm_return_5d', null, null],
    ['空串形态', 'lgbm_return_5d', '', ''],
  ])('%s → 不放行, 提示评估起止必填', (_name, model, s, e) => {
    const r = buildEvalRequest(model, s, e)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('评估起止日期均必填')
  })

  it('模型名清空 → 拦截(MlEvaluateJobRequest.model_name 必填无默认)', () => {
    const r = buildEvalRequest('', '2025-01-01', '2025-12-31')
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('模型名必填')
  })

  it('日期校验先于模型名: 双缺时报日期(与表单字段顺序一致)', () => {
    const r = buildEvalRequest('', null, null)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.error).toContain('评估起止日期均必填')
  })
})
