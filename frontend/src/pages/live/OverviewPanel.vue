<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { AccountSnapshot, LiveBudget, LiveConfig, LiveOverview } from '@/api/types'
import GlossaryTip from '@/components/GlossaryTip.vue'
import { axisStyle, tooltipStyle, useChartTheme, vGradient } from '@/composables/useChartTheme'

import LvBadge from './LvBadge.vue'
import { daemonBadge, num, wan, type BadgeKind } from './logic'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

/* 概览子视图 — 旧 renderOpsCards + 权益曲线段对等:
 * 运维四卡(今日活动/预算/守护/auto-trade 配置只读) + 权益曲线(≥2 快照才成曲线,
 * dry_run 与 live 按 mode 分开画; 单点/零点显示提示文案而非空图框)。
 * 各端点独立轮询, 卡片按各自数据就绪逐个出现(单端点失败不拖垮其他)。 */

const props = defineProps<{
  ov: LiveOverview | null
  budget: LiveBudget | null
  cfg: LiveConfig | null
  series: AccountSnapshot[]
}>()

const palette = useChartTheme()

const cyclesToday = computed(() => props.ov?.cycles_today ?? 0)
const execsToday = computed(() => props.ov?.executions_today ?? 0)

const budgetMain = computed(() => num(props.budget?.submitted_notional))
const budgetSub = computed(() => {
  const b = props.budget
  if (!b) return ''
  return `上限 ${num(b.daily_notional_cap)} · 余 ${num(b.remaining)} · 单笔顶 ${num(b.per_order_notional_cap)}`
})

const daemon = computed(() =>
  props.cfg ? daemonBadge(props.cfg) : { kind: 'info' as BadgeKind, text: '' },
)
const slotsText = computed(() => (props.cfg?.today.expected_slots ?? []).join(' / ') || '-')

const at = computed(() => props.cfg?.auto_trade ?? {})
const atModeCls = computed(() => (at.value.mode === 'live' ? 'fail' : 'info'))
const atSub = computed(
  () => `${at.value.strategy || ''} · ${(at.value.symbols ?? []).length} 标的 · `,
)

// ---- 权益曲线(旧口径: ≥2 快照; 单点提示采样方法; mode 分线, 首线带品牌渐变面) ----
const hasEquity = computed(() => props.series.length >= 2)
const equityHint = computed(() =>
  props.series.length === 1
    ? '已有 1 条权益快照——多次同步后将绘制权益曲线（scripts/sync_live_account.py --watch 30 持续采样）。'
    : '暂无权益快照。',
)

const equityOption = computed(() => {
  if (!hasEquity.value) return null
  const t = palette.value
  const modes = [...new Set(props.series.map((r) => r.mode))]
  const timeline = [...new Set(props.series.map((r) => r.snapshot_time))].sort()
  const tsIndex = new Map(timeline.map((v, i) => [v, i]))
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { color: t.text },
    color: t.series,
    tooltip: {
      trigger: 'axis',
      ...tooltipStyle(t),
      axisPointer: { type: 'line', lineStyle: { color: t.axis, type: 'dashed' } },
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
      type: 'category',
      boundaryGap: false,
      data: timeline.map((v) => v.slice(5, 16)),
      ...axisStyle(t),
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      scale: true,
      ...axisStyle(t),
      axisLabel: { color: t.dim, fontSize: 11, formatter: wan },
    },
    series: modes.map((m, i) => {
      const data: (number | null)[] = new Array<number | null>(timeline.length).fill(null)
      props.series
        .filter((r) => r.mode === m)
        .forEach((r) => {
          const idx = tsIndex.get(r.snapshot_time)
          if (idx !== undefined) data[idx] = r.total_asset
        })
      const col = t.series[i % t.series.length]
      return {
        name: `总资产(${m})`,
        type: 'line',
        smooth: 0.25,
        showSymbol: false,
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
      <div v-if="ov" class="card ops-card">
        <h3>今日活动</h3>
        <div class="big num">{{ cyclesToday }} <span class="unit">循环</span></div>
        <div class="sub t-muted">执行 {{ execsToday }} 笔（含拒单/失败留痕）</div>
      </div>

      <div v-if="budget" class="card ops-card">
        <h3><GlossaryTip term="budget"><span>今日预算（跨模式）</span></GlossaryTip></h3>
        <div class="big num">{{ budgetMain }}</div>
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
          {{ atSub }}<GlossaryTip term="confidence"><span>置信</span></GlossaryTip>≥{{ at.min_confidence ?? '?' }}
        </div>
      </div>
    </div>

    <div class="card chart-card" data-testid="live-equity">
      <div class="chart-head">
        <GlossaryTip term="equity_snap"><span class="chart-title">账户权益（循环快照）</span></GlossaryTip>
      </div>
      <VChart v-if="equityOption" :option="equityOption" autoresize class="chart-equity" />
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
</style>
