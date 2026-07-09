import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { STATUS_LABEL, TERMINAL_STATUS, durationOf, jobTypeLabel, paramsSummary } from '../format'

describe('STATUS_LABEL / TERMINAL_STATUS', () => {
  it('五态中文映射对等旧 jobs.js', () => {
    expect(STATUS_LABEL).toEqual({
      queued: '排队中',
      running: '运行中',
      succeeded: '已完成',
      failed: '失败',
      canceled: '已取消',
    })
  })

  it('终态集合为 succeeded/failed/canceled', () => {
    expect([...TERMINAL_STATUS].sort()).toEqual(['canceled', 'failed', 'succeeded'])
  })
})

describe('jobTypeLabel', () => {
  it('五个后端 job_type 中译(对齐 manager.submit 调用点)', () => {
    expect(jobTypeLabel('backtest')).toBe('回测')
    expect(jobTypeLabel('factor_test')).toBe('因子检验')
    expect(jobTypeLabel('data_refresh')).toBe('数据刷新')
    expect(jobTypeLabel('ml_train')).toBe('ML 训练')
    expect(jobTypeLabel('ml_evaluate')).toBe('ML 评估')
  })

  it('ml_eval 别名同映射(计划书写法)', () => {
    expect(jobTypeLabel('ml_eval')).toBe('ML 评估')
  })

  it('未知类型回退原码(后端新增类型前端不崩)', () => {
    expect(jobTypeLabel('compare')).toBe('compare')
    expect(jobTypeLabel('')).toBe('')
  })
})

describe('durationOf', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-07-04T10:00:00'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('未开始显 "-"', () => {
    expect(durationOf({ started_at: null, finished_at: null })).toBe('-')
  })

  it('<90s 显整秒', () => {
    expect(
      durationOf({ started_at: '2026-07-04T09:58:31', finished_at: '2026-07-04T10:00:00' }),
    ).toBe('89s')
  })

  it('90s 整落分钟档(一位小数)', () => {
    expect(
      durationOf({ started_at: '2026-07-04T09:58:30', finished_at: '2026-07-04T10:00:00' }),
    ).toBe('1.5min')
  })

  it('未结束用当前时间(运行中在跑秒)', () => {
    expect(durationOf({ started_at: '2026-07-04T09:59:15', finished_at: null })).toBe('45s')
  })

  it('时钟倒挂下夹到 0s', () => {
    expect(durationOf({ started_at: '2026-07-04T10:01:00', finished_at: null })).toBe('0s')
  })
})

describe('paramsSummary', () => {
  it('strategies/日期区间 拼装', () => {
    expect(
      paramsSummary({
        params: { strategies: ['micro_value'], start_date: '2024-01-01', end_date: '2024-06-30' },
      }),
    ).toBe('micro_value · 2024-01-01~2024-06-30')
  })

  it('factors/model_name/objective 依旧序拼装', () => {
    expect(
      paramsSummary({
        params: { factors: 'P0', model_name: 'lgbm_return_5d', objective: 'long_only' },
      }),
    ).toBe('P0 · lgbm_return_5d · long_only')
  })

  it('symbols ≤2 全显, >2 缩写为 前2等N只', () => {
    expect(paramsSummary({ params: { symbols: '000001.SZ,600000.SH' } })).toBe(
      '000001.SZ,600000.SH',
    )
    expect(
      paramsSummary({ params: { symbols: ['000001.SZ', '600000.SH', '000002.SZ'] } }),
    ).toBe('000001.SZ,600000.SH等3只')
  })

  it('end_date 缺省显开区间', () => {
    expect(paramsSummary({ params: { start_date: '2024-01-01' } })).toBe('2024-01-01~')
  })

  it('总长截 90 字', () => {
    const long = paramsSummary({ params: { factors: 'x'.repeat(200) } })
    expect(long).toHaveLength(90)
  })

  it('空参数返回空串', () => {
    expect(paramsSummary({ params: {} })).toBe('')
  })
})
