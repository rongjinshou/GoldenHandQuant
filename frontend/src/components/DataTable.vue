<script lang="ts">
/* 列排序纯函数 — 具名导出供单测。排序永远作用于 rows 的浅拷贝副本
 * (不得原地改 props.rows), 且发生在 visible 截断计算之前。 */
export type SortDir = 'desc' | 'asc'

/* 单对比较: null/undefined 恒沉底(升降序皆然, 故先于方向判定早退);
 * 双数值按数值(显式三态比较, NaN 对返回 0 保证比较器良定义不炸),
 * 其余一律 String 化后 localeCompare。 */
export function compareRows(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
  key: string,
  dir: SortDir,
): number {
  const va = a[key]
  const vb = b[key]
  const aNil = va === null || va === undefined
  const bNil = vb === null || vb === undefined
  if (aNil || bNil) return Number(aNil) - Number(bNil) // 双空=0, 单空者恒排后
  const cmp =
    typeof va === 'number' && typeof vb === 'number'
      ? va < vb
        ? -1
        : va > vb
          ? 1
          : 0
      : String(va).localeCompare(String(vb))
  return dir === 'desc' ? -cmp : cmp
}

/* 返回排序后的新数组: 浅拷贝 + 原生稳定排序(ES2019+), 相等键保持原相对顺序 */
export function sortRows(
  rows: Record<string, unknown>[],
  key: string,
  dir: SortDir,
): Record<string, unknown>[] {
  return [...rows].sort((a, b) => compareRows(a, b, key, dir))
}
</script>

<script setup lang="ts">
import { computed, defineComponent, ref, type PropType, type VNode } from 'vue'

export interface Column {
  key: string
  title: string
  render?: (row: Record<string, unknown>) => VNode | string
  align?: 'right'
  gloss?: string
  /* 可排序列: 表头渲染真 <button>(键盘可达), 点击循环 无序→降序→升序→无序;
   * 按行原始值排(数值列数值序), 非渲染文本 */
  sortable?: boolean
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

/* 列排序状态 — 组件内持有, 父级轮询重传 rows 不重置(与展开态跨轮询保持同哲学);
 * 同一时刻仅一列有序。幽灵点击辨析(对齐上方 confirmed-bug 机制): 排序按钮常驻
 * thead 且指示符恒占位(表头宽度不随排序切换漂移), 点击引发的行重排只发生在其
 * 下方 tbody, mouseup 命中测试仍落回按钮自身, 不会像"消失的展开钮"那样把坐标
 * 让给某行误触 rowClick。 */
const sortState = ref<{ key: string; dir: SortDir } | null>(null)

function cycleSort(key: string) {
  if (sortState.value?.key !== key) sortState.value = { key, dir: 'desc' }
  else if (sortState.value.dir === 'desc') sortState.value = { key, dir: 'asc' }
  else sortState.value = null
}

function ariaSort(key: string): 'descending' | 'ascending' | undefined {
  if (sortState.value?.key !== key) return undefined
  return sortState.value.dir === 'desc' ? 'descending' : 'ascending'
}

function sortIndicator(key: string): string {
  if (sortState.value?.key !== key) return ''
  return sortState.value.dir === 'desc' ? '▾' : '▴'
}

/* 排序在截断之前: 对 rows 副本排序, 再交给 visible 做分页切片 */
const sorted = computed(() =>
  sortState.value ? sortRows(props.rows, sortState.value.key, sortState.value.dir) : props.rows,
)

const visible = computed(() =>
  expanded.value || sorted.value.length <= props.pageSize
    ? sorted.value
    : sorted.value.slice(0, props.pageSize),
)
</script>

<template>
  <div class="dt" data-testid="data-table">
    <table>
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            scope="col"
            :class="{ right: column.align === 'right' }"
            :aria-sort="ariaSort(column.key)"
          >
            <button
              v-if="column.sortable"
              class="dt-sort"
              :data-testid="`dt-sort-${column.key}`"
              type="button"
              @click="cycleSort(column.key)"
            >{{ column.title }}<span class="dt-sort-ind" aria-hidden="true">{{ sortIndicator(column.key) }}</span></button>
            <template v-else>{{ column.title }}</template>
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

/* 排序表头: 真 <button> 保键盘可达, 视觉完全继承 th 文字样式 */
.dt-sort {
  background: transparent;
  border: 0;
  color: inherit;
  cursor: pointer;
  font: inherit;
  letter-spacing: inherit;
  padding: 0;
  transition: color var(--dur-fast) var(--ease-out);
}

.dt-sort:hover {
  color: var(--accent-strong, var(--accent)); /* R6-07: light 裸 accent 压卡底仅 2.74:1 → 5.14 */
}

/* 指示符恒占位一格: 无序时也占 1em, 排序切换不改表头宽度(thead 零布局漂移) */
.dt-sort-ind {
  display: inline-block;
  width: 1em;
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
  border-color: var(--accent); /* 图形边框走 3:1 门槛, 保留品牌橙 */
  color: var(--accent-strong, var(--accent)); /* R6-08: 文字级换 strong */
}
</style>
