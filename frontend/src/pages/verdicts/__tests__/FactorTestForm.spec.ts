import { flushPromises, mount } from '@vue/test-utils'
import { NButton, NDatePicker, NInputNumber, NSelect } from 'naive-ui'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import FactorTestForm from '../FactorTestForm.vue'

const META_RESPONSE = {
  factors: [
    { factor_id: 'F01', name: 'ROA', field_ready: true },
    { factor_id: 'F02', name: '停牌因子', field_ready: false },
    { factor_id: 'F03', name: 'PE', field_ready: true },
  ],
  groups: { P0: ['F01', 'F02'], P1: ['F03'] },
}

function jsonResp(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body), text: () => Promise.resolve('') })
}

// naive-ui 组件运行时 .name 不带 N 前缀(如 NSelect.name === 'Select'), 字符串字面量 key
// 匹配不上、真实组件会穿透渲染——按 Task 7 整体复核发现的同类问题, 统一用 [Component.name as string]。
const stubs = {
  [NDatePicker.name as string]: true,
  [NInputNumber.name as string]: true,
  [NSelect.name as string]: true,
  // 只用 <slot/>, 不额外写 @click="$emit('click')": 那样会和 attrs fallthrough
  // 的原生 click 监听同时触发, 导致父层 @click 处理函数被调用两次(此 stub 之前因
  // key 匹配不上从未真正生效, 修 key 后才暴露; 修复方式同 Verdicts.spec.ts 里
  // FactorCard stub 的同款教训)。
  // 声明 loading/disabled 并映射到原生 disabled, 以便断言提交 pending 态(Task 3);
  // 其余 attrs(type/data-testid/onClick)照旧穿透。
  [NButton.name as string]: {
    props: ['loading', 'disabled'],
    template: '<button :disabled="disabled || loading"><slot /></button>',
  },
}

