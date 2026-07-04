<script setup lang="ts">
import { NSelect } from 'naive-ui'
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
import SubNav from '@/components/SubNav.vue'
import { usePolling } from '@/composables/usePolling'

import AuditTable from './live/AuditTable.vue'
import CyclesTable from './live/CyclesTable.vue'
import ExecutionsTable from './live/ExecutionsTable.vue'
import { cumReturn, num, sliceTime } from './live/logic'
import OverviewPanel from './live/OverviewPanel.vue'
import PositionsTable from './live/PositionsTable.vue'
import TicketPanel from './live/TicketPanel.vue'

/* 实盘 / 纸面前向页 — 旧 static/js/pages/live.js 对等:
 * 六子视图(概览/持仓/循环/执行/审计/Ticket)+ KPI 条 + 多端点独立轮询(5s);
 * 子视图与 /live/:view? 路由同步; mode 筛选仅作用于 positions/equity 两端点;
 * db_exists:false 诚实空态。单端点失败不拖垮其他(usePolling tick 失败静默保留旧值)。 */

const POLL = 5000

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

// ---- 多端点并行轮询(各自独立, 单点失败互不牵连) ----
const { data: overviewData, error: overviewError } = usePolling<LiveOverview>(
  () => fetchJSON<LiveOverview>('/api/live/overview'),
  { intervalMs: POLL },
)
const { data: cyclesData, error: cyclesError } = usePolling<{ cycles: TradingCycle[] }>(
  () => fetchJSON<{ cycles: TradingCycle[] }>('/api/live/cycles?limit=500'),
  { intervalMs: POLL },
)
const { data: executionsData, error: executionsError } = usePolling<{
  executions: ExecutionRecord[]
}>(() => fetchJSON<{ executions: ExecutionRecord[] }>('/api/live/executions?limit=1000'), {
  intervalMs: POLL,
})
const {
  data: positionsData,
  error: positionsError,
  refresh: refreshPositions,
} = usePolling<LivePositions>(() => fetchJSON<LivePositions>(positionsUrl()), { intervalMs: POLL })
const {
  data: equityData,
  error: equityError,
  refresh: refreshEquity,
} = usePolling<LiveEquity>(() => fetchJSON<LiveEquity>(equityUrl()), { intervalMs: POLL })
const { data: budgetData, error: budgetError } = usePolling<LiveBudget>(
  () => fetchJSON<LiveBudget>('/api/live/budget'),
  { intervalMs: POLL },
)
const { data: configData, error: configError } = usePolling<LiveConfig>(
  () => fetchJSON<LiveConfig>('/api/live/config'),
  { intervalMs: POLL },
)
const {
  data: auditData,
  error: auditError,
  refresh: refreshAudit,
} = usePolling<{ logs: AuditLog[] }>(() => fetchJSON<{ logs: AuditLog[] }>(auditUrl()), {
  intervalMs: POLL,
})
const { data: ticketsData, error: ticketsError } = usePolling<{ tickets: LiveTicket[] }>(
  () => fetchJSON<{ tickets: LiveTicket[] }>('/api/live/tickets'),
  { intervalMs: POLL },
)

// mode/action 变更即刷对应端点(不扩大到其他端点)
watch(mode, () => {
  void refreshPositions()
  void refreshEquity()
})
watch(auditAction, () => {
  void refreshAudit()
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
const cum = computed(() => cumReturn(series.value, acct.value))
const totalAssetText = computed(() => num(acct.value?.total_asset))
const totalAssetSub = computed(
  () => `${sliceTime(acct.value?.snapshot_time) || '无快照'} · ${acct.value?.mode ?? ''}`,
)
const availCashText = computed(() => num(acct.value?.available_cash))
const availCashSub = computed(() => `冻结 ${num(acct.value?.frozen_cash)}`)
const mktValText = computed(() => num(acct.value?.market_value))
const mktValSub = computed(() => `${positions.value.length} 只持仓`)

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
  ...AUDIT_ACTIONS.map((a) => ({ label: a, value: a })),
]
</script>

<template>
  <section data-testid="page-live">
    <header class="page-head"><h2>实盘 / 纸面前向</h2></header>
    <p class="guide t-muted">
      auto-trade 交易留痕的只读视图——下方分页查看预算与守护、循环、执行、审计、ticket。<GlossaryTip
        term="dry_run"
        ><span>dry_run</span></GlossaryTip
      >
      为纸面模式。网页永远无法下单或修改交易配置。
    </p>

    <ErrorBanner v-if="bannerMsg" :msg="bannerMsg" />

    <!-- KPI 条: 加载后始终渲染(空态显 '-' 占位, 对等旧设计意图 live.js:153) -->
    <div v-if="overviewData !== null" class="kpi-row" data-testid="live-kpi">
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
              data-testid="live-mode"
            />
            <span v-if="posSnapshot" class="snap t-muted num">快照 {{ posSnapshot }}</span>
          </div>
        </div>
        <PositionsTable :rows="positions" />
      </div>

      <div v-else-if="activeView === 'cycles'">
        <div class="view-head">
          <h3 class="view-title">
            <GlossaryTip term="cycle"><span>交易循环</span></GlossaryTip>
          </h3>
          <span class="view-hint t-muted">点击行展开该循环的执行明细</span>
        </div>
        <CyclesTable :cycles="cycles" />
      </div>

      <div v-else-if="activeView === 'executions'">
        <div class="view-head">
          <h3 class="view-title">执行留痕</h3>
          <span class="view-hint t-muted"
            >低于<GlossaryTip term="confidence"><span>置信</span></GlossaryTip>阈值的信号不提交下单</span
          >
        </div>
        <ExecutionsTable :executions="executions" />
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
              data-testid="audit-action"
            />
          </div>
        </div>
        <AuditTable :logs="auditLogs" />
      </div>

      <div v-else-if="activeView === 'tickets'">
        <div class="view-head">
          <h3 class="view-title">
            <GlossaryTip term="ticket"><span>下单 Ticket</span></GlossaryTip>
          </h3>
        </div>
        <TicketPanel :tickets="tickets" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.page-head {
  align-items: baseline;
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
