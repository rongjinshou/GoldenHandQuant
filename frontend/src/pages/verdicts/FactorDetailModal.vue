<script setup lang="ts">
import { NModal } from 'naive-ui'
import { computed } from 'vue'

import type { VerdictFactor } from '@/api/types'
import GlossaryTip from '@/components/GlossaryTip.vue'

import { f2, f3, f4, gcell, gradeClass, isPassReason, pct } from './gates'

/* 因子详情弹框(设计 0705-verdict-cards §6) — 全站首个 modal, 规范:
 * 尺寸 min(760px,92vw)/84vh 滚动, 遮罩 rgba(0,0,0,.4)+blur(2px)。
 * Esc/遮罩点击/✕ 三途径关闭均由 naive-ui NModal 默认行为覆盖(maskClosable/closeOnEsc
 * 默认 true, 已读源码确认两者都收敛到 update:show(false)), 本组件只需监听 update:show。
 * factors/index 是父层过滤排序后的可见序列 — 上一个/下一个即在这个序列里移动。
 *
 * 遮罩样式踩坑记录(Task 7 整体复核发现): NModal 非 preset 模式下, $attrs(含 style)
 * 是 mergeProps 到默认插槽的第一个子节点上(即我们自己的 .verdict-modal div), 不是
 * 遮罩元素——之前直接在 <NModal :style="..."> 上传 background/blur 会变成内容卡片的
 * 内联样式, 盖掉 .verdict-modal 自己的 background:var(--bg-2)(浅色主题下尤其明显,
 * 卡片变成半透明深色)。naive-ui 遮罩默认色已经就是 rgba(0,0,0,.4)(读
 * modal/src/styles/index.cssr.mjs 确认), 不需要覆盖; blur 效果改用下方非 scoped
 * 样式块直接命中 naive-ui 内部的 .n-modal-mask 类名。 */
const props = defineProps<{
  show: boolean
  factors: VerdictFactor[]
  index: number
  longOnly: boolean
  hasSplit: boolean
  runTitle: string
}>()

const emit = defineEmits<{ 'update:show': [boolean]; navigate: [number] }>()

const factor = computed<VerdictFactor | null>(() => props.factors[props.index] ?? null)

interface MetricCell {
  text: string
  cls: string
}

interface MetricRow {
  label: string
  gloss: string
  is: MetricCell
  oos: MetricCell
}

const NA_CELL: MetricCell = { text: '—', cls: '' }

/* gloss 术语沿旧表格口径(见 GLOSSARY): 'ir'/'ic_posrate'/'ls_is' 的释义文本本身
 * 已覆盖多空与长多两种口径, 不需要按 objective 分叉术语 key。 */
const metricRows = computed<MetricRow[]>(() => {
  const f = factor.value
  if (!f) return []
  const oosOr = (name: string, v: number | null, fmt: (x: number) => string): MetricCell =>
    props.hasSplit ? gcell(name, v, fmt) : NA_CELL

  if (props.longOnly) {
    return [
      { label: 'IC均值', gloss: 'ic', is: gcell('ic_mean', f.ic_mean, f4), oos: oosOr('oos_ic_mean', f.oos_ic_mean, f4) },
      { label: '超额信息比', gloss: 'ir', is: gcell('excess_ir', f.excess_ir, f2), oos: NA_CELL },
      { label: '超额正率', gloss: 'ic_posrate', is: gcell('excess_positive_rate', f.excess_positive_rate, pct), oos: NA_CELL },
      { label: '单调性', gloss: 'monotonicity', is: gcell('monotonicity_score', f.monotonicity_score, f2), oos: NA_CELL },
      {
        label: 'Top超额',
        gloss: 'ls_is',
        is: gcell('top_excess_return', f.top_excess_return, pct),
        oos: oosOr('oos_top_excess_return', f.oos_top_excess_return, pct),
      },
    ]
  }
  return [
    { label: 'IC均值', gloss: 'ic', is: gcell('ic_mean', f.ic_mean, f4), oos: oosOr('oos_ic_mean', f.oos_ic_mean, f4) },
    { label: 'IR', gloss: 'ir', is: gcell('ir', f.ir, f3), oos: oosOr('oos_ir', f.oos_ir, f3) },
    { label: 'IC正率', gloss: 'ic_posrate', is: gcell('ic_positive_rate', f.ic_positive_rate, pct), oos: NA_CELL },
    { label: '单调性', gloss: 'monotonicity', is: gcell('monotonicity_score', f.monotonicity_score, f2), oos: NA_CELL },
    {
      label: '多空收益',
      gloss: 'ls_is',
      is: gcell('long_short_return', f.long_short_return, pct),
      oos: oosOr('oos_long_short_return', f.oos_long_short_return, pct),
    },
  ]
})

function go(delta: number): void {
  const next = props.index + delta
  if (next < 0 || next >= props.factors.length) return
  emit('navigate', next)
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    go(-1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    go(1)
  }
}
</script>

