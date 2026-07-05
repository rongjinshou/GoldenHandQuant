<script setup lang="ts">
import { NButton, NDatePicker, NInputNumber, NSelect } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { fetchJSON, postJSON } from '@/api/fetch'
import type { Job, MetaFactor } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'

/* 因子检验表单(设计 0705-verdict-cards §3) — 从 Verdicts.vue 抽取, 置顶页面第一屏;
 * 行为对旧版零改动: chips 分组/P0 默认勾/field_ready 禁用/多重检验提示/JobCard 闭环。
 * lastSplitHint: 父层最近一轮判决的切分日, 用于预填 IS/OOS 切分(消除进页即报
 * "多重检验风险"的常驻警告)。 */
const props = defineProps<{ lastSplitHint: string | null }>()
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
}

const ftStart = ref<string | null>(null)
const ftEnd = ref<string | null>(null)
const ftSplit = ref<string | null>(null)
const ftObjective = ref('long_only')
const ftLayers = ref(5)
const ftRebalance = ref(5)
const ftCost = ref(0.003)
const ftJobIds = ref<string[]>([])

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
  <details class="card form-card" open data-testid="factor-test-form">
    <summary>因子检验</summary>
    <ErrorBanner v-if="error" :msg="error" />
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
