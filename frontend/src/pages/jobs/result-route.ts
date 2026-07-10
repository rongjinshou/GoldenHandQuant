/* 任务行「查看结果」落点判定(纯函数) — 仅 succeeded 且有结果页的类型给链接:
 * backtest→回测页 / factor_test→判决页。不带 run 参数: 两页默认落最新一轮
 * = 刚完成那轮(批三深链逻辑已保证)。ml_train/ml_evaluate/data_refresh 无独立
 * 结果页, 与非成功态/未知类型一律 null(不渲染链接)。 */

const RESULT_PAGE: Record<string, string> = {
  backtest: 'backtests',
  factor_test: 'verdicts',
}

export function resultRoute(jobType: string, status: string): { name: string } | null {
  if (status !== 'succeeded') return null
  const name = RESULT_PAGE[jobType]
  return name ? { name } : null
}
