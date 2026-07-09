import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/* Explorer 流无障碍/反馈的模板契约防线(设计 §8 S5/S6/S8, 任务 1-5):
 * 联想 combobox 键盘 aria、图表 role=img、特征在途/失败反馈、加载骨架等属性直接落在 .vue 模板上,
 * 挂载真实 Explorer(含 ECharts/naive/NPopover)在 jsdom 下代价高且脆; 这里按"读文件断言关键属性存在"
 * 守住不回归(纯逻辑另在 suggest-nav.spec.ts / chart-options.spec.ts 覆盖)。 */

function read(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
}

const explorer = read('../../Explorer.vue')
const featurePanel = read('../FeaturePanel.vue')

describe('Explorer.vue 标的联想 combobox 键盘 aria(任务 1 / §8 S8)', () => {
  it('input 挂 combobox 语义与联动 aria', () => {
    expect(explorer).toContain('role="combobox"')
    expect(explorer).toContain('aria-autocomplete="list"')
    expect(explorer).toContain('aria-expanded')
    expect(explorer).toContain('aria-controls')
    expect(explorer).toContain('aria-activedescendant')
  })

  it('候选列表 listbox/option + aria-selected(高亮读共享 chips.activeIndex, 单一真相源)', () => {
    expect(explorer).toContain('role="listbox"')
    expect(explorer).toContain('role="option"')
    expect(explorer).toContain('aria-selected')
    expect(explorer).toContain('chips.activeIndex')
  })

  it('键盘 ↑↓/Enter/Esc 接线到共享 composable(不自持第二套高亮状态)', () => {
    expect(explorer).toContain('ArrowDown')
    expect(explorer).toContain('ArrowUp')
    expect(explorer).toContain('Escape')
    expect(explorer).toContain('chips.onArrowDown()')
    expect(explorer).toContain('chips.onArrowUp()')
    expect(explorer).toContain('chips.onEscape()')
    expect(explorer).toContain('chips.onEnter()')
  })

  it('点外收起: 监听 document pointerdown + 容器 ref → chips.onEscape', () => {
    expect(explorer).toContain('onDocPointerDown')
    expect(explorer).toContain('chipsBoxRef')
    expect(explorer).toMatch(/onDocPointerDown[\s\S]*?chips\.onEscape\(\)/)
  })

  it('chips 校验错误 role=alert(§8 S6)', () => {
    expect(explorer).toMatch(/sym-err[\s\S]*?role="alert"/)
  })
})

describe('Explorer.vue 图表替代文本与加载态(任务 3/5 / §8 S5)', () => {
  it('K 线容器 role=img + 动态 aria-label', () => {
    expect(explorer).toContain('role="img"')
    expect(explorer).toContain(':aria-label="klineAriaLabel"')
  })

  it('加载期给骨架而非空态文案', () => {
    expect(explorer).toContain('chart-skeleton')
    expect(explorer).toMatch(/v-if="loadingData"/)
  })
})

describe('Explorer.vue 特征在途反馈接线(任务 2)', () => {
  it('向呈现框透传 fetching / fetch-error', () => {
    expect(explorer).toContain(':fetching="panelFetching"')
    expect(explorer).toContain(':fetch-error="featureError"')
  })

  it('refetch 失败落到 featureError 而非顶部 error banner', () => {
    expect(explorer).toContain('featureError.value = (e as Error).message')
    // 顶部 error banner 只在整体 loadAll 失败时用; refetch 不再写 error.value = message
    expect(explorer).not.toMatch(/if \(myFeatureGen !== featureFetchGen\) return[\s\S]{0,80}error\.value = \(e as Error\)/)
  })
})

describe('FeaturePanel.vue 反馈与图表 aria(任务 2/3/5)', () => {
  it('头部在途 spinner(role=status) + 失败提示(role=alert)', () => {
    expect(featurePanel).toContain('data-testid="feature-fetching"')
    expect(featurePanel).toContain('role="status"')
    expect(featurePanel).toContain('data-testid="feature-fetch-error"')
    expect(featurePanel).toContain('role="alert"')
  })

  it('特征图容器 role=img + 动态 aria-label', () => {
    expect(featurePanel).toContain('role="img"')
    expect(featurePanel).toContain(':aria-label="ariaLabel"')
  })

  it('在途且无缓存时给骨架', () => {
    expect(featurePanel).toContain('chart-skeleton')
    expect(featurePanel).toContain('fetching && !option')
  })

  it('接收 fetching / fetchError props', () => {
    expect(featurePanel).toContain('fetching?: boolean')
    expect(featurePanel).toContain('fetchError?: string')
  })
})
