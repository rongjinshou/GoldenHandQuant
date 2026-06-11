# 全闭环 v1 · 晨间运行手册（2026-06-12 起）

整夜委托交付的端到端自动交易已全部落地并测试通过（全量 pytest 绿 + ruff 干净）。
本手册是晨间补审与首次盘中运行的操作脚本。**默认一切 dry-run，真金白银只有第 4 步且明确不建议现在做。**

## 0. 前置检查（约 2 分钟）

```bash
WIN_PY=/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe

# QMT 客户端以极简模式登录（昨日 14:00 冒烟时交易端未在线, connect != 0）
# 数据新鲜度（可选）
$WIN_PY -m src.interfaces.cli.quant data status
```

## 1. 盘中 dry-run 单循环（开盘后任意时刻，建议 09:35 后）

```bash
$WIN_PY -m src.interfaces.cli.quant auto-trade --once --enable
```

预期输出形如：`循环 20260612-093501-xxxxxx [dry_run]: 信号 N | 提交 n | 拒绝 m | 失败 0 | 金额 ¥xxx`。

- 读真实行情与真实账户，**下单走 DryRunTradeGateway，QMT 下单接口零触达**。
- dual_ma 在这 4 只主板标的上大概率无信号（信号 0 | 提交 0）——这同样是合格结果，证明链路通。
- 核对留痕：`$WIN_PY -m src.interfaces.cli.quant dashboard` → http://127.0.0.1:8501/ui/#live
  应看到循环行、账户快照、（若有信号）执行记录与拒因。

## 2. 守护模式跑一整天（纸面前向开始）

```bash
$WIN_PY -m src.interfaces.cli.quant auto-trade --enable    # Ctrl+C 停止
```

- 执行时刻 09:35 / 14:50（trading.yaml `auto_trade.execution_times`）。
- 这就是漏斗 Phase「纸面前向」的载体：积累 dry-run 留痕 = 纸面交易记录。
- 建议先以 dual_ma 跑通基础设施；等因子漏斗出 edge 后换 `auto_trade.strategy`。

## 3. 回测页冒烟（随时）

```bash
$WIN_PY -m src.interfaces.cli.run_backtest        # 跑完自动入库 backtest_runs
# dashboard → 回测页签应出现本次 run 的指标表 + 净值曲线
```

## 4. live 首跑（⚠ 真实下单 — 建议等 edge 验证后再开）

三重确认缺一不可，全部满足才会发真单：

1. `trading.yaml`: `auto_trade.mode: live` **且** `auto_trade.enabled: true`
2. CLI 加 `--live`：`$WIN_PY -m src.interfaces.cli.quant auto-trade --once --live`

防线（任一触发即拒单留痕）：主板白名单 / 交易时段 / 报价新鲜 / ±10% 涨跌停带 /
单笔 ≤¥1500（硬顶 5000）/ 可用资金或持仓 / 单循环 ≤3 单 / 当日 ≤¥3000 /
当日权益回撤 >2% 禁买 / 同标的同方向当日只一次 / 轮询 30s 超时自动撤单。

**回滚动作**：Ctrl+C 停守护 → QMT 客户端手工撤未成单 → `enabled: false` 关总闸。

## 常见拒单原因对照

| 留痕 reject_reason 关键词 | 含义 | 处置 |
|---|---|---|
| 不在 v1 允许范围 | 非沪深主板（60/000/001 开头） | 换标的或扩白名单（需改 domain 闸） |
| 非连续竞价时段 / 非交易日 | 盘外执行 | 等开盘；--once 盘外跑出此拒单也证明链路通 |
| 拿不到有效实时报价 | 停牌/退市/QMT 行情断 | 查 QMT 客户端行情 |
| 超出涨跌停带 | 报价已贴板 | 正常保护，不处置 |
| 金额…超上限 | 单笔预算闸 | 调 `per_order_notional_cap`（硬顶 5000） |
| 可用资金…< 需求 | 现金不足（含 1% 费用 buffer） | 正常保护 |
| 卖出量 > 可用持仓 | T+1 锁定 | 正常保护 |
| 当日预算耗尽 | 日累计 ≥¥3000 | 次日自动重置 |
| 当日亏损超限禁买 | 当日权益回撤 >2% | 当日只允许卖出 |

## 昨夜遗留事项（晨间补审清单）

- [ ] **git push**：WSL 侧无 SSH 私钥（`Permission denied (publickey)`），本地 main 领先 origin 30+ 提交——请在 Windows 侧推送
- [ ] QMT 极简模式登录后执行第 1 步（昨日 14:00 冒烟卡在 `connect != 0`，错误路径已验证正确）
- [ ] `QmtTradeGateway.cancel_order` 为新增接口，未经实盘验证——首次 live 前可用一笔 dry-run 超时单观察日志（dry-run 的撤单是模拟的，真实撤单要等 live 首跑或在 QMT 端手工配合验证）
- [ ] 治理债（设计文档 §六）：`AutoTradingEngine`/`TradingOrchestrator`/`SignalPipeline` 已被 `AutoTradeAppService` 旁路，后续 Spec 决定合并或归档
