<script setup lang="ts">
import { NButton, NDatePicker, NInputNumber, NSelect } from 'naive-ui'
import { computed, ref } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job, MetaFactor, VerdictFactor, VerdictRun } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'

import { f2, f3, f4, gateClass, gradeClass, pct } from './verdicts/gates'
import { buildVerdictRunLabel } from './verdicts/run-naming'

/* 因子判决页 — 旧 pages/verdicts.js 对等:
 * 判决轮次下拉 + meta 条 + objective 切换联动表头/指标/格式化 + reasons 行;
 * 因子检验表单(分组 chips/P0 默认勾/field_ready 禁用/多重检验提示) + JobCard 闭环。 */

const error = ref('')
const loading = ref(true)
const runs = ref<VerdictRun[]>([])
const selectedIdx = ref(0)
// 提前声明: loadVerdicts 成功回调里预填(声明本体在表单区块会触发 TDZ/lint)
const ftSplit = ref<string | null>(null)

async function loadVerdicts(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: VerdictRun[] }>('/api/research/verdicts')
    runs.value = data.runs
    selectedIdx.value = 0
    error.value = ''
    // 检验表单预填最近一轮的切分日 — 消除进页即报"多重检验风险"的常驻警告
    const lastSplit = runs.value[0]?.params?.split
    if (!ftSplit.value && typeof lastSplit === 'string' && lastSplit) ftSplit.value = lastSplit
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

void loadVerdicts()

const run = computed(() => runs.value[selectedIdx.value] ?? null)
const longOnly = computed(() => run.value?.params?.objective === 'long_only')

/* 业务化标题(设计 0705 §3.B): "N 因子 · 口径 · 切分日" 为主, 时间+run_id 收尾括号 —
 * 根治"下拉全是 MFCOMBO-日期, 看不懂业务"(用户原话) */
const runOptions = computed(() =>
  runs.value.map((r, i) => {
    const label = buildVerdictRunLabel(r)
    return { label: `${label.title}（${(r.created_at ?? '').slice(5, 16)} · ${r.run_id}）`, value: i }
  }),
)

// ---- reasons 降噪: 失败项常驻红 chip, 通过项折叠为摘要, 行点击展开全量 ----
const expanded = ref<Set<string>>(new Set())

