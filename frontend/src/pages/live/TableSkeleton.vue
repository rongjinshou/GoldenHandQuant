<script setup lang="ts">
/* Live 页表格加载骨架 — 首响应前占位, 避免空态文案("暂无 X")冒充加载态。
 * 纯装饰 aria-hidden; reduced-motion 下停脉冲(scoped 覆盖 base 全局降级)。 */
withDefaults(defineProps<{ rows?: number; cols?: number }>(), { rows: 3, cols: 5 })
</script>

<template>
  <div class="tbl-skeleton" data-testid="live-skeleton" aria-hidden="true">
    <div v-for="r in rows" :key="r" class="sk-row">
      <span v-for="c in cols" :key="c" class="sk-cell" />
    </div>
  </div>
</template>

<style scoped>
.tbl-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
}

.sk-row {
  display: grid;
  gap: 10px;
  grid-auto-columns: 1fr;
  grid-auto-flow: column;
}

.sk-cell {
  animation: sk-pulse 1.4s ease-in-out infinite;
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  height: 16px;
}

/* 首列略宽, 尾列略窄 — 读作真实表格节奏而非纯色块 */
.sk-row .sk-cell:first-child {
  border-radius: var(--radius-sm);
}

@keyframes sk-pulse {
  50% {
    opacity: 0.45;
  }
}

@media (prefers-reduced-motion: reduce) {
  .sk-cell {
    animation: none;
    opacity: 0.7;
  }
}
</style>
