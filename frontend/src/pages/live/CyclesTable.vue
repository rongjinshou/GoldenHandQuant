<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'

import { fetchJSON } from '@/api/fetch'
import type { ExecutionRecord, TradingCycle } from '@/api/types'

import LvBadge from './LvBadge.vue'
import { num, sliceTime, statusBadge } from './logic'

/* 循环表 — 旧 live.js 循环段对等:
 * 行点击展开钻取该循环的执行明细(/cycles/{id}/executions); 展开态跨轮询保持,
 * 轮询重传时对仍在场的已展开循环重新拉取明细、对已消失的循环剪除展开态;
 * 默认最近 50 行 + "显示全部 N 条"展开(renderBounded 语义)。
 *
 * "显示全部"按钮改为常驻切换(2026-07-05 confirmed-bug, 同款问题已在
 * pages/backtests/useSymbolChips.ts 的联想候选点选场景实测确认): 原先按钮点击后
 * 用 v-if 让按钮本身消失, 同时表格因新增行变高, 按钮原来的屏幕位置会被新展开的
 * 某一可点击行占据——浏览器对这次点击手势 mouseup 的坐标命中测试发生在 DOM 更新
 * 之后, 会对新出现的行补发一次原生 click, 触发 toggle() 把毫不相关的某个循环
 * 展开/收起, 表现为"点显示全部, 结果某一行诡异地展开了"。改成按钮常驻不消失
 * (点击在"显示全部/收起"间切换), 从根上消除"消失元素+新可点击元素抢占同一屏幕
 * 位置"这个几何前提, 而不是加时间窗口去堵事后症状。 */

const ROW_LIMIT = 50

const props = defineProps<{ cycles: TradingCycle[] }>()

const expanded = reactive(new Set<string>())
const showAll = ref(false)

type Detail = 'loading' | 'error' | ExecutionRecord[]
const details = ref<Record<string, Detail>>({})

const visible = computed(() =>
  showAll.value || props.cycles.length <= ROW_LIMIT
    ? props.cycles
    : props.cycles.slice(0, ROW_LIMIT),
)

async function fetchDetail(id: string): Promise<void> {
  details.value = { ...details.value, [id]: 'loading' }
  try {
    const d = await fetchJSON<{ executions: ExecutionRecord[] }>(
      `/api/live/cycles/${id}/executions`,
    )
    details.value = { ...details.value, [id]: d.executions }
  } catch {
    details.value = { ...details.value, [id]: 'error' } // 单循环钻取失败静默留错态
  }
}

function toggle(id: string): void {
  if (expanded.has(id)) {
    expanded.delete(id)
    return
  }
  expanded.add(id)
  if (!details.value[id]) void fetchDetail(id)
}

/* 轮询重传: 已展开且仍在场者刷新明细, 已消失者剪除(对等旧 expandedCycles 维护) */
watch(
  () => props.cycles,
  (rows) => {
    const present = new Set(rows.map((c) => c.cycle_id))
    for (const id of [...expanded]) {
      if (!present.has(id)) expanded.delete(id)
      else void fetchDetail(id)
    }
  },
)

function detailRows(id: string): ExecutionRecord[] | null {
  const d = details.value[id]
  return Array.isArray(d) ? d : null
}

/* 明细方向语义色: A股买红卖绿(t-buy/t-sell), 与执行表/ticket 面板同口径 */
function dirCls(d: string): string {
  return d === 'BUY' ? 't-buy' : d === 'SELL' ? 't-sell' : ''
}
function dirText(d: string): string {
  return d === 'BUY' ? '买' : d === 'SELL' ? '卖' : d
}
</script>

