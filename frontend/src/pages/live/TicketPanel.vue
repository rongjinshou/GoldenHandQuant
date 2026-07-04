<script setup lang="ts">
import type { LiveTicket } from '@/api/types'

import { ticketCells } from './logic'

/* 下单 ticket 面板 — 旧 live.js Ticket 段对等:
 * 每张 ticket 一个 <details open>(文件名为 summary), 内含键值网格(方向买红卖绿、
 * 终态 FILLED 绿/REJECT|FAIL 红), 原始 JSON 收进内层 <details> 折叠;
 * content 非对象 → "内容不可读"; 空列表 → "暂无 ticket"。 */

defineProps<{ tickets: LiveTicket[] }>()

function cells(content: unknown): ReturnType<typeof ticketCells> {
  return ticketCells(content)
}

function rawJson(content: unknown): string {
  return JSON.stringify(content, null, 2)
}
</script>

<template>
  <div class="tp" data-testid="live-tickets">
    <p v-if="!tickets.length" class="empty t-muted">暂无 ticket</p>
    <details v-for="t in tickets" :key="t.file" class="ticket-item" open>
      <summary class="ticket-file num">{{ t.file }}</summary>
      <div v-if="cells(t.content)" class="tk-grid">
        <div v-for="cell in cells(t.content) ?? []" :key="cell.k" class="tk-cell">
          <span class="tk-k t-muted">{{ cell.k }}</span>
          <span class="tk-v num" :class="cell.cls">{{ cell.v }}</span>
        </div>
      </div>
      <div v-else class="tk-empty t-muted">内容不可读</div>
      <details class="ticket-raw">
        <summary>原始 JSON</summary>
        <pre class="ticket-pre num">{{ rawJson(t.content) }}</pre>
      </details>
    </details>
  </div>
</template>

<style scoped>
.tp {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ticket-item {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
}

.ticket-file {
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 600;
}

.tk-grid {
  display: grid;
  gap: 8px 20px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin: 12px 0 6px;
}

.tk-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tk-k {
  font-size: 11px;
  letter-spacing: 0.04em;
}

.tk-v {
  font-size: 13.5px;
  font-weight: 600;
}

.tk-empty {
  margin: 10px 0;
}

.ticket-raw {
  margin-top: 8px;
}

.ticket-raw summary {
  color: var(--text-3);
  cursor: pointer;
  font-size: 12px;
}

.ticket-pre {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 11.5px;
  line-height: 1.5;
  margin: 8px 0 0;
  max-height: 320px;
  overflow: auto;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.empty {
  padding: 22px 0;
  text-align: center;
}
</style>
