# GoldenHandQuant

A 股量化交易系统（回测 + 实盘），DDD 单体架构，Python 3.13。

核心理念：**验证优先**——先把数据和测试引擎修到诚实（无前视、T-1 信息、全成本、
样本内外切分），再让因子假设过硬门槛漏斗，活下来的才进纸面前向 → 小资金 → 全自动。

> ⚠️ 本项目用于个人投研，不构成投资建议。实盘有风险，任何策略上线前必须
> 通过 `docs/feat/0610-factor-library/` 定义的判决流程。

## 架构

依赖方向严格由外向内：

```
interfaces (CLI / FastAPI / Dashboard)
    └─> infrastructure (QMT/Tushare 网关, DuckDB/SQLite 仓储, Mock 回测网关)
            └─> application (回测编排, 因子测试, 市场数据编排)
                    └─> domain (实体/值对象/领域服务 — 无副作用, 可独立测试)
```

- **domain** 允许纯计算库（numpy/pandas/scipy），禁止一切 I/O、SDK、框架
  （规则见 `docs/rules/architecture.md`）
- 领域层只定义 `Protocol` 接口（`ITradeGateway`、`IHistoryDataFetcher`…），
  infrastructure 提供 QMT 实现与回测 Mock 实现，应用层依赖注入

## 环境准备

```bash
conda create -n goldenhandquant python=3.13 -y
conda activate goldenhandquant
pip install -e ".[dev,api]"
```

**QMT/xtquant 注意**：xtquant 仅 Windows 可用。WSL 开发时，取数/因子测试用
Windows conda Python 跑，纯回测/测试可用任一侧：

```bash
WIN_PYTHON="/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe"  # 按机器调整
$WIN_PYTHON -m src.interfaces.cli.quant factor-test ...   # 需要 QMT
python -m src.interfaces.cli.run_backtest                 # 不需要 QMT
```

取数前需启动 QMT 客户端（投研版/极简版）。

## 快速开始（三步看到全貌）

```bash
# 1. 灌市场数据（全 A 股日线 + 基本面 + 截面特征 → data/market.duckdb, 只拉缺口）
quant data refresh --start-date 2021-01-01 --end-date 2025-12-31

# 2. 跑 P0 因子判决（IS/OOS 切分 + 扣成本 + 硬门槛, 结果自动入库）
quant factor-test --factors P0 --start-date 2021-01-01 --end-date 2025-12-31 \
  --split-date 2024-06-30 --rebalance-days 5

# 3. 打开投研驾驶舱
quant dashboard          # → http://127.0.0.1:8501/ui/
```

## CLI 一览

| 命令 | 用途 |
|---|---|
| `quant data refresh / status` | 市场数据库维护（只刷缺口 / 覆盖概览） |
| `quant factor-test --factors P0` | 因子假设硬门槛判决（IC/IR/单调性/扣成本多空/OOS） |
| `quant dashboard` | 投研驾驶舱（数据资产 / 因子判决 / 个股查看 / 回测 / 实盘） |
| `quant backtest -s <strategy>` | 单策略回测（结果自动入库 `backtest_runs`） |
| `quant compare --strategies a,b` | 多策略对比（同上入库, 同 run 并排） |
| `quant list` | 列出可用策略 |
| `quant ml-train / ml-evaluate` | ML 选股管道 |
| `quant order buy --symbol X --lots N` | 受控单笔实单（六道盘前闸） |
| `quant live` | 半自动交易（信号确认后下单） |
| `quant auto-trade --once --enable` | 自动交易循环：**dry-run 默认**（纸面前向）；`--live` + 配置 `mode:live` + `enabled:true` 三重确认才发真单 |

## 市场数据库（DuckDB, `data/market.duckdb`）

六张表：`instruments`（股票池）/ `bars`（前复权日线）/ `fundamental_snapshots`
（日度基本面）/ `stock_features`（截面特征，**T-1 信息口径固化进表结构**，
版本化）/ `factor_verdicts`（判决留痕）/ `backtest_runs`（回测结果留痕：
指标 + 净值曲线，驾驶舱回测页消费）+ `fetch_meta`（履约区间，刷新只拉缺口）。

## 交易留痕库（SQLite WAL, `data/trading.db`）

自动交易循环的运行账本：`trading_cycles`（循环结果）/ `execution_records`
（每单全生命周期，含拒单原因）/ `account_snapshots`、`position_snapshots`
（循环末快照）/ `audit_logs`（审计）。驾驶舱实盘页只读轮询此库。
安全模型：六道盘前闸（与受控单笔同一 domain 实现）+ 循环/日预算闸 +
当日亏损禁买 + 超时撤单；live 模式三重显式确认，缺一自动降级 dry-run。

特征由向量化引擎（`src/domain/market/services/feature_engine.py`）按 symbol
全时段一次算完，与逐日重算的参考实现做过 1e-9 golden 等价验证；
全市场特征构建分钟级，命中缓存后 factor-test 数据准备秒级。

## 测试与 Lint

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/   # 全量（不依赖 QMT）
ruff check src/
```

约定：pytest AAA 模式；domain 测试不用 mock；测试目录与 `src/` 镜像。
关键正确性测试：无前视/T-1/warmup 特征化测试（旧管道与 DB 管道双覆盖）、
特征引擎 golden 等价、收益按实现日键入对齐。

## 文档索引

- `docs/rules/architecture.md` — 架构红线与编码规范
- `docs/feat/0610-factor-library/` — 因子假设库 + 历轮判决报告
- `docs/feat/0611-market-data-store/` — 市场数据库 + 向量化引擎设计/计划
- `docs/feat/0611-dashboard/` — 投研驾驶舱设计/计划
- `docs/feat/0611-realtime-order/` — 实时行情 + 受控单笔（首单回执）
- `docs/feat/0611-closed-loop/` — 全闭环 v1：自动交易/留痕/驾驶舱扩展（设计/计划/晨间手册）
- `CLAUDE.md` — AI 协作约定（Claude Code）
