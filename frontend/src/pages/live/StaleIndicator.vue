<script setup lang="ts">
/* 连接状态行(R6-01) — 消费 usePolling 已有的 isStale/lastSuccessAt(不改 usePolling):
 * 正常态低调常驻「数据更新于 HH:mm:ss」(text-3/fs-xs, 每次成功 tick 响应式刷新);
 * isStale(距上次成功 >2×interval)转警示「⚠ 连接中断，显示 HH:mm:ss 前数据，重试中…」,
 * 恢复后 isStale 复位、时间恢复走表 — 回正常态由响应式天然成立, 无需额外状态。
 * role=status/aria-live=polite 只挂中断分支: 正常态每 5s 变一次时间, 若也进 live region
 * 会对读屏轮播刷屏; 中断态文案里的时间冻结(lastSuccessAt 不再前进), 不会重复播报。
 * 从未成功(lastSuccessAt=null)整行不渲染 — 首载失败已有 ErrorBanner, 不重复表达。 */
import { computed } from 'vue'

import { formatClockTime } from './logic'

const props = defineProps<{ isStale: boolean; lastSuccessAt: number | null }>()

const timeText = computed(() =>
  props.lastSuccessAt === null ? '' : formatClockTime(props.lastSuccessAt),
)
</script>

<template>
  <p v-if="timeText" class="conn-line" data-testid="live-conn-status">
    <span v-if="isStale" class="conn-stale" role="status" aria-live="polite" data-testid="live-conn-stale">
      ⚠ 连接中断，显示 <span class="num">{{ timeText }}</span> 前数据，重试中…
    </span>
    <span v-else class="conn-ok" data-testid="live-conn-ok">
      数据更新于 <span class="num">{{ timeText }}</span>
    </span>
  </p>
</template>

<style scoped>
/* 常驻小字: 贴在页头导语与 KPI 行之间, 负上边距吃掉 PageHeader guide 的 24px 下距一部分 */
.conn-line {
  color: var(--text-3);
  font-size: var(--fs-xs);
  line-height: var(--lh-xs);
  margin: calc(-1 * var(--space-3)) 0 var(--space-3);
}

/* 中断态: warn 文字强化色(light #6d501c 压 bg 7.08:1; 回退 --c-warn 兜底旧变量缺失) */
.conn-stale {
  color: var(--c-warn-strong, var(--c-warn));
}
</style>
