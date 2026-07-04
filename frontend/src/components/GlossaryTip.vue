<script setup lang="ts">
import { NPopover } from 'naive-ui'
import { computed } from 'vue'

import { GLOSSARY } from '@/glossary'

/* 术语教学 tips — 旧 applyGlossary 的组件化(设计 §4.1):
 * 字典缺词降级为纯文本(对等旧 vendor 缺失降级); 标题动态取插槽当前文本由
 * n-popover 触发时的 DOM 决定, 正文来自字典。 */
const props = defineProps<{ term: string }>()

const body = computed(() => GLOSSARY[props.term])
</script>

<template>
  <NPopover v-if="body" trigger="hover" placement="top" style="max-width: 360px" :delay="100">
    <template #trigger>
      <span class="gloss"><slot /></span>
    </template>
    <div class="tip-body">{{ body }}</div>
  </NPopover>
  <span v-else><slot /></span>
</template>

<style scoped>
.gloss {
  border-bottom: 1px dotted var(--text-3);
  cursor: help;
}

.tip-body {
  font-size: 12.5px;
  line-height: 1.6;
}
</style>