<template>
  <div class="ct" data-testid="live-cycles">
    <table>
      <thead>
        <tr>
          <th>时刻</th>
          <th>模式</th>
          <th>策略</th>
          <th class="right">信号</th>
          <th class="right">提交</th>
          <th class="right">拒绝</th>
          <th class="right">失败</th>
          <th class="right">金额</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!cycles.length">
          <td colspan="9" class="empty-cell t-muted">暂无循环</td>
        </tr>
        <template v-for="c in visible" :key="c.cycle_id">
          <tr class="clickable" data-testid="cycle-row" @click="toggle(c.cycle_id)">
            <!-- ▸/▾ 展开指示符: 行可点击展开这一交互此前无任何视觉暗示 -->
            <td class="num">
              <span class="caret" aria-hidden="true">{{ expanded.has(c.cycle_id) ? '▾' : '▸' }}</span>{{ sliceTime(c.cycle_time) }}
            </td>
            <td><LvBadge :kind="c.mode === 'live' ? 'fail' : 'info'">{{ c.mode }}</LvBadge></td>
            <td>{{ c.strategy }}</td>
            <td class="num right">{{ c.signals_generated }}</td>
            <td class="num right">{{ c.orders_submitted }}</td>
            <td class="num right">{{ c.orders_rejected }}</td>
            <td class="num right">{{ c.orders_failed }}</td>
            <td class="num right">{{ num(c.notional_submitted) }}</td>
            <td class="note">{{ c.note ?? '' }}</td>
          </tr>
          <tr v-if="expanded.has(c.cycle_id)" class="row-detail" data-testid="cycle-detail">
            <td colspan="9">
              <div v-if="details[c.cycle_id] === 'loading'" class="t-muted detail-msg">加载中…</div>
              <div v-else-if="details[c.cycle_id] === 'error'" class="t-fail detail-msg">
                明细加载失败
              </div>
              <table v-else class="detail-table">
                <thead>
                  <tr>
                    <th>标的</th>
                    <th>方向</th>
                    <th>状态</th>
                    <th class="right">金额</th>
                    <th>拒绝原因</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!detailRows(c.cycle_id)?.length">
                    <td colspan="5" class="t-muted">该循环无执行记录</td>
                  </tr>
                  <tr v-for="(e, i) in detailRows(c.cycle_id) ?? []" :key="i">
                    <td class="num">{{ e.symbol }}</td>
                    <td :class="dirCls(e.direction)">{{ dirText(e.direction) }}</td>
                    <td><LvBadge :kind="statusBadge(e.status)">{{ e.status }}</LvBadge></td>
                    <td class="num right">{{ num(e.notional) }}</td>
                    <td>{{ e.reject_reason ?? '' }}</td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
    <button
      v-if="cycles.length > ROW_LIMIT"
      class="ct-expand"
      type="button"
      data-testid="cycles-expand"
      @click="showAll = !showAll"
    >
      {{ showAll ? '收起 ▴' : `显示全部 ${cycles.length} 条 ▾` }}
    </button>
  </div>
</template>

<style scoped>
.ct {
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
  vertical-align: top;
}

.right {
  text-align: right;
}

.note {
  color: var(--text-2);
  font-size: 12.5px;
}

.clickable {
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
}

.clickable:hover {
  background: var(--accent-soft);
}

.row-detail > td {
  background: var(--bg);
  padding: 4px 10px 10px;
}

.detail-table {
  width: auto;
}

.detail-table th {
  border-bottom: 1px dashed var(--border);
  font-size: 11px;
  padding: 4px 14px 4px 0;
}

.detail-table td {
  border-bottom: 1px dashed var(--border);
  font-size: 12.5px;
  padding: 5px 14px 5px 0;
}

.caret {
  color: var(--text-3);
  display: inline-block;
  font-size: 11px;
  margin-right: 6px;
  width: 10px;
}

.detail-msg {
  font-size: 12.5px;
  padding: 6px 0;
}

.empty-cell {
  padding: 22px 0;
  text-align: center;
}

.ct-expand {
  background: transparent;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  display: block;
  font-size: 12.5px;
  margin: 10px auto 2px;
  padding: 6px 16px;
  transition: color var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
}

.ct-expand:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
