import { useJobsStore } from '@/stores/jobs'

/* HTTP 错误分类中文化(设计 §10):
 * - 404 记录不存在 / 422 参数校验失败(+ FastAPI detail) / 5xx 服务内部错误 / 503 服务暂时不可用
 * - 网络错误(fetch 抛 TypeError): 无法连接 dashboard 服务
 * - 503 且活跃任务>0: 转 DuckDB 写锁友好文案(样板保留)
 * - 原始技术串始终保留(消息尾括号 + err.technical 附加字段, 供"技术详情"展开) */

export interface ApiError extends Error {
  status: number
  technical?: string
  detail?: string
}

/** 从响应体尽量提取 FastAPI detail: 字符串原样; 数组取各项 .msg join; 其他 JSON 化。非 JSON 返回 undefined。 */
function extractDetail(body: string): string | undefined {
  let parsed: unknown
  try {
    parsed = JSON.parse(body)
  } catch {
    return undefined
  }
  const detail = (parsed as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
      .join('; ')
      .slice(0, 300)
  }
  if (detail != null) return JSON.stringify(detail).slice(0, 300)
  return undefined
}

/** status → 三段式中文(纯函数, 便于单测)。原始技术串保留在消息尾括号与 err.technical。 */
export function humanizeError(status: number, url: string, body: string): ApiError {
  const detail = extractDetail(body)
  const technical = `${status} ${url}: ${body.slice(0, 200)}`
  let lead: string
  if (status === 404) {
    lead = '记录不存在'
  } else if (status === 422) {
    lead = detail ? `参数校验失败：${detail}` : '参数校验失败'
  } else if (status === 503) {
    lead = '服务暂时不可用，请稍后重试'
  } else if (status >= 500) {
    lead = '服务内部错误'
  } else {
    lead = detail ? `请求失败：${detail}` : `请求失败（${status}）`
  }
  const err = new Error(`${lead}（${technical}）`) as ApiError
  err.status = status
  err.technical = technical
  if (detail) err.detail = detail
  return err
}

/** fetch 本身抛错(网络不可达/被断开): 统一提示确认服务已启动。 */
export function networkError(cause?: unknown): ApiError {
  const err = new Error('无法连接 dashboard 服务，确认已启动') as ApiError
  err.status = 0
  err.technical = cause instanceof Error ? `${cause.name}: ${cause.message}` : String(cause)
  return err
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError'
}

function lockAwareError(status: number, url: string, body: string): Error {
  // 503 写锁友好文案: 后台任务占用 DuckDB 单写者时的前端表达(样板保留)
  if (status === 503 && useJobsStore().activeCount > 0) {
    return new Error('后台任务运行中，数据库写锁占用，稍后自动恢复')
  }
  return humanizeError(status, url, body)
}

export async function fetchJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  let resp: Response
  try {
    resp = signal ? await fetch(url, { signal }) : await fetch(url)
  } catch (e) {
    if (isAbort(e)) throw e // 主动取消, 原样上抛
    throw networkError(e)
  }
  if (!resp.ok) {
    const body = await resp.text()
    throw lockAwareError(resp.status, url, body)
  }
  return resp.json() as Promise<T>
}

export async function deleteJSON<T>(url: string, signal?: AbortSignal): Promise<T> {
  const init: RequestInit = { method: 'DELETE' }
  if (signal) init.signal = signal
  let resp: Response
  try {
    resp = await fetch(url, init)
  } catch (e) {
    if (isAbort(e)) throw e
    throw networkError(e)
  }
  if (!resp.ok) {
    const body = await resp.text()
    throw lockAwareError(resp.status, url, body)
  }
  return resp.json() as Promise<T>
}

export async function postJSON<T>(url: string, payload?: unknown, signal?: AbortSignal): Promise<T> {
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  }
  if (signal) init.signal = signal
  let resp: Response
  try {
    resp = await fetch(url, init)
  } catch (e) {
    if (isAbort(e)) throw e
    throw networkError(e)
  }
  if (!resp.ok) {
    const body = await resp.text()
    throw lockAwareError(resp.status, url, body)
  }
  return (await resp.json().catch(() => ({}))) as T
}
