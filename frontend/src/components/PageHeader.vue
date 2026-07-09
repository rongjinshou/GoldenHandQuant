<script setup lang="ts">
/* 页头基元: 六页 page-head + guide 去重(设计 §7)。
 * meta 副行可选; guide 简单文案用 prop, 含 GlossaryTip 等复杂引导用默认插槽。 */
defineProps<{ title: string; meta?: string; guide?: string }>()
</script>

<template>
  <div class="page-header">
    <header class="page-head">
      <h2>{{ title }}</h2>
      <span v-if="meta" class="meta-line t-muted num">{{ meta }}</span>
      <slot name="meta" />
    </header>
    <p v-if="$slots.default || guide" class="guide t-muted">
      <slot>{{ guide }}</slot>
    </p>
  </div>
</template>

<style scoped>
.page-head {
  align-items: baseline;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.page-head h2 {
  font-size: var(--fs-xl);
  line-height: var(--lh-xl);
  margin: 0;
}

.meta-line {
  font-size: var(--fs-sm);
}

.guide {
  font-size: var(--fs-base);
  line-height: var(--lh-base);
  margin: 0 0 var(--space-5);
  max-width: 74ch;
}
</style>
