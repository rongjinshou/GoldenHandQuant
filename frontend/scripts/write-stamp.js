// build 后往产物目录写时间戳, 供 scripts/check_frontend_fresh.py 校验源码/产物漂移(设计 DD-4)
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const out = fileURLToPath(new URL('../../src/interfaces/api/static/.build-stamp', import.meta.url))
writeFileSync(out, new Date().toISOString() + '\n')
console.log('[stamp] ' + out)
