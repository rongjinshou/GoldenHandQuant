import { describe, expect, it } from 'vitest'

import type { BacktestRun, BacktestStrategy, StrategyMeta } from '@/api/types'

import { buildRunLabel, friendlyStrategyName, sourceLabel } from '../run-naming'

/* run 业务化命名 — 根治"全是日期看不懂业务"(设计 0705 §3.B) */

function mkStrat(o: Partial<BacktestStrategy> = {}): BacktestStrategy {
  return {
    strategy: 'DualMaStrategy',
    start_date: '2024-01-01',
    end_date: '2025-12-31',
    initial_capital: 1000,
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

function mkRun(strategies: BacktestStrategy[], run_id = '20260614-103252'): BacktestRun {
  return { run_id, created_at: '2026-06-14 10:32:52.100000', strategies }
}

function mkMeta(o: Partial<StrategyMeta> = {}): StrategyMeta {
  return {
    name: 'dual_ma',
    strategy_type: 'bar',
    description: 'DualMa 双均线策略 (MA5/MA10 金叉死叉)',
    default_params: {},
    ...o,
  }
}

describe('sourceLabel', () => {
  it('已知来源(实际源码枚举)译中文, 未知来源原样透出, 空值兜底"未知来源"', () => {
    expect(sourceLabel('compare_strategies')).toBe('多策略对比')
    expect(sourceLabel('run_backtest')).toBe('CLI 单次回测')
    expect(sourceLabel('f01_investability')).toBe('F01 可投性验证')
    expect(sourceLabel('shadow_paper')).toBe('影子盘')
    expect(sourceLabel('mystery_source')).toBe('mystery_source')
    expect(sourceLabel(null)).toBe('未知来源')
    expect(sourceLabel(undefined)).toBe('未知来源')
  })
})

describe('friendlyStrategyName（策略显示名解析 — 轮次列表标题与表单勾选框共用）', () => {
  const meta = [
    mkMeta({ name: 'dual_ma', description: 'DualMa 双均线策略 (MA5/MA10 金叉死叉)' }),
    mkMeta({ name: 'micro_value', description: '微盘价值质量增强策略' }),
    mkMeta({ name: 'ml_return_prediction', description: 'ML 收益预测选股策略（LightGBM）' }),
  ]

  it('取 description 括号前首短语', () => {
    expect(friendlyStrategyName('dual_ma', meta)).toBe('DualMa 双均线策略')
  })

  it('description 无括号时整句照用', () => {
    expect(friendlyStrategyName('micro_value', meta)).toBe('微盘价值质量增强策略')
  })

  it('全角括号（）同样截断', () => {
    expect(friendlyStrategyName('ml_return_prediction', meta)).toBe('ML 收益预测选股策略')
  })

  it('meta 查不到时回退传入名本身(不炸)', () => {
    expect(friendlyStrategyName('unknown_strategy', meta)).toBe('unknown_strategy')
  })

  it('description 为空时回退代码名(勾选框主文字不渲染成空)', () => {
    const bare = [mkMeta({ name: 'dual_ma', description: '' })]
    expect(friendlyStrategyName('dual_ma', bare)).toBe('dual_ma')
  })

  it('description 以括号起头(首短语截出空串)同样回退代码名', () => {
    const weird = [mkMeta({ name: 'dual_ma', description: '（仅括号补充说明）' })]
    expect(friendlyStrategyName('dual_ma', weird)).toBe('dual_ma')
  })
})

describe('buildRunLabel', () => {
  const meta = [
    mkMeta({ name: 'dual_ma', strategy_type: 'bar', description: 'DualMa 双均线策略 (MA5/MA10 金叉死叉)' }),
    mkMeta({ name: 'micro_value', strategy_type: 'cross_section', description: '微盘价值质量增强策略' }),
  ]

  it('时序策略(标的非空): 策略名 · 首标的 · 区间年份', () => {
    const run = mkRun([
      mkStrat({
        strategy: 'DualMaStrategy',
        params: { strategies: ['dual_ma'], symbols: ['000021.SZ'], source: 'compare_strategies' },
      }),
    ])
    const label = buildRunLabel(run, meta)
    expect(label.title).toBe('DualMa 双均线策略 · 000021.SZ · 2024→2025')
    // 副标题保留年份(P8): 跨年可分辨 2025/2026, 不再 slice 省年
    expect(label.subtitle).toBe('多策略对比 · 2026-06-14 10:32')
  })

  it('截面策略: 对象范围显"全市场", 标的框不生效', () => {
    const run = mkRun([
      mkStrat({
        strategy: 'MicroValueStrategy',
        params: { strategies: ['micro_value'], source: 'run_backtest' },
      }),
    ])
    expect(buildRunLabel(run, meta).title).toBe('微盘价值质量增强策略 · 全市场 · 2024→2025')
  })

  it('多标的: 首标的 + 等N只', () => {
    const run = mkRun([
      mkStrat({
        params: { strategies: ['dual_ma'], symbols: ['000021.SZ', '000001.SZ', '600000.SH'] },
      }),
    ])
    expect(buildRunLabel(run, meta).title).toContain('000021.SZ 等3只')
  })

  it('同起止年份不显箭头, 直接年份', () => {
    const run = mkRun([
      mkStrat({ start_date: '2025-01-01', end_date: '2025-06-30', params: { strategies: ['dual_ma'] } }),
    ])
    expect(buildRunLabel(run, meta).title).toContain('· 2025')
    expect(buildRunLabel(run, meta).title).not.toContain('→')
  })

  it('多策略(>2): 显前2个 + 等N项', () => {
    const run = mkRun([
      mkStrat({ params: { strategies: ['dual_ma', 'micro_value', 'dual_ma'] } }),
    ])
    expect(buildRunLabel(run, meta).title).toContain('等3项')
  })

  it('无 params.strategies(旧 CLI 行) 回退用类名', () => {
    const run = mkRun([mkStrat({ strategy: 'DualMaStrategy', params: {} })])
    expect(buildRunLabel(run, meta).title).toContain('DualMaStrategy')
  })

  it('单数 params.strategy(run_backtest.py/run_f01_investability.py 用此键): 截面判定不漏判', () => {
    const run = mkRun([
      mkStrat({
        strategy: 'MicroValueStrategy',
        params: { strategy: 'micro_value', source: 'f01_investability', top_n: 9 },
      }),
    ])
    const label = buildRunLabel(run, meta)
    // 根治 bug: 曾因只认复数 strategies 键, 漏判 cross_section 而误显"默认标的"
    expect(label.title).toBe('微盘价值质量增强策略 · 全市场 · 2024→2025')
    expect(label.subtitle).toBe('F01 可投性验证 · 2026-06-14 10:32')
  })

  it('meta 查不到策略名 → 全市场/默认标的兜底不炸', () => {
    const run = mkRun([mkStrat({ params: { strategies: ['unknown'] } })])
    const label = buildRunLabel(run, [])
    expect(label.title).toBe('unknown · 默认标的 · 2024→2025')
  })

  it('影子盘(shadow_paper_equity.py 无 source/strategies/symbols, 只有 kind+universe): 不炸且来源可辨', () => {
    const run = mkRun(
      [
        mkStrat({
          strategy: 'MicroValueStrategy',
          start_date: '2026-06-01',
          end_date: '2026-07-04',
          params: { kind: 'shadow_paper_equity', universe: 'mainboard', top_n: 20 },
        }),
      ],
      'SHADOW-PAPER-20260704',
    )
    const label = buildRunLabel(run, meta)
    expect(label.title).toBe('MicroValueStrategy · 主板抽样池 · 2026')
    expect(label.subtitle).toBe('影子盘 · 2026-06-14 10:32')
  })
})
