<script setup lang="ts">
import { computed } from 'vue'

import { useThemeStore } from '@/stores/theme'

const store = useThemeStore()
const label = computed(() => (store.theme === 'dark' ? '切换到日间主题' : '切换到夜间主题'))
</script>

<template>
  <button
    class="theme-toggle"
    type="button"
    data-testid="theme-toggle"
    :aria-label="label"
    :title="label"
    @click="store.toggle()"
  >
    <span aria-hidden="true">{{ store.theme === 'dark' ? '☀' : '☾' }}</span>
  </button>
</template>

<style scoped>
.theme-toggle {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 7px 10px;
  transition:
    color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out),
    transform var(--dur-fast) var(--ease-out);
}

.theme-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
  transform: translateY(-1px);
}
</style>
