<script setup lang="ts">
export interface SubNavItem {
  key: string
  label: string
  badge?: number | string // string 供截断形态 "500+"（Live 子视图, R4）
}

defineProps<{ items: SubNavItem[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [key: string] }>()
</script>

<template>
  <nav class="subnav" data-testid="subnav">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="subnav-item"
      :class="{ active: item.key === modelValue }"
      :aria-current="item.key === modelValue ? 'page' : undefined"
      :data-testid="`subnav-${item.key}`"
      @click="emit('update:modelValue', item.key)"
    >
      {{ item.label }}
      <span v-if="item.badge !== undefined" class="subnav-badge num">{{ item.badge }}</span>
    </button>
  </nav>
</template>

<style scoped>
.subnav {
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 2px;
  margin-bottom: var(--gap);
}

.subnav-item {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-2);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 13.5px;
  padding: 9px 14px;
  transition: color var(--dur-fast) var(--ease-out), border-color var(--dur-base) var(--ease-out);
}

.subnav-item:hover {
  color: var(--text);
}

/* 激活项文字用文字级 accent(F-01/F-04): light #d97757 压 bg 仅 2.96:1 → #a8462e 5.57:1;
   底边条仍 --accent(图形标记 3:1 门槛不同) */
.subnav-item.active {
  border-bottom-color: var(--accent);
  color: var(--accent-strong, var(--accent));
}

.subnav-badge {
  background: var(--bg-3);
  border-radius: 9px;
  color: var(--text-3);
  font-size: 11px;
  margin-left: 5px;
  padding: 1px 7px;
}

.subnav-item.active .subnav-badge {
  background: var(--accent-soft);
  color: var(--accent-strong, var(--accent)); /* accent-soft 合成底上的 11px 小字, 同 F-01 换文字级 accent */
}
</style>
