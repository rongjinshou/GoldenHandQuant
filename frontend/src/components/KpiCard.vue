<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

/* KPI 卡: countUp 数字滚动(rAF, reduced-motion 下 --dur-base=0 时直接终值) */
const props = withDefaults(
  defineProps<{
    label: string
    value: string | number
    tone?: 'up' | 'down' | 'neutral'
    sub?: string
    countUp?: boolean
  }>(),
  { tone: 'neutral', sub: '', countUp: false },
)

const display = ref<string>(String(props.value))

function animateTo(target: number): void {
  const durMs =
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dur-base')) * 3 || 0
  if (durMs <= 0) {
    display.value = target.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
    return
  }
  const start = performance.now()
  const from = 0
  function frame(now: number): void {
    const t = Math.min(1, (now - start) / durMs)
    const eased = 1 - Math.pow(1 - t, 3)
    display.value = (from + (target - from) * eased).toLocaleString('zh-CN', {
      maximumFractionDigits: 2,
    })
    if (t < 1) requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
}

function render(): void {
  if (props.countUp && typeof props.value === 'number' && Number.isFinite(props.value)) {
    animateTo(props.value)
  } else {
    display.value =
      typeof props.value === 'number'
        ? props.value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
        : props.value
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
    <div class="kpi-value num" :class="`tone-${tone}`">{{ display }}</div>
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

.kpi-sub {
  font-size: 12px;
  margin-top: 4px;
}
</style>
