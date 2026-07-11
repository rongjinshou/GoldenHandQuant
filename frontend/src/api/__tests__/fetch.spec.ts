import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useJobsStore } from '@/stores/jobs'

import { deleteJSON, fetchJSON, humanizeError, networkError, postJSON } from '../fetch'

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

describe('humanizeError(纯函数, status→中文 lead)', () => {
  it('404 → 记录不存在; 技术串只进 err.technical 不进 message(R6-02)', () => {
    const e = humanizeError(404, '/api/x', 'run 不存在')
    expect(e.message).toBe('记录不存在')
    expect(e.message).not.toContain('404 /api/x')
    expect(e.status).toBe(404)
    expect(e.technical).toContain('404 /api/x: run 不存在')
  })
  it('422 提取 FastAPI detail 数组', () => {
    const e = humanizeError(422, '/api/y', JSON.stringify({ detail: [{ msg: 'top_n 必须>0' }, { msg: '日期非法' }] }))
    expect(e.message).toContain('参数校验失败')
    expect(e.message).toContain('top_n 必须>0; 日期非法')
    expect(e.detail).toBe('top_n 必须>0; 日期非法')
  })
  it('422 detail 字符串原样', () => {
    const e = humanizeError(422, '/api/y', JSON.stringify({ detail: '参数错误' }))
    expect(e.message).toContain('参数校验失败：参数错误')
  })
  it('500 → 服务内部错误', () => {
    expect(humanizeError(500, '/api/x', 'boom').message).toContain('服务内部错误')
  })
  it('503 → 服务暂时不可用', () => {
    expect(humanizeError(503, '/api/x', 'busy').message).toContain('服务暂时不可用')
  })
  it('其他 4xx → 请求失败(带 status)', () => {
    expect(humanizeError(409, '/api/x', 'conflict').message).toContain('请求失败')
  })
})

describe('networkError', () => {
  it('TypeError → 无法连接提示', () => {
    const e = networkError(new TypeError('Failed to fetch'))
    expect(e.message).toContain('无法连接 dashboard 服务')
    expect(e.status).toBe(0)
    expect(e.technical).toContain('TypeError')
  })
})

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

  it('500 → 服务内部错误(技术串在 technical 字段, 不污染 message)', async () => {
    mockFetchOnce(500, 'boom'.repeat(100))
    await expect(fetchJSON('/api/x')).rejects.toThrow('服务内部错误')
    mockFetchOnce(500, 'boom'.repeat(100))
    await expect(fetchJSON('/api/x')).rejects.toMatchObject({
      message: expect.not.stringContaining('500 /api/x'),
      technical: expect.stringContaining('500 /api/x: boom'),
    })
  })

  it('网络错误(fetch 抛 TypeError) → 无法连接提示', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(fetchJSON('/api/x')).rejects.toThrow('无法连接 dashboard 服务，确认已启动')
  })

  it('503 且活跃任务>0 时转写锁文案', async () => {
    useJobsStore().setActive(2)
    mockFetchOnce(503, 'db locked')
    await expect(fetchJSON('/api/x')).rejects.toThrow('后台任务运行中，数据库写锁占用，稍后自动恢复')
  })

  it('503 但无活跃任务 → 服务暂时不可用(原始串仅在 technical)', async () => {
    mockFetchOnce(503, 'db locked')
    await expect(fetchJSON('/api/x')).rejects.toThrow('服务暂时不可用')
    mockFetchOnce(503, 'db locked')
    await expect(fetchJSON('/api/x')).rejects.toMatchObject({
      technical: expect.stringContaining('503 /api/x: db locked'),
    })
  })

  it('postJSON 422 detail 数组提取 msg 可读化', async () => {
    mockFetchOnce(422, { detail: [{ msg: 'top_n 必须>0' }, { msg: '日期非法' }] })
    await expect(postJSON('/api/y', {})).rejects.toThrow('参数校验失败')
    mockFetchOnce(422, { detail: [{ msg: 'top_n 必须>0' }, { msg: '日期非法' }] })
    await expect(postJSON('/api/y', {})).rejects.toThrow('top_n 必须>0; 日期非法')
  })

  it('postJSON 422 detail 字符串原样', async () => {
    mockFetchOnce(422, { detail: '参数错误' })
    await expect(postJSON('/api/y', {})).rejects.toThrow('参数校验失败：参数错误')
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

  it('404 → 记录不存在(原始串仅在 technical)', async () => {
    mockFetchOnce(404, 'run 不存在: x')
    await expect(deleteJSON('/api/research/backtests/x')).rejects.toThrow('记录不存在')
    mockFetchOnce(404, 'run 不存在: x')
    await expect(deleteJSON('/api/research/backtests/x')).rejects.toMatchObject({
      technical: expect.stringContaining('404 /api/research/backtests/x: run 不存在'),
    })
  })

  it('503 且活跃任务>0 时转写锁文案(同 fetchJSON 语义)', async () => {
    useJobsStore().setActive(1)
    mockFetchOnce(503, 'db locked')
    await expect(deleteJSON('/api/x')).rejects.toThrow('后台任务运行中，数据库写锁占用，稍后自动恢复')
  })
})
