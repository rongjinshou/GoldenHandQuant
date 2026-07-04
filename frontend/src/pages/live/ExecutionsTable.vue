<script setup lang="ts">
import { computed, h, type VNode } from 'vue'

import type { ExecutionRecord } from '@/api/types'
import DataTable from '@/components/DataTable.vue'

import LvBadge from './LvBadge.vue'
import { num, sliceTime, statusBadge } from './logic'

/* 执行留痕表 — 旧 live.js 执行段对等, 走自研 DataTable(50 行 + 展开态跨轮询保持):
 * 方向买红卖绿(t-buy/t-sell), 状态走统一徽章语义(statusBadge), 限价/金额/置信缺失显 '-'。 */

type Col = {
  key: string
  title: string
  render?: (row: Record<string, unknown>) => VNode | string
  align?: 'right'
}

const props = defineProps<{ executions: ExecutionRecord[] }>()

// 接口类型不含隐式索引签名, DataTable 消费 Record<string, unknown>, 故此处收窄口径
const rows = computed<Record<string, unknown>[]>(
  () => props.executions as unknown as Record<string, unknown>[],
)

function asExec(row: Record<string, unknown>): ExecutionRecord {
  return row as unknown as ExecutionRecord
}

const columns: Col[] = [
  { key: 'submitted_at', title: '时间', render: (r) => sliceTime(asExec(r).submitted_at) },
  { key: 'symbol', title: '标的' },
  {
    key: 'direction',
    title: '方向',
    render: (r) => {
      const dir = asExec(r).direction
      return h('span', { class: dir === 'BUY' ? 't-buy' : 't-sell' }, dir)
    },
  },
  {
    key: 'exec_price',
    title: '限价',
    align: 'right',
    render: (r) => {
      const p = asExec(r).exec_price
      return p !== null && p !== undefined ? p.toFixed(2) : '-'
    },
  },
  {
    key: 'volume',
    title: '数量',
    align: 'right',
    render: (r) => {
      const v = asExec(r).volume
      return v !== null && v !== undefined ? String(v) : '-'
    },
  },
  { key: 'notional', title: '金额', align: 'right', render: (r) => num(asExec(r).notional) },
  {
    key: 'confidence',
    title: '置信',
    align: 'right',
    render: (r) => {
      const c = asExec(r).confidence
      return c !== null && c !== undefined ? c.toFixed(2) : '-'
    },
  },
  {
    key: 'status',
    title: '状态',
    render: (r) => {
      const s = asExec(r).status
      return h(LvBadge, { kind: statusBadge(s) }, { default: () => s })
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
