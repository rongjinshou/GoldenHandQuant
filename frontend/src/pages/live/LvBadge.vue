<script setup lang="ts">
import type { BadgeKind } from './logic'

/* 实盘页统一徽章 — 四语义档(info 中性 / pass 绿 / warn 黄 / fail 红)。
 * 旧 live.js 里散落的 .badge.info/.pass/.warn/.fail 收敛为单一组件, 供守护/配置/
 * 循环模式/执行状态复用; 非 prop 透传属性(如 data-testid)落到根 span。 */

defineProps<{ kind: BadgeKind }>()
</script>

<template>
  <span class="lv-badge" :class="kind"><slot /></span>
</template>

<style scoped>
.lv-badge {
  align-items: center;
  border-radius: 20px;
  display: inline-flex;
  font-family: var(--font-display);
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.3;
  padding: 3px 10px;
  white-space: nowrap;
}

.info {
  background: var(--bg-3);
  color: var(--text-2);
}

.pass {
  background: color-mix(in srgb, var(--c-pass) 16%, transparent);
  color: var(--c-pass);
}

.warn {
  background: color-mix(in srgb, var(--c-warn) 18%, transparent);
  color: var(--c-warn);
}

.fail {
  background: color-mix(in srgb, var(--c-fail) 16%, transparent);
  color: var(--c-fail);
}
</style>
