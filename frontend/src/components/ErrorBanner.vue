<script setup lang="ts">
/* 错误横幅: 底色用失败红三件套(此前误用品牌橙 --accent-soft)。
 * retry/close 可选, 默认关 → 现有 <ErrorBanner :msg/> 用法零破坏; 接线在批二。 */
withDefaults(defineProps<{ msg: string; retryable?: boolean; dismissible?: boolean }>(), {
  retryable: false,
  dismissible: false,
})
defineEmits<{ retry: []; close: [] }>()
</script>

<template>
  <div class="error-banner" role="alert" data-testid="error-banner">
    <span class="eb-msg">⚠ {{ msg }}</span>
    <span v-if="retryable || dismissible" class="eb-actions">
      <button v-if="retryable" type="button" class="eb-btn" @click="$emit('retry')">重试</button>
      <button v-if="dismissible" type="button" class="eb-btn eb-close" aria-label="关闭" @click="$emit('close')">✕</button>
    </span>
  </div>
</template>

<style scoped>
.error-banner {
  align-items: center;
  background: var(--c-fail-soft);
  border: 1px solid var(--c-fail-border);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  display: flex;
  font-size: var(--fs-base);
  gap: var(--space-3);
  justify-content: space-between;
  margin-bottom: var(--space-4);
  padding: 10px 14px;
}

.eb-actions {
  display: inline-flex;
  gap: var(--space-2);
}

.eb-btn {
  background: transparent;
  border: 1px solid var(--c-fail-border);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  cursor: pointer;
  font-size: var(--fs-xs);
  min-height: 24px;
  min-width: 24px;
  padding: 2px 8px;
}

.eb-close {
  border-color: transparent;
}
</style>
