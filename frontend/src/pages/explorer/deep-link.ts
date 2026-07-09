/* 行情页 P7 URL 深链 — ?symbols= query ↔ 标的列表的序列化/解析纯函数(设计 §12 P7)。
 *
 * 单一职责: 只做「逗号分隔字符串 ↔ 合法标的有序列表」的双向转换与规范化, 不碰路由/响应式。
 * Explorer.vue 用它把「当前加载的标的组合」写进 ?symbols=、并在挂载/前进后退时从 URL 恢复。
 *
 * 规范化(大写 + 去重 + 保序 + 仅留合法代码)是防「URL↔状态同步死循环」的地基: 只要
 * parse/toQuery 对同一语义标的集合产出稳定的规范形, 同步侧就能靠「规范形相等 → 不重复写」
 * 收敛(见 Explorer.vue applySymbolsFromQuery / syncQueryFromLoaded 的幂等判等)。
 *
 * 标的格式刻意本地内联(与 backtests/useSymbolChips 的 SYMBOL_RE 同口径, 6 位数字 + .SH/SZ/BJ),
 * 不跨文件 import —— 保持本模块自足, 不与他人所有的 composable 产生编译期耦合。 */

const SYMBOL_RE = /^\d{6}\.(SH|SZ|BJ)$/

/**
 * 解析 ?symbols= 的原始 query 值 → 合法标的有序列表。
 *
 * 健壮性保证(绝不抛):
 * - 非字符串输入(vue-router 的 query 值可能是 `string | null | (string|null)[] | undefined`,
 *   重复 key 会给数组) → 空数组;
 * - 逗号切分后逐 token trim + 大写, 丢弃空 token 与不合法代码;
 * - 大小写归一后去重, 保留首次出现顺序。
 */
export function parseSymbolsQuery(raw: unknown): string[] {
  if (typeof raw !== 'string') return []
  const out: string[] = []
  const seen = new Set<string>()
  for (const token of raw.split(',')) {
    const sym = token.trim().toUpperCase()
    if (!sym || seen.has(sym) || !SYMBOL_RE.test(sym)) continue
    seen.add(sym)
    out.push(sym)
  }
  return out
}

/**
 * 标的列表 → ?symbols= query 值(逗号分隔)。
 *
 * 经 parseSymbolsQuery 再规范化一遍(大写/去重/丢非法/保序), 保证写入 URL 的形态始终规范,
 * 且与解析口径一致 —— `symbolsToQuery(parseSymbolsQuery(x))` 天然稳定。空列表 → 空串,
 * 调用方据此决定是删除 query key 还是写入。
 */
export function symbolsToQuery(list: readonly string[]): string {
  return parseSymbolsQuery(list.join(',')).join(',')
}
