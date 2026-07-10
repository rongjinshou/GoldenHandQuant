<script setup lang="ts">
import { NButton, NCheckbox, NDatePicker, NInput, NInputNumber, NSelect } from 'naive-ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { postJSON } from '@/api/fetch'
import type { Job, StrategyMeta } from '@/api/types'
import ErrorBanner from '@/components/ErrorBanner.vue'
import GlossaryTip from '@/components/GlossaryTip.vue'
import JobCard from '@/components/JobCard.vue'

import {
  type EditableParam,
  editableParams,
  type ParamDefaults,
  type ParamEditValue,
  paramOverrides,
} from './param-overrides'
import { friendlyStrategyName } from './run-naming'
import { useSymbolChips } from './useSymbolChips'

/* 新建回测表单 — 旧 backtests.js initBacktestForm/renderParamInputs/submitBacktest 对等:
 * 策略勾选(dual_ma 默认, 主文字中文显示名+代码名小字)/每策略参数区(渐进披露: 勾选才展开,
 * 数值 NInputNumber、字符串 NInput, 初值=默认+「默认 x」淡字标注, 可一键还原默认,
 * 取消勾选值仍保留重勾不丢)/日期资金配置/标的 chips 联想/截面策略禁标的框 + 提示/
 * 提交 → JobCard 闭环(成功 emit done 让父页刷列表)。
 * 提交体 params 只带 ≠默认 的键(diff 纯函数 param-overrides.ts, 已单测), 全默认不发。 */
const props = defineProps<{ strategyMeta: StrategyMeta[] }>()
const emit = defineEmits<{ done: [] }>()

const HINT_TEXT =
  '截面策略需基本面通道（QMT 客户端在线，或配置 Tushare），且全市场回测耗时数分钟。' +
  '回测对象为全市场抽样池，下方标的输入不生效。'

const CONFIG_OPTIONS = [
  { label: 'resources/backtest.yaml（默认）', value: '' },
  { label: 'backtest_multi_factor.yaml', value: 'resources/backtest_multi_factor.yaml' },
]

const error = ref('')
const checked = ref<Set<string>>(new Set())
const startDate = ref<string | null>('2024-01-01')
const endDate = ref<string | null>('2025-12-31')
const capital = ref<number | null>(null)
const config = ref('')
const jobIds = ref<string[]>([])
const submitting = ref(false)

const chips = useSymbolChips()

/* 联想浮层"点外收起": 指针落在标的输入区之外即关闭候选(WCAG §9 combobox 收起路径之一);
 * 区内点击(含候选 <li>)不受影响, 与既有幽灵点击防护互不干扰。 */
const chipsBoxRef = ref<HTMLElement | null>(null)
function onDocPointerDown(e: PointerEvent): void {
  if (chipsBoxRef.value && !chipsBoxRef.value.contains(e.target as Node)) {
    chips.onEscape()
  }
}
onMounted(() => document.addEventListener('pointerdown', onDocPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointerDown))

function typeOf(name: string): string | undefined {
  return props.strategyMeta.find((s) => s.name === name)?.strategy_type
}

/* 勾选框主文字 = 中文显示名(识别>回忆), 与轮次列表标题同源 run-naming.friendlyStrategyName;
 * 代码名(dual_ma 等)降为次要小字, 仍可对照 CLI/配置。 */
function displayName(s: StrategyMeta): string {
  return friendlyStrategyName(s.name, props.strategyMeta)
}

/* 选中策略按 meta 顺序(与 DOM 勾选顺序等价), 供参数/提交/提示 */
const selectedStrategies = computed(() =>
  props.strategyMeta.filter((s) => checked.value.has(s.name)).map((s) => s.name),
)

const hasCross = computed(() => selectedStrategies.value.some((n) => typeOf(n) === 'cross_section'))

function toggleStrategy(name: string, v: boolean): void {
  const next = new Set(checked.value)
  if (v) next.add(name)
  else next.delete(name)
  checked.value = next
}

// ---- 参数编辑(渐进披露: 勾选策略才展开参数区; 取消勾选值仍保留, 重勾不丢) ----
/** 编辑态: 策略 → { 参数 → 当前值 }; null = 用默认(NInputNumber 清空) */
const paramEdits = ref<Record<string, Record<string, ParamEditValue>>>({})

/** 每策略可编辑参数(null/字典参数不生成输入行, 数值/字符串分控件) */
const editablesByStrategy = computed<Record<string, EditableParam[]>>(() => {
  const out: Record<string, EditableParam[]> = {}
  for (const s of props.strategyMeta) out[s.name] = editableParams(s.default_params ?? {})
  return out
})

