<script setup lang="ts">
import { NButton, NDatePicker, NInputNumber, NSelect } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job, MetaFactor } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'
import { GLOSSARY } from '@/glossary'

import { applyLastRun, toggleGroup } from './factor-selection'

/* 因子检验表单(设计 0705-verdict-cards §3) — 从 Verdicts.vue 抽取, 置顶页面第一屏;
 * 行为对旧版零改动: chips 分组/P0 默认勾/field_ready 禁用/多重检验提示/JobCard 闭环。
 * lastSplitHint: 父层最近一轮判决的切分日, 用于预填 IS/OOS 切分(消除进页即报
 * "多重检验风险"的常驻警告)。
 * lastRunFactorIds: 父层当前选中判决轮的因子集合 —「上轮同款」一键复用的数据源;
 * 无轮次时 null → 按钮禁用。 */
const props = defineProps<{
  lastSplitHint: string | null
  lastRunFactorIds?: readonly string[] | null
}>()
const emit = defineEmits<{ refresh: [] }>()

const error = ref('')

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
  applyNotice.value = null
}

// ---- 快捷组(P 标签整组切换 + 上轮同款; 集合运算在 factor-selection.ts) ----

const disabledIds = computed(
  () =>
    new Set(
      chipGroups.value.flatMap((g) =>
        g.chips.filter((c) => c.disabled).map((c) => c.factor.factor_id),
      ),
    ),
)
const availableIds = computed(
  () => new Set(chipGroups.value.flatMap((g) => g.chips.map((c) => c.factor.factor_id))),
)

/* P 标签已是真按钮, 不再套 GlossaryTip(其触发器本身是 role=button, 嵌套交互元素伤
 * 键盘可达) — 原 factor_group 术语释义并入原生 title 第二行, 教学不丢。 */
const groupToggleTitle = `点击全选/清空该组\n${GLOSSARY.factor_group ?? ''}`.trimEnd()

function toggleGroupChecked(g: ChipGroup): void {
  checked.value = toggleGroup(
    checked.value,
    g.chips.map((c) => c.factor.factor_id),
    disabledIds.value,
  )
  applyNotice.value = null
}

/* 套用结果小字(role=status): 只在有信息量时出现(有跳过/未改动), 手动改勾选即清除。 */
const applyNotice = ref<string | null>(null)

function applyLastRunSelection(): void {
  const ids = props.lastRunFactorIds
  if (!ids?.length) return
  const res = applyLastRun(checked.value, ids, availableIds.value, disabledIds.value)
  checked.value = res.next
  applyNotice.value =
    res.applied === 0
      ? `上轮 ${res.skipped} 个因子均已下架/禁用，勾选未改动`
      : res.skipped > 0
        ? `已套用上轮组合，跳过 ${res.skipped} 个已下架/禁用因子`
        : null
}

const ftStart = ref<string | null>(null)
const ftEnd = ref<string | null>(null)
const ftSplit = ref<string | null>(null)
const ftObjective = ref('long_only')
const ftLayers = ref(5)
const ftRebalance = ref(5)
const ftCost = ref(0.003)
const ftJobIds = ref<string[]>([])
const submitting = ref(false)

watch(
  () => props.lastSplitHint,
  (hint) => {
    if (!ftSplit.value && hint) ftSplit.value = hint
  },
  { immediate: true },
)

const OBJECTIVE_OPTIONS = [
  { label: 'Top层纯多头超额 (long_only)', value: 'long_only' },
  { label: '多空价差 (long_short)', value: 'long_short' },
]

const ftHint = computed(() => checked.value.size > 1 && !ftSplit.value)

/* 日期语义就地透明(回忆→识别): 起止全空提示全历史; 任一端填了改为区间回显,
 * 空端回显其全历史语义。常驻渲染保持布局稳定。 */
const dateHint = computed(() =>
  !ftStart.value && !ftEnd.value
    ? '留空 = 全历史（2021-01-01 起）'
    : `检验区间：${ftStart.value || '全历史起点'} ～ ${ftEnd.value || '全历史终点'}`,
)

