<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import {
  AriaComponent,
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { NCheckbox } from 'naive-ui'
import { computed } from 'vue'
import VChart from 'vue-echarts'

import type { FeatureData } from '@/api/types'
import GlossaryTip from '@/components/GlossaryTip.vue'
import { useChartTheme } from '@/composables/useChartTheme'

import {
  buildFeatureAriaLabel,
  buildFeaturePanelOption,
  EXPLORER_CHART_GROUP,
  FEATURE_GROUPS,
  type SymbolMeta,
} from './chart-options'

use([
  LineChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
  DataZoomComponent,
  AxisPointerComponent,
  AriaComponent, // 图表容器 role=img 之外, 让 ECharts 生成内部无障碍描述(设计 §8 S5)
  CanvasRenderer,
])

/* 特征呈现框 — 行情页多标的叠加改造(设计 docs/feat/0705-explorer-multi-symbol) 的可重复添加子组件:
 * 参照 EquityChart.vue 先例, 纯 props 受控展示层, 不自持"已勾选特征"业务状态 —
 * 权威状态在父层 Explorer.vue 的 panels 数组, 本组件勾选/删除均只 emit 出去由父层改写后
 * 经 props 传回, 单向数据流。palette 与 EquityChart.vue 一致, 自行调用 useChartTheme(), 不接受 prop。 */

const props = withDefaults(
  defineProps<{
    symbols: SymbolMeta[] // 已加载标的快照(含颜色), 由父层按 loadedSymbols 下标算好
    featuresBySymbol: Map<string, FeatureData> // 共享特征缓存(按标的), 只读
    modelValue: string[] // 本呈现框当前勾选的特征名
    removable: boolean // 是否显示删除本呈现框的按钮(父层按 panels.length>1 算好传入)
    panelIndex: number // 本呈现框在列表里的序号(0-based) — 仅用于 data-testid 锚点
    fetching?: boolean // 特征在途(首拉/勾选新特征自动重拉) — 头部小 spinner + 无缓存时骨架(任务 2/5)
    fetchError?: string // 特征拉取失败 — 面板近处提示, 不进顶部 banner(任务 2)
  }>(),
  { fetching: false, fetchError: '' },
)

const emit = defineEmits<{
  'update:modelValue': [string[]]
  remove: []
}>()

const palette = useChartTheme()

const option = computed(() =>
  buildFeaturePanelOption(palette.value, props.symbols, props.featuresBySymbol, props.modelValue),
)

/* 图表容器 role=img 的读屏摘要(设计 §8 S5): 标的 + 勾选特征名 */
const ariaLabel = computed(() => buildFeatureAriaLabel(props.symbols, props.modelValue))

/* update-options notMerge(confirmed-bug 修复, 2026-07-05): 1 标的分支与 2+ 标的分支的 option 形状
 * 不同(如 1 标的顶层 color=palette.series 数组循环取色 vs 2+ 标的逐系列显式 itemStyle.color) ——
 * vue-echarts 默认走 merge 语义(setOption 第二参数 notMerge 缺省 false), 已存在的 ECharts 实例
 * 在标的数跨越 1↔2+ 边界时收到形状迥异的新 option, merge 会残留旧形状的内部组件引用, 抛
 * `xAxis "0" not found` 等运行时错误并使组件此后持续处于损坏渲染状态。固定传 notMerge:true
 * 让每次 option 变化都整份替换, 避免这条合并路径。 */

/* 缩放联动(R2-B): 本呈现框图表挂 EXPLORER_CHART_GROUP 入页级 connect 组, 与 Explorer 的
 * K 线图及其他呈现框同步缩放(单组结构依据/日期域一致性证据见 chart-options 该常量注释;
 * connect() 由 Explorer 挂载时统一调一次, 本组件只负责挂组名)。 */

/* 兼容既有截图脚本(scripts/ui_smoke.py / frontend/scripts/shot.py): 第一个呈现框固定叫
 * "feature-chart"(不能改), 第二个及以后按当前位置编号追加后缀。 */
const testId = computed(() => (props.panelIndex === 0 ? 'feature-chart' : `feature-chart-${props.panelIndex}`))

function toggleFeature(name: string, checked: boolean): void {
  emit('update:modelValue', checked ? [...props.modelValue, name] : props.modelValue.filter((x) => x !== name))
}
</script>

<template>
  <div class="panel-card card" :data-testid="testId">
    <div class="panel-head">
      <span class="t-muted picker-label">特征</span>
      <div class="feature-list">
        <!-- 分组展示(Miller 分块, 任务 2): 组 = 语义类别, 组标签小字 + 组间距 > 组内距 -->
        <div
          v-for="g in FEATURE_GROUPS"
          :key="g.label"
          class="feature-group"
          role="group"
          :aria-label="`${g.label}类特征`"
        >
          <span class="group-label" aria-hidden="true">{{ g.label }}</span>
          <!-- F-05(WCAG 4.1.2 嵌套交互): GlossaryTip 触发器(tabindex=0 role=button)不得嵌进
               NCheckbox 的 label — label 只留纯文本, 释义触发器改为紧随其后的兄弟 ⓘ(plain 免
               双下划线); 悬停/Tab 到 ⓘ 仍可读释义, 点击 label 勾选行为不变 -->
          <span v-for="fm in g.items" :key="fm.name" class="feature-item">
            <NCheckbox
              :checked="modelValue.includes(fm.name)"
              size="small"
              @update:checked="(v: boolean) => toggleFeature(fm.name, v)"
            ><span class="feature-name">{{ fm.label }}</span></NCheckbox>
            <GlossaryTip :term="fm.name" plain><span class="feature-tip">ⓘ</span></GlossaryTip>
          </span>
        </div>
      </div>
      <span
        v-if="fetching"
        class="feat-status"
        role="status"
        aria-live="polite"
        data-testid="feature-fetching"
      >
        <span class="feat-spinner" aria-hidden="true" />更新中…
      </span>
      <span
        v-else-if="fetchError"
        class="feat-status feat-error t-warn"
        role="alert"
        data-testid="feature-fetch-error"
      >⚠ 特征更新失败：{{ fetchError }}</span>
      <button
        v-if="removable"
        type="button"
        class="panel-remove"
        data-testid="panel-remove"
        title="删除本呈现框"
        @click="emit('remove')"
      >
        ✕
      </button>
    </div>
    <div class="chart-body">
      <!-- 首拉/无缓存时在途 → 骨架占位, 不让空态文案冒充加载(任务 5) -->
      <div v-if="fetching && !option" class="chart-skeleton chart-feature" aria-hidden="true" />
      <VChart
        v-else-if="option"
        role="img"
        :aria-label="ariaLabel"
        :group="EXPLORER_CHART_GROUP"
        :option="option"
        :update-options="{ notMerge: true }"
        autoresize
        class="chart chart-feature"
      />
      <p v-else class="t-muted empty">暂无特征曲线——勾选上方特征</p>
    </div>
  </div>
</template>

<style scoped>
.panel-card {
  margin-bottom: var(--gap);
  padding: 10px 16px 12px;
}

.panel-head {
  align-items: baseline;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding-bottom: 10px;
}

.picker-label {
  flex: none;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
}

.feature-list {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: wrap;
  gap: 8px 22px; /* 组间列距(22px) > 组内列距(12px): 靠近性成组, 分块可感知 */
  min-width: 0;
}

.feature-group {
  align-items: center;
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px 12px;
}

.group-label {
  color: var(--text-3);
  flex: none;
  font-size: var(--fs-xs);
}

.feature-name {
  font-size: 12px;
}

/* 复选框 + ⓘ 成组(F-05): 组内 3px 紧贴, 与 .feature-group 的 12px 组内距区分归属 */
.feature-item {
  align-items: center;
  display: inline-flex;
  gap: 3px;
}

.feature-tip {
  color: var(--text-3); /* 5.98(暗)/5.36(亮) on 卡片底 */
  font-size: 11px;
  line-height: 1;
}

/* 删除本呈现框: 小 ✕ 次级按钮, 常态即可见(不依赖行 hover) — 视觉调性参照 Backtests.vue .run-delete,
 * 但本组件不处在可 hover 的列表行语境里, 因此不做 opacity:0 常驻隐藏那套。 */
.panel-remove {
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  flex: none;
  font-size: 13px;
  line-height: 1;
  margin-left: auto;
  padding: 3px 7px;
  transition:
    background var(--dur-fast) var(--ease-out),
    color var(--dur-fast) var(--ease-out);
}

.panel-remove:hover {
  background: color-mix(in srgb, var(--c-fail) 14%, transparent);
  color: var(--c-fail);
}

/* 在途/失败状态: 紧贴特征勾选区右侧, 删除钮之前(删除钮 margin-left:auto 仍靠最右) */
.feat-status {
  align-items: center;
  color: var(--text-3);
  display: inline-flex;
  flex: none;
  font-size: 11.5px;
  gap: 5px;
}

.feat-error {
  max-width: 320px;
}

.feat-spinner {
  animation: feat-spin 0.7s linear infinite;
  border: 2px solid var(--border);
  border-radius: 50%;
  border-top-color: var(--accent);
  display: inline-block;
  height: 12px;
  width: 12px;
}

@keyframes feat-spin {
  to {
    transform: rotate(360deg);
  }
}

.chart-body {
  padding-top: 10px;
}

.chart {
  width: 100%;
}

.chart-feature {
  height: 320px;
}

/* 加载骨架: 固定高度占位, 数据到达不跳版(任务 5); reduced-motion 归零 */
.chart-skeleton {
  animation: feat-skeleton-pulse 1.4s ease-in-out infinite;
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  width: 100%;
}

@keyframes feat-skeleton-pulse {
  50% {
    opacity: 0.5;
  }
}

@media (prefers-reduced-motion: reduce) {
  .feat-spinner {
    animation: none;
  }

  .chart-skeleton {
    animation: none;
    opacity: 0.7;
  }
}

.empty {
  padding: 60px 0;
  text-align: center;
}
</style>
