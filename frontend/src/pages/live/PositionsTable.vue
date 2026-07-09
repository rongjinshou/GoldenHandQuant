<script setup lang="ts">
import { computed } from 'vue'

import type { PositionSnapshot } from '@/api/types'
import GlossaryTip from '@/components/GlossaryTip.vue'

import { positionRow } from './logic'

/* 持仓表 — 旧持仓段对等: 现价/市值盯市, 浮动盈亏涨红跌绿;
 * 现价缺失(null/0)回退成本估市值且不显示盈亏(positionRow 收敛该口径)。 */

const props = defineProps<{ rows: PositionSnapshot[] }>()

const views = computed(() => props.rows.map(positionRow))
</script>

<template>
  <div class="pt" data-testid="live-positions">
    <table>
      <thead>
        <tr>
          <th scope="col">标的</th>
          <th scope="col" class="right">总量</th>
          <th scope="col" class="right">可用</th>
          <th scope="col" class="right">成本价</th>
          <th scope="col" class="right">现价</th>
          <th scope="col" class="right">市值</th>
          <th scope="col" class="right"><GlossaryTip term="float_pnl"><span>浮动盈亏</span></GlossaryTip></th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!views.length">
          <td colspan="7" class="empty-cell t-muted">无持仓快照</td>
        </tr>
        <tr v-for="p in views" :key="p.symbol">
          <td class="num">{{ p.symbol }}</td>
          <td class="num right">{{ p.totalVolume }}</td>
          <td class="num right">{{ p.available }}</td>
          <td class="num right">{{ p.costText }}</td>
          <td class="num right">{{ p.lastText }}</td>
          <td class="num right">{{ p.mktValText }}</td>
          <td class="num right" :class="p.pnlCls" data-testid="pos-pnl">{{ p.pnlText }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.pt {
  overflow-x: auto;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th {
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 8px 10px;
  text-align: left;
  white-space: nowrap;
}

td {
  border-bottom: 1px solid var(--border);
  font-size: 13.5px;
  padding: 8px 10px;
  text-align: left;
}

.right {
  text-align: right;
}

tbody tr {
  transition: background var(--dur-fast) var(--ease-out);
}

tbody tr:hover {
  background: var(--accent-soft);
}

.empty-cell {
  padding: 22px 0;
  text-align: center;
}
</style>