/** 归一化默认值表 — 种子/还原/提交 diff 三处同源 */
const defaultsByStrategy = computed<ParamDefaults>(() => {
  const out: ParamDefaults = {}
  for (const [name, list] of Object.entries(editablesByStrategy.value)) {
    out[name] = Object.fromEntries(list.map((p) => [p.key, p.def]))
  }
  return out
})

/** 勾选中且有可编辑参数的策略 → 各自展开一块参数面板 */
const paramStrategies = computed(() =>
  props.strategyMeta.filter(
    (s) => checked.value.has(s.name) && editablesByStrategy.value[s.name].length > 0,
  ),
)

/** 勾选/元数据就绪时补种默认值为初值(已有编辑不覆盖) */
function seedEdits(): void {
  for (const name of selectedStrategies.value) {
    if (!paramEdits.value[name]) {
      const defs = defaultsByStrategy.value[name]
      if (defs) paramEdits.value[name] = { ...defs }
    }
  }
}

function numValue(strat: string, key: string): number | null {
  const v = paramEdits.value[strat]?.[key]
  return typeof v === 'number' ? v : null
}

function strValue(strat: string, key: string): string {
  const v = paramEdits.value[strat]?.[key]
  return typeof v === 'string' ? v : ''
}

function setParam(strat: string, key: string, v: ParamEditValue): void {
  ;(paramEdits.value[strat] ??= {})[key] = v
}

function restoreDefaults(strat: string): void {
  const defs = defaultsByStrategy.value[strat]
  if (defs) paramEdits.value[strat] = { ...defs }
}

watch(
  () => props.strategyMeta,
  (meta) => {
    if (!meta.length) return
    // dual_ma 默认勾选(仅首次, 用户改动后不覆盖)
    if (checked.value.size === 0 && meta.some((s) => s.name === 'dual_ma')) {
      checked.value = new Set(['dual_ma'])
    }
    seedEdits()
  },
  { immediate: true },
)
watch(selectedStrategies, seedEdits)

// ---- 标的 chips 输入接线(native input 保留 inputType 粘贴检测) ----
function onSymInput(e: Event): void {
  chips.input.value = (e.target as HTMLInputElement).value
  chips.onInput(e)
}
function onSymKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter') {
    e.preventDefault()
    chips.onEnter()
  } else if (e.key === 'ArrowDown') {
    e.preventDefault() // 阻止光标跳到行尾, 改为在候选间下移高亮
    chips.onArrowDown()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    chips.onArrowUp()
  } else if (e.key === 'Escape') {
    chips.onEscape()
  } else if (e.key === 'Backspace') {
    chips.onBackspace()
  }
}

const symPlaceholder = computed(() =>
  hasCross.value
    ? '截面策略回测对象 = 全市场抽样池，此处不生效'
    : '输入代码/名称联想，回车或点选添加',
)

