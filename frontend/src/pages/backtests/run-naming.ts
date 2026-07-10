/* run 业务化命名(纯展示层, 不入库) — 设计 docs/feat/0705-research-narrative §3.B。
 * 根治"全是日期看不懂业务": 列表主标题从参数生成人话摘要, 机器 run_id 降级副行小字。 */

import type { BacktestRun, StrategyMeta } from '@/api/types'

import { firstStrategy } from './chart-data'

/* 回测提交来源枚举(实际取值逐一核对源码: compare_strategies.py/run_backtest.py/
 * commands/backtest.py/scripts/run_f01_investability.py/shadow_paper_equity.py;
 * 网页提交经 job_commands.build_backtest_argv 走 compare_strategies, 无独立 'web' 来源) → 中文 */
const SOURCE_LABELS: Record<string, string> = {
  compare_strategies: '多策略对比',
  run_backtest: 'CLI 单次回测',
  'quant backtest': 'CLI 单次回测',
  f01_investability: 'F01 可投性验证',
  shadow_paper: '影子盘',
}

export function sourceLabel(source: string | null | undefined): string {
  if (!source) return '未知来源'
  return SOURCE_LABELS[source] ?? source
}

const UNIVERSE_LABELS: Record<string, string> = { mainboard: '主板' }

/* meta description 首短语(括号前部分) — 单一来源于 /api/meta/strategies,
 * 不在前端另写映射表以免随后端策略增减漂移; 查不到时回退传入名本身。
 * 轮次列表标题与表单策略勾选框共用此函数(单一真相源, 两处显示名保持一致);
 * description 为空/纯括号时同样回退代码名, 勾选框主文字不至于渲染成空。 */
export function friendlyStrategyName(metaName: string, meta: StrategyMeta[]): string {
  const m = meta.find((x) => x.name === metaName)
  if (!m) return metaName
  return m.description.split(/[（(]/)[0].trim() || metaName
}

export interface RunLabel {
  /* 业务人话标题: 策略 · 对象范围 · 区间年份 */
  title: string
  /* 副行: 来源 · 短时间戳 */
  subtitle: string
}

/* run 业务化标题 — 优先用 params.strategies(compare_strategies.py/网页提交, 数组);
 * 单策略 CLI(run_backtest.py/run_f01_investability.py) 写的是单数 params.strategy(字符串),
 * 两种键都要认, 否则单策略轮次的截面判定(anyCross)会漏判成"默认标的"。
 * 都缺省(如旧 CLI 行无 params)回退 strategies[].strategy(类名, 如 DualMaStrategy)。 */
export function buildRunLabel(run: BacktestRun, meta: StrategyMeta[]): RunLabel {
  const first = firstStrategy(run) ?? run.strategies[0]
  const metaNames =
    (first?.params?.strategies as string[] | undefined) ??
    (typeof first?.params?.strategy === 'string' ? [first.params.strategy] : [])
  const classNames = run.strategies.map((s) => s.strategy)
  const names = metaNames.length ? metaNames.map((n) => friendlyStrategyName(n, meta)) : classNames

  const shown = names.slice(0, 2).join(' + ')
  const more = names.length > 2 ? ` 等${names.length}项` : ''
  const strategyPart = shown || '未知策略'

  const anyCross = metaNames.some(
    (n) => meta.find((m) => m.name === n)?.strategy_type === 'cross_section',
  )
  const symbols = (first?.params?.symbols as string[] | undefined) ?? []
  const universe =
    typeof first?.params?.universe === 'string' ? (first.params.universe as string) : undefined
  const scopePart = anyCross
    ? '全市场'
    : symbols.length
      ? `${symbols[0]}${symbols.length > 1 ? ` 等${symbols.length}只` : ''}`
      : universe
        ? `${UNIVERSE_LABELS[universe] ?? universe}抽样池`
        : '默认标的'

  const y0 = first?.start_date?.slice(0, 4) ?? '?'
  const y1 = first?.end_date?.slice(0, 4) ?? '?'
  const rangePart = y0 === y1 ? y0 : `${y0}→${y1}`

  const title = `${strategyPart}${more} · ${scopePart} · ${rangePart}`
  // 影子盘脚本(shadow_paper_equity.py)params 无 source 字段, 用 kind 判定来源
  const rawSource = first?.params?.source
  const kind = first?.params?.kind
  const source =
    (typeof rawSource === 'string' && rawSource) ||
    (kind === 'shadow_paper_equity' ? 'shadow_paper' : undefined)
  // 副标题日期保留年份(设计 §12 P8): 原 slice(5,16) 省年, 跨年无法分辨 2025/2026;
  // slice(0,16) 取 'YYYY-MM-DD HH:mm' 完整到分钟
  const subtitle = `${sourceLabel(source)} · ${(run.created_at ?? '').slice(0, 16)}`
  return { title, subtitle }
}
