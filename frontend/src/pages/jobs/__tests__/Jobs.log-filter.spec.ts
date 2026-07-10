/* Jobs 页日志过滤框接线测试 — 纯函数 filterLogLines 语义已在 ui.spec 覆盖,
 * 此处只验组件接线: 输入→行集过滤+N/M 计数、无命中空面板、清空恢复全量、
 * 轮询新帧在过滤态下持续生效。挂载脚手架对齐 pages/__tests__/Jobs.spec.ts
 * (该文件不在本轮改动范围, 故新增独立 spec 不动既有断言)。 */
import { flushPromises, mount } from '@vue/test-utils'
import { NPopconfirm } from 'naive-ui'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Job, JobStatus } from '@/api/types'

import Jobs from '../../Jobs.vue'

function mkJob(id: string, status: JobStatus, extra: Partial<Job> = {}): Job {
  return {
    job_id: id,
    job_type: 'backtest',
    params: {},
    status,
    created_at: '2026-07-04T09:30:00',
    started_at: '2026-07-04T09:59:15',
    finished_at: null,
    return_code: null,
    log_path: 'x.log',
    ...extra,
  }
}

function jsonResp(body: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  })
}

let pinia: Pinia
let tail: string[] // 明细端点每次 tick 读取的最新 log_tail(可变, 便于模拟新帧)
let wrapper: { unmount(): void } | null = null

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-07-04T10:00:00'))
  pinia = createPinia()
  setActivePinia(pinia)
  tail = []
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: unknown) => {
      const url = String(input)
      if (url.startsWith('/api/jobs?limit=')) {
        return jsonResp({ jobs: [mkJob('j1', 'running')], active: true })
      }
      if (/\/api\/jobs\/j1\?tail=\d+$/.test(url)) {
        // 始终 running: 日志轮询不因终态停表, 供"过滤态下新帧"用例推进
        return jsonResp(mkJob('j1', 'running', { log_tail: [...tail] }))
      }
      return Promise.reject(new Error(`unexpected url: ${url}`))
    }),
  )
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

/** 挂载 + 钻取 j1 日志(首帧 lines), 返回 wrapper */
async function mountWithLog(lines: string[]) {
  tail = lines
  const w = mount(Jobs, {
    global: {
      plugins: [pinia],
      stubs: {
        NDatePicker: true,
        NInput: true,
        NInputNumber: true,
        NButton: true,
        GlossaryTip: { template: '<span><slot /></span>' },
        [NPopconfirm.name as string]: true,
      },
    },
  })
  wrapper = w
  await flushPromises() // 列表首帧
  await w.findAll('[data-testid="job-row"]')[0].trigger('click')
  await flushPromises() // 日志首帧
  return w
}

describe('Jobs 日志过滤框', () => {
  it('未过滤: 全量显示且不显 N/M 计数', async () => {
    const w = await mountWithLog(['Epoch 1 loss=0.52', 'saving checkpoint'])

    expect(w.find('[data-testid="job-log"]').text()).toBe('Epoch 1 loss=0.52\nsaving checkpoint')
    expect(w.find('[data-testid="job-log-filter"]').exists()).toBe(true)
    expect(w.find('[data-testid="job-log-filter-count"]').exists()).toBe(false)
  })

  it('输入过滤词仅显命中行(大小写不敏感), 并显 N/M 行计数', async () => {
    const w = await mountWithLog(['Epoch 1 loss=0.52', 'saving checkpoint', 'EPOCH 2 loss=0.41'])

    await w.find('[data-testid="job-log-filter"]').setValue('epoch')

    expect(w.find('[data-testid="job-log"]').text()).toBe('Epoch 1 loss=0.52\nEPOCH 2 loss=0.41')
    expect(w.find('[data-testid="job-log-filter-count"]').text()).toBe('2/3 行')
  })

  it('无命中: 面板清空, 计数 0/N 行说明非日志缺失', async () => {
    const w = await mountWithLog(['alpha', 'beta'])

    await w.find('[data-testid="job-log-filter"]').setValue('zzz')

    expect(w.find('[data-testid="job-log"]').text()).toBe('')
    expect(w.find('[data-testid="job-log-filter-count"]').text()).toBe('0/2 行')
  })

  it('清空过滤恢复全量并隐藏计数', async () => {
    const w = await mountWithLog(['alpha', 'beta'])
    await w.find('[data-testid="job-log-filter"]').setValue('alp')
    expect(w.find('[data-testid="job-log"]').text()).toBe('alpha')

    await w.find('[data-testid="job-log-filter"]').setValue('')
    await flushPromises() // 清空 watch: nextTick 后恢复滚底

    expect(w.find('[data-testid="job-log"]').text()).toBe('alpha\nbeta')
    expect(w.find('[data-testid="job-log-filter-count"]').exists()).toBe(false)
  })

  it('过滤态下轮询新帧持续生效: 行集与计数随刷新', async () => {
    const w = await mountWithLog(['ERROR a', 'info b'])
    await w.find('[data-testid="job-log-filter"]').setValue('error')
    expect(w.find('[data-testid="job-log"]').text()).toBe('ERROR a')
    expect(w.find('[data-testid="job-log-filter-count"]').text()).toBe('1/2 行')

    tail = ['ERROR a', 'info b', 'error c'] // 后端新增一行命中行
    await vi.advanceTimersByTimeAsync(2000) // 日志轮询下一 tick
    await flushPromises()

    expect(w.find('[data-testid="job-log"]').text()).toBe('ERROR a\nerror c')
    expect(w.find('[data-testid="job-log-filter-count"]').text()).toBe('2/3 行')
  })
})
