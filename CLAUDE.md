# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

QuantFlow — A 股量化交易系统（实盘 + 回测框架），基于 DDD 单体架构。

## 常用命令

```bash
# 运行全部测试
python -m pytest tests/

# 运行单个测试文件
python -m pytest tests/domain/trade/test_order.py

# 运行单个测试用例
python -m pytest tests/domain/trade/test_order.py::TestOrder::test_submit_should_change_status_to_submitted

# 执行回测
python -m src.interfaces.cli.run_backtest
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

完整规范见 `.trae/rules/architecture.md`。核心要点：

- **Python 3.11+**：使用 `list[X]`、`dict[K,V]`、`X | None`（弃用 `List`、`Dict`、`Optional`）
- **Dataclass**：实体/值对象使用 `@dataclass(slots=True, kw_only=True)`
- **状态机**：优先使用 `match/case` 语法
- **Domain 红线**：`src/domain/` 下禁止 import 任何第三方库（pandas、numpy 等）
- **测试**：pytest + AAA 模式；domain 层测试不需要 mock；测试文件命名 `test_<源文件名>.py`，目录结构与 `src/` 镜像映射
- **QMT/xtquant**：获取 K 线必须用 `get_market_data_ex()`（禁用旧版 `get_market_data()`），必须指定 `dividend_type='front'`
