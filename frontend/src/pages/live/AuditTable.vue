<script setup lang="ts">
import { computed, h, type VNode } from 'vue'

import type { AuditLog } from '@/api/types'
import DataTable from '@/components/DataTable.vue'

import { sliceTime } from './logic'

/* 审计日志表 — 旧 live.js 审计段对等, 走自研 DataTable(50 行 + 展开态跨轮询保持):
 * 资源列拼 type:id, 明细列 <code> 截前 120 字(Vue 文本节点自转义, 无需手工 escHtml)。 */

type Col = {
  key: string
  title: string
  render?: (row: Record<string, unknown>) => VNode | string
  align?: 'right'
}

const props = defineProps<{ logs: AuditLog[] }>()

const rows = computed<Record<string, unknown>[]>(
  () => props.logs as unknown as Record<string, unknown>[],
)

function asLog(row: Record<string, unknown>): AuditLog {
  return row as unknown as AuditLog
}

const columns: Col[] = [
  { key: 'timestamp', title: '时间', render: (r) => sliceTime(asLog(r).timestamp) },
  { key: 'action', title: '动作' },
  {
    key: 'resource',
    title: '资源',
    render: (r) => {
      const l = asLog(r)
      return `${l.resource_type ?? ''}:${l.resource_id ?? ''}`
    },
  },
  {
    key: 'details',
    title: '明细',
    render: (r) => h('code', {}, String(asLog(r).details ?? '').slice(0, 120)),
  },
]
</script>

<template>
  <div data-testid="live-audit">
    <DataTable :rows="rows" :columns="columns" row-key="log_id" />
    <p v-if="!logs.length" class="empty-cell t-muted">暂无审计记录</p>
  </div>
</template>

<style scoped>
.empty-cell {
  padding: 22px 0;
  text-align: center;
}

code {
  color: var(--text-2);
  font-size: 12px;
}
</style>
