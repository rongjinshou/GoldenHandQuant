<script setup lang="ts">
import { NSelect, NSpin } from 'naive-ui'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchJSON } from '@/api/fetch'
import type {
  AuditLog,
  ExecutionRecord,
  LiveBudget,
  LiveConfig,
  LiveEquity,
  LiveOverview,
  LivePositions,
  LiveTicket,
  TradingCycle,
} from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import KpiCard from '@/components/KpiCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import SubNav from '@/components/SubNav.vue'
import { usePolling } from '@/composables/usePolling'

import AuditTable from './live/AuditTable.vue'
import CyclesTable from './live/CyclesTable.vue'
import ExecutionsTable from './live/ExecutionsTable.vue'
import { auditActionLabel } from './live/labels'
import { cumReturn, num, sliceTime } from './live/logic'
import OverviewPanel from './live/OverviewPanel.vue'
import PositionsTable from './live/PositionsTable.vue'
import TableSkeleton from './live/TableSkeleton.vue'
import TicketPanel from './live/TicketPanel.vue'

/* 实盘 / 纸面前向页 — 旧 static/js/pages/live.js 对等:
 * 六子视图(概览/持仓/循环/执行/审计/Ticket)+ KPI 条 + 多端点独立轮询(5s);
 * 子视图与 /live/:view? 路由同步; mode 筛选仅作用于 positions/equity 两端点;
 * db_exists:false 诚实空态。单端点失败不拖垮其他(usePolling tick 失败静默保留旧值)。 */

/* 分频轮询(设计 §9 Live 分频轮询):
 * - 概览端点 overview 常轮 5s —— 驱动 KPI 四个主数值(总资产/可用/市值)与 hasDb 门,
 *   且是默认落地视图, 必须鲜活。
 * - 其余八个明细端点后台降频 30s(POLL_SLOW): 循环/执行/审计/ticket 是追加型留痕,
 *   预算/守护配置慢变, 持仓/权益只喂 KPI 的慢变副项(持仓数/累计%)—— 30s 足够。
 * - 切入某子视图时对该视图端点 refresh() 即时补一帧, 不必等下一个 30s tick, 兼顾时效。
 * usePolling 的暂停/迟到丢弃/退避机制不受影响: 只是各端点 intervalMs 不同 + 额外手动 refresh。 */
const POLL = 5000
const POLL_SLOW = 30_000

const route = useRoute()
const router = useRouter()

const VIEWS = ['overview', 'positions', 'cycles', 'executions', 'audit', 'tickets'] as const
type ViewKey = (typeof VIEWS)[number]
function normalizeView(v: unknown): ViewKey {
  return VIEWS.includes(v as ViewKey) ? (v as ViewKey) : 'overview'
}

const activeView = ref<ViewKey>(normalizeView(route.params.view))
watch(
  () => route.params.view,
  (v) => {
    activeView.value = normalizeView(v)
  },
)
function onView(v: string): void {
  const next = normalizeView(v)
  if (next === activeView.value) return
  activeView.value = next
  // 无参路径默认概览, 其余同步到 /live/<view>
  void router.replace(next === 'overview' ? { name: 'live' } : { name: 'live', params: { view: next } })
}

// ---- 两个仅作用于既定端点的筛选(mode → positions/equity; action → audit) ----
const mode = ref('')
const auditAction = ref('')

function positionsUrl(): string {
  return mode.value ? `/api/live/positions?mode=${mode.value}` : '/api/live/positions'
}
function equityUrl(): string {
  return mode.value ? `/api/live/equity?mode=${mode.value}&limit=2000` : '/api/live/equity?limit=2000'
}
function auditUrl(): string {
  return `/api/live/audit?limit=500${auditAction.value ? `&action=${auditAction.value}` : ''}`
}

