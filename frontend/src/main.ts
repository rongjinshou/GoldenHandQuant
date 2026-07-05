import '@fontsource/poppins/400.css'
import '@fontsource/poppins/600.css'
import '@fontsource/poppins/700.css'
import '@fontsource/lora/400.css'
import '@fontsource/lora/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/600.css'
import '@/styles/tokens.css'
import '@/styles/base.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import { loadGates } from './pages/verdicts/gates'

// D2: 启动时预加载闸门阈值（失败有回退，不阻塞渲染）
loadGates()

createApp(App).use(createPinia()).use(router).mount('#app')