function toggleExpand(id: string): void {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function isPassReason(r: string): boolean {
  // 后端 verdict.py 用 '✓'(U+2713); 兼容 '√'(U+221A) 防历史数据
  return r.includes('✓') || r.includes('√')
}

function failedReasons(f: VerdictFactor): string[] {
  return (f.reasons ?? []).filter((r) => !isPassReason(r))
}

function passedCount(f: VerdictFactor): number {
  return (f.reasons ?? []).filter(isPassReason).length
}

const metaItems = computed(() => {
  const p = run.value?.params ?? {}
  return [
    { label: '区间', value: `${p.start ?? '?'} → ${p.end ?? '?'}` },
    { label: '切分', value: p.split ?? '无', gloss: 'split_date' },
    { label: '调仓', value: `${p.rebalance_days ?? 1} 日`, gloss: 'rebalance' },
    { label: '记分牌', value: longOnly.value ? '长多(Top超额)' : '多空', gloss: 'objective' },
    { label: '覆盖股票池', value: `${p.universe_count ?? '?'} 只`, gloss: 'universe_lineage' },
    { label: '特征', value: `v${p.feature_version ?? '?'}` },
  ]
})

/* objective 切换联动: 表头/取值字段/格式化 整体切换 */
interface Col {
  th: string
  gloss?: string
  cell: (f: VerdictFactor) => { text: string; cls: string }
}

function gcell(
  name: string,
  v: number | null | undefined,
  fmt: (x: number) => string,
): { text: string; cls: string } {
  return { text: v === null || v === undefined ? '-' : fmt(v), cls: gateClass(name, v) }
}

const columns = computed<Col[]>(() => [
  { th: 'IC均值', gloss: 'ic', cell: (f) => gcell('ic_mean', f.ic_mean, f4) },
  longOnly.value
    ? { th: '超额IR', gloss: 'ir', cell: (f) => gcell('excess_ir', f.excess_ir, f2) }
    : { th: 'IR', gloss: 'ir', cell: (f) => gcell('ir', f.ir, f3) },
  longOnly.value
    ? {
        th: '超额正率',
        gloss: 'ic_posrate',
        cell: (f) => gcell('excess_positive_rate', f.excess_positive_rate, pct),
      }
    : {
        th: 'IC正率',
        gloss: 'ic_posrate',
        cell: (f) => gcell('ic_positive_rate', f.ic_positive_rate, pct),
      },
  {
    th: '单调性',
    gloss: 'monotonicity',
    cell: (f) => gcell('monotonicity_score', f.monotonicity_score, f2),
  },
  longOnly.value
    ? {
        th: 'Top超额(IS)',
        gloss: 'ls_is',
        cell: (f) => gcell('top_excess_return', f.top_excess_return, pct),
      }
    : {
        th: '多空(IS)',
        gloss: 'ls_is',
        cell: (f) => gcell('long_short_return', f.long_short_return, pct),
      },
  { th: 'OOS IC', gloss: 'oos_ic', cell: (f) => gcell('oos_ic_mean', f.oos_ic_mean, f4) },
  { th: 'OOS IR', gloss: 'oos_ir', cell: (f) => gcell('oos_ir', f.oos_ir, f3) },
  longOnly.value
    ? {
        th: 'Top超额(OOS)',
        gloss: 'ls_oos',
        cell: (f) => gcell('oos_top_excess_return', f.oos_top_excess_return, pct),
      }
    : {
        th: '多空(OOS)',
        gloss: 'ls_oos',
        cell: (f) => gcell('oos_long_short_return', f.oos_long_short_return, pct),
      },
])

// ---- 因子检验表单 ----
interface ChipGroup {
  group: string
  chips: { factor: MetaFactor; disabled: boolean }[]
}

const chipGroups = ref<ChipGroup[]>([])
const checked = ref<Set<string>>(new Set())

async function loadFactorMeta(): Promise<void> {
  try {
    const data = await fetchJSON<{ factors: MetaFactor[]; groups: Record<string, string[]> }>(
      '/api/meta/factors',
    )
    const byId = new Map(data.factors.map((f) => [f.factor_id, f]))
    chipGroups.value = Object.entries(data.groups).map(([group, ids]) => ({
      group,
      chips: ids
        .filter((id) => byId.has(id))
        .map((id) => ({ factor: byId.get(id)!, disabled: byId.get(id)!.field_ready === false })),
    }))
    // P0 组默认勾选(非禁用)
    const p0 = chipGroups.value.find((g) => g.group === 'P0')
    checked.value = new Set(p0?.chips.filter((c) => !c.disabled).map((c) => c.factor.factor_id))
  } catch (e) {
    error.value = (e as Error).message
  }
}

void loadFactorMeta()

function toggleChip(id: string, disabled: boolean): void {
  if (disabled) return
  const next = new Set(checked.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  checked.value = next
}

const ftStart = ref<string | null>(null)
const ftEnd = ref<string | null>(null)
const ftObjective = ref('long_only')
const ftLayers = ref(5)
const ftRebalance = ref(5)
const ftCost = ref(0.003)
const ftJobIds = ref<string[]>([])

const OBJECTIVE_OPTIONS = [
  { label: 'Top层纯多头超额 (long_only)', value: 'long_only' },
  { label: '多空价差 (long_short)', value: 'long_short' },
]

/* 多重检验提示: 多因子且未设切分 */
const ftHint = computed(() => checked.value.size > 1 && !ftSplit.value)

async function submitFactorTest(): Promise<void> {
  error.value = ''
  if (checked.value.size === 0) {
    error.value = '至少勾选一个因子'
    return
  }
  const payload: Record<string, unknown> = {
    factors: [...checked.value].join(','),
    start_date: ftStart.value ?? '',
    end_date: ftEnd.value ?? '',
    objective: ftObjective.value,
    num_layers: ftLayers.value,
    rebalance_days: ftRebalance.value,
    cost_rate: ftCost.value,
  }
  if (ftSplit.value) payload.split_date = ftSplit.value
  try {
    const job = await postJSON<Job>('/api/jobs/factor-test', payload)
    ftJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  }
}
</script>

<template>
  <section data-testid="page-verdicts">
    <header class="page-head">
      <h2>因子判决</h2>
      <NSelect
        v-if="runOptions.length"
        v-model:value="selectedIdx"
        :options="runOptions"
        size="small"
        style="width: 420px"
        data-testid="run-select"
      />
    </header>
    <p class="guide t-muted">
      每轮因子检验的预测力（IC/IR）、样本外表现与硬性闸门结论。<b class="t-pass">PASS</b>
      = 全部闸门通过；FAIL 行下方红色项即未过原因，点击行可展开全部判定明细。
    </p>

    <ErrorBanner v-if="error" :msg="error" />
    <p v-if="loading" class="t-muted">加载判决轮次…</p>
    <p v-else-if="!runs.length" class="t-muted" data-testid="verdicts-empty">
      暂无判决轮次 — 用下方表单提交一次因子检验。
    </p>

    <template v-if="run">
      <div class="meta-strip card">
        <span v-for="m in metaItems" :key="m.label" class="rm">
          <GlossaryTip v-if="m.gloss" :term="m.gloss"><i>{{ m.label }}</i></GlossaryTip>
          <i v-else>{{ m.label }}</i>
          <b>{{ m.value }}</b>
        </span>
      </div>

      <div class="list-head">
        <span class="list-title">因子明细</span>
        <span class="list-count num">{{ run.factors.length }} 个因子</span>
      </div>
      <div class="table-wrap card">
        <table>
          <thead>
            <tr>
              <th>因子</th>
              <th v-for="c in columns" :key="c.th" class="th-num">
                <GlossaryTip v-if="c.gloss" :term="c.gloss">{{ c.th }}</GlossaryTip>
                <template v-else>{{ c.th }}</template>
              </th>
              <th><GlossaryTip term="score">评分</GlossaryTip></th>
              <th><GlossaryTip term="verdict_badge">判决</GlossaryTip></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="f in run.factors" :key="f.factor_id">
              <!-- 主行: 因子(id+名称合并一格), 点击切换判定明细展开 -->
              <tr class="factor-row" @click="toggleExpand(f.factor_id)">
                <td class="factor-cell" :title="f.expression ?? ''">
                  <span class="fx num">{{ expanded.has(f.factor_id) ? '▾' : '▸' }}</span>
                  <span class="factor-id-name">
                    <span class="fid num">{{ f.factor_id }}</span>
                    <span class="fname">{{ f.factor_name ?? '' }}</span>
                  </span>
                </td>
                <td v-for="c in columns" :key="c.th" class="num" :class="c.cell(f).cls">
                  {{ c.cell(f).text }}
                </td>
                <td class="score-cell">
                  <template v-if="f.score !== null && f.score !== undefined">
                    <span class="score-num num">{{ f.score.toFixed(0) }}</span>
                    <span v-if="f.grade" class="grade" :class="gradeClass(f.grade)">{{
                      f.grade.toUpperCase()
                    }}</span>
                  </template>
                  <span v-else class="gate-na">-</span>
                </td>
                <td>
                  <GlossaryTip :term="f.passed ? 'verdict_pass' : 'verdict_fail'" plain>
                    <span class="badge" :class="f.passed ? 'pass' : 'fail'">{{
                      f.passed ? 'PASS' : 'FAIL'
                    }}</span>
                  </GlossaryTip>
                </td>
              </tr>
              <!-- 明细行: 折叠=失败项红chip+通过摘要; 展开=表达式+全部判定chips -->
              <tr class="reasons-row">
                <td :colspan="columns.length + 3">
                  <template v-if="expanded.has(f.factor_id)">
                    <code v-if="f.expression" class="expr num">{{ f.expression }}</code>
                    <span
                      v-for="(r, ri) in f.reasons ?? []"
                      :key="ri"
                      class="reason"
                      :class="isPassReason(r) ? 'r-pass' : 'r-fail'"
                    >{{ r }}</span>
                  </template>
                  <template v-else>
                    <span v-for="(r, ri) in failedReasons(f)" :key="ri" class="reason r-fail">{{ r }}</span>
                    <span v-if="passedCount(f) > 0" class="reason r-summary">
                      ✓ {{ failedReasons(f).length ? `其余 ${passedCount(f)} 项通过` : `全部 ${passedCount(f)} 项通过` }}
                    </span>
                  </template>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>

    <details class="card form-card" open>
      <summary>因子检验</summary>
      <div v-for="g in chipGroups" :key="g.group" class="factor-group" data-testid="ft-factors">
        <GlossaryTip term="factor_group"><span class="group-title">{{ g.group }}</span></GlossaryTip>
        <div class="fchips">
          <button
            v-for="c in g.chips"
            :key="c.factor.factor_id"
            type="button"
            class="fchip"
            :class="{ checked: checked.has(c.factor.factor_id), disabled: c.disabled }"
            :title="(c.factor.expression ?? '') + (c.disabled ? '（数据管道缺字段，禁用）' : '')"
            data-testid="ft-factor-chip"
            @click="toggleChip(c.factor.factor_id, c.disabled)"
          >
            <span class="fchip-id">{{ c.factor.factor_id }}</span>
            <span class="fchip-name">{{ c.factor.name }}</span>
          </button>
        </div>
      </div>

      <div class="form-row">
        <label>起始 <NDatePicker v-model:formatted-value="ftStart" value-format="yyyy-MM-dd" type="date" clearable /></label>
        <label>结束 <NDatePicker v-model:formatted-value="ftEnd" value-format="yyyy-MM-dd" type="date" clearable /></label>
        <label><GlossaryTip term="split_date">IS/OOS 切分</GlossaryTip> <NDatePicker v-model:formatted-value="ftSplit" value-format="yyyy-MM-dd" type="date" clearable /></label>
        <label><GlossaryTip term="objective">记分牌</GlossaryTip> <NSelect v-model:value="ftObjective" :options="OBJECTIVE_OPTIONS" style="width: 220px" /></label>
        <label><GlossaryTip term="layers">分层</GlossaryTip> <NInputNumber v-model:value="ftLayers" :min="2" :max="10" style="width: 90px" /></label>
        <label><GlossaryTip term="rebalance">调仓(日)</GlossaryTip> <NInputNumber v-model:value="ftRebalance" :min="1" style="width: 90px" /></label>
        <label><GlossaryTip term="cost_rate">成本率</GlossaryTip> <NInputNumber v-model:value="ftCost" :step="0.001" style="width: 110px" /></label>
        <NButton type="primary" data-testid="ft-submit" @click="submitFactorTest">提交检验</NButton>
      </div>
      <p v-if="ftHint" class="t-warn hint">
        多因子批量检验未设 IS/OOS 切分——存在多重检验风险，建议保留切分日期。
      </p>
      <div data-testid="ft-job-area">
        <JobCard v-for="id in ftJobIds" :key="id" :job-id="id" @done="() => loadVerdicts()" />
      </div>
    </details>
  </section>
</template>

<style scoped>
.page-head {
  align-items: center;
  display: flex;
  gap: 14px;
  margin-bottom: 6px;
}

.page-head h2 {
  margin: 0;
}

.guide {
  font-size: 13px;
  margin: 0 0 var(--gap);
}

.meta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 22px;
  margin-bottom: var(--gap);
  padding: 10px 16px;
}

.rm i {
  color: var(--text-3);
  font-size: 12px;
  font-style: normal;
  margin-right: 6px;
}

.rm b {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
}

.list-head {
  align-items: baseline;
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
  padding: 0 2px;
}

.list-title {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.list-count {
  background: var(--bg-3);
  border-radius: 10px;
  color: var(--text-2);
  font-size: 11.5px;
  padding: 1px 8px;
}

/* 限高滚动 + 粘性表头: 长因子表不再铺满整屏, 滚动时列名常驻 */
.table-wrap {
  margin-bottom: var(--gap);
  max-height: min(62vh, 620px);
  overflow: auto;
  padding: 0 10px;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th {
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 11.5px;
  padding: 8px 9px;
  position: sticky;
  top: 0;
  text-align: left;
  white-space: nowrap;
  z-index: 1;
}

td {
  font-size: 13px;
  padding: 7px 9px;
}

/* 数值列右对齐: 小数点纵向对位便于比较 */
th.th-num {
  text-align: right;
}

td.num {
  text-align: right;
}

/* 因子=一个视觉单元: 主行与明细行之间无线, 明细行下边框做因子分界 */
.factor-row {
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.factor-row:hover {
  background: var(--accent-soft);
}

.factor-cell {
  white-space: nowrap;
}

.fx {
  color: var(--text-3);
  display: inline-block;
  font-size: 11px;
  margin-right: 4px;
  width: 12px;
}

.factor-id-name {
  display: inline-flex;
  flex-direction: column;
  gap: 1px;
  vertical-align: middle;
}

.fid {
  font-size: 12.5px;
  font-weight: 600;
  text-align: left;
}

.fname {
  color: var(--text-3);
  font-size: 11.5px;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.reasons-row td {
  background: color-mix(in srgb, var(--bg-3) 36%, transparent);
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
  font-size: 11.5px;
  padding: 4px 9px 9px 25px;
}

.expr {
  color: var(--accent-blue);
  display: block;
  font-size: 11.5px;
  margin: 2px 0 6px;
  white-space: pre-wrap;
}

/* 判定 chips: 失败=红(为什么FAIL一眼可见), 通过=灰, 摘要=绿 */
.reason {
  border-radius: 4px;
  display: inline-block;
  font-size: 11px;
  line-height: 1.5;
  margin: 2px 6px 2px 0;
  padding: 1px 7px;
}

.r-fail {
  background: color-mix(in srgb, var(--c-fail) 12%, transparent);
  color: var(--c-fail);
}

.r-pass {
  background: var(--bg-3);
  color: var(--text-3);
}

.r-summary {
  background: color-mix(in srgb, var(--c-pass) 10%, transparent);
  color: var(--c-pass);
}

.gate-na {
  color: var(--text-3);
}

.score-cell {
  white-space: nowrap;
}

.score-num {
  font-weight: 600;
  margin-right: 6px;
}

.grade {
  border-radius: 4px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
}

.grade-a {
  background: color-mix(in srgb, var(--c-pass) 18%, transparent);
  color: var(--c-pass);
}

.grade-b {
  background: var(--bg-3);
  color: var(--text-2);
}

.grade-c {
  background: color-mix(in srgb, var(--c-warn) 18%, transparent);
  color: var(--c-warn);
}

.grade-d {
  background: color-mix(in srgb, var(--c-fail) 18%, transparent);
  color: var(--c-fail);
}

.badge {
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 10px;
}

.badge.pass {
  background: color-mix(in srgb, var(--c-pass) 16%, transparent);
  color: var(--c-pass);
}

.badge.fail {
  background: color-mix(in srgb, var(--c-fail) 16%, transparent);
  color: var(--c-fail);
}

.form-card summary {
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
}

.factor-group {
  align-items: baseline;
  display: flex;
  gap: 12px;
  margin: 12px 0;
}

.group-title {
  color: var(--accent);
  font-family: var(--font-display);
  font-size: 12.5px;
  font-weight: 700;
  min-width: 28px;
}

.fchips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fchip {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 16px;
  color: var(--text-2);
  cursor: pointer;
  font-size: 12px;
  padding: 4px 12px;
  transition:
    background var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.fchip:hover:not(.disabled) {
  border-color: var(--accent);
}

.fchip.checked {
  background: var(--accent);
  border-color: var(--accent);
  color: #faf9f5;
}

.fchip.disabled {
  border-style: dashed;
  cursor: not-allowed;
  opacity: 0.55;
  text-decoration: line-through;
}

.fchip-id {
  font-family: var(--font-mono);
  font-weight: 600;
  margin-right: 5px;
}

.form-row {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin: 14px 0;
}

.form-row label {
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
}

.hint {
  font-size: 12.5px;
}
</style>