// ---- 多端点并行轮询(各自独立, 单点失败互不牵连; 概览 5s, 明细 30s 降频) ----
const { data: overviewData, error: overviewError } = usePolling<LiveOverview>(
  () => fetchJSON<LiveOverview>('/api/live/overview'),
  { intervalMs: POLL },
)
const {
  data: cyclesData,
  error: cyclesError,
  refresh: refreshCycles,
} = usePolling<{ cycles: TradingCycle[] }>(
  () => fetchJSON<{ cycles: TradingCycle[] }>('/api/live/cycles?limit=500'),
  { intervalMs: POLL_SLOW },
)
const {
  data: executionsData,
  error: executionsError,
  refresh: refreshExecutions,
} = usePolling<{
  executions: ExecutionRecord[]
}>(() => fetchJSON<{ executions: ExecutionRecord[] }>('/api/live/executions?limit=1000'), {
  intervalMs: POLL_SLOW,
})
const {
  data: positionsData,
  error: positionsError,
  loading: positionsLoading,
  refresh: refreshPositions,
} = usePolling<LivePositions>(() => fetchJSON<LivePositions>(positionsUrl()), {
  intervalMs: POLL_SLOW,
})
const {
  data: equityData,
  error: equityError,
  refresh: refreshEquity,
} = usePolling<LiveEquity>(() => fetchJSON<LiveEquity>(equityUrl()), { intervalMs: POLL_SLOW })
const {
  data: budgetData,
  error: budgetError,
  refresh: refreshBudget,
} = usePolling<LiveBudget>(() => fetchJSON<LiveBudget>('/api/live/budget'), {
  intervalMs: POLL_SLOW,
})
const {
  data: configData,
  error: configError,
  refresh: refreshConfig,
} = usePolling<LiveConfig>(() => fetchJSON<LiveConfig>('/api/live/config'), {
  intervalMs: POLL_SLOW,
})
const {
  data: auditData,
  error: auditError,
  loading: auditLoading,
  refresh: refreshAudit,
} = usePolling<{ logs: AuditLog[] }>(() => fetchJSON<{ logs: AuditLog[] }>(auditUrl()), {
  intervalMs: POLL_SLOW,
})
const {
  data: ticketsData,
  error: ticketsError,
  refresh: refreshTickets,
} = usePolling<{ tickets: LiveTicket[] }>(
  () => fetchJSON<{ tickets: LiveTicket[] }>('/api/live/tickets'),
  { intervalMs: POLL_SLOW },
)

// 切入子视图即对该视图端点补一帧(降频后不必等下个 30s tick; overview 端点自身已 5s,
// 但概览视图还展示 budget/config/equity 三个慢端点, 一并即时补)
watch(activeView, (v) => {
  switch (v) {
    case 'overview':
      void refreshEquity()
      void refreshBudget()
      void refreshConfig()
      break
    case 'positions':
      void refreshPositions()
      break
    case 'cycles':
      void refreshCycles()
      break
    case 'executions':
      void refreshExecutions()
      break
    case 'audit':
      void refreshAudit()
      break
    case 'tickets':
      void refreshTickets()
      break
  }
})

// ---- 筛选反馈: 切 mode/审计动作时消费对应端点 loading, 表格降透明度 + 行内 spinner ----
// (仅筛选触发的拉取才置 filtering; loading 落地即清, 故 30s 后台 tick 不会误触发 dim)
const positionsFiltering = ref(false)
watch(mode, () => {
  positionsFiltering.value = true
  void refreshPositions()
  void refreshEquity()
})
watch(positionsLoading, (l) => {
  if (!l) positionsFiltering.value = false
})

const auditFiltering = ref(false)
watch(auditAction, () => {
  auditFiltering.value = true
  void refreshAudit()
})
watch(auditLoading, (l) => {
  if (!l) auditFiltering.value = false
})

// ---- 派生视图数据 ----
const series = computed(() => equityData.value?.series ?? [])
const positions = computed(() => positionsData.value?.positions ?? [])
const cycles = computed(() => cyclesData.value?.cycles ?? [])
const executions = computed(() => executionsData.value?.executions ?? [])
const auditLogs = computed(() => auditData.value?.logs ?? [])
const tickets = computed(() => ticketsData.value?.tickets ?? [])
const acct = computed(() => overviewData.value?.latest_account ?? null)
const posSnapshot = computed(() => sliceTime(positionsData.value?.snapshot_time))

// 首载错误横幅: 聚合全部端点(旧版单 Promise.all 任一失败即弹, 这里取首个非空 message)。
// usePolling 只在首载失败置 error、后续 tick 静默, 故不会刷屏。
const bannerMsg = computed(() => {
  const errs = [
    overviewError,
    cyclesError,
    executionsError,
    positionsError,
    equityError,
    budgetError,
    configError,
    auditError,
    ticketsError,
  ]
  for (const e of errs) {
    if (e.value?.message) return e.value.message
  }
  return ''
})
const hasDb = computed(() => overviewData.value?.db_exists === true)
const showEmpty = computed(() => overviewData.value !== null && !hasDb.value)