// ---- 提交 ----
async function submitBacktest(): Promise<void> {
  if (submitting.value) return // 防双击重复提交
  error.value = ''
  const strategies = selectedStrategies.value
  if (!strategies.length) {
    error.value = '至少选择一个策略'
    return
  }
  if (capital.value !== null && !(capital.value > 0)) {
    error.value = '初始资金须为正数'
    return
  }
  const payload: Record<string, unknown> = {
    strategies,
    start_date: startDate.value ?? '',
    end_date: endDate.value ?? '',
  }
  // 残留在输入框的文本先转 chips, 再取 chips 集合(截面禁用时不传)
  if (!hasCross.value && chips.input.value.trim()) {
    const bad = chips.commitText(chips.input.value)
    chips.input.value = bad.join(',')
    if (bad.length) {
      chips.err.value = `非法标的: ${bad.join(', ')}（格式 6位代码.SH/SZ/BJ）`
      return
    }
    chips.err.value = ''
  }
  if (!hasCross.value && chips.symbols.value.length) payload.symbols = [...chips.symbols.value]
  if (capital.value !== null && capital.value > 0) payload.initial_capital = capital.value
  if (config.value) payload.config = config.value
  // 仅传与默认不同的参数(纯函数 diff): 只取本次提交策略的编辑态; 全默认 → 不带 params 字段
  const edited: Record<string, Record<string, ParamEditValue>> = {}
  for (const name of strategies) {
    const kv = paramEdits.value[name]
    if (kv) edited[name] = kv
  }
  const params = paramOverrides(edited, defaultsByStrategy.value)
  if (params) payload.params = params
  submitting.value = true
  try {
    const job = await postJSON<Job>('/api/jobs/backtest', payload)
    jobIds.value.unshift(job.job_id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <details class="card form-card" open>
    <summary>新建回测 / 多策略对比</summary>

    <ErrorBanner v-if="error" :msg="error" />

    <div class="form-row">
      <span class="group-title">策略</span>
      <span class="check-group" data-testid="bt-strategies">
        <span
          v-for="s in strategyMeta"
          :key="s.name"
          class="strat-item"
          :title="s.description"
        >
          <NCheckbox
            :checked="checked.has(s.name)"
            @update:checked="(v: boolean) => toggleStrategy(s.name, v)"
          >
            {{ displayName(s) }}
            <!-- 显示名回退成代码名时(description 缺失)不重复渲染同一串 -->
            <span v-if="displayName(s) !== s.name" class="strat-code num">{{ s.name }}</span>
          </NCheckbox>
          <GlossaryTip :term="s.strategy_type === 'cross_section' ? 'cs_strategy' : 'ts_strategy'">
            <span class="type-badge">[{{ s.strategy_type === 'cross_section' ? '截面' : '时序' }}]</span>
          </GlossaryTip>
        </span>
      </span>
    </div>

    <!-- 渐进披露: 仅勾选的策略展开参数面板(取消勾选即藏, 已改值保留); 初值=默认, 只提交改过的键 -->
    <div v-if="paramStrategies.length" class="param-area" data-testid="bt-params">
      <section
        v-for="s in paramStrategies"
        :key="s.name"
        class="param-panel"
        :data-testid="`bt-params-${s.name}`"
      >
        <header class="param-head">
          <span class="param-title">
            {{ displayName(s) }} 参数
            <span v-if="displayName(s) !== s.name" class="num param-code">{{ s.name }}</span>
          </span>
          <NButton size="tiny" quaternary @click="restoreDefaults(s.name)">还原默认</NButton>
        </header>
        <div class="param-grid">
          <label v-for="p in editablesByStrategy[s.name]" :key="p.key" class="param-item">
            <span class="num param-key">{{ p.key }}</span>
            <NInputNumber
              v-if="p.numeric"
              size="small"
              :show-button="false"
              :value="numValue(s.name, p.key)"
              :placeholder="String(p.def)"
              style="width: 104px"
              @update:value="(v: number | null) => setParam(s.name, p.key, v)"
            />
            <NInput
              v-else
              size="small"
              :value="strValue(s.name, p.key)"
              :placeholder="String(p.def)"
              style="width: 104px"
              @update:value="(v: string) => setParam(s.name, p.key, v)"
            />
            <span class="param-def">默认 {{ p.def }}</span>
          </label>
        </div>
      </section>
    </div>

    <!-- 字段统一 160px 栅格, 配置收尾 280px — 行内框边对齐 -->
    <div class="form-row">
      <label>起 <NDatePicker v-model:formatted-value="startDate" value-format="yyyy-MM-dd" type="date" clearable style="width: 160px" data-testid="bt-start" /></label>
      <label>止 <NDatePicker v-model:formatted-value="endDate" value-format="yyyy-MM-dd" type="date" clearable style="width: 160px" data-testid="bt-end" /></label>
      <label>
        <GlossaryTip term="initial_capital">初始资金</GlossaryTip>
        <NInputNumber v-model:value="capital" placeholder="配置默认" :step="10000" :show-button="false" style="width: 160px" />
      </label>
      <label>
        <GlossaryTip term="bt_config">配置</GlossaryTip>
        <NSelect v-model:value="config" :options="CONFIG_OPTIONS" style="width: 280px" />
      </label>
    </div>

    <div class="form-row sym-row">
      <label class="sym-field">
        标的（留空=配置默认）
        <div ref="chipsBoxRef" class="chips-box" :class="{ disabled: hasCross }">
          <span v-for="sym in chips.symbols.value" :key="sym" class="chip" data-testid="bt-chip">
            {{ sym }}
            <button class="chip-x" type="button" :aria-label="`移除标的 ${sym}`" @click="chips.remove(sym)">×</button>
          </span>
          <input
            class="chip-input"
            data-testid="bt-symbols-input"
            :value="chips.input.value"
            :disabled="hasCross"
            :placeholder="symPlaceholder"
            autocomplete="off"
            role="combobox"
            aria-autocomplete="list"
            aria-controls="bt-sym-listbox"
            :aria-expanded="chips.suggestions.value.length > 0"
            :aria-activedescendant="
              chips.activeIndex.value >= 0 ? `bt-sym-opt-${chips.activeIndex.value}` : undefined
            "
            @input="onSymInput"
            @keydown="onSymKeydown"
          />
          <ul v-if="chips.suggestions.value.length" id="bt-sym-listbox" class="suggest card" role="listbox">
            <li
              v-for="(hit, i) in chips.suggestions.value"
              :id="`bt-sym-opt-${i}`"
              :key="hit.symbol"
              role="option"
              :aria-selected="chips.activeIndex.value === i"
              :class="{ 'is-active': chips.activeIndex.value === i }"
              @click="chips.pickSuggestion(hit)"
            >
              <span class="num">{{ hit.symbol }}</span> {{ hit.name }}
            </li>
          </ul>
        </div>
      </label>
      <NButton
        type="primary"
        :loading="submitting"
        :disabled="submitting"
        data-testid="bt-submit"
        @click="submitBacktest"
        >提交回测</NButton
      >
    </div>

    <p v-if="chips.err.value" class="form-hint sym-err t-warn">{{ chips.err.value }}</p>
    <p v-if="hasCross" class="form-hint t-muted">{{ HINT_TEXT }}</p>

    <div data-testid="bt-job-area">
      <JobCard v-for="id in jobIds" :key="id" :job-id="id" @done="emit('done')" />
    </div>
  </details>
</template>

<style scoped>
.form-card {
  margin-bottom: var(--gap);
}

.form-card summary {
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
}

.form-row {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap);
  margin: 14px 0;
}

.form-row > label {
  color: var(--text-3);
  display: flex;
  flex-direction: column;
  font-size: 12.5px;
  gap: 6px;
}

/* 信息型标注降为灰阶 — 橙色只留给主按钮/激活态, 不与 CTA 争焦点 */
.group-title {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: 12.5px;
  font-weight: 700;
}

.check-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
}

.strat-item {
  align-items: center;
  display: inline-flex;
  gap: 4px;
}

/* 代码名次要小字: 淡色+mono(.num), 主文字(中文显示名)保持勾选框默认字号 */
.strat-code {
  color: var(--text-3);
  font-size: 11px;
  margin-left: 2px;
}

.type-badge {
  color: var(--accent-blue);
  font-family: var(--font-display);
  font-size: 11.5px;
  font-weight: 700;
}

/* 参数区 — 视觉克制: --bg-3 微凹底、--space-2 紧凑距、--fs-xs 标签, 不与 CTA 争焦点 */
.param-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: var(--space-2) 0 14px;
}

