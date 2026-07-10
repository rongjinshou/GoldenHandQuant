import { describe, expect, it } from 'vitest'

import { resultRoute } from '../result-route'

/* 五类型×五状态全矩阵: 只有 succeeded 的 backtest/factor_test 给结果落点 */
const JOB_TYPES = ['backtest', 'factor_test', 'data_refresh', 'ml_train', 'ml_evaluate'] as const
const NON_SUCCEEDED = ['queued', 'running', 'failed', 'canceled'] as const

describe('resultRoute', () => {
  it('succeeded: backtest→回测页, factor_test→判决页', () => {
    expect(resultRoute('backtest', 'succeeded')).toEqual({ name: 'backtests' })
    expect(resultRoute('factor_test', 'succeeded')).toEqual({ name: 'verdicts' })
  })

  it('succeeded 但无结果页的类型(data_refresh/ml_train/ml_evaluate)不给链接', () => {
    expect(resultRoute('data_refresh', 'succeeded')).toBeNull()
    expect(resultRoute('ml_train', 'succeeded')).toBeNull()
    expect(resultRoute('ml_evaluate', 'succeeded')).toBeNull()
  })

  it('非 succeeded 一律 null(五类型×四状态矩阵)', () => {
    for (const jobType of JOB_TYPES) {
      for (const status of NON_SUCCEEDED) {
        expect(resultRoute(jobType, status), `${jobType} × ${status}`).toBeNull()
      }
    }
  })

  it('未知类型/未知状态回退 null, 后端新增类型前端不崩', () => {
    expect(resultRoute('shadow_replay', 'succeeded')).toBeNull()
    expect(resultRoute('backtest', 'weird')).toBeNull()
    expect(resultRoute('', '')).toBeNull()
  })
})
