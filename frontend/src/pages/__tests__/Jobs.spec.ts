import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Job, JobStatus } from '@/api/types'
import { useJobsStore } from '@/stores/jobs'

import Jobs from '../Jobs.vue'

function mkJob(id: string, status: JobStatus, extra: Partial<Job> = {}): Job {
  return {
    job_id: id,
    job_type: 'backtest',
    params: {},
    status,
    created_at: '2026-07-04T09:30:00',
    started_at: null,
    finished_at: null,
    return_code: null,
    log_path: 'x.log',
    ...extra,
  }
}

let pinia: Pinia
let listJobs: Job[]
let detailQueues: Record<string, Job[]>
let detailFail: boolean
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

/* 按 id 出队明细响应: 队列耗尽后重复最后一帧; 无脚本时默认已完成(供 JobCard done 闭环) */
function detailResp(id: string): Job {
  const q = detailQueues[id]
  if (q && q.length > 0) return q.length > 1 ? q.shift()! : q[0]
  return mkJob(id, 'succeeded', {
    started_at: '2026-07-04T09:59:00',
    finished_at: '2026-07-04T09:59:30',
    log_tail: [],
  })
}

function urls(re: RegExp): string[] {
  return fetchMock.mock.calls.map((c) => String(c[0])).filter((u) => re.test(u))
}

function bodyOf(url: string): unknown {
  const call = fetchMock.mock.calls.find((c) => String(c[0]) === url)
  if (!call) return null
  return JSON.parse((call[1] as { body: string }).body)
}

