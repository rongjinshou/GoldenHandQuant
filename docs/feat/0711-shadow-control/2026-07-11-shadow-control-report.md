# 影子盘过程受控化（E1/E2）— 完成报告（2026-07-11）

> 设计 SC-1..SC-6 全部落地，TDD 先红后绿，验收链全绿。用户全权委托模式（"按你推荐的来搞，不要问我"），决策自裁留痕于设计文档与 0710 §11。

## 交付物

| 件 | 文件 | 验证 |
|---|---|---|
| 过程仪表 SC-1/SC-2 | `src/application/shadow_audit.py`（台账七状态 + G1-G5 机器判据 + G6/G7 人工项）+ `src/interfaces/cli/commands/shadow_cmd.py` + `quant.py` 注册 | 18+7 用例；生产库实跑：`07-07 MISSED`、有效 `0/6`、下一到期 `07-14`、退出码 1（与体检结论逐位一致） |
| 周二编排器 SC-3 | `src/application/shadow_ops.py`（安全律/QMT 看护重试至 14:30/09:35 开盘等待/链式步骤/收盘链）+ `scripts/shadow_tuesday.py` 薄壳 | 11 用例（含 mode≠dry_run 拒绝、超时 MISSED 告警、步骤失败中断、`--live` 永不出现断言）；WSL 冒烟：周六正确走"非调仓日"退出 0 |
| 通知接线 SC-4 | 复用 notification factory（console 恒有，email/wechat 按 `risk.notification` 配置），走 `NotificationMessage` 通用接口 | 冒烟中 ConsoleNotifier 实际发声 |
| 任务计划模板 SC-5 | `scripts/windows/register_shadow_tasks.ps1`（周二 09:20/15:10，`-Unregister` 卸载） | 静态审查；注册待 Windows 侧执行（interop 恢复后可代跑） |
| 文档收编 SC-6 | runbook §5 收敛为两命令+仪表自查；CLAUDE.md 命令区；debt-ledger §五 E3-E9 挂账；0710 §11 第四轮识别记录 | 交叉引用齐 |

## 验证汇总

- `verify_all`：ruff ✓ / pytest ✓（**1381 passed, 0 failed**，gateway 按设计 WSL skip）/ frontend-fresh ✓ / data-quality ✓ —— **全绿**
- 架构守卫（layer purity）过：两个新 application 模块零顶层 infra import（全注入）

## 07-14（下周二）就绪清单

1. （一次性）Windows 侧注册任务计划：`powershell -ExecutionPolicy Bypass -File scripts\windows\register_shadow_tasks.ps1`；不注册也可手动跑两条命令（runbook §5）
2. 周二早晨唯一人工职责：**打开 QMT 极简端**（09:20 起编排器会提醒并等待，14:30 未开则 MISSED 高声告警）
3. 随时进度：`quant shadow status --gate`（WSL 可跑）

## 遗留

- Windows 真实环境端到端（编排器全链 + 任务计划触发）待 interop 恢复或 07-14 实战首验
- 07-07 脱靶已如实入账（MISSED 计数 1/1 预算已用，G5 语义下再脱一次即判过程失控）
- 下一 chunk：演进点 E3（DD-6 ST 诚实债，输出 G7 判据）