function mountForm(lastSplitHint: string | null = null) {
  return mount(FactorTestForm, { props: { lastSplitHint }, global: { stubs } })
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.useFakeTimers()
  fetchMock = vi.fn().mockImplementation((input: unknown, init?: { method?: string }) => {
    const url = String(input)
    if (url === '/api/meta/factors') return jsonResp(META_RESPONSE)
    if (url === '/api/jobs/factor-test') {
      expect(init?.method).toBe('POST')
      return jsonResp({ job_id: 'jt1', job_type: 'factor_test', status: 'queued' })
    }
    if (url === '/api/jobs/jt1?tail=120') {
      return jsonResp({
        job_id: 'jt1', job_type: 'factor_test', params: {}, status: 'succeeded',
        created_at: '2026-07-05T09:00:00', started_at: '2026-07-05T09:00:01',
        finished_at: '2026-07-05T09:00:30', return_code: 0, log_path: 'x.log', log_tail: [],
      })
    }
    return Promise.reject(new Error(`unexpected url: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('FactorTestForm', () => {
  it('P0 组默认勾选非禁用因子, 禁用项(field_ready=false)不勾选', async () => {
    const w = mountForm()
    await flushPromises()
    const chips = w.findAll('[data-testid="ft-factor-chip"]')
    expect(chips).toHaveLength(3)
    expect(chips[0]?.classes()).toContain('checked') // F01: P0 且非禁用
    expect(chips[1]?.classes()).toContain('disabled') // F02: field_ready=false
    expect(chips[1]?.classes()).not.toContain('checked')
    expect(chips[2]?.classes()).not.toContain('checked') // F03: P1 组不自动勾
  })

  it('点击禁用 chip 不改变勾选状态', async () => {
    const w = mountForm()
    await flushPromises()
    const disabledChip = w.findAll('[data-testid="ft-factor-chip"]')[1]!
    await disabledChip.trigger('click')
    expect(disabledChip.classes()).not.toContain('checked')
  })

  it('点击可用 chip 切换勾选', async () => {
    const w = mountForm()
    await flushPromises()
    const chip = w.findAll('[data-testid="ft-factor-chip"]')[2]!
    await chip.trigger('click')
    expect(chip.classes()).toContain('checked')
    await chip.trigger('click')
    expect(chip.classes()).not.toContain('checked')
  })

  it('取消全部勾选后提交报错, 不发请求', async () => {
    const w = mountForm()
    await flushPromises()
    await w.findAll('[data-testid="ft-factor-chip"]')[0]!.trigger('click') // 取消 F01(唯一默认勾选项)
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="error-banner"]').text()).toContain('至少勾选一个因子')
    expect(fetchMock.mock.calls.some((c) => String(c[0]) === '/api/jobs/factor-test')).toBe(false)
  })

  it('提交默认载荷含默认勾选因子与默认表单值', async () => {
    const w = mountForm()
    await flushPromises()
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()

    const call = fetchMock.mock.calls.find((c) => String(c[0]) === '/api/jobs/factor-test')
    expect(call).toBeTruthy()
    const body = JSON.parse((call?.[1] as { body: string }).body)
    expect(body).toEqual({
      factors: 'F01',
      start_date: '',
      end_date: '',
      objective: 'long_only',
      num_layers: 5,
      rebalance_days: 5,
      cost_rate: 0.003,
    })
    expect(w.find('[data-testid="ft-job-area"]').find('[data-testid="job-card"]').exists()).toBe(true)
  })

  it('lastSplitHint 预填切分日, 提交载荷带 split_date', async () => {
    const w = mountForm('2024-06-30')
    await flushPromises()
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()
    const call = fetchMock.mock.calls.find((c) => String(c[0]) === '/api/jobs/factor-test')
    const body = JSON.parse((call?.[1] as { body: string }).body)
    expect(body.split_date).toBe('2024-06-30')
  })

  it('勾选多因子且未设切分 → 显示多重检验提示', async () => {
    const w = mountForm()
    await flushPromises()
    await w.findAll('[data-testid="ft-factor-chip"]')[2]!.trigger('click') // 加勾 F03 → 2 个已勾, 无切分
    expect(w.find('.hint').exists()).toBe(true)
  })

  it('JobCard 真实终态(succeeded)后 emit refresh', async () => {
    const w = mountForm()
    await flushPromises()
    await w.find('[data-testid="ft-submit"]').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(w.emitted('refresh')).toHaveLength(1)
  })

  it('提交检验期间按钮进入 pending(disabled), 完成后恢复', async () => {
    // gate 卡住 POST, 观测在途 pending 态; 其余 URL 沿用同批响应
    let releasePost!: () => void
    const gate = new Promise<void>((r) => {
      releasePost = r
    })
    fetchMock.mockImplementation((input: unknown, init?: { method?: string }) => {
      const url = String(input)
      if (url === '/api/meta/factors') return jsonResp(META_RESPONSE)
      if (url === '/api/jobs/factor-test') {
        expect(init?.method).toBe('POST')
        return gate.then(() => ({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ job_id: 'jt1', job_type: 'factor_test', status: 'queued' }),
          text: () => Promise.resolve(''),
        }))
      }
      if (url === '/api/jobs/jt1?tail=120') {
        return jsonResp({
          job_id: 'jt1', job_type: 'factor_test', params: {}, status: 'succeeded',
          created_at: '2026-07-05T09:00:00', started_at: '2026-07-05T09:00:01',
          finished_at: '2026-07-05T09:00:30', return_code: 0, log_path: 'x.log', log_tail: [],
        })
      }
      return Promise.reject(new Error(`unexpected url: ${url}`))
    })

    const w = mountForm()
    await flushPromises()
    const btn = w.find('[data-testid="ft-submit"]')
    expect(btn.attributes('disabled')).toBeUndefined()

    await btn.trigger('click') // 提交发起, POST 被 gate 卡住
    expect(btn.attributes('disabled')).toBeDefined() // pending 中

    releasePost()
    await flushPromises()
    await flushPromises()
    expect(btn.attributes('disabled')).toBeUndefined() // 恢复
  })
})
