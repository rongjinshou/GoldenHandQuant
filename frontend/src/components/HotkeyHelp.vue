<script setup lang="ts">
import { NModal } from 'naive-ui'

import { NAV_ITEMS } from '@/router'

/* 快捷键帮助浮层('?' 唤起, R4 可发现性): 全站快捷键的唯一集中式说明。
 * Esc/遮罩点击/✕ 三途径关闭均由 NModal preset=card 默认行为覆盖(closeOnEsc/maskClosable
 * 默认 true, 均收敛到 update:show(false) — 同 FactorDetailModal 已验证结论), 本组件只透传 show。
 * 页签行从 NAV_ITEMS 动态生成: 路由增删页签时本浮层零改动跟随。 */
defineProps<{ show: boolean }>()

const emit = defineEmits<{ 'update:show': [boolean] }>()
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    size="small"
    title="键盘快捷键"
    :style="{ width: 'min(360px, 92vw)' }"
    data-testid="hotkey-help"
    @update:show="(v: boolean) => emit('update:show', v)"
  >
    <div class="hk" data-testid="hotkey-help-body">
      <p class="hk-group">切换页签</p>
      <ul class="hk-list">
        <li
          v-for="(item, i) in NAV_ITEMS"
          :key="item.name"
          class="hk-row"
          data-testid="hotkey-help-nav"
        >
          <kbd class="hk-key">{{ i + 1 }}</kbd>
          <span class="hk-desc">{{ item.label }}</span>
        </li>
      </ul>

      <p class="hk-group">通用</p>
      <ul class="hk-list">
        <li class="hk-row">
          <kbd class="hk-key">?</kbd>
          <span class="hk-desc">打开本帮助</span>
        </li>
        <li class="hk-row">
          <kbd class="hk-key">Esc</kbd>
          <span class="hk-desc">关闭弹层</span>
        </li>
      </ul>
    </div>
  </NModal>
</template>

<style scoped>
.hk {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.hk-group {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  letter-spacing: 0.06em;
  margin: 0;
}

.hk-group + .hk-group,
.hk-list + .hk-group {
  margin-top: var(--space-2);
}

.hk-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  list-style: none;
  margin: 0;
  padding: 0;
}

.hk-row {
  align-items: center;
  display: flex;
  gap: var(--space-3);
}

.hk-key {
  background: var(--bg-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
  min-width: 30px;
  padding: 2px var(--space-2);
  text-align: center;
}

.hk-desc {
  color: var(--text-2);
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}
</style>
