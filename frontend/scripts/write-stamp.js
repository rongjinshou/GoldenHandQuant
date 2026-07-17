// build 后往产物目录写构建戳, 供 scripts/check_frontend_fresh.py 校验源码/产物漂移(设计 DD-4)。
// 2026-07-10 六西格玛 D1: 由纯时间戳升级为「源码内容哈希」— git checkout 不保留
// mtime, 时间比对在检出后必然误报; 哈希跨 clone/checkout 稳定。
// 哈希规格(与 check_frontend_fresh.py 的 source_hash 严格一致):
//   sha256( 按相对 POSIX 路径字典序, 逐文件 update(relpath + '\0' + bytes + '\0') )
//   文件集 = frontend/src/** + index.html + vite.config.ts + package.json
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const out = fileURLToPath(new URL('../../src/interfaces/api/static/.build-stamp', import.meta.url))

function walk(dir) {
  const files = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) files.push(...walk(p))
    else if (st.isFile()) files.push(p)
  }
  return files
}

function sourceFiles() {
  const candidates = ['src', 'index.html', 'vite.config.ts', 'package.json']
  const files = []
  for (const c of candidates) {
    const p = join(frontendRoot, c)
    let st
    try { st = statSync(p) } catch { continue }
    if (st.isDirectory()) files.push(...walk(p))
    else files.push(p)
  }
  return files
}

function sourceHash() {
  const h = createHash('sha256')
  const entries = sourceFiles()
    .map((p) => [relative(frontendRoot, p).split('\\').join('/'), p])
    .sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0))
  for (const [rel, p] of entries) {
    h.update(Buffer.from(rel, 'utf-8'))
    h.update(Buffer.from([0]))
    h.update(readFileSync(p))
    h.update(Buffer.from([0]))
  }
  return 'sha256:' + h.digest('hex')
}

writeFileSync(out, JSON.stringify({
  builtAt: new Date().toISOString(),
  srcHash: sourceHash(),
}) + '\n')
console.log('[stamp] ' + out)
