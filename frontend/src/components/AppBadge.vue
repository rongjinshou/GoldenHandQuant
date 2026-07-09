<script setup lang="ts">
/* 徽章基元(设计 §7): 收敛 8 份重复 badge 变体。
 * kind 消费状态色三件套(tokens §4.2); accent 用 --text-on-accent 保证白底达标。 */
withDefaults(defineProps<{ kind: 'info' | 'pass' | 'warn' | 'fail' | 'accent'; size?: 'sm' | 'md' }>(), {
  size: 'md',
})
</script>

<template>
  <span class="badge" :class="[`badge--${kind}`, { 'badge--sm': size === 'sm' }]" data-testid="app-badge">
    <slot />
  </span>
</template>

<style scoped>
.badge {
  align-items: center;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  display: inline-flex;
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 2px 8px;
}

.badge--sm {
  padding: 1px 6px;
}

.badge--pass { background: var(--c-pass-soft); border-color: var(--c-pass-border); color: var(--c-pass); }
.badge--fail { background: var(--c-fail-soft); border-color: var(--c-fail-border); color: var(--c-fail); }
.badge--warn { background: var(--c-warn-soft); border-color: var(--c-warn-border); color: var(--c-warn); }
.badge--info { background: var(--c-info-soft); border-color: var(--c-info-border); color: var(--c-info); }
.badge--accent { background: var(--accent); color: var(--text-on-accent); }
</style>
