<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { AccountSnapshot, LiveBudget, LiveConfig, LiveOverview } from '@/api/types'
import GlossaryTip from '@/components/GlossaryTip.vue'
import { axisStyle, tooltipStyle, useChartTheme, vGradient } from '@/composables/useChartTheme'

import LvBadge from './LvBadge.vue'
import { daemonBadge, equityAriaLabel, num, wan, type BadgeKind } from './logic'

// AriaComponent: 启用 ECharts 内建无障碍(option.aria) — 图表 role=img + aria-label 之外的兜底
use([LineChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, CanvasRenderer])

/* 概览子视图 — 旧 renderOpsCards + 权益曲线段对等:
 * 运维四卡(今日活动/预算/守护/auto-trade 配置只读) + 权益曲线(≥2 快照才成曲线,
 * dry_run 与 live 按 mode 分开画; 单点/零点显示提示文案而非空图框)。
 * 各端点独立轮询, 卡片按各自数据就绪逐个出现(单端点失败不拖垮其他)。 */

const props = defineProps<{
  ov: LiveOverview | null
  budget: LiveBudget | null
  cfg: LiveConfig | null
  series: AccountSnapshot[]
  /** 权益端点是否已首响应 — 区分"加载中"(骨架)与真空态"暂无权益快照" */
  equityLoaded?: boolean
}>()

// 运维四卡首响应前(全 null)显骨架, 不留空白冒充加载
const cardsPending = computed(() => !props.ov && !props.budget && !props.cfg)

const palette = useChartTheme()

const cyclesToday = computed(() => props.ov?.cycles_today ?? 0)
const execsToday = computed(() => props.ov?.executions_today ?? 0)

// 大数字=已提交金额(裸 0 曾被误读为"无预算", 故旁挂"已提交"标注);
// 单笔上限塞不进副行 → 移到标题词条触发文本旁的小字
const budgetMain = computed(() => num(props.budget?.submitted_notional))
const budgetSub = computed(() => {
  const b = props.budget
  if (!b) return ''
  return `上限 ${num(b.daily_notional_cap)} · 余 ${num(b.remaining)}`
})
const perOrderCap = computed(() => num(props.budget?.per_order_notional_cap))

const daemon = computed(() =>
  props.cfg ? daemonBadge(props.cfg) : { kind: 'info' as BadgeKind, text: '' },
)
const slotsText = computed(() => (props.cfg?.today.expected_slots ?? []).join(' / ') || '-')

const at = computed(() => props.cfg?.auto_trade ?? {})
const atModeCls = computed(() => (at.value.mode === 'live' ? 'fail' : 'info'))
// 空段过滤再拼 — 避免 "0 标的" 误导(空 symbols=标的由策略宇宙决定)与首尾悬空分隔符
const atSub = computed(() => {
  const syms = at.value.symbols ?? []
  const parts = [
    at.value.strategy,
    syms.length ? `${syms.length} 标的` : '标的由策略宇宙决定',
  ].filter((p): p is string => !!p)
  return parts.join(' · ')
})

// ---- 权益曲线(旧口径: ≥2 快照; 单点提示采样方法; mode 分线, 首线带品牌渐变面;
// x 轴用 time 而非 category — 等距排快照会把 3 分钟画得与 17 天一样宽, 且截到分钟出现重复刻度) ----
const hasEquity = computed(() => props.series.length >= 2)
// 图表容器 role="img" 的替代文本(WCAG 1.1.1): 概述曲线条数/最新总资产/区间
const equityAria = computed(() => equityAriaLabel(props.series))
const equityHint = computed(() =>
  props.series.length === 1
    ? '已有 1 条权益快照——多次同步后将绘制权益曲线（scripts/sync_live_account.py --watch 30 持续采样）。'
    : '暂无权益快照。',
)

