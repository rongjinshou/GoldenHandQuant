import { createRouter, createWebHashHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: { name: 'overview' } },
    { path: '/overview', name: 'overview', component: () => import('@/pages/Overview.vue') },
    { path: '/backtests', name: 'backtests', component: () => import('@/pages/Backtests.vue') },
    { path: '/explorer', name: 'explorer', component: () => import('@/pages/Explorer.vue') },
    { path: '/verdicts', name: 'verdicts', component: () => import('@/pages/Verdicts.vue') },
    { path: '/live/:view?', name: 'live', component: () => import('@/pages/Live.vue') },
    { path: '/jobs', name: 'jobs', component: () => import('@/pages/Jobs.vue') },
    // 影子盘页为阶段 2 占位(设计 §6): 路由先重定向, 菜单不显示
    { path: '/shadow', redirect: { name: 'overview' } },
  ],
})

/* 顺序按流水线心智: 数据→判决→回测→实盘 (与总览页 PipelineMap 一致) */
export const NAV_ITEMS = [
  { name: 'overview', label: '总览' },
  { name: 'explorer', label: '行情' },
  { name: 'verdicts', label: '判决' },
  { name: 'backtests', label: '回测' },
  { name: 'live', label: '实盘' },
  { name: 'jobs', label: '任务' },
] as const

/** 路由名 → 浏览器标签标题(纯函数, 便于单测); 未知/空名退化为纯品牌名。 */
export function pageTitle(name: unknown): string {
  const label = NAV_ITEMS.find((n) => n.name === name)?.label
  return label ? `${label} · GoldenHandQuant` : 'GoldenHandQuant'
}

// document.title 随路由更新(设计 §8 无障碍/可定位)
router.afterEach((to) => {
  document.title = pageTitle(to.name)
})
