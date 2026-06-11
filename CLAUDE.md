# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

GoldenHandQuant — A 股量化交易系统（实盘 + 回测框架），基于 DDD 单体架构, python3.13。

## 环境配置

```bash
# 创建 conda 环境
conda create -n goldenhandquant python=3.13 -y

# 激活环境
conda activate goldenhandquant

# 安装项目依赖（基于 pyproject.toml）
pip install -e ".[dev,api]"
```

### WSL 环境特殊说明

在 WSL 中使用 xtquant（QMT SDK）需要调用 Windows 的 Python：

```bash
# Windows conda Python 路径
WIN_PYTHON="/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe"

# 使用 Windows Python 运行需要 xtquant 的代码
$WIN_PYTHON your_script.py

# 使用 WSL Python 运行回测等不需要 xtquant 的代码
python -m src.interfaces.cli.run_backtest
```

**注意：** xtquant 是 Windows 特定的包，只能在 Windows Python 环境中使用。

## 常用命令

```bash
# 运行全部测试
python -m pytest tests/ --ignore=tests/infrastructure/gateway/

# 运行单个测试文件
python -m pytest tests/domain/trade/test_order.py

# 运行单个测试用例
python -m pytest tests/domain/trade/test_order.py::TestOrder::test_submit_should_change_status_to_submitted

# 运行 ruff lint
ruff check src/

# 执行回测
python -m src.interfaces.cli.run_backtest

# 多策略对比
python -m src.interfaces.cli.compare_strategies --strategies dual_ma,micro_value --plot

# 市场数据库维护（DuckDB, 只刷缺口; 需 Windows Python + QMT）
$WIN_PYTHON -m src.interfaces.cli.quant data refresh --start-date 2021-01-01 --end-date 2025-12-31
$WIN_PYTHON -m src.interfaces.cli.quant data status

# 因子判决（结果自动入库 factor_verdicts）
$WIN_PYTHON -m src.interfaces.cli.quant factor-test --factors P0 --split-date 2024-06-30

# 投研驾驶舱（http://127.0.0.1:8501/ui/, 含回测/实盘页签）
$WIN_PYTHON -m src.interfaces.cli.quant dashboard

# 自动交易循环（dry-run 默认=纸面前向; 留痕入 data/trading.db; 需 QMT 客户端）
$WIN_PYTHON -m src.interfaces.cli.quant auto-trade --once --enable
# live 真单需三重确认: 配置 mode:live + enabled:true + CLI --live（运行手册:
# docs/feat/0611-closed-loop/2026-06-12-morning-runbook.md）
```

## 核心架构

**依赖方向（由外向内）**: `interfaces → infrastructure → application → domain`

### 四层职责

- **`src/domain/`** — 纯业务逻辑，只能使用 Python 标准库。定义实体、值对象、领域服务和外部依赖接口（gateway interface / Protocol 类）。子域包括 `account`、`trade`、`market`、`strategy`、`risk`、`backtest`、`portfolio`。
- **`src/application/`** — 用例编排层，协调领域对象与基础设施。例如 `BacktestAppService` 串联行情推进 → 策略信号 → 下单撮合 → 日终结算的完整回测循环。
- **`src/infrastructure/`** — 外部依赖具体实现。`gateway/` 是 QMT/xtquant 对接，`mock/` 是回测模拟网关，`visualization/` 是图表绘制。
- **`src/interfaces/`** — 系统入口。`cli/` 是命令行入口，`api/` 预留 FastAPI 路由。

### 关键模式：接口隔离

领域层只定义 `Protocol` 接口（如 `ITradeGateway`、`IMarketGateway`），具体实现在 infrastructure 层（如 `QmtTradeGateway`、`MockTradeGateway`）。应用层通过依赖注入接收具体实现，永远不直接依赖 infrastructure。

### 回测主流程（`BacktestAppService.run_backtest`）

1. 推进行情时间（`market_gateway.set_current_time`）
2. 获取当前 Bar 数据
3. 策略生成信号（`strategy.generate_signals`）
4. PositionSizer 计算目标数量 → 创建订单 → `trade_gateway.place_order`
5. 日终结算（撤销未成交单 + T+1 持仓释放）
6. 记录每日快照 → 生成 `BacktestReport`

### 关键领域实体

- **`Order`** — 订单状态机：`CREATED → SUBMITTED → (PARTIAL_FILLED) → FILLED / CANCELED / REJECTED`。买入量必须为 100 的整数倍。
- **`Position`** — 区分 `total_volume` 和 `available_volume`（T+1：当日买不可卖）。
- **`Asset`** — 区分 `available_cash` 和 `frozen_cash`，下单时冻结，成交/撤单时解冻。

### A 股交易成本（已内置于 MockTradeGateway 和 DailySettlementService）

- 佣金：双向万 2.5，最低 5 元
- 印花税：仅卖出，千 0.5
- 过户费：双向，十万分之一
- 滑点：买入上浮 0.1%，卖出下浮 0.1%
- 流动性限制：单笔不超过当日成交量 10%

## 代码规范

完整规范见 `docs/rules/`（按主题拆分，入口 `architecture.md` 含索引；写代码读 `coding-style.md`、写测试读 `testing.md`、动 domain/网关读 `domain-rules.md`、动实盘链路读 `live-trading.md`、动数据层读 `data-layer.md`、找代码读 `codebase-map.md`）。核心要点：

- **Python 3.13+**：使用 `list[X]`、`dict[K,V]`、`X | None`（弃用 `List`、`Dict`、`Optional`）
- **Dataclass**：实体/值对象使用 `@dataclass(slots=True, kw_only=True)`
- **状态机**：优先使用 `match/case` 语法
- **Domain 红线**：`src/domain/` 允许纯计算库（numpy/pandas/scipy，无 I/O、无网络、无全局状态）；仍禁止数据源 SDK（xtquant/tushare）、存储引擎（duckdb/sqlite 包装）、Web 框架、可视化、ML 训练库（变更记录：`docs/feat/0611-market-data-store/`）
- **测试**：pytest + AAA 模式；domain 层测试不需要 mock；测试文件命名 `test_<源文件名>.py`，目录结构与 `src/` 镜像映射
- **QMT/xtquant**：获取 K 线必须用 `get_market_data_ex()`（禁用旧版 `get_market_data()`），必须指定 `dividend_type='front'`

## Superpowers 配置

设计文档（specs）存放在 `docs/feat/` 目录下，格式为：

```
docs/feat/MMDD-feature-name/
  └── YYYY-MM-DD-feature-name-design.md
  └── YYYY-MM-DD-feature-name-plan.md
```

示例：`docs/feat/0520-agent-team-v2/2026-05-20-agent-team-v2-design.md`

superpowers 的 brainstorming/writing-plans skill 应遵循此目录结构，不要使用 `docs/superpowers/specs/`。