function mountJobs() {
  const w = mount(Jobs, {
    global: {
      plugins: [pinia],
      stubs: {
        NDatePicker: true,
        NInput: true,
        NInputNumber: true,
        NButton: { template: '<button><slot /></button>' },
        GlossaryTip: { template: '<span><slot /></span>' },
      },
    },
  })
  wrapper = w
  return w
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-07-04T10:00:00'))
  pinia = createPinia()
  setActivePinia(pinia)
  listJobs = [
    mkJob('j1', 'running', {
      started_at: '2026-07-04T09:59:15',
      params: { strategies: ['micro_value'], start_date: '2024-01-01', end_date: '2024-06-30' },
    }),
    mkJob('j2', 'queued', { job_type: 'factor_test', params: { factors: 'P0' } }),
    mkJob('j3', 'succeeded', {
      started_at: '2026-07-04T09:00:00',
      finished_at: '2026-07-04T09:01:00',
    }),
  ]
  detailQueues = {}
  detailFail = false
  fetchMock = vi.fn().mockImplementation((input: unknown, init?: { method?: string }) => {
    const url = String(input)
    if (url.startsWith('/api/jobs?limit=')) {
      return jsonResp({ jobs: listJobs, active: true })
    }
    if (/\/api\/jobs\/[^/?]+\/cancel$/.test(url)) {
      return jsonResp({})
    }
    if (url === '/api/jobs/ml-train' || url === '/api/jobs/ml-evaluate') {
      expect(init?.method).toBe('POST')
      return jsonResp(mkJob('mlj1', 'queued'))
    }
    const detail = /\/api\/jobs\/([^/?]+)\?tail=\d+$/.exec(url)
    if (detail) {
      if (detailFail) return Promise.reject(new Error('net down'))
      return jsonResp(detailResp(detail[1]))
    }
    return Promise.reject(new Error(`unexpected url: ${url}`))
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('Jobs 任务列表', () => {
  it('渲染中文状态/参数摘要/创建切片/耗时, 活跃数写回 store', async () => {
    const w = mountJobs()
    await flushPromises()

    const rows = w.findAll('[data-testid="job-row"]')
    expect(rows).toHaveLength(3)
    expect(w.text()).toContain('运行中')
    expect(w.text()).toContain('排队中')
    expect(w.text()).toContain('已完成')
    expect(w.text()).toContain('micro_value · 2024-01-01~2024-06-30')
    expect(w.text()).toContain('07-04T09:30:00') // created_at.slice(5,19)
    expect(w.text()).toContain('45s') // running: now-started
    expect(w.text()).toContain('60s') // finished-started
    // 仅 queued|running 行有取消钮
    expect(w.findAll('[data-testid="job-row-cancel"]')).toHaveLength(2)
    // queued+running 计数写回 store(顶栏徽章/503 文案依赖)
    expect(useJobsStore().activeCount).toBe(2)
  })

  it('空列表显空态并清零活跃数', async () => {
    listJobs = []
    const w = mountJobs()
    await flushPromises()

    expect(w.find('[data-testid="jobs-empty"]').exists()).toBe(true)
    expect(w.text()).toContain('暂无任务')
    expect(useJobsStore().activeCount).toBe(0)
  })

  it('取消: POST cancel 后刷新列表, .stop 不触发日志钻取', async () => {
    const w = mountJobs()
    await flushPromises()
    const listCalls = urls(/\/api\/jobs\?limit=100$/).length

    await w.find('[data-testid="job-row-cancel"]').trigger('click')
    await flushPromises()

    const cancelCall = fetchMock.mock.calls.find((c) => String(c[0]).endsWith('/j1/cancel'))
    expect(cancelCall).toBeTruthy()
    expect((cancelCall?.[1] as { method?: string }).method).toBe('POST')
    expect(urls(/\/api\/jobs\?limit=100$/).length).toBe(listCalls + 1)
    expect(urls(/\?tail=300$/)).toHaveLength(0)
  })
})

describe('Jobs 日志钻取', () => {
  it('行点击 → tail=300 2s 轮询, 标题 jobId·状态, 终态停', async () => {
    detailQueues.j1 = [
      mkJob('j1', 'running', { started_at: '2026-07-04T09:59:15', log_tail: ['l1', 'l2'] }),
      mkJob('j1', 'succeeded', {
        started_at: '2026-07-04T09:59:15',
        finished_at: '2026-07-04T10:00:30',
        log_tail: ['l1', 'l2', 'done'],
      }),
    ]
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-row"]')[0].trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="job-log-title"]').text()).toBe('j1 · 运行中')
    expect(w.find('[data-testid="job-log"]').text()).toBe('l1\nl2')

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(w.find('[data-testid="job-log-title"]').text()).toBe('j1 · 已完成')
    expect(w.find('[data-testid="job-log"]').text()).toBe('l1\nl2\ndone')

    const n = urls(/\?tail=300$/).length
    await vi.advanceTimersByTimeAsync(6000)
    expect(urls(/\?tail=300$/).length).toBe(n) // 终态已停轮询
  })

  it('日志空输出显（无输出）', async () => {
    detailQueues.j3 = [
      mkJob('j3', 'succeeded', {
        started_at: '2026-07-04T09:00:00',
        finished_at: '2026-07-04T09:01:00',
        log_tail: [],
      }),
    ]
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-row"]')[2].trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="job-log"]').text()).toBe('（无输出）')
  })

  it('连续 5 次查询失败停轮询并显服务重启文案', async () => {
    detailFail = true
    const w = mountJobs()
    await flushPromises()

    await w.findAll('[data-testid="job-row"]')[0].trigger('click')
    await flushPromises() // 失败 1
    await vi.advanceTimersByTimeAsync(8000) // 失败 2..5
    await flushPromises()

    expect(w.find('[data-testid="job-log"]').text()).toBe('任务查询失败（服务可能已重启）')
    const n = urls(/\?tail=300$/).length
    expect(n).toBe(5)
    await vi.advanceTimersByTimeAsync(6000)
    expect(urls(/\?tail=300$/).length).toBe(n) // 已停
  })
})

describe('Jobs ML 表单', () => {
  it('训练提交默认载荷, JobCard 挂 ml-job-area, done 后刷列表', async () => {
    const w = mountJobs()
    await flushPromises()

    await w.find('[data-testid="ml-train-submit"]').trigger('click')
    await flushPromises()
    await flushPromises()

    expect(bodyOf('/api/jobs/ml-train')).toEqual({
      start_date: '2021-01-01',
      end_date: '2024-12-31',
      symbols: '000300.SH',
      model_name: 'lgbm_return_5d',
      n_trials: 50,
    })
    const area = w.find('[data-testid="ml-job-area"]')
    expect(area.find('[data-testid="job-card"]').exists()).toBe(true)

    // 默认明细响应=已完成 → JobCard 首 tick 即 done → 列表刷新
    await flushPromises()
    await flushPromises()
    expect(urls(/\/api\/jobs\?limit=100$/).length).toBe(2)
  })

  it('评估提交默认载荷(共用模型名输入)', async () => {
    const w = mountJobs()
    await flushPromises()

    await w.find('[data-testid="ml-eval-submit"]').trigger('click')
    await flushPromises()

    expect(bodyOf('/api/jobs/ml-evaluate')).toEqual({
      model_name: 'lgbm_return_5d',
      eval_start: '2025-01-01',
      eval_end: '2025-12-31',
    })
  })
})