async function submitFactorTest(): Promise<void> {
  error.value = ''
  if (checked.value.size === 0) {
    error.value = '至少勾选一个因子'
    return
  }
  const payload: Record<string, unknown> = {
    factors: [...checked.value].join(','),
    objective: ftObjective.value,
    num_layers: ftLayers.value,
    rebalance_days: ftRebalance.value,
    cost_rate: ftCost.value,
  }
  /* 留空不发键(同 split_date 惯例) → 后端 FactorTestJobRequest Field 默认生效
   * = 全历史(2021-01-01 起), 与上方 dateHint 文案一致; 旧版发 '' 会撞
   * pattern=^\d{4}-\d{2}-\d{2}$ 校验直接 422, "留空=全历史"从未真正走通 */
  if (ftStart.value) payload.start_date = ftStart.value
  if (ftEnd.value) payload.end_date = ftEnd.value
  if (ftSplit.value) payload.split_date = ftSplit.value
  submitting.value = true
  try {
    const job = await postJSON<Job>('/api/jobs/factor-test', payload)
    ftJobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <details class="card form-card" open data-testid="factor-test-form">
    <summary>因子检验</summary>
    <ErrorBanner v-if="error" :msg="error" />
    <div v-if="chipGroups.length" class="factor-toolbar">
      <span v-if="applyNotice" class="apply-notice" role="status" data-testid="ft-last-run-notice">
        {{ applyNotice }}
      </span>
      <NButton
        size="small"
        quaternary
        :disabled="!lastRunFactorIds?.length"
        :title="lastRunFactorIds?.length ? '把勾选置为当前所选判决轮的因子组合' : '暂无判决轮可复用'"
        data-testid="ft-apply-last-run"
        @click="applyLastRunSelection"
      >上轮同款</NButton>
    </div>
    <div v-for="g in chipGroups" :key="g.group" class="factor-group" data-testid="ft-factors">
      <button
        type="button"
        class="group-title"
        :title="groupToggleTitle"
        :aria-label="`${g.group} 组全选/清空切换`"
        data-testid="ft-group-toggle"
        @click="toggleGroupChecked(g)"
      >{{ g.group }}</button>
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
      <!-- 260px 实测下限: 最长选项「Top层纯多头超额 (long_only)」约 190px 字宽, 加 naive 触发器
           38px / 浮层选项(含勾标位) 44px 内衬 — 原 220px 收起态与下拉浮层都截成 "long_o…" -->
      <label><GlossaryTip term="objective">记分牌</GlossaryTip> <NSelect v-model:value="ftObjective" :options="OBJECTIVE_OPTIONS" aria-label="记分牌口径" style="width: 260px" /></label>
      <label><GlossaryTip term="layers">分层</GlossaryTip> <NInputNumber v-model:value="ftLayers" :min="2" :max="10" style="width: 90px" /></label>
      <label><GlossaryTip term="rebalance">调仓(日)</GlossaryTip> <NInputNumber v-model:value="ftRebalance" :min="1" style="width: 90px" /></label>
      <label><GlossaryTip term="cost_rate">成本率</GlossaryTip> <NInputNumber v-model:value="ftCost" :step="0.001" style="width: 110px" /></label>
      <NButton type="primary" :loading="submitting" :disabled="submitting" data-testid="ft-submit" @click="submitFactorTest">提交检验</NButton>
    </div>
    <p class="t-muted date-hint" data-testid="ft-date-hint">{{ dateHint }}</p>
    <p v-if="ftHint" class="t-warn hint">
      多因子批量检验未设 IS/OOS 切分——存在多重检验风险，建议保留切分日期。
    </p>
    <div data-testid="ft-job-area">
      <JobCard v-for="id in ftJobIds" :key="id" :job-id="id" @done="() => emit('refresh')" />
    </div>
  </details>
</template>

<style scoped>
.form-card summary {
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
}

/* 因子区右上角快捷条: 常态只有一枚小按钮, 负 margin 让其贴住下方组列表不多占一行高 */
.factor-toolbar {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin: 8px 0 -6px;
}

.apply-notice {
  color: var(--text-3);
  font-size: var(--fs-xs);
}

.factor-group {
  align-items: baseline;
  display: flex;
  gap: 12px;
  margin: 12px 0;
}

/* P 标签 = 真按钮(整组全选/清空), 视觉沿用旧 span 行标, 加 hover 下划线提示可点 */
.group-title {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--accent);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 12.5px;
  font-weight: 700;
  min-width: 28px;
  padding: 0;
  text-align: left;
}

.group-title:hover {
  text-decoration: underline dotted;
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

/* 紧贴日期行下方的语义小字(常驻, 不随填写增删布局) */
.date-hint {
  font-size: var(--fs-xs);
  margin: -6px 0 10px;
}
</style>