// ---- KPI 条(4 卡) ----
// 累计收益按最新账户的模式过滤 series — 全模式混合下 series[0] 起点与
// latest_account 现值可能分属不同 mode, 相除即跨模式串账
const cum = computed(() => {
  const m = acct.value?.mode
  const s = m ? series.value.filter((r) => r.mode === m) : series.value
  return cumReturn(s, acct.value)
})
const totalAssetText = computed(() => num(acct.value?.total_asset))
const totalAssetSub = computed(
  () => `${sliceTime(acct.value?.snapshot_time) || '无快照'} · ${acct.value?.mode ?? ''}`,
)
const availCashText = computed(() => num(acct.value?.available_cash))
const availCashSub = computed(() => `冻结 ${num(acct.value?.frozen_cash)}`)
const mktValText = computed(() => num(acct.value?.market_value))
// 市值口径=最新账户快照(acct.mode), 计数须同口径 — positions 受页内 mode 筛选影响会分叉
const mktValSub = computed(() => {
  const m = acct.value?.mode
  const rows = positionsData.value?.positions ?? []
  const n = m ? rows.filter((r) => r.mode === m).length : rows.length
  return `${n} 只持仓`
})

type NavItem = { key: string; label: string; badge?: number }
const subnavItems = computed<NavItem[]>(() => [
  { key: 'overview', label: '概览' },
  { key: 'positions', label: '持仓', badge: positions.value.length },
  { key: 'cycles', label: '循环', badge: cycles.value.length },
  { key: 'executions', label: '执行', badge: executions.value.length },
  { key: 'audit', label: '审计', badge: auditLogs.value.length },
  { key: 'tickets', label: 'Ticket', badge: tickets.value.length },
])

const MODE_OPTIONS = [
  { label: '全部模式', value: '' },
  { label: '纸面 dry_run', value: 'dry_run' },
  { label: '实盘 live', value: 'live' },
]
const AUDIT_ACTIONS = [
  'cycle_start',
  'cycle_end',
  'place_order',
  'reject_order',
  'place_order_failed',
  'execute_failed',
  'cancel_order',
]
const AUDIT_OPTIONS = [
  { label: '全部动作', value: '' },
  ...AUDIT_ACTIONS.map((a) => ({ label: auditActionLabel(a), value: a })),
]
</script>

