<script lang="ts">
/** countUp 缓动插值(纯函数, 便于单测): 进度 t∈[0,1] 时从 prev 滚到 target 的当前值。
 * t=0 返回 prev(上次终值) —— 刷新时从旧值滚起而非先归零(设计 §9)。 */
export function rollFrom(prev: number, target: number, t: number): number {
  const eased = 1 - Math.pow(1 - t, 3)
  return prev + (target - prev) * eased
}
</script>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

/* KPI 卡: countUp 数字滚动(rAF, reduced-motion 下 --dur-base=0 时直接终值) */
const props = withDefaults(
  defineProps<{
    label: string
    value: string | number
    tone?: 'up' | 'down' | 'neutral'
    sub?: string
    unit?: string
    countUp?: boolean
  }>(),
  { tone: 'neutral', sub: '', unit: '', countUp: false },
)

const display = ref<string>(String(props.value))
let prevValue = 0 // 上次数值终值; 刷新时从此滚起(不再从 0 归零)

function fmt(n: number): string {
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function animateTo(target: number): void {
  const durMs =
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dur-base')) * 3 || 0
  const from = prevValue
  prevValue = target // 记录新终值供下次刷新滚起
  if (durMs <= 0) {
    display.value = fmt(target)
    return
  }
  const start = performance.now()
  function frame(now: number): void {
    const t = Math.min(1, (now - start) / durMs)
    display.value = fmt(rollFrom(from, target, t))
    if (t < 1) requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
}

function render(): void {
  if (props.countUp && typeof props.value === 'number' && Number.isFinite(props.value)) {
    animateTo(props.value)
  } else if (typeof props.value === 'number') {
    if (Number.isFinite(props.value)) prevValue = props.value // 非动画数值也记录, 以便后续滚动从此起
    display.value = fmt(props.value)
  } else {
    display.value = props.value
  }
}

onMounted(render)
watch(
  () => props.value,
  () => render(),
)
</script>

<template>
  <div class="kpi card card--hoverable" data-testid="kpi-card">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value num" :class="`tone-${tone}`">
      {{ display }}<span v-if="unit" class="kpi-unit">{{ unit }}</span>
    </div>
    <div v-if="sub" class="kpi-sub t-muted">{{ sub }}</div>
  </div>
</template>

<style scoped>
.kpi {
  min-width: 160px;
  padding: 14px 18px;
}

.kpi-label {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.kpi-value {
  font-size: 26px;
  font-weight: 600;
  line-height: 1.2;
}

.tone-up {
  color: var(--c-up);
}

.tone-down {
  color: var(--c-down);
}

.kpi-unit {
  color: var(--text-3);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 400;
  margin-left: 4px;
}

.kpi-sub {
  font-size: 12px;
  margin-top: 4px;
}
</style>
