<script setup lang="ts">
defineProps<{ msg: string }>()
</script>

<template>
  <div class="error-banner" role="alert" data-testid="error-banner">⚠ {{ msg }}</div>
</template>

<style scoped>
.error-banner {
  background: var(--accent-soft);
  border: 1px solid var(--c-fail);
  border-radius: var(--radius-sm);
  color: var(--c-fail);
  font-size: 13.5px;
  margin-bottom: var(--gap);
  padding: 10px 14px;
}
</style>
