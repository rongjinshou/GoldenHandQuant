<script setup lang="ts">
import { NConfigProvider, zhCN, dateZhCN } from 'naive-ui'

import AppBadge from '@/components/AppBadge.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { NAV_ITEMS } from '@/router'
import { useJobsStore } from '@/stores/jobs'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const jobsStore = useJobsStore()
</script>

<template>
  <NConfigProvider
    :theme="themeStore.naiveTheme"
    :theme-overrides="themeStore.naiveOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <div class="shell" data-testid="app-shell">
      <header class="topbar">
        <h1 class="brand">GoldenHandQuant</h1>
        <nav class="nav" aria-label="主导航">
          <RouterLink
            v-for="item in NAV_ITEMS"
            :key="item.name"
            :to="{ name: item.name }"
            class="nav-link"
            :data-testid="`nav-${item.name}`"
          >
            {{ item.label }}
            <AppBadge
              v-if="item.name === 'jobs' && jobsStore.activeCount > 0"
              kind="accent"
              size="sm"
              class="num nav-badge"
            >{{ jobsStore.activeCount }}</AppBadge>
          </RouterLink>
        </nav>
        <ThemeToggle />
      </header>

      <main class="content">
        <RouterView v-slot="{ Component }">
          <Transition name="page">
            <component :is="Component" :key="($route.name as string) ?? ''" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </NConfigProvider>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.topbar {
  align-items: center;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: var(--gap-lg);
  padding: 12px var(--gap-lg);
  position: sticky;
  top: 0;
  z-index: 100;
  transition: background var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out);
}

.brand {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin: 0;
  white-space: nowrap;
}

.nav {
  display: flex;
  flex: 1;
  gap: 4px;
}

.nav-link {
  border-radius: var(--radius-sm);
  color: var(--text-2);
  font-family: var(--font-display);
  font-size: 14px;
  padding: 7px 14px;
  position: relative;
  transition: color var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out);
}

.nav-link:hover {
  background: var(--accent-soft);
  color: var(--text);
  opacity: 1;
}

/* 活跃态: accent 下划线滑入 */
.nav-link::after {
  background: var(--accent);
  border-radius: 1px;
  bottom: 2px;
  content: '';
  height: 2px;
  left: 50%;
  position: absolute;
  transform: translateX(-50%) scaleX(0);
  transition: transform var(--dur-base) var(--ease-out);
  width: calc(100% - 24px);
}

.nav-link.router-link-active {
  color: var(--accent);
}

.nav-link.router-link-active::after {
  transform: translateX(-50%) scaleX(1);
}

.nav-badge {
  margin-left: 6px;
}

.content {
  flex: 1;
  margin: 0 auto;
  max-width: 1280px;
  padding: var(--gap-lg);
  width: 100%;
}

/* 路由切换过渡: enter-only 快速淡入(离场瞬时) — 恢复即时切页手感, 去掉位移settle感 */
.page-enter-active {
  transition: opacity var(--dur-fast) var(--ease-out);
}

.page-enter-from {
  opacity: 0;
}
</style>
