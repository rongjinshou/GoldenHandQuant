<script setup lang="ts">
import { NButton, NPopconfirm, NSelect } from 'naive-ui'
import { computed, ref, watch } from 'vue'

import { deleteJSON, fetchJSON } from '@/api/fetch'
import type { VerdictRun } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'

import FactorCard from './verdicts/FactorCard.vue'
import FactorDetailModal from './verdicts/FactorDetailModal.vue'
import FactorTestForm from './verdicts/FactorTestForm.vue'
import { buildVerdictRunLabel } from './verdicts/run-naming'
import { SORT_OPTIONS, filterFactors, sortFactors, type FilterKey, type SortKey } from './verdicts/sort'

/* 因子判决页(设计 0705-verdict-cards) — 检验表单置顶 + 判决结果卡片化:
 * 卡片替代表格行, 闸门轨道为签名元素, 点击卡片开详情弹框, 排序+过滤工具条。 */

const error = ref('')
const loading = ref(true)
const runs = ref<VerdictRun[]>([])
const selectedIdx = ref(0)

async function loadVerdicts(): Promise<void> {
  try {
    const data = await fetchJSON<{ runs: VerdictRun[] }>('/api/research/verdicts')
    runs.value = data.runs
    selectedIdx.value = 0
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

void loadVerdicts()

const run = computed(() => runs.value[selectedIdx.value] ?? null)
const longOnly = computed(() => run.value?.params?.objective === 'long_only')
const hasSplit = computed(() => !!run.value?.params?.split)
const lastSplitHint = computed(() => runs.value[0]?.params?.split ?? null)

/* 研究记录退役(设计 docs/feat/0705-research-retire, commit 8dc2558) — 整轮硬删除, 无回收站。
 * 与本次卡片化重排(0705-verdict-cards)并行落地在同一文件, 重排时原样保留、随 run-select
 * 一起挪到结果区头, 不属于本次重排设计的新增范围。 */
const deletingRun = ref(false)

async function deleteCurrentRun(): Promise<void> {
  const id = run.value?.run_id
  if (!id) return
  deletingRun.value = true
  try {
    await deleteJSON(`/api/research/verdicts/${id}`)
    await loadVerdicts()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    deletingRun.value = false
  }
}

/* 业务化标题(设计 0705 §3.B): "N 因子 · 口径 · 切分日" 为主, 时间+run_id 收尾括号 —
 * 根治"下拉全是 MFCOMBO-日期, 看不懂业务"(用户原话) */
const runOptions = computed(() =>
  runs.value.map((r, i) => {
    const label = buildVerdictRunLabel(r)
    return { label: `${label.title}（${(r.created_at ?? '').slice(5, 16)} · ${r.run_id}）`, value: i }
  }),
)

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

// ---- 过滤 + 排序 ----
const filterKey = ref<FilterKey>('all')
const sortKey = ref<SortKey>('verdict')

const totalCount = computed(() => run.value?.factors.length ?? 0)
const passCount = computed(() => run.value?.factors.filter((f) => f.passed).length ?? 0)
const failCount = computed(() => totalCount.value - passCount.value)

const visibleFactors = computed(() => {
  if (!run.value) return []
  return sortFactors(filterFactors(run.value.factors, filterKey.value), sortKey.value, longOnly.value)
})

// ---- 详情弹框 ----
const modalOpen = ref(false)
const modalIndex = ref(0)
const lastFocusedEl = ref<HTMLElement | null>(null)

function openModal(i: number): void {
  lastFocusedEl.value = document.activeElement as HTMLElement | null
  modalIndex.value = i
  modalOpen.value = true
}

watch(modalOpen, (open) => {
  if (!open) lastFocusedEl.value?.focus()
})

// 过滤/排序或切换轮次时, 弹框下标语义会变 — 直接关闭而非静默指向别的因子
watch(() => run.value?.run_id, () => { modalOpen.value = false })
watch([filterKey, sortKey], () => { modalOpen.value = false })
</script>

<template>
  <section data-testid="page-verdicts">
    <header class="page-head">
      <h2>因子判决</h2>
    </header>
    <p class="guide t-muted">
      先检验因子，判决结果随后以卡片呈现——左缘色条与闸门轨道标出 PASS/FAIL，点击卡片看全部细节。
    </p>

    <ErrorBanner v-if="error" :msg="error" />

    <FactorTestForm :last-split-hint="lastSplitHint" @refresh="loadVerdicts" />

    <p v-if="loading" class="t-muted">加载判决轮次…</p>
    <p v-else-if="!runs.length" class="t-muted" data-testid="verdicts-empty">
      暂无判决轮次 — 用上方表单提交一次因子检验。
    </p>

    <template v-if="run">
      <div class="result-head">
        <span class="list-title">判决结果</span>
        <NSelect
          v-model:value="selectedIdx"
          :options="runOptions"
          size="small"
          style="width: 380px"
          data-testid="run-select"
        />
        <NPopconfirm
          positive-text="删除"
          negative-text="取消"
          @positive-click="deleteCurrentRun"
        >
          <template #trigger>
            <NButton size="small" quaternary :loading="deletingRun" data-testid="verdict-delete">删除本轮</NButton>
          </template>
          <div class="confirm-body">
            <div>删除这轮判决？</div>
            <div><b>{{ runOptions[selectedIdx]?.label }}</b></div>
            <div class="t-muted">不可恢复</div>
          </div>
        </NPopconfirm>
        <div class="filter-seg" role="group" aria-label="按判决过滤" data-testid="verdict-filter">
          <button type="button" :class="{ active: filterKey === 'all' }" @click="filterKey = 'all'">全部 {{ totalCount }}</button>
          <button type="button" :class="{ active: filterKey === 'pass' }" @click="filterKey = 'pass'">PASS {{ passCount }}</button>
          <button type="button" :class="{ active: filterKey === 'fail' }" @click="filterKey = 'fail'">FAIL {{ failCount }}</button>
        </div>
        <NSelect
          v-model:value="sortKey"
          :options="SORT_OPTIONS"
          size="small"
          style="width: 190px"
          data-testid="verdict-sort"
        />
      </div>

      <div class="meta-strip card">
        <span v-for="m in metaItems" :key="m.label" class="rm">
          <GlossaryTip v-if="m.gloss" :term="m.gloss"><i>{{ m.label }}</i></GlossaryTip>
          <i v-else>{{ m.label }}</i>
          <b>{{ m.value }}</b>
        </span>
      </div>

      <p v-if="!visibleFactors.length" class="t-muted" data-testid="verdict-filter-empty">
        无匹配因子 — <button type="button" class="link-btn" @click="filterKey = 'all'">清除过滤</button>
      </p>
      <div v-else class="factor-grid" data-testid="verdict-grid">
        <FactorCard
          v-for="(f, i) in visibleFactors"
          :key="f.factor_id"
          :factor="f"
          :long-only="longOnly"
          :has-split="hasSplit"
          @click="openModal(i)"
        />
      </div>
    </template>

    <FactorDetailModal
      v-model:show="modalOpen"
      :factors="visibleFactors"
      :index="modalIndex"
      :long-only="longOnly"
      :has-split="hasSplit"
      :run-title="run ? buildVerdictRunLabel(run).title : ''"
      @navigate="(i) => (modalIndex = i)"
    />
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

.result-head {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin: var(--gap-lg) 0 10px;
}

.list-title {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.filter-seg {
  display: flex;
  gap: 4px;
}

.filter-seg button {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  font-size: 12px;
  padding: 5px 11px;
  transition:
    background var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}

.filter-seg button:hover {
  border-color: var(--accent);
}

.filter-seg button.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #faf9f5;
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

.link-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: inherit;
  padding: 0;
  text-decoration: underline;
}

.factor-grid {
  display: grid;
  gap: 12px;
  /* auto-fill(非 auto-fit): 少量因子时卡片保持 ~240px 扫读宽度, 不被拉伸铺满整行 */
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  margin-bottom: var(--gap-lg);
}

/* NPopconfirm 默认插槽是 flex 布局, <br/> 不生效 — 显式 block 分行(同回测页) */
.confirm-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-width: 260px;
}
</style>