<template>
  <NModal :show="show" @update:show="(v: boolean) => emit('update:show', v)">
    <div
      v-if="factor"
      class="verdict-modal"
      data-testid="verdict-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="vm-title"
      @keydown="onKeydown"
    >
      <header class="vm-head">
        <span id="vm-title">
          <span class="fid num">{{ factor.factor_id }}</span>
          <span class="fname">{{ factor.factor_name ?? '' }}</span>
        </span>
        <span
          v-if="factor.score !== null && factor.score !== undefined"
          class="grade-badge"
          :class="gradeClass(factor.grade)"
        >{{ (factor.grade ?? '?').toUpperCase() }} {{ factor.score.toFixed(0) }}</span>
        <GlossaryTip :term="factor.passed ? 'verdict_pass' : 'verdict_fail'" plain>
          <span class="badge" :class="factor.passed ? 'pass' : 'fail'">{{ factor.passed ? 'PASS' : 'FAIL' }}</span>
        </GlossaryTip>
        <button type="button" class="vm-close" aria-label="关闭" @click="emit('update:show', false)">✕</button>
      </header>
      <p class="vm-context t-muted">{{ runTitle }}</p>

      <code v-if="factor.expression" class="vm-expr num">{{ factor.expression }}</code>

      <h4 class="vm-section">指标对照</h4>
      <table class="vm-metrics">
        <thead>
          <tr>
            <th></th>
            <th class="th-num">IS</th>
            <th class="th-num">OOS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in metricRows" :key="row.label">
            <td><GlossaryTip :term="row.gloss">{{ row.label }}</GlossaryTip></td>
            <td class="num" :class="row.is.cls">{{ row.is.text }}</td>
            <td class="num" :class="row.oos.cls">{{ row.oos.text }}</td>
          </tr>
        </tbody>
      </table>

      <h4 class="vm-section">逐关判定</h4>
      <ul class="vm-reasons">
        <li v-for="(r, i) in factor.reasons ?? []" :key="i" :class="isPassReason(r) ? 'r-pass' : 'r-fail'">{{ r }}</li>
      </ul>

      <footer class="vm-nav">
        <button type="button" :disabled="index === 0" data-testid="verdict-modal-prev" @click="go(-1)">
          ‹ 上一个<template v-if="factors[index - 1]"> ({{ factors[index - 1].factor_id }})</template>
        </button>
        <span class="vm-pos num">{{ index + 1 }} / {{ factors.length }}</span>
        <button
          type="button"
          :disabled="index === factors.length - 1"
          data-testid="verdict-modal-next"
          @click="go(1)"
        >下一个<template v-if="factors[index + 1]"> ({{ factors[index + 1].factor_id }})</template> ›</button>
      </footer>
    </div>
  </NModal>
</template>

<style scoped>
.verdict-modal {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-pop);
  max-height: 84vh;
  overflow-y: auto;
  padding: var(--gap-lg);
  width: min(760px, 92vw);
}

.vm-head {
  align-items: center;
  display: flex;
  gap: 10px;
}

#vm-title {
  align-items: baseline;
  display: flex;
  flex: 1;
  gap: 8px;
  min-width: 0;
}

.vm-head .fid {
  font-size: 15px;
  font-weight: 700;
}

.vm-head .fname {
  color: var(--text-3);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.vm-context {
  font-size: 12px;
  margin: 4px 0 0;
}

.vm-close {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 4px 8px;
  transition: background var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out);
}

.vm-close:hover {
  background: var(--bg-3);
  color: var(--text);
}

.vm-expr {
  color: var(--accent-blue);
  display: block;
  font-size: 12px;
  margin: 14px 0;
  white-space: pre-wrap;
}

.vm-section {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  margin: 18px 0 8px;
}

.vm-metrics {
  border-collapse: collapse;
  width: 100%;
}

.vm-metrics th {
  border-bottom: 1px solid var(--border);
  color: var(--text-3);
  font-size: 11px;
  padding: 4px 8px;
  text-align: left;
}

.vm-metrics th.th-num {
  text-align: right;
}

.vm-metrics td {
  font-size: 13px;
  padding: 5px 8px;
}

.vm-metrics td.num {
  text-align: right;
}

.vm-reasons {
  list-style: none;
  margin: 0;
  padding: 0;
}

.vm-reasons li {
  border-radius: var(--radius-sm);
  font-size: 12px;
  margin-bottom: 4px;
  padding: 4px 9px;
}

.r-pass {
  background: var(--bg-3);
  color: var(--text-3);
}

.r-fail {
  background: color-mix(in srgb, var(--c-fail) 12%, transparent);
  color: var(--c-fail);
}

.vm-nav {
  align-items: center;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  margin-top: 18px;
  padding-top: 14px;
}

.vm-nav button {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-2);
  cursor: pointer;
  font-size: 12.5px;
  padding: 6px 12px;
  transition: border-color var(--dur-fast) var(--ease-out);
}

.vm-nav button:hover:not(:disabled) {
  border-color: var(--accent);
}

.vm-nav button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.vm-pos {
  color: var(--text-3);
  font-size: 12px;
}

.grade-badge {
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
}

.grade-a { background: color-mix(in srgb, var(--c-pass) 18%, transparent); color: var(--c-pass); }
.grade-b { background: var(--bg-3); color: var(--text-2); }
.grade-c { background: color-mix(in srgb, var(--c-warn) 18%, transparent); color: var(--c-warn); }
.grade-d { background: color-mix(in srgb, var(--c-fail) 18%, transparent); color: var(--c-fail); }

.badge {
  border-radius: 12px;
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 10px;
}

.badge.pass { background: color-mix(in srgb, var(--c-pass) 16%, transparent); color: var(--c-pass); }
.badge.fail { background: color-mix(in srgb, var(--c-fail) 16%, transparent); color: var(--c-fail); }
</style>

<style>
/* 非 scoped: 目标是 naive-ui 内部渲染的遮罩元素(.n-modal-mask), scoped 样式的
 * data-v 属性选择器够不到组件外部渲染的节点。遮罩底色 naive-ui 默认已是
 * rgba(0,0,0,.4)(见其 modal/src/styles/index.cssr.mjs), 这里只加设计要的模糊。 */
.n-modal-mask {
  backdrop-filter: blur(2px);
}
</style>
