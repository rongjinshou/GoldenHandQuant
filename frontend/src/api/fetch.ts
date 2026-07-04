import { useJobsStore } from '@/stores/jobs'

/* 旧 static/js/api.js 语义对等(设计 §4.1):
 * - 非 2xx: Error('${status} ${url}: ${body 前 200 字}')
 * - 503 且活跃任务>0: 转写锁文案(DuckDB 单写者的前端表达)
 * - POST 422: detail 数组提取 .msg join '; ' 截 300 字 */

function lockAwareError(status: number, url: string, body: string): Error {
  if (status === 503 && useJobsStore().activeCount > 0) {
    return new Error('后台任务运行中，数据库写锁占用，稍后自动恢复')
  }
  return new Error(`${status} ${url}: ${body.slice(0, 200)}`)
}

export async function fetchJSON<T>(url: string): Promise<T> {
  const resp = await fetch(url)
  if (!resp.ok) {
    const body = await resp.text()
    throw lockAwareError(resp.status, url, body)
  }
  return resp.json() as Promise<T>
}

export async function deleteJSON<T>(url: string): Promise<T> {
  const resp = await fetch(url, { method: 'DELETE' })
  if (!resp.ok) {
    const body = await resp.text()
    throw lockAwareError(resp.status, url, body)
  }
  return resp.json() as Promise<T>
}

export async function postJSON<T>(url: string, payload?: unknown): Promise<T> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  })
  const body: unknown = await resp.json().catch(() => ({}))
  if (!resp.ok) {
    if (resp.status === 503 && useJobsStore().activeCount > 0) {
      throw new Error('后台任务运行中，数据库写锁占用，稍后自动恢复')
    }
    const detail = (body as { detail?: unknown }).detail
    let msg: string
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail)) {
      msg = detail
        .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
        .join('; ')
        .slice(0, 300)
    } else {
      msg = JSON.stringify(detail ?? body).slice(0, 300)
    }
    throw new Error(`${resp.status}: ${msg}`)
  }
  return body as T
}
