import { describe, expect, it } from 'vitest'

import type {
  BacktestRun,
  BacktestStrategy,
  StrategyMeta,
  VerdictFactor,
  VerdictRun,
} from '@/api/types'

import { backtestActivity, latestOf, shortTime, verdictActivity } from '../recent-activity'

/* 总览「最近动态」发射台装配 — 最新轮判定 + 两卡格式化(口径同判决/回测页) */

function mkFactor(passed: boolean, id: string): VerdictFactor {
  return {
    factor_id: id,
    ic_mean: null,
    ir: null,
    ic_positive_rate: null,
    monotonicity_score: null,
    long_short_return: null,
    oos_ic_mean: null,
    oos_ir: null,
    oos_long_short_return: null,
    excess_ir: null,
    excess_positive_rate: null,
    top_excess_return: null,
    oos_top_excess_return: null,
    score: null,
    grade: null,
    passed,
    reasons: null,
  }
}

function mkVerdictRun(o: Partial<VerdictRun> = {}): VerdictRun {
  return {
    run_id: 'MFCOMBO-20260708-093000',
    created_at: '2026-07-08 09:30:22.123456',
    params: { split: '2024-06-30' },
    factors: [mkFactor(true, 'a'), mkFactor(true, 'b'), mkFactor(false, 'c')],
    ...o,
  }
}

function mkStrat(o: Partial<BacktestStrategy> = {}): BacktestStrategy {
  return {
    strategy: 'MicroValueStrategy',
    start_date: '2024-01-01',
    end_date: '2025-12-31',
    initial_capital: 1000000,
    params: {},
    total_return: null,
    annualized_return: null,
    max_drawdown: null,
    sharpe_ratio: null,
    sortino_ratio: null,
    calmar_ratio: null,
    win_rate: null,
    trade_count: null,
    turnover_rate: null,
    equity_curve: {},
    trades: [],
    ...o,
  }
}

function mkBtRun(strategies: BacktestStrategy[]): BacktestRun {
  return { run_id: '20260708-101500', created_at: '2026-07-08 10:15:00.000000', strategies }
}

const META: StrategyMeta[] = [
  {
    name: 'micro_value',
    strategy_type: 'cross_section',
    description: '微盘价值质量增强策略',
    default_params: {},
  },
]

describe('latestOf', () => {
  it('空列表 → null', () => {
    expect(latestOf([])).toBeNull()
  })

  it('API 倒序(最新在首) → 取首条', () => {
    const runs = [
      { run_id: 'new', created_at: '2026-07-08 10:00:00' },
      { run_id: 'old', created_at: '2026-07-01 10:00:00' },
    ]
    expect(latestOf(runs)?.run_id).toBe('new')
  })

  it('不赌端序: 乱序仍按 created_at 取最大者', () => {
    const runs = [
      { run_id: 'old', created_at: '2026-07-01 10:00:00' },
      { run_id: 'new', created_at: '2026-07-08 10:00:00' },
      { run_id: 'mid', created_at: '2026-07-04 10:00:00' },
    ]
    expect(latestOf(runs)?.run_id).toBe('new')
  })

  it('created_at 并列 → 保持先出现者(稳定)', () => {
    const runs = [
      { run_id: 'a', created_at: '2026-07-08 10:00:00' },
      { run_id: 'b', created_at: '2026-07-08 10:00:00' },
    ]
    expect(latestOf(runs)?.run_id).toBe('a')
  })
})

describe('shortTime', () => {
  it('DB 空格分隔截到分钟', () => {
    expect(shortTime('2026-07-08 09:30:22.123456')).toBe('2026-07-08 09:30')
  })

  it('ISO T 分隔归一为空格', () => {
    expect(shortTime('2026-07-08T09:30:22')).toBe('2026-07-08 09:30')
  })

  it('空值兜底 —(不炸)', () => {
    expect(shortTime(null)).toBe('—')
    expect(shortTime(undefined)).toBe('—')
    expect(shortTime('')).toBe('—')
  })
})

describe('verdictActivity', () => {
  it('计数 PASS/FAIL + 切分日 + 入库时间截到分钟', () => {
    expect(verdictActivity(mkVerdictRun())).toEqual({
      runId: 'MFCOMBO-20260708-093000',
      factorCount: 3,
      passCount: 2,
      failCount: 1,
      splitText: '切分 2024-06-30',
      createdAt: '2026-07-08 09:30',
    })
  })

  it('无 split → 未切分(词汇同判决页); params 缺省不炸', () => {
    expect(verdictActivity(mkVerdictRun({ params: { split: null } })).splitText).toBe('未切分')
    expect(verdictActivity(mkVerdictRun({ params: null })).splitText).toBe('未切分')
  })

  it('零因子轮: 计数全 0 不炸', () => {
    const a = verdictActivity(mkVerdictRun({ factors: [] }))
    expect(a.factorCount).toBe(0)
    expect(a.passCount).toBe(0)
    expect(a.failCount).toBe(0)
  })
})

describe('backtestActivity', () => {
  it('标题复用 buildRunLabel(meta 命中人话名), 正收益 → 行情红 t-up', () => {
    const run = mkBtRun([
      mkStrat({
        params: { strategies: ['micro_value'], source: 'compare_strategies' },
        total_return: 0.1234,
        equity_curve: { dates: ['2024-01-02'], values: [1000000] },
      }),
    ])
    const a = backtestActivity(run, META)
    expect(a.runId).toBe('20260708-101500')
    expect(a.title).toBe('微盘价值质量增强策略 · 全市场 · 2024→2025')
    expect(a.ret).toEqual({ text: '12.34%', cls: 't-up' })
    expect(a.createdAt).toBe('2026-07-08 10:15')
  })

  it('负收益 → 行情绿 t-down', () => {
    const run = mkBtRun([mkStrat({ total_return: -0.05 })])
    expect(backtestActivity(run, META).ret).toEqual({ text: '-5.00%', cls: 't-down' })
  })

  it('总收益缺失(旧 CLI 行) → "-" 中性灰', () => {
    const run = mkBtRun([mkStrat({ total_return: null })])
    expect(backtestActivity(run, META).ret).toEqual({ text: '-', cls: 't-muted' })
  })

  it('meta 未载(拉取失败降级) → 标题回退原始名不炸', () => {
    const run = mkBtRun([mkStrat({ params: { strategies: ['micro_value'] } })])
    expect(backtestActivity(run, []).title).toContain('micro_value')
  })

  it('多策略混曲线: 总收益取首个有曲线策略(同回测页 firstStrategy 口径)', () => {
    const run = mkBtRun([
      mkStrat({ strategy: 'NoCurve', total_return: 0.9, equity_curve: {} }),
      mkStrat({
        strategy: 'WithCurve',
        total_return: 0.05,
        equity_curve: { dates: ['2024-01-02'], values: [1000000] },
      }),
    ])
    expect(backtestActivity(run, []).ret.text).toBe('5.00%')
  })
})