.param-panel {
  background: var(--bg-3);
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3);
}

.param-head {
  align-items: center;
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.param-title {
  color: var(--text-3);
  font-family: var(--font-display);
  font-size: var(--fs-xs);
  font-weight: 700;
}

.param-code {
  font-size: var(--fs-xs);
  font-weight: 400;
  margin-left: 2px;
}

.param-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}

.param-item {
  align-items: center;
  color: var(--text-3);
  display: inline-flex;
  font-size: var(--fs-xs);
  gap: var(--space-2);
}

.param-key {
  color: var(--text-2);
  font-size: var(--fs-xs);
}

/* 「默认 5」淡字标注 — 改动后仍可对照原默认 */
.param-def {
  font-size: var(--fs-xs);
  opacity: 0.75;
  white-space: nowrap;
}

.sym-row {
  align-items: end;
}

.sym-field {
  flex: 1;
  min-width: 280px;
}

.chips-box {
  align-items: center;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 38px;
  padding: 5px 8px;
  position: relative;
  transition: border-color var(--dur-fast) var(--ease-out);
}

.chips-box:focus-within {
  border-color: var(--accent);
}

.chips-box.disabled {
  background: var(--bg-3);
  opacity: 0.7;
}

.chip {
  align-items: center;
  background: var(--accent-soft);
  border-radius: 14px;
  color: var(--accent);
  display: inline-flex;
  font-family: var(--font-mono);
  font-size: 12px;
  gap: 4px;
  padding: 2px 6px 2px 10px;
}

.chip-x {
  background: transparent;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
}

.chip-x:hover {
  color: var(--c-fail);
}

.chip-input {
  background: transparent;
  border: none;
  color: var(--text);
  flex: 1;
  font-family: var(--font-body);
  font-size: 13px;
  min-width: 180px;
  outline: none;
  padding: 4px 2px;
}

.suggest {
  left: 0;
  list-style: none;
  margin: 0;
  max-height: 260px;
  overflow-y: auto;
  padding: 4px;
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: 50;
}

.suggest li {
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  padding: 6px 10px;
  transition: background var(--dur-fast) var(--ease-out);
}

.suggest li:hover,
.suggest li.is-active {
  background: var(--accent-soft);
}

.form-hint {
  font-size: 12.5px;
  margin: 6px 0 0;
}
</style>