/* time 轴刻度/浮层统一 MM-DD HH:mm(快照分钟粒度足够定位) */
function fmtTs(ms: number): string {
  const d = new Date(ms)
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

interface EquityTipParam {
  axisValue?: number | string
  marker?: string
  seriesName?: string
  value?: unknown
}

const equityOption = computed(() => {
  if (!hasEquity.value) return null
  const t = palette.value
  const modes = [...new Set(props.series.map((r) => r.mode))]
  return {
    backgroundColor: 'transparent',
    animation: false,
    aria: { enabled: true }, // ECharts 内建无障碍描述(role=img aria-label 之外的兜底)
    textStyle: { color: t.text },
    color: t.series,
    tooltip: {
      trigger: 'axis',
      ...tooltipStyle(t),
      axisPointer: { type: 'line', lineStyle: { color: t.axis, type: 'dashed' } },
      // time 轴 axisValue 是毫秒时间戳, 自行格式化; value 是 [时间, 权益] 二元组取第二元
      formatter: (ps: EquityTipParam[]): string => {
        if (!ps.length) return ''
        const lines = [fmtTs(Number(ps[0].axisValue))]
        for (const q of ps) {
          const v = Array.isArray(q.value) ? (q.value[1] as number | null) : null
          if (v === null || v === undefined) continue
          lines.push(`${q.marker ?? ''}${q.seriesName ?? ''}: ${Number(v).toLocaleString()}`)
        }
        return lines.join('<br>')
      },
    },
    legend: {
      top: 9,
      right: 14,
      itemWidth: 16,
      itemHeight: 8,
      textStyle: { color: t.dim, fontSize: 11 },
    },
    grid: { left: 70, right: 24, top: 46, bottom: 40 },
    xAxis: {
      type: 'time',
      ...axisStyle(t),
      axisLabel: { color: t.dim, fontSize: 11, formatter: fmtTs, hideOverlap: true },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      ...axisStyle(t),
      axisLabel: { color: t.dim, fontSize: 11, formatter: wan },
    },
    series: modes.map((m, i) => {
      // [snapshot_time, total_asset] 二元组按真实时间落点(ISO 串字典序=时间序)
      const data = props.series
        .filter((r) => r.mode === m)
        .map((r) => [r.snapshot_time, r.total_asset] as [string, number | null])
        .sort((a, b) => (a[0] < b[0] ? -1 : 1))
      const col = t.series[i % t.series.length]
      // time 轴下系列自身时间跨度过窄(如 live 仅几分钟的两次快照)时线宽不足 1px 不可见,
      // 按跨度占全图比例判定是否显式显符号
      const times = data.filter((d) => d[1] !== null && d[1] !== undefined).map((d) => +new Date(d[0]))
      const allTimes = props.series.map((r) => +new Date(r.snapshot_time))
      const globalSpan = Math.max(...allTimes) - Math.min(...allTimes) || 1
      const ownSpan = times.length > 1 ? Math.max(...times) - Math.min(...times) : 0
      return {
        name: `总资产(${m})`,
        type: 'line',
        smooth: 0.25,
        showSymbol: ownSpan / globalSpan < 0.02,
        symbolSize: 7,
        connectNulls: true,
        data,
        lineStyle: { color: col, width: 2.2 },
        itemStyle: { color: col },
        ...(i === 0 ? { areaStyle: { color: vGradient(t.brandArea[0], t.brandArea[1]) } } : {}),
      }
    }),
  }
})
</script>

<template>
  <div>
    <div class="ops-cards">
      <!-- 首响应前(全 null)显骨架, 不让空白冒充加载 -->
      <div
        v-for="i in cardsPending ? 4 : 0"
        :key="`sk-${i}`"
        class="card kpi-skeleton"
        aria-hidden="true"
      ></div>
      <div v-if="ov" class="card ops-card">
        <h3>今日活动</h3>
        <div class="big num">{{ cyclesToday }} <span class="unit">循环</span></div>
        <div class="sub t-muted">执行 {{ execsToday }} 笔（含拒单/失败留痕）</div>
      </div>

      <div v-if="budget" class="card ops-card">
        <h3>
          <GlossaryTip term="budget"><span>今日预算（跨模式）</span></GlossaryTip>
          <span class="cap-note num">单笔顶 {{ perOrderCap }}</span>
        </h3>
        <div class="big num">{{ budgetMain }} <span class="unit">已提交</span></div>
        <div class="sub t-muted num">{{ budgetSub }}</div>
      </div>

      <div v-if="cfg" class="card ops-card">
        <h3><GlossaryTip term="daemon"><span>守护状态</span></GlossaryTip></h3>
        <div class="big big-badge">
          <LvBadge :kind="daemon.kind" data-testid="daemon-badge">{{ daemon.text }}</LvBadge>
        </div>
        <div class="sub t-muted num">执行槽位 {{ slotsText }}</div>
      </div>

      <div v-if="cfg" class="card ops-card">
        <h3><GlossaryTip term="at_config"><span>auto-trade 配置（只读）</span></GlossaryTip></h3>
        <div class="big big-badge">
          <GlossaryTip v-if="at.mode === 'dry_run'" term="dry_run">
            <LvBadge kind="info">{{ at.mode }}</LvBadge>
          </GlossaryTip>
          <LvBadge v-else :kind="atModeCls">{{ at.mode || '?' }}</LvBadge>
          <LvBadge :kind="at.enabled ? 'warn' : 'info'">
            {{ at.enabled ? 'enabled' : 'disabled' }}
          </LvBadge>
        </div>
        <div class="sub t-muted">
          {{ atSub }} · <GlossaryTip term="confidence"><span>置信</span></GlossaryTip>≥{{ at.min_confidence ?? '?' }}
        </div>
      </div>
    </div>

    <div class="card chart-card" data-testid="live-equity">
      <div class="chart-head">
        <GlossaryTip term="equity_snap"><span class="chart-title">账户权益（循环快照）</span></GlossaryTip>
      </div>
      <div v-if="equityLoaded === false" class="chart-skeleton" aria-hidden="true"></div>
      <VChart
        v-else-if="equityOption"
        role="img"
        :aria-label="equityAria"
        :option="equityOption"
        autoresize
        class="chart-equity"
        data-testid="live-equity-chart"
      />
      <p v-else class="equity-hint t-muted" data-testid="live-equity-hint">{{ equityHint }}</p>
    </div>
  </div>
</template>

<style scoped>
.ops-cards {
  display: grid;
  gap: var(--gap);
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  margin-bottom: var(--gap);
}

.ops-card h3 {
  color: var(--text-3);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.big {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.25;
}

.big-badge {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 30px;
}

.unit {
  color: var(--text-3);
  font-size: 13px;
  font-weight: 400;
}

/* 卡标题旁的次要参数(单笔上限) — 比标题再弱一档 */
.cap-note {
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0;
  margin-left: 6px;
}

.sub {
  font-size: 12px;
  margin-top: 4px;
}

.chart-card {
  margin-bottom: var(--gap);
  padding: 10px 12px;
}

.chart-head {
  padding: 4px 4px 0;
}

.chart-title {
  font-family: var(--font-display);
  font-size: 13.5px;
  font-weight: 600;
}

.chart-equity {
  height: 340px;
  width: 100%;
}

.equity-hint {
  padding: 46px 0;
  text-align: center;
}

/* 加载骨架: 卡片沿用全站 .kpi-skeleton 脉冲; 图表区块占满真实高度不跳版 */
.kpi-skeleton {
  animation: ops-skeleton-pulse 1.4s ease-in-out infinite;
  min-height: 96px;
}

.chart-skeleton {
  animation: ops-skeleton-pulse 1.4s ease-in-out infinite;
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  height: 340px;
  width: 100%;
}

@keyframes ops-skeleton-pulse {
  50% {
    opacity: 0.5;
  }
}

@media (prefers-reduced-motion: reduce) {
  .kpi-skeleton,
  .chart-skeleton {
    animation: none;
    opacity: 0.7;
  }
}
</style>
