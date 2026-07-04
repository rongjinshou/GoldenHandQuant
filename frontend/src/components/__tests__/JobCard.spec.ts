import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Job } from '@/api/types'

import JobCard from '../JobCard.vue'

function job(status: Job['status'], extra: Partial<Job> = {}): Job {
  return {
    job_id: 'abc123',
    job_type: 'backtest',
    params: { strategies: ['micro_value'], start_date: '2024-01-01', end_date: '2024-06-30' },
    status,
    created_at: '2026-07-04T10:00:00',
    started_at: '2026-07-04T10:00:01',
    finished_at: null,
    return_code: null,
    log_path: 'x.log',
    log_tail: ['line1', 'line2'],
    ...extra,
  }
}

let responses: Job[]

beforeEach(() => {
  vi.useFakeTimers()
  responses = []
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(() => {
      const next = responses.length > 1 ? responses.shift()! : responses[0]
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(next), text: () => Promise.resolve('') })
    }),
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('JobCard', () => {
  it('渲染中文状态与参数摘要', async () => {
    responses = [job('running')]
    const w = mount(JobCard, { props: { jobId: 'abc123' } })
    await flushPromises()
    expect(w.text()).toContain('运行中')
    expect(w.text()).toContain('micro_value')
    expect(w.text()).toContain('2024-01-01~2024-06-30')
    expect(w.find('pre').text()).toBe('line1\nline2')
  })

  it('done 仅 succeeded 终态触发一次, 且取消钮消失', async () => {
    responses = [job('running'), job('succeeded', { finished_at: '2026-07-04T10:01:31' })]
    const w = mount(JobCard, { props: { jobId: 'abc123' } })
    await flushPromises()
    expect(w.find('[data-testid="job-cancel"]').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(w.emitted('done')).toHaveLength(1)
    expect(w.find('[data-testid="job-cancel"]').exists()).toBe(false)
    expect(w.text()).toContain('已完成')
    expect(w.text()).toContain('1.5min') // durationOf 对等旧版: sec<90 显秒, 90s 整落分钟档
  })

  it('failed 终态不触发 done', async () => {
    responses = [job('failed')]
    const w = mount(JobCard, { props: { jobId: 'abc123' } })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000)
    expect(w.emitted('done')).toBeUndefined()
  })

  it('连续 5 次查询失败终止轮询显示失败态', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
    const w = mount(JobCard, { props: { jobId: 'abc123' } })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000 * 6)
    await flushPromises()
    expect(w.text()).toContain('查询失败')
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.length
    await vi.advanceTimersByTimeAsync(2000 * 3)
    expect((fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(calls) // 已停
  })
})
