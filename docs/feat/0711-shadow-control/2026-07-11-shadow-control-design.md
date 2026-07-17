# 影子盘过程受控化 + 过闸判据（演进点 E1/E2）设计

| 项 | 值 |
|---|---|
| **状态** | 已定稿（用户全权委托："按你推荐的来搞，不要问我"，决策自裁留痕） |
| **创建日期** | 2026-07-11 |
| **前置** | 0626 阶段 1 影子盘已落地（signal_snapshots/一致性比对/纸面净值三件套可用）；0710 六西格玛 §11 第四轮识别出演进点清单，用户裁定主攻「通往小资金实盘」+ 路线方案甲 |
| **动机（Measure）** | 真单开闸唯一依赖「每周二一次、事后不可补采」的采样事件；该过程 100% 人肉、零控制手段，**07-07 首个正式采样已脱靶**（实测脱靶率 1/1）。错过一次 = 真单推迟一周 |

---

## 一、目标与范围

把「每周二影子盘采样」从人肉记得跑四条命令，变成**受控过程**：

1. **单命令编排**：`scripts/shadow_tuesday.py` 一条命令跑完 runbook §5 全链（上午段采样 / 收盘段比对+净值）。
2. **QMT 在线看护**：探测不在线 → 通知提醒 → 限时重试 → 超时按 MISSED 高声告警。人的职责收敛为一步：周二开 QMT 极简端（硬约束，不可自动化）。
3. **过程仪表**：`quant shadow status` 随时回答「攒到第几个样本 / 哪周脱靶 / 下一采样日 / 离过闸还差什么」。
4. **过闸判据固化**（E2）：何谓「样本攒够可开真单 Spec」，机器可判，判据即规格。

**路线裁定（方案甲·半自动看护）**：乙案（全自动含 QMT 自动登录）否决——凭据安全风险 + Windows 计划任务会话隔离脆 + dry-run 阶段收益低；丙案（纯手动 + 日历提醒）否决——对已实测脱靶的现状只做微调，控制力不足。

**非目标**：QMT 自动登录；补采语义（live 快照错过即永失，MISSED 就是 MISSED，不造假数据）；驾驶舱可视化（E7，留给前端线）；`frontend/` 任何改动；真单路径任何改动（编排器硬拒 `mode: live`）。

## 二、设计决策（SC-*，避免与台账 DD-* 混淆）

### SC-1 过程仪表 `quant shadow status`

- 新 `src/application/shadow_audit.py`（`ShadowAuditService`，纯逻辑）+ `src/interfaces/cli/commands/shadow_cmd.py`（装配与呈现）。
- **周二台账**：自 **2026-07-07**（阶段 1 计划首采日）起逐周二判定，七种状态：
  - `VALID`：当日有 `mode=dry_run` 的 signal_snapshot，且 `data/shadow_checks/<D>.json` 存在且 `consistent=true`；
  - `UNCHECKED`：有快照、无比对文件（比对输入是落库快照，离线随时可补跑——提示补跑命令）；
  - `DIVERGED`：有快照、比对 `consistent=false`（立案信号）；
  - `MISSED`：无快照且 D 是交易日（bars 当日有行）；
  - `EXEMPT`：无快照且 D 非交易日（bars 当日 0 行，且 D ≤ bars 已知最大日——节假日周二，白名单情形）；
  - `UNKNOWN`：无快照且 D > bars 已知最大日（数据未刷新，无法判交易日——三值诚实语义，提示先 `data refresh`，不猜）；
  - `PENDING`：D > today（未来）。
- 显示：台账表 + 有效样本 n/6 + MISSED 计数 + 下一到期采样日。
- **退出码**（对准"当前失控"而非历史记录，避免单次历史脱靶让仪表永远报警）：以下任一 → 1，否则 0：
  ① **最近一个已到期采样日**为 MISSED（过程正脱轨）；② MISSED 累计 ≥ 2（G5 失控线）；
  ③ 存在 DIVERGED；④ 存在过去周二 UNKNOWN（数据未刷可能掩盖脱靶，提示 refresh）。
  历史性单次 MISSED（如 07-07）在后续采样恢复后不再触发非零退出，但台账与 gate 的 MISSED 计数永久如实保留。
- 今日恰为周二且尚无快照 → 记 `PENDING`（采样窗口进行中，不提前判 MISSED），下一到期日 = 今日。
- 分层：服务只依赖注入的 callables（快照日集合 / 交易日三值查询 / 比对结果加载 / 纸面净值 run 日期），CLI 侧接 `TradingStore`/`MarketDataStore`/文件系统。application 顶层不 import infrastructure（架构守卫已在门禁）。

### SC-2 过闸判据 `quant shadow status --gate`（E2 tollgate）

机器判据（全 PASS → 提示「可开真单 Spec（E5）」）：

| # | 判据 | 阈值依据 |
|---|---|---|
| G1 | 有效样本（VALID）≥ **6** 个调仓周二 | 阶段 1 report「攒 4-8 周」取中偏保守；EXEMPT 不计不罚 |
| G2 | DIVERGED = 0 | 未解释分歧存在期间 gate 恒 FAIL；分歧样本修复并解释后**不回转** VALID，后续样本继续累计 |
| G3 | 全部采样 `data_health = ok` | 数据故障周期不得计入证据 |
| G4 | 纸面净值 `SHADOW-PAPER-*` 周度入库无断档（入库数 ≥ 有效样本数） | 0704 DD-2 的画像基线不断线 |
| G5 | MISSED 累计 ≤ 1 | ≥2 = 采样过程本身失控，须先复盘过程再人工确认继续 |

