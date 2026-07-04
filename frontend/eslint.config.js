// ESLint v10 flat config — Vue 3 + TypeScript
// 用 typescript-eslint(flat 助手) + eslint-plugin-vue flat/recommended;
// no-undef 由 TS 负责(tseslint recommended 已关), 故不需 @eslint/js/globals。
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist/', 'node_modules/', '**/*.d.ts'] },
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
  },
  {
    rules: {
      // 页面组件名单词(Overview/Live/Jobs...) — 关多词强制
      'vue/multi-word-component-names': 'off',
      // 格式类交给编辑器/prettier, 不做 lint 噪音
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/multiline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      // 图表 option/echarts 动态结构偶需 any — 降为 warn 而非拦截
      '@typescript-eslint/no-explicit-any': 'warn',
      // 允许 _ 前缀有意未用
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
)
