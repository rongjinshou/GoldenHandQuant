/* 判决轮次业务化命名(纯展示层, 不入库) — 设计 docs/feat/0705-research-narrative §3.B。
 * 同回测页道理: 下拉不再只有 run_id, 主标题讲"检验了几个因子/什么口径/切分在哪"。 */

import type { VerdictRun } from '@/api/types'

/* 记分牌口径词汇与页内 metaItems/objective gloss 保持一致(长多/多空), 见 Verdicts.vue */
export function objectiveLabel(o: string | null | undefined): string {
  if (o === 'long_only') return '长多'
  if (o === 'long_short') return '多空'
  return '?'
}

export interface VerdictRunLabel {
  title: string
  subtitle: string
}

export function buildVerdictRunLabel(run: VerdictRun): VerdictRunLabel {
  const n = run.factors.length
  const obj = objectiveLabel(run.params?.objective)
  const split = run.params?.split
  const splitPart = split ? `切分 ${split}` : '未切分'
  const title = `${n} 因子 · ${obj} · ${splitPart}`
  // 日期保留年份(slice(0,16)='YYYY-MM-DD HH:MM'): 省年会让跨年的同月日撞脸, 无法分辨。
  const subtitle = `${(run.created_at ?? '').slice(0, 16)} · ${run.run_id}`
  return { title, subtitle }
}