人工判据（`--gate` 列为清单提示，以债务台账核销状态为准，不自动判）：

- G6：M4 成交回报回填 + 断线重连，QMT 实环境联测完成（E4）；
- G7：DD-6 ST 诚实债重验后 F01 gate 仍 PASS（E3——若重验 FAIL 则不上钱，回研究阶段，这正是把它排进等待期的理由）。

### SC-3 周二编排器

- `src/application/shadow_ops.py`（`ShadowTuesdayOrchestrator`，注入 step-runner / QMT probe / clock / notifier / sleep，可测）+ `scripts/shadow_tuesday.py` 薄壳装配（Windows python 运行）。
- **安全律**：启动即读 trading.yaml，`auto_trade.mode != dry_run` → 拒绝运行（本工具只服务影子盘）；子命令永不携带 `--live`。
- **上午段**（默认；`--morning` 显式）：
  1. QMT probe（`xtdata.get_instrument_detail('000001.SZ')` 非空，与 `ensure_ready` 同口径）；失败 → 通知「请开 QMT 极简端」→ 每 60s 重试至 deadline（默认 **14:30**）→ 超时 → MISSED 告警 + exit 1。
  0. **开盘等待**：任务计划 09:20 拉起（给人 15 分钟开 QMT 的提醒窗口），但链条步骤 2-4 须等到 ≥ **09:35**（开盘价定型，阶段 1 比对口径）才执行——probe/提醒先行，采样动作后置。
  2. `quant data refresh`（窗口 today-14d..today，只刷缺口幂等）+ `scripts/fetch_index_bars.py`（指数不在 refresh 宇宙）。
  3. `quant auto-trade --once --enable`（dry_run）。
  4. 读回当日 signal_snapshot 确认落库 → 成功通知（含 gate_passed / 宇宙规模 / staleness）。
- **收盘段**（`--post-close`）：refresh + index → `shadow_consistency_check` → `shadow_paper_equity` → `shadow status` 摘要 → 通知（含 diff 结论）。
- 非周二运行：提示非调仓日，exit 0（`--force` 越过，供冒烟）。任一步失败：高声通知 + 非零退出，步骤输出尾部并入通知。
- deadline 14:30 依据：采样须在收盘前留出撮合闸时段（盘外跑会得到「非连续竞价时段」拒单——链路通但样本质量降级）；09:35 后开盘价已定型即可比（阶段 1 裁定），越早越好，14:30 是底线。

### SC-4 通知接线

- 复用 `infrastructure/notification` factory（console 恒有；email/wechat 按 trading.yaml `risk.notification` 既有配置节）。
- 走 `INotificationGateway.send(NotificationMessage)` 通用接口，不占用 RiskEvent 风控枚举。
- 通知失败不阻断流程（与 EmailNotifier 既有裁定一致），但记入编排器日志。

### SC-5 Windows 任务计划模板

- `scripts/windows/register_shadow_tasks.ps1`：注册两个**仅周二**任务（09:20 上午段 / 15:10 收盘段），`-Unregister` 卸载，顶部注释即使用说明。
- 用户在 Windows 侧执行一次（或 WSL interop 恢复后代跑）。未注册也不失控：runbook 收敛为两条命令，`shadow status` 兜底暴露脱靶。

### SC-6 文档收编

- morning-runbook §5：四命令块 → `shadow_tuesday.py` 两条 + `shadow status` 自查。
- CLAUDE.md 常用命令区补影子盘两条。
- debt-ledger：E3-E9 演进点挂账留痕（引用 0710 §11 清单）。

## 三、07-07 脱靶的处置

诚实记 `MISSED`（台账首行可见），不补造——当日 live 快照已不可重建，离线重放两侧同源等于自证。07-04（周六）冒烟不在周二全集，自然不计。有效样本从 07-14 起累计。

## 四、验收标准

1. TDD 先红后绿：`ShadowAuditService` 七状态判定与 gate 判据；编排器时序（probe 重试 / deadline 超时告警 / 步骤失败中断 / 非周二退出 / mode 安全律 / 收盘段链）。
2. ruff 全仓 0；架构守卫（layer purity）过。
3. WSL 实跑：`quant shadow status` 显示 07-07 `MISSED`、下一到期 07-14、有效 0/6、退出码 1。
4. `verify_all` WSL 部分全绿（frontend-fresh 拦截在途前端改动属正确行为，除外）。
5. Windows 侧真跑 + 任务注册：待 interop 恢复或 07-14 晨由用户执行（用户唯一职责=开 QMT）。
6. 文档全落：本设计 + plan + runbook + CLAUDE.md + debt-ledger + 0710 §11。

## 五、风险与诚实校准

- 编排器**无法保证** QMT 被打开——方案甲的边界。它保证的是「没开会被大声告知 + 脱靶被如实记录」，不是「不会脱靶」。彻底消除人依赖属 E8（全自动）议题。
- `shadow status` 的交易日判定依赖 bars 刷新进度，未知区如实报 `UNKNOWN` 而非猜测——与 T5 交易日历三值语义一致，不引入第二套日历。
- 通知渠道当前大概率仅 console（email/wechat 未配置则静默缺席）；ps1 注册的计划任务窗口输出用户可能看不到——因此 MISSED 的最终防线是 `shadow status` 的退出码与台账，通知只是加速器。
