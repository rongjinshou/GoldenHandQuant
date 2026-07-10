<script setup lang="ts">
import { NConfigProvider, NMessageProvider, NNotificationProvider, zhCN, dateZhCN } from 'naive-ui'
import { onMounted, ref } from 'vue'

import AppBadge from '@/components/AppBadge.vue'
import HotkeyHelp from '@/components/HotkeyHelp.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { usePageHotkeys } from '@/composables/usePageHotkeys'
import { NAV_ITEMS } from '@/router'
import { useJobsStore } from '@/stores/jobs'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const jobsStore = useJobsStore()

// R2-D 专家效率: 数字键 1-6 直达页签, '?' 唤起快捷键帮助(输入框/修饰键/输入法合成中自动让路)
const showHotkeyHelp = ref(false)
usePageHotkeys(() => {
  showHotkeyHelp.value = true
})

// 任务徽章全局鲜活: App 级轮询回填 activeCount, 使任意页(非仅任务页)徽章与 503 写锁文案随任务变化(设计 §10)
onMounted(() => jobsStore.startGlobalPolling())
</script>

<template>
  <NConfigProvider
    :theme="themeStore.naiveTheme"
    :theme-overrides="themeStore.naiveOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <NNotificationProvider :max="3">
    <NMessageProvider>
    <div class="shell" data-testid="app-shell">
      <header class="topbar">
        <h1 class="brand">GoldenHandQuant</h1>
        <nav class="nav" aria-label="主导航">
          <RouterLink
            v-for="(item, i) in NAV_ITEMS"
            :key="item.name"
            :to="{ name: item.name }"
            class="nav-link"
            :data-testid="`nav-${item.name}`"
            :title="`${item.label} (${i + 1})`"
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

      <HotkeyHelp v-model:show="showHotkeyHelp" />
    </div>
    </NMessageProvider>
    </NNotificationProvider>
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
  flex-wrap: wrap;           /* 窄屏兜底: 放不下时 nav/主题钮换行, 不横向溢出/遮挡 */
  gap: var(--gap-lg);
  row-gap: var(--space-2);   /* 换行后行间收紧, sticky 顶栏不虚高(宽屏不换行时无效) */
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
  flex-wrap: wrap;   /* 窄屏兜底: nav-link 内部换行, 收缩 nav 最小宽度, 顶栏不被撑破 */
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
