import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import type { StrategyMeta } from '@/api/types'

import BacktestForm from '../BacktestForm.vue'

/* R7 接线验收: 日期 clearable 清空后提交 → 前端拦截(不发 /api/jobs/backtest, 表单内
 * 中文必填提示), 默认日期完好路径提交载荷不回归。stub 惯例同 pages/__tests__/Jobs.spec。 */

const META: StrategyMeta[] = [
  { name: 'dual_ma', strategy_type: 'bar', description: '双均线（趋势跟随）', default_params: {} },
]

let fetchMock: ReturnType<typeof vi.fn>
let wrapper: { unmount(): void } | null = null

function jsonResp(body: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  })
}

function postedUrls(): string[] {
  return fetchMock.mock.calls.map((c) => String(c[0]))
}

/* stub 组件(NDatePicker = true)按 data-testid 定位后发 v-model 更新事件 —
 * findComponent(string) 的类型是 WrapperLike(无 vm), 运行时实为组件包装器, 此处收窄 */
function emitStub(w: ReturnType<typeof mountForm>, testid: string, event: string, value: unknown): void {
  const stub = w.findComponent(`[data-testid="${testid}"]`) as unknown as {
    vm: { $emit(e: string, v: unknown): void }
  }
  stub.vm.$emit(event, value)
}

function mountForm() {
  const w = mount(BacktestForm, {
    props: { strategyMeta: META },
    global: {
      stubs: {
        NCheckbox: true,
        NDatePicker: true,
        NInput: true,
        NInputNumber: true,
        NSelect: true,
        NButton: {
          props: ['loading', 'disabled'],
          template: '<button :disabled="disabled"><slot /></button>',
        },
        GlossaryTip: { template: '<span><slot /></span>' },
        JobCard: true,
      },
    },
  })
  wrapper = w
  return w
}

beforeEach(() => {
  fetchMock = vi.fn().mockImplementation((input: unknown) => {
    const url = String(input)
    if (url === '/api/jobs/backtest') {
      return jsonResp({ job_id: 'bt1', status: 'queued' })
    }
    return Promise.reject(new Error(`unexpected url: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('BacktestForm 日期必填收口(R7)', () => {
  it('默认日期完好: 提交发出 start/end 双非空载荷(行为不回归)', async () => {
    const w = mountForm()
    await flushPromises() // meta watch 默认勾选 dual_ma

    await w.find('[data-testid="bt-submit"]').trigger('click')
    await flushPromises()

    expect(postedUrls()).toContain('/api/jobs/backtest')
    const body = JSON.parse(
      (fetchMock.mock.calls.find((c) => String(c[0]) === '/api/jobs/backtest')![1] as { body: string }).body,
    )
    expect(body).toEqual({
      strategies: ['dual_ma'],
      start_date: '2024-01-01',
      end_date: '2025-12-31',
    })
  })

  it.each([
    ['清空起始日期', 'bt-start'],
    ['清空结束日期', 'bt-end'],
  ])('%s → 拦截: 零请求 + 表单内「起止日期均必填」提示', async (_name, testid) => {
    const w = mountForm()
    await flushPromises()

    // NDatePicker clearable 清空 = v-model:formatted-value 收到 null
    emitStub(w, testid, 'update:formattedValue', null)
    await nextTick()

    await w.find('[data-testid="bt-submit"]').trigger('click')
    await flushPromises()

    expect(postedUrls()).not.toContain('/api/jobs/backtest')
    const banner = w.find('[data-testid="error-banner"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('起止日期均必填')
  })

  it('重新补齐日期后可正常提交(拦截不粘滞)', async () => {
    const w = mountForm()
    await flushPromises()

    emitStub(w, 'bt-start', 'update:formattedValue', null)
    await nextTick()
    await w.find('[data-testid="bt-submit"]').trigger('click')
    await flushPromises()
    expect(postedUrls()).not.toContain('/api/jobs/backtest')

    emitStub(w, 'bt-start', 'update:formattedValue', '2023-06-01')
    await nextTick()
    await w.find('[data-testid="bt-submit"]').trigger('click')
    await flushPromises()

    expect(postedUrls()).toContain('/api/jobs/backtest')
    expect(w.find('[data-testid="error-banner"]').exists()).toBe(false)
  })
})
