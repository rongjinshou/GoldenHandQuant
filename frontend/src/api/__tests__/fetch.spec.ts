import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useJobsStore } from '@/stores/jobs'

import { deleteJSON, fetchJSON, postJSON } from '../fetch'

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
    }),
  )
}

describe('fetchJSON / postJSON', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('200 返回 json', async () => {
    mockFetchOnce(200, { ok: 1 })
    await expect(fetchJSON('/api/x')).resolves.toEqual({ ok: 1 })
  })

  it('500 抛 "status url: body前200字"', async () => {
    mockFetchOnce(500, 'boom'.repeat(100))
    await expect(fetchJSON('/api/x')).rejects.toThrow(/^500 \/api\/x: boom/)
    try {
      mockFetchOnce(500, 'boom'.repeat(100))
      await fetchJSON('/api/x')
    } catch (e) {
      expect((e as Error).message.length).toBeLessThanOrEqual(220)
    }
  })

  it('503 且活跃任务>0 时转写锁文案', async () => {
    useJobsStore().setActive(2)
    mockFetchOnce(503, 'db locked')
    await expect(fetchJSON('/api/x')).rejects.toThrow('后台任务运行中，数据库写锁占用，稍后自动恢复')
  })

  it('503 但无活跃任务时保持原始错误', async () => {
    mockFetchOnce(503, 'db locked')
    await expect(fetchJSON('/api/x')).rejects.toThrow(/^503 \/api\/x: db locked/)
  })

  it('postJSON 422 detail 数组提取 msg 可读化', async () => {
    mockFetchOnce(422, { detail: [{ msg: 'top_n 必须>0' }, { msg: '日期非法' }] })
    await expect(postJSON('/api/y', {})).rejects.toThrow('422: top_n 必须>0; 日期非法')
  })

  it('postJSON 422 detail 字符串原样', async () => {
    mockFetchOnce(422, { detail: '参数错误' })
    await expect(postJSON('/api/y', {})).rejects.toThrow('422: 参数错误')
  })
})

describe('deleteJSON', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('200 返回 json 且以 DELETE 方法请求', async () => {
    mockFetchOnce(200, { deleted: 1 })
    await expect(deleteJSON('/api/research/backtests/r1')).resolves.toEqual({ deleted: 1 })
    expect(fetch).toHaveBeenCalledWith('/api/research/backtests/r1', { method: 'DELETE' })
  })

  it('404 抛 "status url: body前200字"', async () => {
    mockFetchOnce(404, 'run 不存在: x')
    await expect(deleteJSON('/api/research/backtests/x')).rejects.toThrow(/^404 \/api\/research\/backtests\/x: run 不存在/)
  })

  it('503 且活跃任务>0 时转写锁文案(同 fetchJSON 语义)', async () => {
    useJobsStore().setActive(1)
    mockFetchOnce(503, 'db locked')
    await expect(deleteJSON('/api/x')).rejects.toThrow('后台任务运行中，数据库写锁占用，稍后自动恢复')
  })
})
