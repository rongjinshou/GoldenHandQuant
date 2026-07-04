import { defineStore } from 'pinia'
import { ref } from 'vue'

/* 活跃任务计数 — 旧版 window.__activeJobs 的正经化(设计 §4.1)。
 * 由任务列表/JobCard 轮询回填, 不自轮询; fetch 层 503 条件友好化消费它。 */
export const useJobsStore = defineStore('jobs', () => {
  const activeCount = ref(0)

  function setActive(n: number): void {
    activeCount.value = n
  }

  return { activeCount, setActive }
})
