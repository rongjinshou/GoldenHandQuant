/* Live 页面向机器的英文枚举 → 中文 label(纯函数, 未知值一律回退原值)。
 * 页面内映射, 不入 glossary.ts —— 术语条走 GlossaryTip, 此处只做机读枚举本地化。
 * 取值权威来源:
 *   审计动作 = application/auto_trade_app.py 的 action=... 调用点;
 *   执行状态 = pages/live/logic.ts STATUS_BADGE 键(对等后端 execution.status);
 *   方向/开关 = ExecutionRecord.direction / AutoTradeConfig.enabled。 */

/* 审计动作(snake_case 机读码) → 中文。缺失回退原码, 前端不因后端新增动作而崩。 */
const AUDIT_ACTION_LABELS: Record<string, string> = {
  cycle_start: '循环开始',
  cycle_end: '循环结束',
  place_order: '下单',
  place_order_failed: '下单失败',
  reject_order: '拒单',
  execute_failed: '执行失败',
  cancel_order: '撤单',
}

export function auditActionLabel(code: string): string {
  return AUDIT_ACTION_LABELS[code] ?? code
}

/* 执行/订单状态(UPPER_SNAKE) → 中文。与 statusBadge(语义色)分工: 此处只管文案。 */
const EXEC_STATUS_LABELS: Record<string, string> = {
  DRY_RUN: '纸面',
  SUBMITTED: '已提交',
  FILLED: '已成交',
  PARTIAL: '部分成交',
  ALIVE: '挂单中',
  TIMEOUT_CANCELED: '超时已撤',
  TIMEOUT_UNCANCELED: '超时未撤',
  CANCELED: '已撤单',
  REJECTED: '已拒单',
  FAILED: '失败',
}

export function execStatusLabel(code: string): string {
  return EXEC_STATUS_LABELS[code] ?? code
}

/* 买卖方向 → 中文单字(A股买红卖绿的色由调用方另给); 未知方向回退原值。 */
export function directionLabel(code: string): string {
  return code === 'BUY' ? '买' : code === 'SELL' ? '卖' : code
}

/* auto-trade 开关: true→已启用 / 其余(false/缺省)→已停用(对等旧 'enabled'/'disabled')。 */
export function enabledLabel(enabled: boolean | null | undefined): string {
  return enabled ? '已启用' : '已停用'
}
