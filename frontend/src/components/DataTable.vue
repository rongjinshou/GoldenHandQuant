<script setup lang="ts">
import { computed, defineComponent, ref, type PropType, type VNode } from 'vue'

export interface Column {
  key: string
  title: string
  render?: (row: Record<string, unknown>) => VNode | string
  align?: 'right'
  gloss?: string
}

/* 单元格渲染器: render 列返回 VNode/string, 普通列取值转字符串 */
const CellRender = defineComponent({
  props: {
    row: { type: Object as PropType<Record<string, unknown>>, required: true },
    col: { type: Object as PropType<Column>, required: true },
  },
  setup(props) {
    return () => {
      if (props.col.render) return props.col.render(props.row)
      const v = props.row[props.col.key]
      return v === null || v === undefined ? '-' : String(v)
    }
  },
})

/* 自研分页长表(设计 §4.1 评审裁定) — 旧 live.js renderBounded 语义收敛:
 * 默认渲染前 pageSize 行, "显示全部 N 条"展开; 展开态组件内保持, 父级轮询重传 rows 不回折。
 *
 * "显示全部"按钮常驻不消失(2026-07-05 confirmed-bug, 同款问题已在
 * pages/live/CyclesTable.vue/pages/backtests/useSymbolChips.ts 两处实测确认过机制):
 * 若用 v-if 让按钮点击后消失, 表格因新增行变高会让某一新展开行占据按钮原屏幕位置,
 * 浏览器对这次点击手势 mouseup 的坐标命中测试发生在 DOM 更新之后, 会对新行补发一次
 * 原生 click, 误触发它的 rowClick。此组件当前虽无消费者接了 rowClick(隐患休眠), 但
 * 接口已存在, 保持按钮常驻可从根上避免这个隐患将来被激活。 */
const props = withDefaults(
  defineProps<{
    rows: Record<string, unknown>[]
    columns: Column[]
    rowKey: string
    pageSize?: number
    clickable?: boolean
  }>(),
  { pageSize: 50, clickable: false },
)

const emit = defineEmits<{ rowClick: [row: Record<string, unknown>] }>()

const expanded = ref(false)
const visible = computed(() =>
  expanded.value || props.rows.length <= props.pageSize
    ? props.rows
    : props.rows.slice(0, props.pageSize),
)
</script>

<template>
  <div class="dt" data-testid="data-table">
    <table>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key" scope="col" :class="{ right: column.align === 'right' }">
            {{ column.title }}
          </th>
        </tr>
      </thead>
      <TransitionGroup tag="tbody" name="dt-row" appear>
        <tr
          v-for="record in visible"
          :key="String(record[rowKey])"
          :class="{ 'row-clickable': clickable }"
          @click="clickable && emit('rowClick', record)"
        >
          <td
            v-for="column in columns"
            :key="column.key"
            :class="{ right: column.align === 'right', num: column.align === 'right' }"
          >
            <CellRender :row="record" :col="column" />
          </td>
        </tr>
      </TransitionGroup>
    </table>
    <button
      v-if="rows.length > pageSize"
      class="dt-expand"
      data-testid="dt-expand"
      type="button"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起 ▴' : `显示全部 ${rows.length} 条 ▾` }}
    </button>
  </div>
</template>

<style scoped>
.dt {
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

/* hover 高亮仅在真正可点时给出, 堵住"看似可点实无消费者"的幽灵隐患 */
tbody tr.row-clickable {
  cursor: pointer;
}

tbody tr.row-clickable:hover {
  background: var(--accent-soft);
}

/* 行 staggered 入场(首次渲染, reduced-motion 下 --dur-base=0 即瞬时) */
.dt-row-enter-active {
  transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out);
}

.dt-row-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.dt-expand {
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

.dt-expand:hover {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
