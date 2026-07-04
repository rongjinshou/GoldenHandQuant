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

export const NAV_ITEMS = [
  { name: 'overview', label: '总览' },
  { name: 'backtests', label: '回测' },
  { name: 'explorer', label: '行情' },
  { name: 'verdicts', label: '判决' },
  { name: 'live', label: '实盘' },
  { name: 'jobs', label: '任务' },
] as const
