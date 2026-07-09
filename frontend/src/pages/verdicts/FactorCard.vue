<script setup lang="ts">
import { computed } from 'vue'

import type { VerdictFactor } from '@/api/types'

import { f2, f3, f4, gateTrack, gradeClass, isPassReason, pct } from './gates'
import { mcell } from './verdict-metric-cell'

/* 因子判决卡片(设计 0705-verdict-cards §4) — 表格行的替代品:
 * 左缘判决色条 → id+中文名+评分等级 → 三项关键指标 → 闸门轨道(签名元素) → PASS/FAIL徽章
 * (+FAIL 首要死因)。根元素是原生 <button>: 点击/回车/空格触发原生 click,
 * 无需自定义 emit 或 keydown 处理(父层用 @click 走 attrs fallthrough)。 */
const props = defineProps<{ factor: VerdictFactor; longOnly: boolean; hasSplit: boolean }>()

const track = computed(() => gateTrack(props.factor, props.longOnly, props.hasSplit))
const passCount = computed(() => track.value.filter((c) => c.state === 'pass').length)

/* 数值格子配色改走 mcell(设计 §6.1): OOS超额/OOS多空=带符号收益→行情色(正红/负绿),
 * IC均值/超额IR/IR=预测力质量指标→中性; 闸门判定色只留给下方 PASS/FAIL 徽章与闸门轨道。 */
const metrics = computed(() => {
  const f = props.factor
  return props.longOnly
    ? [
        { label: 'IC均值', ...mcell('ic_mean', f.ic_mean, f4) },
        { label: '超额IR', ...mcell('excess_ir', f.excess_ir, f2) },
        { label: 'OOS超额', ...mcell('oos_top_excess_return', f.oos_top_excess_return, pct) },
      ]
    : [
        { label: 'IC均值', ...mcell('ic_mean', f.ic_mean, f4) },
        { label: 'IR', ...mcell('ir', f.ir, f3) },
        { label: 'OOS多空', ...mcell('oos_long_short_return', f.oos_long_short_return, pct) },
      ]
})

const firstFailReason = computed(() => {
  if (props.factor.passed) return null
  return (props.factor.reasons ?? []).find((r) => !isPassReason(r)) ?? null
})
</script>

<template>
  <button
    type="button"
    class="factor-card card card--hoverable"
    :class="factor.passed ? 'verdict-pass' : 'verdict-fail'"
    data-testid="verdict-card"
  >
    <div class="fc-head">
      <span class="fc-id-name">
        <span class="fid num">{{ factor.factor_id }}</span>
        <span class="fname">{{ factor.factor_name ?? '' }}</span>
      </span>
      <span
        v-if="factor.score !== null && factor.score !== undefined"
        class="grade-badge"
        :class="gradeClass(factor.grade)"
        data-testid="verdict-card-grade"
      >{{ (factor.grade ?? '?').toUpperCase() }} {{ factor.score.toFixed(0) }}</span>
      <span v-else class="grade-badge grade-na" data-testid="verdict-card-grade">—</span>
    </div>

    <div class="fc-metrics">
      <span v-for="m in metrics" :key="m.label" class="fc-metric">
        <i>{{ m.label }}</i>
        <b class="num" :class="m.cls">{{ m.text }}</b>
      </span>
    </div>

    <div class="fc-track" data-testid="verdict-card-track" :aria-label="`7 道闸门通过 ${passCount} 道`">
      <span v-for="c in track" :key="c.key" class="gate-cell" :class="c.state" :title="c.detail" />
    </div>

    <div class="fc-foot">
      <span class="badge" :class="factor.passed ? 'pass' : 'fail'">{{ factor.passed ? 'PASS' : 'FAIL' }}</span>
    </div>
    <p
      v-if="firstFailReason"
      class="fc-fail-reason"
      :title="firstFailReason"
      data-testid="verdict-card-fail-reason"
    >{{ firstFailReason }}</p>
  </button>
</template>

<style scoped>
.factor-card {
  animation: card-in var(--dur-base) var(--ease-out) backwards;
  appearance: none;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  font: inherit;
  gap: 10px;
  min-height: 152px;
  text-align: left;
  width: 100%;
}

.factor-card.verdict-pass {
  border-left-color: var(--c-pass);
  border-left-width: 3px;
}

.factor-card.verdict-fail {
  border-left-color: var(--c-fail);
  border-left-width: 3px;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .factor-card {
    animation: none;
  }
}

.fc-head {
  align-items: flex-start;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.fc-id-name {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.fid {
  font-size: 13px;
  font-weight: 600;
}

.fname {
  color: var(--text-3);
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grade-badge {
  border-radius: var(--radius-sm);
  flex-shrink: 0;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  white-space: nowrap;
}

.grade-badge.grade-na {
  background: var(--bg-3);
  color: var(--text-3);
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

.fc-metrics {
  display: flex;
  justify-content: space-between;
}

.fc-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.fc-metric i {
  color: var(--text-3);
  font-size: 10.5px;
  font-style: normal;
}

.fc-metric b {
  font-size: 13px;
  font-weight: 600;
}

.fc-track {
  display: flex;
  gap: 3px;
}

.gate-cell {
  border-radius: 2px;
  height: 10px;
  width: 10px;
}

.gate-cell.pass {
  background: color-mix(in srgb, var(--c-pass) 72%, transparent);
}

.gate-cell.fail {
  background: var(--c-fail);
}

.gate-cell.na {
  background: transparent;
  border: 1px solid var(--border);
}

.fc-foot {
  margin-top: auto;
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

.fc-fail-reason {
  color: var(--c-fail);
  font-size: 11px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
