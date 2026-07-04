if (process.platform !== 'win32') {
  console.error('\n[GHQ] npm 必须在 Windows 侧执行 (powershell.exe 包装), 当前平台: ' + process.platform)
  console.error('[GHQ] WSL 侧安装会以 linux 二进制毒化 node_modules。见设计 docs/feat/0704-frontend-framework §2.3。\n')
  process.exit(1)
}