<template>
  <section data-testid="page-live">
    <PageHeader title="实盘 / 纸面前向">
      auto-trade 交易留痕的只读视图——下方分页查看预算与守护、循环、执行、审计、ticket。<GlossaryTip
        term="dry_run"
        ><span>dry_run</span></GlossaryTip
      >
      为纸面模式。网页永远无法下单或修改交易配置。
    </PageHeader>

    <ErrorBanner v-if="bannerMsg" :msg="bannerMsg" />

    <!-- KPI 骨架: 首响应前占位, 不让空态 '-' 冒充加载 -->
    <div v-if="overviewData === null" class="kpi-row" data-testid="live-kpi-skeleton">
      <div v-for="i in 4" :key="i" class="card kpi-skeleton" aria-hidden="true"></div>
    </div>

    <!-- KPI 条: 加载后始终渲染(空态显 '-' 占位, 对等旧设计意图 live.js:153) -->
    <div v-else class="kpi-row" data-testid="live-kpi">
      <KpiCard label="总资产" :value="totalAssetText" :sub="totalAssetSub" />
      <KpiCard label="累计收益" :value="cum.text" :tone="cum.tone" :sub="cum.sub" />
      <KpiCard label="可用资金" :value="availCashText" :sub="availCashSub" />
      <KpiCard label="持仓市值" :value="mktValText" :sub="mktValSub" />
    </div>

    <div v-if="showEmpty" class="empty-banner card" data-testid="live-empty">
      暂无交易留痕 — 运行 <code>quant auto-trade --once --enable</code>（dry-run）或
      <code>scripts/seed_paper_trading.py</code> 后生成 data/trading.db。
    </div>

    <template v-if="hasDb">
      <SubNav :items="subnavItems" :model-value="activeView" @update:model-value="onView" />

      <OverviewPanel
        v-if="activeView === 'overview'"
        :ov="overviewData"
        :budget="budgetData"
        :cfg="configData"
        :series="series"
        :equity-loaded="equityData !== null"
      />

      <div v-else-if="activeView === 'positions'">
        <div class="view-head">
          <h3 class="view-title">
            <GlossaryTip term="position"><span>当前持仓</span></GlossaryTip>
          </h3>
          <div class="toolbar">
            <NSelect
              v-model:value="mode"
              :options="MODE_OPTIONS"
              size="small"
              style="width: 160px"
              aria-label="按交易模式筛选持仓与权益"
              data-testid="live-mode"
            />
            <NSpin v-if="positionsFiltering" :size="14" data-testid="live-mode-spin" />
            <span v-if="posSnapshot" class="snap t-muted num">快照 {{ posSnapshot }}</span>
          </div>
        </div>
        <div :class="{ filtering: positionsFiltering }">
          <PositionsTable v-if="positionsData !== null" :rows="positions" />
          <TableSkeleton v-else :cols="7" />
        </div>
      </div>

      <div v-else-if="activeView === 'cycles'">
        <div class="view-head">
          <h3 class="view-title">
            <GlossaryTip term="cycle"><span>交易循环</span></GlossaryTip>
          </h3>
          <span class="view-hint t-muted">展开某行查看该循环的执行明细</span>
        </div>
        <CyclesTable v-if="cyclesData !== null" :cycles="cycles" />
        <TableSkeleton v-else :cols="9" />
      </div>

      <div v-else-if="activeView === 'executions'">
        <div class="view-head">
          <h3 class="view-title">执行留痕</h3>
          <span class="view-hint t-muted"
            >低于<GlossaryTip term="confidence"><span>置信</span></GlossaryTip>阈值的信号不提交下单</span
          >
        </div>
        <ExecutionsTable v-if="executionsData !== null" :executions="executions" />
        <TableSkeleton v-else :cols="9" />
      </div>

      <div v-else-if="activeView === 'audit'">
        <div class="view-head">
          <h3 class="view-title">
            <GlossaryTip term="audit"><span>审计日志</span></GlossaryTip>
          </h3>
          <div class="toolbar">
            <NSelect
              v-model:value="auditAction"
              :options="AUDIT_OPTIONS"
              size="small"
              style="width: 200px"
              aria-label="按审计动作筛选日志"
              data-testid="audit-action"
            />
            <NSpin v-if="auditFiltering" :size="14" data-testid="audit-action-spin" />
          </div>
        </div>
        <div :class="{ filtering: auditFiltering }">
          <AuditTable v-if="auditData !== null" :logs="auditLogs" />
          <TableSkeleton v-else :cols="4" />
        </div>
      </div>

      <div v-else-if="activeView === 'tickets'">
        <div class="view-head">
          <h3 class="view-title">
            <GlossaryTip term="ticket"><span>下单 Ticket</span></GlossaryTip>
          </h3>
        </div>
        <TicketPanel v-if="ticketsData !== null" :tickets="tickets" />
        <TableSkeleton v-else :rows="2" :cols="3" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.empty-banner {
  font-size: 13.5px;
  line-height: 1.7;
  padding: 22px 20px;
}

.empty-banner code {
  color: var(--accent-blue);
  font-size: 12.5px;
}

.kpi-row {
  display: grid;
  gap: var(--gap);
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  margin-bottom: var(--gap);
}

/* KPI 加载骨架(复用 Overview kpi-skeleton 思路): 固定高度脉冲, 数据到达不跳版 */
.kpi-skeleton {
  animation: live-skeleton-pulse 1.4s ease-in-out infinite;
  min-height: 92px;
}

@keyframes live-skeleton-pulse {
  50% {
    opacity: 0.55;
  }
}

/* 筛选中: 表格降透明度(配 toolbar 行内 spinner), 提示用户筛选正在生效 */
.filtering {
  opacity: 0.5;
  transition: opacity var(--dur-fast) var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .kpi-skeleton {
    animation: none;
    opacity: 0.7;
  }
}

.view-head {
  align-items: baseline;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-bottom: 10px;
}

.view-title {
  font-size: 15px;
  margin: 0;
}

.view-hint {
  font-size: 12.5px;
}

.toolbar {
  align-items: center;
  display: flex;
  gap: 14px;
  margin-left: auto;
}

.snap {
  font-size: 12px;
}
</style>
