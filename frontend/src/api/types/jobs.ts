/* Job 族类型 — 对齐 src/infrastructure/jobs/job_manager.py Job.to_dict() */

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'

export interface Job {
  job_id: string
  job_type: string
  params: Record<string, unknown>
  status: JobStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  return_code: number | null
  log_path: string
  log_tail?: string[]
}
