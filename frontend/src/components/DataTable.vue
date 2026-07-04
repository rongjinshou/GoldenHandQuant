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
 * 默认渲染前 pageSize 行, "显示全部 N 条"展开; 展开态组件内保持, 父级轮询重传 rows 不回折。 */
const props = withDefaults(
  defineProps<{
    rows: Record<string, unknown>[]
    columns: Column[]
    rowKey: string
    pageSize?: number
  }>(),
  { pageSize: 50 },
)

const emit = defineEmits<{ rowClick: [row: Record<string, unknown>] }>()

const expanded = ref(false)
const visible = computed(() =>
  expanded.value || props.rows.length <= props.pageSize
    ? props.rows
    : props.rows.slice(0, props.pageSize),
)
const hiddenCount = computed(() => props.rows.length - visible.value.length)
</script>

<template>
  <div class="dt" data-testid="data-table">
    <table>
      <thead>
        <tr>
          <th v-for="column in columns" :key="column.key" :class="{ right: column.align === 'right' }">
            {{ column.title }}
          </th>
        </tr>
      </thead>
      <TransitionGroup tag="tbody" name="dt-row" appear>
        <tr
          v-for="record in visible"
          :key="String(record[rowKey])"
          @click="emit('rowClick', record)"
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
    <button v-if="hiddenCount > 0" class="dt-expand" data-testid="dt-expand" type="button" @click="expanded = true">
      显示全部 {{ rows.length }} 条 ▾
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

tbody tr:hover {
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
