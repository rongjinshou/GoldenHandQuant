<script setup lang="ts">
import { NPopover } from 'naive-ui'
import { computed } from 'vue'

import { GLOSSARY } from '@/glossary'

/* 术语教学 tips — 旧 applyGlossary 的组件化(设计 §4.1):
 * 字典缺词降级为纯文本(对等旧 vendor 缺失降级); 标题动态取插槽当前文本由
 * n-popover 触发时的 DOM 决定, 正文来自字典。 */
/* plain: 插槽内容自带交互形态(色块徽章/按钮)时关掉虚线下划线 — 双重悬浮提示会显得多余,
 * 保留 cursor:help 即可, 元素本身的色彩/形状已是"可交互"的视觉线索。 */
const props = withDefaults(defineProps<{ term: string; plain?: boolean }>(), { plain: false })

const body = computed(() => GLOSSARY[props.term])
</script>

<template>
  <NPopover v-if="body" trigger="hover" placement="top" style="max-width: 360px" :delay="100">
    <template #trigger>
      <span class="gloss" :class="{ plain }"><slot /></span>
    </template>
    <div class="tip-body">{{ body }}</div>
  </NPopover>
  <span v-else><slot /></span>
</template>

<style scoped>
.gloss {
  border-bottom: 1px dotted var(--text-3);
  cursor: help;
  /* flex-column label 里防 stretch: 虚线只压文字宽, 不拉满整列(行内场景 width 对 inline 无效, 不受影响) */
  width: fit-content;
}

.gloss.plain {
  border-bottom: none;
}

.tip-body {
  font-size: 12.5px;
  line-height: 1.6;
}
</style>
