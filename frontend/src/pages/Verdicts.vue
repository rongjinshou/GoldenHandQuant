<script setup lang="ts">
import { NButton, NPopconfirm, NSelect } from 'naive-ui'
import { computed, getCurrentInstance, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { deleteJSON, fetchJSON } from '@/api/fetch'
import type { VerdictRun } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import PageHeader from '@/components/PageHeader.vue'

import FactorCard from './verdicts/FactorCard.vue'
import FactorDetailModal from './verdicts/FactorDetailModal.vue'
import FactorTestForm from './verdicts/FactorTestForm.vue'
import { resolveReloadSelection } from './verdicts/reload-selection'
import { runQueryNeedsUpdate, selectionFromRunParam } from './verdicts/run-deeplink'
import { buildVerdictRunLabel } from './verdicts/run-naming'
import { SORT_OPTIONS, filterFactors, sortFactors, type FilterKey, type SortKey } from './verdicts/sort'

/* 因子判决页(设计 0705-verdict-cards) — 检验表单置顶 + 判决结果卡片化:
 * 卡片替代表格行, 闸门轨道为签名元素, 点击卡片开详情弹框, 排序+过滤工具条。 */

const error = ref('')
const loading = ref(true)
const runs = ref<VerdictRun[]>([])
const selectedIdx = ref(0)
/* 新轮到达提示条(设计 §9): reload 保留原选中时, 用它非侵入告知"有更新的轮", 不强切。 */
const newRunNotice = ref<string | null>(null)

/* URL 深链(设计 0710 P7): 选中判决轮 ↔ ?run=<run_id>。router-optional —— 本页需能在无
 * router 环境(单测直接 mount Verdicts)下挂载。先探测 router 是否已安装(app.use(router) 会
 * 注入 $router 全局属性), 未装则不调用 useRoute/useRouter —— 既免 inject 落空的告警, 深链
 * 逻辑也随之惰性关闭(route/router 为 undefined), 不影响页面其余行为。 */
const hasRouter = !!getCurrentInstance()?.appContext.config.globalProperties.$router
const route = hasRouter ? useRoute() : undefined
const router = hasRouter ? useRouter() : undefined
let firstLoad = true

async function loadVerdicts(): Promise<void> {
  // 直接读 runs/selectedIdx(而非尚在 TDZ 的 run 计算属性): 首次 void 调用发生在 run 定义之前。
  const prevRunId = runs.value[selectedIdx.value]?.run_id ?? null
  const prevRunIds = runs.value.map((r) => r.run_id)
  try {
    const data = await fetchJSON<{ runs: VerdictRun[] }>('/api/research/verdicts')
    runs.value = data.runs
    // 保留选中: 原轮仍在则定位其新下标, 否则回落最新(0); 新轮到达仅提示不强切。
    const sel = resolveReloadSelection(prevRunId, prevRunIds, data.runs)
    selectedIdx.value = sel.selectedIdx
    newRunNotice.value = sel.newRunId
    // 首次加载: ?run= 深链优先于默认落点(命中才覆盖, 未命中/无参保持批二 reload 决策)。
    // 在此同步定案 selectedIdx, 使写回 watcher 只 settle 一次(且幂等), 不会先写默认再被深链覆盖。
    if (firstLoad) {
      const deepIdx = selectionFromRunParam(route?.query?.run, data.runs)
      if (deepIdx >= 0) selectedIdx.value = deepIdx
    }
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    firstLoad = false
    loading.value = false
  }
}

function jumpToNewRun(): void {
  const idx = runs.value.findIndex((r) => r.run_id === newRunNotice.value)
  if (idx >= 0) selectedIdx.value = idx
  newRunNotice.value = null
}

void loadVerdicts()

const run = computed(() => runs.value[selectedIdx.value] ?? null)
const longOnly = computed(() => run.value?.params?.objective === 'long_only')
const hasSplit = computed(() => !!run.value?.params?.split)
const lastSplitHint = computed(() => runs.value[0]?.params?.split ?? null)
/* 「上轮同款」数据源(最小侵入: 复用已加载的轮次数据, 不另发请求): 取当前选中判决轮的
 * 因子集合 — 用户正看哪轮, "同款"就是哪轮; 默认选中最新轮(0), 与"最新一轮"语义自然重合。 */
const lastRunFactorIds = computed(() => run.value?.factors.map((f) => f.factor_id) ?? null)

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
    // 副标题(含年份)整体复用, 不再就地 slice —— 与 run-naming 单一口径, 跨年日期可分辨。
    return { label: `${label.title}（${label.subtitle}）`, value: i }
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
// 选中回到最新轮(点"查看最新"或手动选最新)后, "新轮就绪"提示失去意义 → 清除
watch(selectedIdx, (i) => { if (i === 0) newRunNotice.value = null })

// ---- URL 深链 ?run= 双向同步(P7) ----
// 前进/后退: 地址栏 ?run= 变化 → 恢复选中(命中才动, 未命中保持既有选中不强跳; 幂等)。
watch(
  () => route?.query?.run,
  (raw) => {
    const idx = selectionFromRunParam(raw, runs.value)
    if (idx >= 0 && idx !== selectedIdx.value) selectedIdx.value = idx
  },
)
// 选中轮变化(用户切换 / 批二 reload 保留到某轮) → 幂等写回 ?run=;
// query 已是目标值就绝不再 replace, 断"恢复→写回"死循环; replace 不 push, 不污染历史栈。
watch(
  () => run.value?.run_id,
  (runId) => {
    if (!router || !route || !runId) return
    if (runQueryNeedsUpdate(route.query.run, runId)) {
      void router.replace({ query: { ...route.query, run: runId } })
    }
  },
)
</script>

<template>
  <section data-testid="page-verdicts">
    <PageHeader title="因子判决">
      先检验因子，判决结果随后以卡片呈现——左缘色条与闸门轨道标出 PASS/FAIL，点击卡片看全部细节。
    </PageHeader>

    <ErrorBanner v-if="error" :msg="error" />

    <FactorTestForm
      :last-split-hint="lastSplitHint"
      :last-run-factor-ids="lastRunFactorIds"
      @refresh="loadVerdicts"
    />

    <p v-if="loading" class="t-muted">加载判决轮次…</p>
    <p v-else-if="!runs.length" class="t-muted" data-testid="verdicts-empty">
      暂无判决轮次 — 用上方表单提交一次因子检验。
    </p>

    <template v-if="run">
      <div
        v-if="newRunNotice"
        class="new-run-notice"
        role="status"
        data-testid="verdict-new-run-notice"
      >
        <span>已有更新的判决轮就绪 — 当前仍停在你正在查看的这轮。</span>
        <button type="button" class="notice-view" @click="jumpToNewRun">查看最新</button>
        <button
          type="button"
          class="notice-dismiss"
          aria-label="忽略新轮提示"
          @click="newRunNotice = null"
        >✕</button>
      </div>
      <div class="result-head">
        <span class="list-title">判决结果</span>
        <NSelect
          v-model:value="selectedIdx"
          :options="runOptions"
          size="small"
          style="width: 380px"
          aria-label="判决轮次"
          data-testid="run-select"
        />
        <div class="filter-seg" role="group" aria-label="按判决过滤" data-testid="verdict-filter">
          <button type="button" :class="{ active: filterKey === 'all' }" :aria-pressed="filterKey === 'all'" @click="filterKey = 'all'">全部 {{ totalCount }}</button>
          <button type="button" :class="{ active: filterKey === 'pass' }" :aria-pressed="filterKey === 'pass'" @click="filterKey = 'pass'">PASS {{ passCount }}</button>
          <button type="button" :class="{ active: filterKey === 'fail' }" :aria-pressed="filterKey === 'fail'" @click="filterKey = 'fail'">FAIL {{ failCount }}</button>
        </div>
        <NSelect
          v-model:value="sortKey"
          :options="SORT_OPTIONS"
          size="small"
          style="width: 190px"
          aria-label="因子排序"
          data-testid="verdict-sort"
        />
        <!-- 删除本轮(易用性迭代·Fitts 隔离): 破坏性操作挪到工具条最右端, 靠 .del-run-btn 的
             margin-left:auto 与高频过滤/排序拉开物理距离(窄屏 wrap 时仍收尾在末行右缘);
             常态淡色降视觉权重, hover 才显 fail 语义 — NPopconfirm 确认与 :loading 原样保留, 删除逻辑未动。 -->
        <NPopconfirm
          positive-text="删除"
          negative-text="取消"
          @positive-click="deleteCurrentRun"
        >
          <template #trigger>
            <NButton size="small" quaternary class="del-run-btn" :loading="deletingRun" data-testid="verdict-delete">
              <template #icon>
                <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M2.5 4.2h11M6 4.2V2.6h4v1.6M4.2 4.2l.7 9.2h6.2l.7-9.2M6.6 7v4M9.4 7v4" />
                </svg>
              </template>
              删除本轮
            </NButton>
          </template>
          <div class="confirm-body">
            <div>删除这轮判决？</div>
            <div><b>{{ runOptions[selectedIdx]?.label }}</b></div>
            <div class="t-muted">不可恢复</div>
          </div>
        </NPopconfirm>
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
/* 新轮到达提示条(设计 §9): info 语义色, 非侵入 — 不遮挡内容, 可"查看最新"或"忽略"。 */
.new-run-notice {
  align-items: center;
  background: var(--c-info-soft);
  border: 1px solid var(--c-info-border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-wrap: wrap;
  font-size: 12.5px;
  gap: 10px;
  margin: var(--gap-lg) 0 0;
  padding: 8px 14px;
}

.notice-view {
  background: transparent;
  border: 1px solid var(--c-info-border);
  border-radius: var(--radius-sm);
  color: var(--c-info);
  cursor: pointer;
  font-size: 12px;
  min-height: 24px;
  padding: 3px 10px;
  transition: border-color var(--dur-fast) var(--ease-out);
}

.notice-view:hover {
  border-color: var(--c-info);
}

.notice-dismiss {
  background: transparent;
  border: none;
  color: var(--text-3);
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  margin-left: auto;
  min-height: 24px;
  min-width: 24px;
  padding: 4px 6px;
  transition: color var(--dur-fast) var(--ease-out);
}

.notice-dismiss:hover {
  color: var(--text);
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

/* 删除本轮(Fitts 隔离): margin-left:auto 推到工具条最右, 与高频过滤/排序拉开;
   常态 text-3 淡色降权, hover/键盘聚焦才显 fail 语义 — 同回测页 .run-delete 的视觉语言。
   选择器带 button 元素名把特异性抬到 (0,n,1), 确定性压过 naive-ui 运行时注入的
   .n-button:not(.n-button--disabled):hover (0,3,0), 不赌 <style> 注入顺序。 */
button.del-run-btn {
  color: var(--text-3);
  margin-left: auto;
}

button.del-run-btn:not(.n-button--disabled):hover,
button.del-run-btn:not(.n-button--disabled):focus-visible {
  background-color: var(--c-fail-soft);
  color: var(--c-fail);
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
