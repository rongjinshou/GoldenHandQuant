<script setup lang="ts">
import { NPopover } from 'naive-ui'
import { computed, ref } from 'vue'

import { GLOSSARY } from '@/glossary'

/* 术语教学 tips — 旧 applyGlossary 的组件化(设计 §4.1 / §8 S1 无障碍):
 * 字典缺词降级为纯文本(对等旧 vendor 缺失降级); 正文来自字典。
 * 焦点可达(WCAG 1.4.13): 触发元素 tabindex=0 role=button, NPopover 改 manual,
 * 由 focus/blur/hover/Esc 控制显隐 —— 键盘用户 Tab 到即可读到术语解释。
 * API(term prop + 默认插槽)保持不变(118 处消费点)。 */
/* plain: 插槽内容自带交互形态(色块徽章/按钮)时关掉虚线下划线 — 双重悬浮提示会显得多余,
 * 保留 cursor:help 即可, 元素本身的色彩/形状已是"可交互"的视觉线索。 */
const props = withDefaults(defineProps<{ term: string; plain?: boolean }>(), { plain: false })

const body = computed(() => GLOSSARY[props.term])
const show = ref(false)
function open(): void {
  show.value = true
}
function close(): void {
  show.value = false
}
</script>

<template>
  <NPopover v-if="body" :show="show" trigger="manual" placement="top" style="max-width: 360px">
    <template #trigger>
      <span
        class="gloss"
        :class="{ plain }"
        tabindex="0"
        role="button"
        :aria-label="term"
        @focus="open"
        @blur="close"
        @mouseenter="open"
        @mouseleave="close"
        @keydown.escape="close"
        ><slot
      /></span>
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
