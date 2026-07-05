import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import type { FeatureData } from '@/api/types'

import { FEATURE_META, type SymbolMeta } from '../chart-options'
import FeaturePanel from '../FeaturePanel.vue'

/* 特征呈现框组件挂载测试(设计 docs/feat/0705-explorer-multi-symbol) —
 * 纯 props 受控展示层: 勾选/删除只 emit, 不自持内部业务状态。
 * VChart(vue-echarts) shallow-stub 掉: jsdom 无 canvas 2D 后端, 真实 echarts 渲染在此环境下
 * 既不可靠也无必要, 只需断言 option 是否为 null 决定的 v-if 分支即可, 不断言真实图形/canvas。
 * GlossaryTip 用纯透传 stub(同 Jobs.spec.ts 既有先例), 绕开 NPopover/vueuc 定位系统在 jsdom
 * 下需要的 ResizeObserver polyfill(与本测试目标——勾选联动逻辑——无关)。
 * NCheckbox 不 stub: 用真实组件验证"点击 → emit update:modelValue"这条集成路径本身。
 * 需要 active Pinia: useChartTheme() → useThemeStore()(同 Jobs.spec.ts 既有先例)。
 * 注意: stub key 必须是 "Echarts"(vue-echarts 组件内部 name 字段), 不是本文件里的导入别名
 * "VChart" —— VTU 按 setup 局部绑定名匹配的 Prio 1 路径在这套 vite+vitest 组合下未命中,
 * 实测落回 Prio 2(组件内部 name 字段)才生效; 用 "VChart" 当 key 会静默不生效, 真实
 * vue-echarts 组件仍会挂载, 在无 canvas 后端的 jsdom 下因 ResizeObserver 缺失而崩溃。 */

let pinia: Pinia

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
})

interface PanelProps {
  symbols: SymbolMeta[]
  featuresBySymbol: Map<string, FeatureData>
  modelValue: string[]
  removable: boolean
  panelIndex: number
}

function mkSymbols(): SymbolMeta[] {
  return [{ symbol: '000001.SZ', color: '#c0392b' }]
}

function mkFeatureCache(): Map<string, FeatureData> {
  return new Map([
    [
      '000001.SZ',
      {
        dates: ['2024-01-01', '2024-01-02'],
        series: { return_20d: [0.1, 0.2], volatility_20d: [0.01, 0.02], rsi_14: [50, 55] },
      },
    ],
  ])
}

function labelOf(name: string): string {
  return FEATURE_META.find((f) => f.name === name)!.label
}

function mountPanel(overrides: Partial<PanelProps> = {}) {
  const props: PanelProps = {
    symbols: mkSymbols(),
    featuresBySymbol: mkFeatureCache(),
    modelValue: ['return_20d'],
    removable: true,
    panelIndex: 0,
    ...overrides,
  }
  return mount(FeaturePanel, {
    props,
    global: {
      plugins: [pinia],
      stubs: {
        GlossaryTip: { template: '<span><slot /></span>' },
        Echarts: true,
      },
    },
  })
}

function checkboxFor(w: ReturnType<typeof mountPanel>, featureName: string) {
  const label = labelOf(featureName)
  const box = w.findAll('[role="checkbox"]').find((b) => b.text().includes(label))
  if (!box) throw new Error(`checkbox not found for ${featureName}`)
  return box
}

describe('FeaturePanel', () => {
  it('勾选一个未选中的特征: emit update:modelValue 且新数组包含该特征名', async () => {
    const w = mountPanel({ modelValue: ['return_20d'] })
    await checkboxFor(w, 'rsi_14').trigger('click')
    const emitted = w.emitted('update:modelValue')
    expect(emitted).toHaveLength(1)
    expect(emitted![0][0]).toEqual(['return_20d', 'rsi_14'])
  })

  it('取消勾选已选中的特征: emit update:modelValue 且新数组不含该特征名', async () => {
    const w = mountPanel({ modelValue: ['return_20d', 'volatility_20d'] })
    await checkboxFor(w, 'return_20d').trigger('click')
    const emitted = w.emitted('update:modelValue')
    expect(emitted).toHaveLength(1)
    expect(emitted![0][0]).toEqual(['volatility_20d'])
  })

  it('removable=false 时删除按钮不渲染', () => {
    const w = mountPanel({ removable: false })
    expect(w.find('[data-testid="panel-remove"]').exists()).toBe(false)
  })

  it('removable=true 时点击删除按钮 emit remove 恰好一次', async () => {
    const w = mountPanel({ removable: true })
    expect(w.find('[data-testid="panel-remove"]').exists()).toBe(true)
    await w.find('[data-testid="panel-remove"]').trigger('click')
    expect(w.emitted('remove')).toHaveLength(1)
  })

  it('modelValue 为空数组时显示空态文案而不是图表', () => {
    const w = mountPanel({ modelValue: [] })
    expect(w.text()).toContain('暂无特征曲线——勾选上方特征')
    expect(w.find('.empty').exists()).toBe(true)
  })

  it('modelValue 非空且有匹配数据时渲染图表(非空态)', () => {
    const w = mountPanel({ modelValue: ['return_20d'] })
    expect(w.find('.empty').exists()).toBe(false)
  })

  it('data-testid: panelIndex=0 固定为 feature-chart, 非 0 按位置编号拼接(截图脚本锚点契约)', () => {
    const w0 = mountPanel({ panelIndex: 0 })
    expect(w0.attributes('data-testid')).toBe('feature-chart')
    const w2 = mountPanel({ panelIndex: 2 })
    expect(w2.attributes('data-testid')).toBe('feature-chart-2')
  })
})
