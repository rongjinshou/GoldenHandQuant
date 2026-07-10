<script setup lang="ts">
import { computed, h } from 'vue'

import type { ExecutionRecord } from '@/api/types'
import DataTable, { type Column } from '@/components/DataTable.vue'

import { directionLabel, execStatusLabel } from './labels'
import LvBadge from './LvBadge.vue'
import { num, sliceTime, statusBadge } from './logic'

/* 执行留痕表 — 旧 live.js 执行段对等, 走自研 DataTable(50 行 + 展开态跨轮询保持):
 * 方向买红卖绿(t-buy/t-sell), 状态走统一徽章语义(statusBadge), 限价/金额/置信缺失显 '-'。
 * 数值/时间/状态列 sortable(按行原始值排: 数值列数值序且 null 恒沉底,
 * 时间是 ISO 串故字典序即时间序), 列类型直接复用 DataTable 导出的 Column。 */

const props = defineProps<{ executions: ExecutionRecord[] }>()

// 接口类型不含隐式索引签名, DataTable 消费 Record<string, unknown>, 故此处收窄口径
const rows = computed<Record<string, unknown>[]>(
  () => props.executions as unknown as Record<string, unknown>[],
)

function asExec(row: Record<string, unknown>): ExecutionRecord {
  return row as unknown as ExecutionRecord
}

const columns: Column[] = [
  {
    key: 'submitted_at',
    title: '时间',
    sortable: true,
    render: (r) => sliceTime(asExec(r).submitted_at),
  },
  { key: 'symbol', title: '标的' },
  {
    key: 'direction',
    title: '方向',
    render: (r) => {
      const dir = asExec(r).direction
      return h('span', { class: dir === 'BUY' ? 't-buy' : 't-sell' }, directionLabel(dir))
    },
  },
  {
    key: 'exec_price',
    title: '限价',
    align: 'right',
    sortable: true,
    render: (r) => {
      const p = asExec(r).exec_price
      return p !== null && p !== undefined ? p.toFixed(2) : '-'
    },
  },
  {
    key: 'volume',
    title: '数量',
    align: 'right',
    sortable: true,
    render: (r) => {
      const v = asExec(r).volume
      return v !== null && v !== undefined ? String(v) : '-'
    },
  },
  {
    key: 'notional',
    title: '金额',
    align: 'right',
    sortable: true,
    render: (r) => num(asExec(r).notional),
  },
  {
    key: 'confidence',
    title: '置信',
    align: 'right',
    sortable: true,
    render: (r) => {
      const c = asExec(r).confidence
      return c !== null && c !== undefined ? c.toFixed(2) : '-'
    },
  },
  {
    key: 'status',
    title: '状态',
    sortable: true,
    render: (r) => {
      const s = asExec(r).status
      return h(LvBadge, { kind: statusBadge(s) }, { default: () => execStatusLabel(s) })
    },
  },
  { key: 'reject_reason', title: '拒因', render: (r) => asExec(r).reject_reason ?? '' },
]
</script>

<template>
  <div data-testid="live-executions">
    <DataTable :rows="rows" :columns="columns" row-key="order_id" />
    <p v-if="!executions.length" class="empty-cell t-muted">暂无执行记录</p>
  </div>
</template>

<style scoped>
.empty-cell {
  padding: 22px 0;
  text-align: center;
}
</style>
