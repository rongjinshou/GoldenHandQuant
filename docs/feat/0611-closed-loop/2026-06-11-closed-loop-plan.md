# 全闭环 v1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## ✅ 完成状态（2026-06-11 夜, 同日执行完毕）

全部 11 个任务已实现并验证：全量 pytest 绿（exit 0, --ignore=gateway）+ `ruff check src/` 干净。
提交序列：`ebe22b4`(卫生) → `22bb99d`(盘前闸) → `08ddf6d`(撤单) → `35199a3`(留痕库+DryRun)
→ `f65807f`(循环服务) → `80dcebf`(CLI 接线) → `e4cf007`(回测入库) → `4190607`(API)
→ `6bc8616`(前端+缺表修复) → 文档收尾提交。

### 实施偏差记录（计划 vs 实际）

| # | 偏差 | 原因与处置 |
|---|---|---|
| 1 | pytest `--basetemp` 移入项目目录 `.pytest_tmp/`（pyproject addopts） | 系统 Temp 下 `pytest-of-11492` 目录 ACL 损坏且 takeown/icacls/rmdir 全部拒绝，tmp_path fixture 全体 ERROR；项目内 basetemp 一劳永逸 |
| 2 | Task 2 happy-path 断言改 5.01/501.0（计划写 5.0/500.0） | `min(ask1=5.01, last×1.002=5.01)`=5.01——计划断言笔误，实现与 ticket 口径一致 |
| 3 | Task 6 测试替身 FakeTradeGateway 默认改「永远 DRY_RUN」 | 原设计 statuses 耗尽后返回 ALIVE，固定时钟下多单轮询死循环（首跑即挂） |
| 4 | Task 8 `--no-store/--db` 旗标改为环境变量 `GHQ_NO_STORE`/`GHQ_MARKET_DB` | `run_backtest.py` 本无 argparse（纯 YAML 配置驱动），不为旗标引入参数解析；compare 复用同一 `store_backtest_reports()` |
| 5 | Task 9 增补：`load_backtest_runs` 缺表优雅返回空 + 回归测试 | 冒烟发现真实路径 500——既有 market.duckdb 是旧 schema，read_only 连接不执行 DDL；新建库的测试测不出此问题 |
| 6 | Task 11 盘中 QMT 冒烟未完成，移入晨间手册 | 14:00 实测交易端 `connect != 0`（QMT 客户端未在线）；错误路径验证正确，并给 CLI 加了友好报错（不再裸 traceback） |
| 7 | 顺手修一处存量 lint（fetch_account.py E501） | `ruff check src/` 全量验收时暴露，独立 commit `b738adf` |

**Goal:** 打通「自动交易循环（dry-run/live）+ 交易留痕 + 回测结果入库 + 驾驶舱回测/实盘两页签」的端到端闭环。

**Architecture:** 自动循环脊柱 = 已实测的 `LiveSignalService`，新建 `AutoTradeAppService` 编排「扫描→过滤→三层防线→下单→轮询→撤单→留痕」；盘前闸提取为 domain 纯函数与单笔 ticket 共用；交易留痕入 SQLite `data/trading.db`（新 `TradingStore` + 既有审计仓储），回测结果入 `market.duckdb` 新表 `backtest_runs`；驾驶舱沿用只读 REST + 原生 JS 页签。设计：`2026-06-11-closed-loop-design.md`（DD-1~DD-8）。

**Tech Stack:** Python 3.13 / FastAPI / SQLite(WAL) / DuckDB / ECharts(已 vendor) / pytest。

**运行约定**（本机 WSL 无 Python 环境，一切命令走 Windows conda Python）：

```bash
WIN_PY=/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe
# 全量测试
$WIN_PY -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
# lint
$WIN_PY -m ruff check src/
```

提交约定：逐任务 commit，中文 conventional 前缀，直推 main。

---

### Task 1: 仓库卫生 — gitignore + 审计仓储补测试入库

**Files:**
- Modify: `.gitignore`
- Commit（已存在未跟踪）: `src/infrastructure/persistence/repositories/audit_log_repository.py`
- Create: `tests/infrastructure/persistence/repositories/test_audit_log_repository.py`

- [ ] **Step 1.1: .gitignore 增加两行**（`models/` 是 ML 训练产物、`src/.cgcignore` 是 CodeGraphContext 工具生成物，均不入库）

```
models/
src/.cgcignore
```

- [ ] **Step 1.2: 写审计仓储测试**（仓储已实现：`SqliteAuditLogRepository(db: Database)`，`save/query/count`；domain 契约与 `AuditService` 已提交且有测试）

```python
"""SqliteAuditLogRepository 测试 — 临时库文件，覆盖建表/写入/查询。"""
from datetime import datetime, timedelta

from src.domain.common.value_objects.audit_log_entry import AuditLogEntry
from src.infrastructure.persistence.database import Database
from src.infrastructure.persistence.repositories.audit_log_repository import (
    SqliteAuditLogRepository,
)


def _entry(action: str = "place_order", ts: datetime | None = None) -> AuditLogEntry:
    return AuditLogEntry(
        user_id="auto-trade",
        action=action,
        resource_type="Order",
        resource_id="ord-1",
        timestamp=ts or datetime(2026, 6, 10, 9, 35),
        details={"price": 5.05},
    )


class TestSqliteAuditLogRepository:
    def test_save_then_query_roundtrip(self, tmp_path):
        repo = SqliteAuditLogRepository(Database(str(tmp_path / "t.db")))
        repo.save(_entry())

        rows = repo.query()

        assert len(rows) == 1
        assert rows[0].action == "place_order"
        assert rows[0].details == {"price": 5.05}

    def test_query_filters_by_action(self, tmp_path):
        repo = SqliteAuditLogRepository(Database(str(tmp_path / "t.db")))
        repo.save(_entry("place_order"))
        repo.save(_entry("cancel_order"))

        rows = repo.query(action="cancel_order")

        assert [r.action for r in rows] == ["cancel_order"]

    def test_count_by_time_window(self, tmp_path):
        repo = SqliteAuditLogRepository(Database(str(tmp_path / "t.db")))
        base = datetime(2026, 6, 10, 9, 0)
        repo.save(_entry(ts=base))
        repo.save(_entry(ts=base + timedelta(days=1)))

        assert repo.count(start=base, end=base + timedelta(hours=1)) == 1
```

> 注意：先 Read 仓储源码核对 `query/count` 的关键字参数名（`action=`/`start=`/`end=`），与实现不符时**改测试适配实现**（仓储是既有已验收代码）。

- [ ] **Step 1.3: 跑测试确认绿** — `$WIN_PY -m pytest tests/infrastructure/persistence/repositories/test_audit_log_repository.py -q` → PASS
- [ ] **Step 1.4: Commit** — `chore(repo): gitignore 补 models/.cgcignore; 审计仓储入库并补测试`

---

### Task 2: domain 盘前闸纯函数 + ticket 行为等价重构（DD-3）

**Files:**
- Create: `src/domain/trade/services/pre_trade_checks.py`
- Create: `tests/domain/trade/services/test_pre_trade_checks.py`
- Modify: `src/application/order_ticket_app.py`（内联闸改调用，常量迁移再导出）

- [ ] **Step 2.1: 写闸函数失败测试**（核心断言：与 ticket 现行为完全一致的取整/边界）

```python
from datetime import datetime

from src.domain.market.value_objects.quote import Quote
from src.domain.trade.services.pre_trade_checks import (
    MAX_NOTIONAL_CEILING,
    build_limit_price,
    check_buy_cash,
    check_daily_loss_block_buys,
    check_notional_cap,
    check_price_band,
    check_sell_volume,
    check_symbol_scope,
    check_trading_session,
    run_pre_trade_gates,
)
from src.domain.trade.value_objects.order_direction import OrderDirection

WED = datetime(2026, 6, 10, 10, 0)  # 周三盘中


def _quote(last=5.0, bid1=4.99, ask1=5.01, prev_close=5.0) -> Quote:
    return Quote(symbol="601006.SH", last=last, bid1=bid1, ask1=ask1,
                 prev_close=prev_close, timestamp=WED)


class TestScopeAndSession:
    def test_main_board_passes(self):
        assert check_symbol_scope("601006.SH") is None
        assert check_symbol_scope("000001.SZ") is None

    def test_gem_and_sme_rejected(self):
        assert check_symbol_scope("300750.SZ") is not None
        assert check_symbol_scope("002284.SZ") is not None

    def test_session_boundaries(self):
        assert check_trading_session(datetime(2026, 6, 10, 9, 29)) is not None
        assert check_trading_session(datetime(2026, 6, 10, 9, 30)) is None
        assert check_trading_session(datetime(2026, 6, 13, 10, 0)) is not None  # 周六


class TestPricing:
    def test_buy_price_is_min_of_ask_and_protection(self):
        assert build_limit_price(OrderDirection.BUY, _quote(ask1=5.20)) == round(5.0 * 1.002, 2)
        assert build_limit_price(OrderDirection.BUY, _quote(ask1=5.001)) == 5.0

    def test_buy_falls_back_when_no_ask(self):
        assert build_limit_price(OrderDirection.BUY, _quote(ask1=None)) == round(5.0 * 1.002, 2)

    def test_sell_price_is_max_of_bid_and_protection(self):
        assert build_limit_price(OrderDirection.SELL, _quote(bid1=5.0)) == 5.0
        assert build_limit_price(OrderDirection.SELL, _quote(bid1=None)) == round(5.0 * 0.998, 2)
        assert build_limit_price(OrderDirection.SELL, _quote(bid1=4.5)) == round(5.0 * 0.998, 2)

    def test_price_band(self):
        assert check_price_band(5.49, prev_close=5.0) is None
        assert check_price_band(5.51, prev_close=5.0) is not None


class TestCapsAndFunds:
    def test_notional_cap(self):
        assert check_notional_cap(1500.0, cap=1500.0) is None
        assert check_notional_cap(1500.01, cap=1500.0) is not None

    def test_buy_cash_includes_fee_buffer(self):
        assert check_buy_cash(1000.0, available_cash=1010.0) is None
        assert check_buy_cash(1000.0, available_cash=1009.9) is not None

    def test_sell_volume(self):
        assert check_sell_volume(100, available_volume=100) is None
        assert check_sell_volume(200, available_volume=100) is not None

    def test_daily_loss_block(self):
        assert check_daily_loss_block_buys(100000.0, 97999.0, limit_ratio=0.02) is True
        assert check_daily_loss_block_buys(100000.0, 98001.0, limit_ratio=0.02) is False
        assert check_daily_loss_block_buys(0.0, 0.0, limit_ratio=0.02) is False


class TestAggregateGates:
    def test_buy_happy_path_returns_price_and_notional(self):
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_cash=10000.0,
        )
        assert r.passed and r.reject_reason is None
        assert r.limit_price == 5.0 and r.notional == 500.0

    def test_each_gate_rejects_in_order(self):
        bad_scope = run_pre_trade_gates(
            symbol="300750.SZ", direction=OrderDirection.BUY, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_cash=1e6,
        )
        assert not bad_scope.passed and "范围" in bad_scope.reject_reason

        stale = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.BUY, volume=100,
            quote=None, now=WED, max_notional=1500.0, available_cash=1e6,
        )
        assert not stale.passed and "报价" in stale.reject_reason

    def test_sell_uses_volume_gate_not_cash(self):
        r = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.SELL, volume=100,
            quote=_quote(), now=WED, max_notional=1500.0, available_volume=100,
        )
        assert r.passed
        r2 = run_pre_trade_gates(
            symbol="601006.SH", direction=OrderDirection.SELL, volume=200,
            quote=_quote(), now=WED, max_notional=1500.0, available_volume=100,
        )
        assert not r2.passed
```

- [ ] **Step 2.2: 跑测试确认失败**（模块不存在）
- [ ] **Step 2.3: 实现 `pre_trade_checks.py`**（纯标准库，守 domain 红线）

```python
"""盘前安全闸 — domain 纯函数集，单笔 ticket 与自动循环共用（单一事实来源）。

口径与首笔实单验证一致（docs/feat/0611-realtime-order 设计 D2/D3/D4）：
主板 only、连续竞价时段、报价新鲜、±10% 涨跌停带、单笔金额硬顶、资金/持仓校验。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.market.value_objects.quote import Quote
from src.domain.trade.value_objects.order_direction import OrderDirection

PRICE_BAND = 0.10                 # 主板涨跌停带
MAX_NOTIONAL_CEILING = 5000.0     # 单笔金额上限的硬顶
CASH_FEE_BUFFER = 1.01            # 买入资金费用 buffer
_SESSIONS = (("09:30", "11:30"), ("13:00", "15:00"))


@dataclass(frozen=True, slots=True, kw_only=True)
class GateResult:
    """聚合闸结果：通过时携带限价与金额。"""
    passed: bool
    reject_reason: str | None = None
    limit_price: float | None = None
    notional: float | None = None


def check_symbol_scope(symbol: str) -> str | None:
    code, _, market = symbol.partition(".")
    if market == "SH" and code.startswith("60"):
        return None
    if market == "SZ" and (code.startswith("000") or code.startswith("001")):
        return None
    return f"{symbol} 不在 v1 允许范围 (仅沪深主板 60xxxx/000xxx)"


def check_trading_session(now: datetime) -> str | None:
    if now.weekday() >= 5:
        return f"非交易日: {now:%Y-%m-%d} (周{now.weekday() + 1})"
    hm = now.strftime("%H:%M")
    if any(start <= hm <= end for start, end in _SESSIONS):
        return None
    return f"非连续竞价时段: {now:%Y-%m-%d %H:%M} (9:30-11:30/13:00-15:00)"


def build_limit_price(direction: OrderDirection, quote: Quote) -> float:
    """买: 贴卖一但不超 last×1.002；卖: 贴买一但不低于 last×0.998。"""
    if direction == OrderDirection.BUY:
        raw = quote.ask1 if quote.ask1 else quote.last * 1.002
        return round(min(raw, quote.last * 1.002), 2)
    raw = quote.bid1 if quote.bid1 else quote.last * 0.998
    return round(max(raw, quote.last * 0.998), 2)


def check_price_band(price: float, *, prev_close: float, band: float = PRICE_BAND) -> str | None:
    low = round(prev_close * (1 - band), 2)
    high = round(prev_close * (1 + band), 2)
    if low <= price <= high:
        return None
    return f"限价 {price} 超出涨跌停带 [{low}, {high}] (前收 {prev_close})"


def check_notional_cap(notional: float, *, cap: float) -> str | None:
    effective = min(cap, MAX_NOTIONAL_CEILING)
    if notional <= effective:
        return None
    return f"金额 {notional:.2f} 超上限 {effective:.2f}"


def check_buy_cash(notional: float, *, available_cash: float) -> str | None:
    required = notional * CASH_FEE_BUFFER
    if available_cash >= required:
        return None
    return f"可用资金 {available_cash:.2f} < 需求 {required:.2f}"


def check_sell_volume(volume: int, *, available_volume: int) -> str | None:
    if volume <= available_volume:
        return None
    return f"卖出量 {volume} > 可用持仓 {available_volume} (T+1)"


def check_daily_loss_block_buys(
    day_start_equity: float, current_equity: float, *, limit_ratio: float
) -> bool:
    """当日权益回撤超限 → True(禁买)。基准非正时不拦截。"""
    if day_start_equity <= 0:
        return False
    drawdown = (day_start_equity - current_equity) / day_start_equity
    return drawdown > limit_ratio


def run_pre_trade_gates(
    *,
    symbol: str,
    direction: OrderDirection,
    volume: int,
    quote: Quote | None,
    now: datetime,
    max_notional: float,
    available_cash: float | None = None,
    available_volume: int | None = None,
) -> GateResult:
    """六道闸逐序检查（自动循环用的聚合入口）。"""
    if volume <= 0 or volume % 100 != 0:
        return GateResult(passed=False, reject_reason=f"数量非法: {volume} (须为 100 整数倍)")
    if reason := check_symbol_scope(symbol):
        return GateResult(passed=False, reject_reason=reason)
    if reason := check_trading_session(now):
        return GateResult(passed=False, reject_reason=reason)
    if quote is None or quote.last <= 0 or quote.prev_close <= 0:
        return GateResult(passed=False, reject_reason="拿不到有效实时报价 (停牌/退市/行情断连?)")

    price = build_limit_price(direction, quote)
    if reason := check_price_band(price, prev_close=quote.prev_close):
        return GateResult(passed=False, reject_reason=reason)

    notional = price * volume
    if reason := check_notional_cap(notional, cap=max_notional):
        return GateResult(passed=False, reject_reason=reason)

    if direction == OrderDirection.BUY:
        if reason := check_buy_cash(notional, available_cash=available_cash or 0.0):
            return GateResult(passed=False, reject_reason=reason)
    else:
        if reason := check_sell_volume(volume, available_volume=available_volume or 0):
            return GateResult(passed=False, reject_reason=reason)

    return GateResult(passed=True, limit_price=price, notional=round(notional, 2))
```

- [ ] **Step 2.4: 跑新测试至绿**
- [ ] **Step 2.5: ticket 重构为调用闸函数**（行为等价）：`order_ticket_app.py` 删除 `_PRICE_BAND/_SESSIONS/_in_trading_session/_is_main_board`，改 `from src.domain.trade.services.pre_trade_checks import MAX_NOTIONAL_CEILING, build_limit_price, check_buy_cash, check_notional_cap, check_price_band, check_symbol_scope, check_trading_session`；`buy_lots` 内闸 0→`check_symbol_scope`、闸 1→`check_trading_session(now)`、闸 3→`price = build_limit_price(OrderDirection.BUY, quote)` + `check_price_band`、闸 4→`check_notional_cap(notional, cap=self._max_notional)`（注意 `self._max_notional` 构造时已 `min(…, MAX_NOTIONAL_CEILING)`，行为不变）、闸 5→`check_buy_cash`。拒单文案保持由闸函数返回（与原文案一致）。
- [ ] **Step 2.6: ticket 原测试全绿** — `$WIN_PY -m pytest tests/application/test_order_ticket_app.py tests/domain/trade/ -q` → PASS（12 个 ticket 用例一个不许动）
- [ ] **Step 2.7: Commit** — `refactor(trade): 盘前闸提取为 domain 纯函数, ticket 与自动循环共用 (DD-3)`

---

### Task 3: QmtTradeGateway 撤单能力

**Files:**
- Modify: `src/infrastructure/gateway/qmt_trade.py`（`query_order_status` 之后加方法）

- [ ] **Step 3.1: 实现 `cancel_order`**（gateway 测试目录在常规跑测时被 ignore，无法离线单测；以 lint + 晨间盘中冒烟验收）

```python
    def cancel_order(self, order_id: str) -> bool:
        """按 QMT 委托号撤单。返回是否受理(异步撤单, 受理≠已撤)。"""
        if not self._check_initialized():
            return False
        try:
            result = self.xt_trader.cancel_order_stock(
                self.account, int(order_id)
            )
            if result == 0:
                logger.info(f"Cancel accepted for order {order_id}")
                return True
            logger.warning(f"Cancel rejected for order {order_id}: {result}")
            return False
        except Exception as e:
            logger.error(f"Error canceling order {order_id}: {e}", exc_info=True)
            return False
```

- [ ] **Step 3.2: lint** — `$WIN_PY -m ruff check src/infrastructure/gateway/qmt_trade.py` → 无告警
- [ ] **Step 3.3: Commit** — `feat(gateway): QmtTradeGateway 撤单接口 (自动循环超时撤单用)`

---

### Task 4: TradingStore — 交易留痕库（DD-4）

**Files:**
- Create: `src/infrastructure/persistence/trading_store.py`
- Create: `tests/infrastructure/persistence/test_trading_store.py`

- [ ] **Step 4.1: 写失败测试**

```python
"""TradingStore 测试 — 临时 SQLite 文件，覆盖循环/执行/快照/预算统计。"""
from datetime import datetime

from src.infrastructure.persistence.trading_store import TradingStore

T0 = datetime(2026, 6, 10, 9, 35, 0)


def _store(tmp_path) -> TradingStore:
    return TradingStore(str(tmp_path / "trading.db"))


def _exec_row(order_id="o1", symbol="601006.SH", direction="BUY",
              status="SUBMITTED", notional=500.0, submitted_at=T0) -> dict:
    return {
        "order_id": order_id, "cycle_id": "c1", "mode": "dry_run",
        "symbol": symbol, "direction": direction,
        "signal_price": 5.0, "exec_price": 5.0, "volume": 100,
        "notional": notional, "status": status, "reject_reason": None,
        "strategy_name": "dual_ma", "confidence": 0.8,
        "submitted_at": submitted_at.isoformat(), "final_status_at": None,
        "status_trail": "[]",
    }


class TestCycles:
    def test_start_then_finalize_roundtrip(self, tmp_path):
        s = _store(tmp_path)
        s.save_cycle_start(cycle_id="c1", cycle_time=T0.isoformat(),
                           mode="dry_run", strategy="dual_ma")
        s.finalize_cycle(cycle_id="c1", signals_generated=3, orders_submitted=1,
                         orders_rejected=2, orders_failed=0,
                         notional_submitted=500.0, note="")

        cycles = s.load_cycles(limit=10)

        assert len(cycles) == 1
        assert cycles[0]["orders_submitted"] == 1
        assert cycles[0]["notional_submitted"] == 500.0


class TestExecutions:
    def test_save_is_upsert_by_order_id(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row(status="SUBMITTED"))
        s.save_execution(_exec_row(status="FILLED"))

        rows = s.load_executions(limit=10)

        assert len(rows) == 1
        assert rows[0]["status"] == "FILLED"

    def test_today_submitted_notional_excludes_rejected(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row("o1", status="SUBMITTED", notional=500.0))
        s.save_execution(_exec_row("o2", status="REJECTED", notional=999.0))
        s.save_execution(_exec_row("o3", status="DRY_RUN", notional=300.0))

        total = s.today_submitted_notional(mode="dry_run", today=T0.date().isoformat())

        assert total == 800.0

    def test_today_traded_keys(self, tmp_path):
        s = _store(tmp_path)
        s.save_execution(_exec_row("o1", symbol="601006.SH", direction="BUY"))
        s.save_execution(_exec_row("o2", symbol="600000.SH", direction="SELL",
                                   status="REJECTED"))

        keys = s.today_traded_keys(mode="dry_run", today=T0.date().isoformat())

        assert keys == {"601006.SH:BUY"}  # 拒单不算已交易


class TestSnapshots:
    def test_account_snapshot_and_day_start_equity(self, tmp_path):
        s = _store(tmp_path)
        s.save_account_snapshot(snapshot_time=T0.isoformat(), mode="dry_run",
                                total_asset=146000.0, available_cash=140000.0,
                                frozen_cash=0.0, market_value=6000.0)
        s.save_account_snapshot(snapshot_time=T0.replace(hour=14).isoformat(),
                                mode="dry_run", total_asset=145000.0,
                                available_cash=139000.0, frozen_cash=0.0,
                                market_value=6000.0)

        assert s.day_start_equity(mode="dry_run", today=T0.date().isoformat()) == 146000.0
        series = s.load_account_series(mode="dry_run", limit=10)
        assert len(series) == 2

    def test_position_snapshots_latest_batch(self, tmp_path):
        s = _store(tmp_path)
        s.save_position_snapshots(snapshot_time=T0.isoformat(), mode="dry_run", rows=[
            {"symbol": "601006.SH", "total_volume": 100, "available_volume": 0,
             "average_cost": 5.05, "last_price": 5.06},
        ])
        s.save_position_snapshots(snapshot_time=T0.replace(hour=14).isoformat(),
                                  mode="dry_run", rows=[
            {"symbol": "601006.SH", "total_volume": 100, "available_volume": 100,
             "average_cost": 5.05, "last_price": 5.10},
        ])

        latest = s.load_latest_positions(mode="dry_run")

        assert len(latest) == 1
        assert latest[0]["available_volume"] == 100
```

- [ ] **Step 4.2: 跑测试确认失败**
- [ ] **Step 4.3: 实现 `TradingStore`**

```python
"""交易留痕库 (SQLite WAL) — 循环/执行记录/账户与持仓快照。

独立于 market.duckdb(研究资产): 交易进程长驻写、驾驶舱只读轮询。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-4
"""

from __future__ import annotations

from src.infrastructure.persistence.database import Database

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS trading_cycles (
        cycle_id TEXT PRIMARY KEY, cycle_time TEXT NOT NULL, mode TEXT NOT NULL,
        strategy TEXT NOT NULL, signals_generated INTEGER DEFAULT 0,
        orders_submitted INTEGER DEFAULT 0, orders_rejected INTEGER DEFAULT 0,
        orders_failed INTEGER DEFAULT 0, notional_submitted REAL DEFAULT 0,
        note TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )""",
    """CREATE TABLE IF NOT EXISTS execution_records (
        order_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL, mode TEXT NOT NULL,
        symbol TEXT NOT NULL, direction TEXT NOT NULL,
        signal_price REAL, exec_price REAL, volume INTEGER, notional REAL,
        status TEXT NOT NULL, reject_reason TEXT, strategy_name TEXT,
        confidence REAL, submitted_at TEXT NOT NULL, final_status_at TEXT,
        status_trail TEXT DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS account_snapshots (
        snapshot_time TEXT NOT NULL, mode TEXT NOT NULL, total_asset REAL,
        available_cash REAL, frozen_cash REAL, market_value REAL
    )""",
    """CREATE TABLE IF NOT EXISTS position_snapshots (
        snapshot_time TEXT NOT NULL, mode TEXT NOT NULL, symbol TEXT NOT NULL,
        total_volume INTEGER, available_volume INTEGER,
        average_cost REAL, last_price REAL
    )""",
]

# 占用预算的状态(意向已发出): 拒单/失败不占
_BUDGET_STATUSES = ("DRY_RUN", "SUBMITTED", "FILLED", "PARTIAL",
                    "TIMEOUT_CANCELED", "TIMEOUT_UNCANCELED", "ALIVE")


class TradingStore:
    def __init__(self, db_path: str = "data/trading.db") -> None:
        self._db = Database(db_path)
        for ddl in _SCHEMA:
            self._db.execute(ddl)
        self._db.commit()

    @property
    def db(self) -> Database:
        """供审计仓储共用同一连接/文件。"""
        return self._db

    def close(self) -> None:
        self._db.close()

    # --- cycles ---
    def save_cycle_start(self, *, cycle_id: str, cycle_time: str, mode: str,
                         strategy: str) -> None:
        self._db.execute(
            "INSERT INTO trading_cycles (cycle_id, cycle_time, mode, strategy) "
            "VALUES (?, ?, ?, ?)",
            (cycle_id, cycle_time, mode, strategy),
        )
        self._db.commit()

    def finalize_cycle(self, *, cycle_id: str, signals_generated: int,
                       orders_submitted: int, orders_rejected: int,
                       orders_failed: int, notional_submitted: float,
                       note: str = "") -> None:
        self._db.execute(
            """UPDATE trading_cycles SET signals_generated=?, orders_submitted=?,
               orders_rejected=?, orders_failed=?, notional_submitted=?, note=?
               WHERE cycle_id=?""",
            (signals_generated, orders_submitted, orders_rejected,
             orders_failed, notional_submitted, note, cycle_id),
        )
        self._db.commit()

    def load_cycles(self, limit: int = 50) -> list[dict]:
        cur = self._db.execute(
            "SELECT * FROM trading_cycles ORDER BY cycle_time DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in cur.fetchall()]

    # --- executions ---
    def save_execution(self, row: dict) -> None:
        cols = ("order_id", "cycle_id", "mode", "symbol", "direction",
                "signal_price", "exec_price", "volume", "notional", "status",
                "reject_reason", "strategy_name", "confidence", "submitted_at",
                "final_status_at", "status_trail")
        self._db.execute(
            f"INSERT OR REPLACE INTO execution_records ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            tuple(row.get(c) for c in cols),
        )
        self._db.commit()

    def load_executions(self, limit: int = 200) -> list[dict]:
        cur = self._db.execute(
            "SELECT * FROM execution_records ORDER BY submitted_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]

    def today_submitted_notional(self, *, mode: str, today: str) -> float:
        cur = self._db.execute(
            f"""SELECT COALESCE(SUM(notional), 0) FROM execution_records
                WHERE mode=? AND date(submitted_at)=?
                  AND status IN ({', '.join('?' for _ in _BUDGET_STATUSES)})""",
            (mode, today, *_BUDGET_STATUSES),
        )
        return float(cur.fetchone()[0])

    def today_traded_keys(self, *, mode: str, today: str) -> set[str]:
        cur = self._db.execute(
            f"""SELECT DISTINCT symbol || ':' || direction FROM execution_records
                WHERE mode=? AND date(submitted_at)=?
                  AND status IN ({', '.join('?' for _ in _BUDGET_STATUSES)})""",
            (mode, today, *_BUDGET_STATUSES),
        )
        return {r[0] for r in cur.fetchall()}

    # --- snapshots ---
    def save_account_snapshot(self, *, snapshot_time: str, mode: str,
                              total_asset: float, available_cash: float,
                              frozen_cash: float, market_value: float) -> None:
        self._db.execute(
            "INSERT INTO account_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (snapshot_time, mode, total_asset, available_cash, frozen_cash,
             market_value),
        )
        self._db.commit()

    def day_start_equity(self, *, mode: str, today: str) -> float | None:
        cur = self._db.execute(
            """SELECT total_asset FROM account_snapshots
               WHERE mode=? AND date(snapshot_time)=?
               ORDER BY snapshot_time ASC LIMIT 1""",
            (mode, today),
        )
        row = cur.fetchone()
        return float(row[0]) if row else None

    def load_account_series(self, *, mode: str, limit: int = 500) -> list[dict]:
        cur = self._db.execute(
            """SELECT * FROM account_snapshots WHERE mode=?
               ORDER BY snapshot_time DESC LIMIT ?""",
            (mode, limit),
        )
        return [dict(r) for r in reversed(cur.fetchall())]

    def save_position_snapshots(self, *, snapshot_time: str, mode: str,
                                rows: list[dict]) -> None:
        self._db.executemany(
            "INSERT INTO position_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(snapshot_time, mode, r["symbol"], r["total_volume"],
              r["available_volume"], r["average_cost"], r.get("last_price"))
             for r in rows],
        )
        self._db.commit()

    def load_latest_positions(self, *, mode: str) -> list[dict]:
        cur = self._db.execute(
            """SELECT * FROM position_snapshots WHERE mode=? AND snapshot_time=(
                 SELECT MAX(snapshot_time) FROM position_snapshots WHERE mode=?
               ) ORDER BY symbol""",
            (mode, mode),
        )
        return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 4.4: 跑测试至绿**；**Step 4.5: Commit** — `feat(persistence): TradingStore 交易留痕库 (循环/执行/快照/预算统计)`

---

### Task 5: DryRunTradeGateway（DD-2）

**Files:**
- Create: `src/infrastructure/gateway/dry_run_trade.py`
- Create: `tests/infrastructure/gateway_offline/test_dry_run_trade.py`（**新目录** `gateway_offline`，不依赖 xtquant，常规跑测不被 ignore；加空 `__init__.py` 不需要——pytest rootdir 约定与现有 tests 一致即可）

- [ ] **Step 5.1: 失败测试**

```python
from src.domain.trade.entities.order import Order
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.gateway.dry_run_trade import DryRunTradeGateway


class _FakeReal:
    def __init__(self):
        self.place_called = 0
    def place_order(self, order):
        self.place_called += 1
        return "real-1"
    def get_asset(self):
        return "ASSET"
    def get_positions(self):
        return ["POS"]


def _order() -> Order:
    return Order(order_id="x", account_id="", ticker="601006.SH",
                 direction=OrderDirection.BUY, price=5.0, volume=100,
                 type=OrderType.LIMIT)


class TestDryRunTradeGateway:
    def test_place_order_never_touches_real_gateway(self):
        real = _FakeReal()
        gw = DryRunTradeGateway(real)

        oid1, oid2 = gw.place_order(_order()), gw.place_order(_order())

        assert real.place_called == 0
        assert oid1.startswith("dry-") and oid1 != oid2

    def test_query_and_cancel_are_simulated(self):
        gw = DryRunTradeGateway(_FakeReal())
        oid = gw.place_order(_order())
        assert gw.query_order_status(oid) == "DRY_RUN"
        assert gw.cancel_order(oid) is True

    def test_reads_delegate_to_real(self):
        gw = DryRunTradeGateway(_FakeReal())
        assert gw.get_asset() == "ASSET"
        assert gw.get_positions() == ["POS"]
```

- [ ] **Step 5.2: 确认失败 → 实现**

```python
"""Dry-run 交易网关 — 读真实账户/持仓, 下单只记录不触达 QMT (纸面前向载体)。

设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-2
"""

from __future__ import annotations

import logging
from itertools import count

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.trade.entities.order import Order

logger = logging.getLogger(__name__)


class DryRunTradeGateway:
    """包装真实网关: 读操作透传, 写操作模拟。状态 DRY_RUN 为终态。"""

    def __init__(self, real_gateway) -> None:
        self._real = real_gateway
        self._seq = count(1)

    def place_order(self, order: Order) -> str:
        order_id = f"dry-{next(self._seq):06d}"
        logger.info(
            "[DRY-RUN] 模拟下单 %s: %s %s %d股 @ %.2f",
            order_id, order.ticker, order.direction.value, order.volume, order.price,
        )
        return order_id

    def query_order_status(self, order_id: str) -> str:
        return "DRY_RUN"

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_asset(self) -> Asset | None:
        return self._real.get_asset()

    def get_positions(self) -> list[Position]:
        return self._real.get_positions()
```

- [ ] **Step 5.3: 跑测试至绿**；**Step 5.4: Commit** — `feat(gateway): DryRunTradeGateway 纸面前向网关`

---

### Task 6: AutoTradeAppService — 循环编排核心（DD-1/DD-2）

**Files:**
- Create: `src/application/auto_trade_app.py`
- Create: `tests/application/test_auto_trade_app.py`

- [ ] **Step 6.1: 失败测试**（fake 协作者 + 假时钟 + 临时 TradingStore；逐场景）

```python
"""AutoTradeAppService 测试 — 全链路 dry-run、各闸拒单、预算/亏损/去重/超时撤单。"""
from datetime import datetime

import pytest

from src.application.auto_trade_app import AutoTradeAppService, AutoTradeConfig
from src.application.live_signal_service import SignalDisplay
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.common.services.audit_service import AuditService
from src.domain.market.value_objects.quote import Quote
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.infrastructure.persistence.repositories.audit_log_repository import (
    SqliteAuditLogRepository,
)
from src.infrastructure.persistence.trading_store import TradingStore

NOW = datetime(2026, 6, 10, 9, 35)  # 周三盘中


def _display(symbol="601006.SH", direction=SignalDirection.BUY,
             confidence=0.9, price=5.0, volume=100) -> SignalDisplay:
    return SignalDisplay(symbol=symbol, direction=direction, current_price=price,
                         suggested_price=price, suggested_volume=volume,
                         required_capital=price * volume, reason="test",
                         strategy_name="dual_ma", confidence_score=confidence)


class FakeSignalService:
    def __init__(self, displays):
        self._displays = displays
    def scan(self, strategy_name, symbols):
        return self._displays


class FakeQuotes:
    def __init__(self, quote=None):
        self._q = quote if quote is not None else Quote(
            symbol="601006.SH", last=5.0, bid1=4.99, ask1=5.01,
            prev_close=5.0, timestamp=NOW)
    def subscribe_first_tick(self, symbol, timeout=3.0):
        return self._q


class FakeTradeGateway:
    """模拟终态可编程的网关。"""
    def __init__(self, statuses=("FILLED",), place_id="gw-1"):
        self.placed: list = []
        self.canceled: list[str] = []
        self._statuses = list(statuses)
        self._place_id = place_id
    def place_order(self, order):
        self.placed.append(order)
        return self._place_id
    def query_order_status(self, order_id):
        return self._statuses.pop(0) if self._statuses else "ALIVE"
    def cancel_order(self, order_id):
        self.canceled.append(order_id)
        return True


class FakeAccount:
    def __init__(self, cash=100000.0, total=146000.0, positions=()):
        self._asset = Asset(account_id="t", total_asset=total,
                            available_cash=cash, frozen_cash=0.0)
        self._positions = list(positions)
    def get_asset(self):
        return self._asset
    def get_positions(self):
        return self._positions


def _service(tmp_path, *, displays, trade_gw=None, account=None,
             config=None, quote=None) -> tuple[AutoTradeAppService, TradingStore, FakeTradeGateway]:
    store = TradingStore(str(tmp_path / "t.db"))
    gw = trade_gw or FakeTradeGateway(statuses=("DRY_RUN",))
    svc = AutoTradeAppService(
        signal_service=FakeSignalService(displays),
        quote_fetcher=FakeQuotes(quote) if quote is not False else FakeQuotes(),
        trade_gateway=gw,
        account_gateway=account or FakeAccount(),
        store=store,
        audit=AuditService(SqliteAuditLogRepository(store.db)),
        config=config or AutoTradeConfig(mode="dry_run"),
        clock=lambda: NOW,
        sleep=lambda s: None,
    )
    return svc, store, gw


class TestHappyPath:
    def test_full_cycle_persists_everything(self, tmp_path):
        svc, store, gw = _service(tmp_path, displays=[_display()])

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert len(gw.placed) == 1
        cycles = store.load_cycles()
        assert cycles[0]["orders_submitted"] == 1 and cycles[0]["signals_generated"] == 1
        execs = store.load_executions()
        assert execs[0]["status"] == "DRY_RUN" and execs[0]["notional"] == 500.0
        assert store.day_start_equity(mode="dry_run", today="2026-06-10") == 146000.0

    def test_sell_signal_passes_with_position(self, tmp_path):
        pos = Position(account_id="t", ticker="601006.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        svc, store, gw = _service(
            tmp_path, displays=[_display(direction=SignalDirection.SELL)],
            account=FakeAccount(positions=[pos]))

        summary = svc.run_cycle()

        assert summary.orders_submitted == 1
        assert gw.placed[0].direction.value == "SELL"


class TestFiltersAndBudget:
    def test_low_confidence_filtered(self, tmp_path):
        svc, store, _ = _service(tmp_path, displays=[_display(confidence=0.5)])
        summary = svc.run_cycle()
        assert summary.orders_submitted == 0 and summary.signals_generated == 1

    def test_max_orders_per_cycle_truncates(self, tmp_path):
        displays = [_display(symbol=f"60000{i}.SH") for i in range(5)]
        svc, store, _ = _service(
            tmp_path, displays=displays,
            config=AutoTradeConfig(mode="dry_run", max_orders_per_cycle=2))
        summary = svc.run_cycle()
        assert summary.orders_submitted + summary.orders_rejected == 2

    def test_daily_notional_cap_rejects(self, tmp_path):
        svc, store, _ = _service(
            tmp_path, displays=[_display()],
            config=AutoTradeConfig(mode="dry_run", daily_notional_cap=400.0))
        summary = svc.run_cycle()
        execs = store.load_executions()
        assert summary.orders_rejected == 1
        assert "预算" in execs[0]["reject_reason"]

    def test_same_day_same_key_dedup(self, tmp_path):
        svc, store, gw = _service(tmp_path, displays=[_display()])
        svc.run_cycle()
        summary2 = svc.run_cycle()
        assert summary2.orders_submitted == 0 and len(gw.placed) == 1

    def test_daily_loss_blocks_buys_allows_sells(self, tmp_path):
        pos = Position(account_id="t", ticker="600000.SH",
                       total_volume=100, available_volume=100, average_cost=5.0)
        store = TradingStore(str(tmp_path / "t.db"))
        store.save_account_snapshot(snapshot_time=NOW.replace(hour=9, minute=31).isoformat(),
                                    mode="dry_run", total_asset=150000.0,
                                    available_cash=1e5, frozen_cash=0.0, market_value=5e4)
        gw = FakeTradeGateway(statuses=("DRY_RUN",))
        svc = AutoTradeAppService(
            signal_service=FakeSignalService([
                _display(symbol="601006.SH", direction=SignalDirection.BUY),
                _display(symbol="600000.SH", direction=SignalDirection.SELL),
            ]),
            quote_fetcher=FakeQuotes(), trade_gateway=gw,
            account_gateway=FakeAccount(total=146000.0, positions=[pos]),  # -2.67%
            store=store,
            audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run", daily_loss_limit_ratio=0.02),
            clock=lambda: NOW, sleep=lambda s: None)

        summary = svc.run_cycle()

        execs = {e["symbol"]: e for e in store.load_executions()}
        assert "亏损" in execs["601006.SH"]["reject_reason"]
        assert execs["600000.SH"]["status"] == "DRY_RUN"


class TestExecutionLifecycle:
    def test_timeout_cancels_order(self, tmp_path):
        gw = FakeTradeGateway(statuses=())  # 永远 ALIVE
        svc, store, _ = _service(
            tmp_path, displays=[_display()], trade_gw=gw,
            config=AutoTradeConfig(mode="dry_run", poll_timeout_seconds=0.0))

        svc.run_cycle()

        assert gw.canceled == ["gw-1"]
        assert store.load_executions()[0]["status"] == "TIMEOUT_CANCELED"

    def test_gate_rejection_recorded(self, tmp_path):
        svc, store, gw = _service(
            tmp_path, displays=[_display(symbol="300750.SZ")])
        summary = svc.run_cycle()
        assert summary.orders_rejected == 1 and not gw.placed
        assert "范围" in store.load_executions()[0]["reject_reason"]

    def test_scan_exception_finalizes_cycle_with_note(self, tmp_path):
        class Boom:
            def scan(self, strategy_name, symbols):
                raise RuntimeError("qmt down")
        store = TradingStore(str(tmp_path / "t.db"))
        svc = AutoTradeAppService(
            signal_service=Boom(), quote_fetcher=FakeQuotes(),
            trade_gateway=FakeTradeGateway(), account_gateway=FakeAccount(),
            store=store, audit=AuditService(SqliteAuditLogRepository(store.db)),
            config=AutoTradeConfig(mode="dry_run"),
            clock=lambda: NOW, sleep=lambda s: None)

        summary = svc.run_cycle()

        assert summary.orders_submitted == 0
        assert "qmt down" in store.load_cycles()[0]["note"]
```

- [ ] **Step 6.2: 确认失败 → 实现 `auto_trade_app.py`**

```python
"""自动交易循环编排 — 扫描→过滤→三层防线→下单→轮询→撤单→留痕。

脊柱复用已实测的 LiveSignalService(quant live 同路径), 安全闸复用
domain pre_trade_checks(与首单 ticket 同一实现)。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-1/DD-2
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from src.application.live_signal_service import LiveSignalService, SignalDisplay
from src.domain.common.services.audit_service import AuditService
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.services.pre_trade_checks import (
    check_daily_loss_block_buys,
    run_pre_trade_gates,
)
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.persistence.trading_store import TradingStore

logger = logging.getLogger(__name__)

_TERMINAL = ("FILLED", "CANCELED", "REJECTED", "DRY_RUN")
_AUDIT_USER = "auto-trade"


@dataclass(slots=True, kw_only=True)
class AutoTradeConfig:
    mode: str = "dry_run"               # dry_run | live
    strategy: str = "dual_ma"
    symbols: list[str] = field(default_factory=list)
    min_confidence: float = 0.6
    max_orders_per_cycle: int = 3
    per_order_notional_cap: float = 1500.0
    daily_notional_cap: float = 3000.0
    daily_loss_limit_ratio: float = 0.02
    poll_timeout_seconds: float = 30.0


@dataclass(slots=True, kw_only=True)
class CycleSummary:
    cycle_id: str
    mode: str
    signals_generated: int = 0
    orders_submitted: int = 0
    orders_rejected: int = 0
    orders_failed: int = 0
    notional_submitted: float = 0.0
    note: str = ""


class AutoTradeAppService:
    """单次循环可独立调用(--once), 守护模式由 TradingScheduler 周期触发。"""

    def __init__(
        self,
        *,
        signal_service: LiveSignalService,
        quote_fetcher,
        trade_gateway,
        account_gateway,
        store: TradingStore,
        audit: AuditService,
        config: AutoTradeConfig,
        clock: Callable[[], datetime] = datetime.now,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._signals = signal_service
        self._quotes = quote_fetcher
        self._trade = trade_gateway
        self._account = account_gateway
        self._store = store
        self._audit = audit
        self._cfg = config
        self._clock = clock
        self._sleep = sleep

    # ------------------------------------------------------------------ cycle
    def run_cycle(self) -> CycleSummary:
        now = self._clock()
        cycle_id = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        summary = CycleSummary(cycle_id=cycle_id, mode=self._cfg.mode)
        self._store.save_cycle_start(
            cycle_id=cycle_id, cycle_time=now.isoformat(),
            mode=self._cfg.mode, strategy=self._cfg.strategy,
        )
        self._audit.log_action(
            user_id=_AUDIT_USER, action="cycle_start", resource_type="TradingCycle",
            resource_id=cycle_id, details={"mode": self._cfg.mode,
                                           "strategy": self._cfg.strategy},
        )

        try:
            displays = self._signals.scan(self._cfg.strategy, self._cfg.symbols)
        except Exception as e:  # 扫描失败不杀循环, 留痕收口
            logger.error("信号扫描失败: %s", e, exc_info=True)
            summary.note = f"scan failed: {e}"
            self._finalize(summary)
            return summary

        summary.signals_generated = len(displays)
        candidates = self._select(displays, now)
        block_buys, asset = self._daily_loss_check(now)

        for d in candidates:
            record = self._execute_one(d, cycle_id, now, block_buys, asset)
            self._store.save_execution(record)
            match record["status"]:
                case "REJECTED":
                    summary.orders_rejected += 1
                case "FAILED":
                    summary.orders_failed += 1
                case _:
                    summary.orders_submitted += 1
                    summary.notional_submitted += record["notional"] or 0.0

        self._snapshot(now)
        self._finalize(summary)
        return summary

    # ------------------------------------------------------------ selection
    def _select(self, displays: list[SignalDisplay], now: datetime) -> list[SignalDisplay]:
        passed = [d for d in displays if d.confidence_score >= self._cfg.min_confidence]
        done = self._store.today_traded_keys(
            mode=self._cfg.mode, today=now.date().isoformat())
        fresh = [d for d in passed if f"{d.symbol}:{d.direction.value}" not in done]
        fresh.sort(key=lambda d: (0 if d.direction == SignalDirection.SELL else 1,
                                  -d.confidence_score))
        return fresh[: self._cfg.max_orders_per_cycle]

    def _daily_loss_check(self, now: datetime):
        asset = self._account.get_asset()
        day_start = self._store.day_start_equity(
            mode=self._cfg.mode, today=now.date().isoformat())
        if asset is None or day_start is None:
            return False, asset
        blocked = check_daily_loss_block_buys(
            day_start, asset.total_asset, limit_ratio=self._cfg.daily_loss_limit_ratio)
        if blocked:
            logger.warning("当日权益回撤超 %.1f%%, 本循环禁买",
                           self._cfg.daily_loss_limit_ratio * 100)
        return blocked, asset

    # ------------------------------------------------------------ execution
    def _execute_one(self, d: SignalDisplay, cycle_id: str, now: datetime,
                     block_buys: bool, asset) -> dict:
        direction = (OrderDirection.BUY if d.direction == SignalDirection.BUY
                     else OrderDirection.SELL)
        record = {
            "order_id": f"pre-{uuid.uuid4().hex[:10]}", "cycle_id": cycle_id,
            "mode": self._cfg.mode, "symbol": d.symbol,
            "direction": direction.value, "signal_price": d.suggested_price,
            "exec_price": None, "volume": d.suggested_volume, "notional": None,
            "status": "REJECTED", "reject_reason": None,
            "strategy_name": d.strategy_name, "confidence": d.confidence_score,
            "submitted_at": now.isoformat(), "final_status_at": None,
            "status_trail": "[]",
        }

        if block_buys and direction == OrderDirection.BUY:
            return self._reject(record, "当日亏损超限禁买 (仅放行卖出)")

        quote = self._quotes.subscribe_first_tick(d.symbol)
        available_volume = 0
        if direction == OrderDirection.SELL:
            positions = {p.ticker: p for p in self._account.get_positions()}
            pos = positions.get(d.symbol)
            available_volume = pos.available_volume if pos else 0
        gate = run_pre_trade_gates(
            symbol=d.symbol, direction=direction, volume=d.suggested_volume,
            quote=quote, now=now, max_notional=self._cfg.per_order_notional_cap,
            available_cash=asset.available_cash if asset else 0.0,
            available_volume=available_volume,
        )
        if not gate.passed:
            return self._reject(record, gate.reject_reason)

        spent = self._store.today_submitted_notional(
            mode=self._cfg.mode, today=now.date().isoformat())
        if spent + gate.notional > self._cfg.daily_notional_cap:
            return self._reject(
                record,
                f"当日预算耗尽: 已提交 {spent:.2f} + 本单 {gate.notional:.2f} "
                f"> 上限 {self._cfg.daily_notional_cap:.2f}")

        order = Order(
            order_id=f"auto-{uuid.uuid4().hex[:8]}", account_id="",
            ticker=d.symbol, direction=direction, price=gate.limit_price,
            volume=d.suggested_volume, type=OrderType.LIMIT,
            remark="auto-trade-v1",
        )
        record.update({"exec_price": gate.limit_price, "notional": gate.notional})
        try:
            order_id = str(self._trade.place_order(order))
        except OrderSubmitError as e:
            record.update({"status": "FAILED", "reject_reason": str(e)})
            self._audit_order(record, "place_order_failed")
            return record
        except Exception as e:
            logger.error("下单异常: %s", e, exc_info=True)
            record.update({"status": "FAILED", "reject_reason": str(e)})
            self._audit_order(record, "place_order_failed")
            return record

        record["order_id"] = order_id
        self._audit_order(record, "place_order")
        final, trail = self._poll(order_id)
        record.update({
            "status": final, "status_trail": json.dumps(trail, ensure_ascii=False),
            "final_status_at": self._clock().isoformat(),
        })
        return record

    def _poll(self, order_id: str) -> tuple[str, list[dict]]:
        trail: list[dict] = []
        deadline = self._clock().timestamp() + self._cfg.poll_timeout_seconds
        last: str | None = None
        while True:
            state = self._trade.query_order_status(order_id)
            if state and state != last:
                trail.append({"t": self._clock().isoformat(), "status": state})
                last = state
            if state in _TERMINAL:
                return state, trail
            if self._clock().timestamp() >= deadline:
                break
            self._sleep(2.0)
        # 超时: 主动撤单 (闸口约定, 不留隔夜意外敞口)
        if self._trade.cancel_order(order_id):
            self._audit.log_action(
                user_id=_AUDIT_USER, action="cancel_order", resource_type="Order",
                resource_id=order_id, details={"reason": "poll timeout"})
            return "TIMEOUT_CANCELED", trail
        logger.error("订单 %s 超时且撤单未受理, 需人工处理!", order_id)
        return "TIMEOUT_UNCANCELED", trail

    # ------------------------------------------------------------ persistence
    def _reject(self, record: dict, reason: str | None) -> dict:
        record.update({"status": "REJECTED", "reject_reason": reason})
        self._audit_order(record, "reject_order")
        return record

    def _audit_order(self, record: dict, action: str) -> None:
        self._audit.log_action(
            user_id=_AUDIT_USER, action=action, resource_type="Order",
            resource_id=record["order_id"],
            details={"symbol": record["symbol"], "direction": record["direction"],
                     "notional": record["notional"], "mode": record["mode"],
                     "reason": record["reject_reason"]})

    def _snapshot(self, now: datetime) -> None:
        asset = self._account.get_asset()
        if asset is not None:
            self._store.save_account_snapshot(
                snapshot_time=now.isoformat(), mode=self._cfg.mode,
                total_asset=asset.total_asset, available_cash=asset.available_cash,
                frozen_cash=asset.frozen_cash,
                market_value=asset.total_asset - asset.available_cash - asset.frozen_cash)
        positions = self._account.get_positions()
        if positions:
            self._store.save_position_snapshots(
                snapshot_time=now.isoformat(), mode=self._cfg.mode,
                rows=[{"symbol": p.ticker, "total_volume": p.total_volume,
                       "available_volume": p.available_volume,
                       "average_cost": p.average_cost, "last_price": None}
                      for p in positions])

    def _finalize(self, s: CycleSummary) -> None:
        self._store.finalize_cycle(
            cycle_id=s.cycle_id, signals_generated=s.signals_generated,
            orders_submitted=s.orders_submitted, orders_rejected=s.orders_rejected,
            orders_failed=s.orders_failed,
            notional_submitted=round(s.notional_submitted, 2), note=s.note)
        self._audit.log_action(
            user_id=_AUDIT_USER, action="cycle_end", resource_type="TradingCycle",
            resource_id=s.cycle_id,
            details={"submitted": s.orders_submitted, "rejected": s.orders_rejected,
                     "failed": s.orders_failed, "note": s.note})
        logger.info("循环 %s 完成: 信号=%d 提交=%d 拒绝=%d 失败=%d",
                    s.cycle_id, s.signals_generated, s.orders_submitted,
                    s.orders_rejected, s.orders_failed)
```

> 实现提示：`Asset` 字段为 `total_asset/available_cash/frozen_cash`（无 market_value 字段，快照里现算）；首循环 `day_start_equity` 为 None → 不禁买，本循环末写入首个快照成为次循环基准。`test_daily_loss_blocks_buys_allows_sells` 预置了 09:31 的快照作基准。

- [ ] **Step 6.3: 跑测试至绿** — `$WIN_PY -m pytest tests/application/test_auto_trade_app.py -q`
- [ ] **Step 6.4: Commit** — `feat(app): AutoTradeAppService 自动循环编排 (三层防线+轮询撤单+全程留痕)`

---

### Task 7: 配置扩展 + CLI 接线（DD-7/DD-8）

**Files:**
- Modify: `src/infrastructure/config/settings.py`（`AutoTradeSettings` 扩字段）
- Modify: `resources/trading.yaml`（加 `auto_trade` 段）
- Modify: `src/interfaces/cli/cli_utils.py`（迁入 `resolve_account_id`）
- Modify: `src/interfaces/cli/commands/order_cmd.py`（改为从 cli_utils 导入）
- Rewrite: `src/interfaces/cli/auto_trade.py`（骨架 → 完整接线）
- Modify: `src/interfaces/cli/quant.py`（auto-trade 子命令加 `--live`）
- Create: `tests/infrastructure/config/test_auto_trade_settings.py`

- [ ] **Step 7.1: 失败测试**（配置加载新字段 + live 降级判定）

```python
from src.infrastructure.config.settings import AutoTradeSettings
from src.interfaces.cli.auto_trade import resolve_mode


class TestAutoTradeSettings:
    def test_new_fields_have_safe_defaults(self):
        s = AutoTradeSettings()
        assert s.mode == "dry_run" and s.enabled is False
        assert s.per_order_notional_cap == 1500.0
        assert s.daily_notional_cap == 3000.0
        assert s.daily_loss_limit_ratio == 0.02
        assert s.poll_timeout_seconds == 30.0
        assert s.db_path == "data/trading.db"


class TestResolveMode:
    def test_live_requires_all_three_confirmations(self):
        s = AutoTradeSettings(mode="live", enabled=True)
        assert resolve_mode(s, live_flag=True) == "live"

    def test_missing_any_confirmation_downgrades(self):
        assert resolve_mode(AutoTradeSettings(mode="live", enabled=True),
                            live_flag=False) == "dry_run"
        assert resolve_mode(AutoTradeSettings(mode="live", enabled=False),
                            live_flag=True) == "dry_run"
        assert resolve_mode(AutoTradeSettings(mode="dry_run", enabled=True),
                            live_flag=True) == "dry_run"
```

- [ ] **Step 7.2: 扩展 `AutoTradeSettings`**（保留既有字段，追加）

```python
@dataclass(slots=True, kw_only=True)
class AutoTradeSettings:
    """自动交易配置。"""
    enabled: bool = False
    mode: str = "dry_run"               # dry_run | live (live 还需 CLI --live)
    strategy: str = "dual_ma"
    strategy_names: list[str] = field(default_factory=list)   # 兼容旧字段
    symbols: list[str] = field(default_factory=list)
    execution_times: list[str] = field(default_factory=lambda: ["09:35", "14:50"])
    max_orders_per_cycle: int = 3
    min_confidence: float = 0.6
    check_interval_seconds: int = 60
    per_order_notional_cap: float = 1500.0
    daily_notional_cap: float = 3000.0
    daily_loss_limit_ratio: float = 0.02
    poll_timeout_seconds: float = 30.0
    position_ratio: float = 0.1
    bar_lookback: int = 100
    db_path: str = "data/trading.db"
```

- [ ] **Step 7.3: trading.yaml 加段**（设计 DD-8 原文；symbols 全在主板白名单内）

```yaml
auto_trade:
  enabled: false              # 双保险: 配置 + CLI; live 模式还需 --live
  mode: dry_run               # dry_run | live
  strategy: dual_ma
  symbols: ["600000.SH", "601006.SH", "600096.SH", "000021.SZ"]
  execution_times: ["09:35", "14:50"]
  min_confidence: 0.6
  max_orders_per_cycle: 3
  per_order_notional_cap: 1500.0
  daily_notional_cap: 3000.0
  daily_loss_limit_ratio: 0.02
  poll_timeout_seconds: 30
  position_ratio: 0.1
  bar_lookback: 100
  db_path: "data/trading.db"
```

- [ ] **Step 7.4: `resolve_account_id` 迁入 `cli_utils.py`**（连同 `_mask` → `mask_account_id`；`order_cmd.py` 改 import，函数体不动；ticket 命令行为不变）
- [ ] **Step 7.5: 重写 `auto_trade.py`**

```python
"""自动交易 CLI 入口 — 完整接线 (dry-run 默认 / live 三重确认)。

用法:
    quant auto-trade --once                  # 单循环 (dry-run)
    quant auto-trade                          # 守护循环 (execution_times 触发)
    quant auto-trade --once --live            # live 还需配置 mode:live + enabled:true
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from src.infrastructure.config.settings import AutoTradeSettings, load_trading_config

logger = logging.getLogger(__name__)


def resolve_mode(settings: AutoTradeSettings, *, live_flag: bool) -> str:
    """live 三重确认: 配置 mode=live + 配置 enabled=true + CLI --live。"""
    if settings.mode == "live" and settings.enabled and live_flag:
        return "live"
    if settings.mode == "live" or live_flag:
        logger.warning("live 确认不齐全 (mode=%s enabled=%s --live=%s), 降级 dry_run",
                       settings.mode, settings.enabled, live_flag)
    return "dry_run"


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_service(settings, mode: str):
    """组装全部依赖 (需 QMT 客户端在线)。"""
    from src.application.auto_trade_app import AutoTradeAppService, AutoTradeConfig
    from src.application.live_signal_service import LiveSignalService
    from src.domain.common.services.audit_service import AuditService
    from src.domain.portfolio.services.sizers.fixed_ratio_sizer import FixedRatioSizer
    from src.infrastructure.gateway.dry_run_trade import DryRunTradeGateway
    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_realtime_quote import QmtRealtimeQuoteFetcher
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway
    from src.infrastructure.persistence.repositories.audit_log_repository import (
        SqliteAuditLogRepository,
    )
    from src.infrastructure.persistence.trading_store import TradingStore
    from src.interfaces.cli.cli_utils import resolve_account_id

    at = settings.auto_trade
    qmt = settings.qmt
    if not qmt.userdata_path:
        raise RuntimeError("QMT 路径未配置 (trading.yaml qmt.userdata_path)")

    account_id = resolve_account_id(qmt, qmt.userdata_path, qmt.session_id)
    real_gateway = QmtTradeGateway(
        path=qmt.userdata_path, session_id=qmt.session_id,
        account_id=account_id, account_type=qmt.account_type,
    )
    trade_gateway = real_gateway if mode == "live" else DryRunTradeGateway(real_gateway)

    store = TradingStore(at.db_path)
    signal_service = LiveSignalService(
        market_gateway=QmtMarketGateway(),
        account_gateway=real_gateway,
        trade_gateway=trade_gateway,
        sizer=FixedRatioSizer(ratio=at.position_ratio),
        bar_lookback=at.bar_lookback,
    )
    config = AutoTradeConfig(
        mode=mode, strategy=at.strategy, symbols=at.symbols,
        min_confidence=at.min_confidence,
        max_orders_per_cycle=at.max_orders_per_cycle,
        per_order_notional_cap=at.per_order_notional_cap,
        daily_notional_cap=at.daily_notional_cap,
        daily_loss_limit_ratio=at.daily_loss_limit_ratio,
        poll_timeout_seconds=at.poll_timeout_seconds,
    )
    return AutoTradeAppService(
        signal_service=signal_service,
        quote_fetcher=QmtRealtimeQuoteFetcher(),
        trade_gateway=trade_gateway,
        account_gateway=real_gateway,
        store=store,
        audit=AuditService(SqliteAuditLogRepository(store.db)),
        config=config,
    )


def main(args: argparse.Namespace | None = None) -> None:
    if args is None:
        parser = argparse.ArgumentParser(description="GoldenHandQuant 自动交易引擎")
        parser.add_argument("--config", default="resources/trading.yaml")
        parser.add_argument("--once", action="store_true", help="仅执行一次循环")
        parser.add_argument("--enable", action="store_true",
                            help="临时启用 (仅 dry-run 生效)")
        parser.add_argument("--live", action="store_true",
                            help="真实下单 (还需配置 mode:live + enabled:true)")
        args = parser.parse_args()

    _setup_logging()
    settings = load_trading_config(args.config)
    at = settings.auto_trade

    if not (at.enabled or args.enable):
        logger.error("自动交易未启用: 请配置 auto_trade.enabled: true 或加 --enable")
        sys.exit(1)

    mode = resolve_mode(at, live_flag=getattr(args, "live", False))
    logger.info("=== 自动交易引擎 === 模式=%s 策略=%s 标的=%s 执行时刻=%s",
                mode.upper(), at.strategy, ",".join(at.symbols), at.execution_times)
    if mode == "live":
        logger.warning(">>> LIVE 模式: 将提交真实订单! 单笔上限 ¥%.0f 日上限 ¥%.0f <<<",
                       at.per_order_notional_cap, at.daily_notional_cap)

    service = _build_service(settings, mode)

    if args.once:
        s = service.run_cycle()
        print(f"循环 {s.cycle_id} [{s.mode}]: 信号 {s.signals_generated} | "
              f"提交 {s.orders_submitted} | 拒绝 {s.orders_rejected} | "
              f"失败 {s.orders_failed} | 金额 ¥{s.notional_submitted:.2f}"
              + (f" | note: {s.note}" if s.note else ""))
        print(f"留痕: {at.db_path} (驾驶舱实盘页可视)")
        return

    from src.application.trading_scheduler import TradingScheduler
    scheduler = TradingScheduler(
        check_interval_seconds=at.check_interval_seconds,
        execution_times=at.execution_times,
    )
    scheduler.register_cycle_callback(lambda now: service.run_cycle())
    scheduler.start()
    logger.info("守护循环已启动 (Ctrl+C 停止)")

    def _shutdown(signum, frame):
        logger.info("收到停止信号, 正在关闭...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7.6: `quant.py` auto-trade 段加 `--live`**

```python
    p_at.add_argument("--live", action="store_true",
                      help="真实下单 (还需配置 mode:live + enabled:true)")
```

- [ ] **Step 7.7: 跑测试**（新配置测试 + ticket 回归）至绿；`$WIN_PY -m ruff check src/` 干净
- [ ] **Step 7.8: Commit** — `feat(cli): auto-trade 完整接线 — dry-run 默认/live 三重确认/守护循环 (闭环核心)`

---

### Task 8: 回测结果入库（DD-5）

**Files:**
- Modify: `src/infrastructure/persistence/market_data_store.py`（DDL + 两方法）
- Create: `src/infrastructure/persistence/backtest_run_mapper.py`
- Create: `tests/infrastructure/persistence/test_backtest_run_store.py`
- Modify: `src/interfaces/cli/run_backtest.py` 与 `src/interfaces/cli/compare_strategies.py`（跑完入库 + `--no-store`）

- [ ] **Step 8.1: 失败测试**

```python
from datetime import datetime

from src.domain.backtest.entities.backtest_report import BacktestReport
from src.infrastructure.persistence.backtest_run_mapper import build_backtest_run_row
from src.infrastructure.persistence.market_data_store import MarketDataStore


def _report() -> BacktestReport:
    return BacktestReport(
        start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31),
        initial_capital=100000.0, final_capital=112000.0,
        total_return=0.12, annualized_return=0.12, max_drawdown=0.08,
        win_rate=0.55, profit_loss_ratio=1.6, trade_count=42,
        dates=[datetime(2024, 1, 2), datetime(2024, 1, 3)],
        equity_curve=[100000.0, 100500.0], daily_returns=[0.0, 0.005],
        strategy_name="dual_ma",
    )


class TestBacktestRunMapper:
    def test_row_contains_metrics_and_curve(self):
        row = build_backtest_run_row(_report(), run_id="r1", params={"timeframe": "1d"})
        assert row["run_id"] == "r1" and row["strategy"] == "dual_ma"
        assert row["total_return"] == 0.12 and row["trade_count"] == 42
        assert row["sharpe_ratio"] == _report().sharpe_ratio
        import json
        curve = json.loads(row["equity_curve"])
        assert curve["dates"] == ["2024-01-02", "2024-01-03"]
        assert curve["values"] == [100000.0, 100500.0]


class TestBacktestRunStore:
    def test_insert_and_load_grouped_by_run(self):
        store = MarketDataStore(":memory:")
        row = build_backtest_run_row(_report(), run_id="r1", params={})
        store.insert_backtest_runs([row])

        runs = store.load_backtest_runs()

        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"
        assert runs[0]["strategies"][0]["strategy"] == "dual_ma"
        assert runs[0]["strategies"][0]["total_return"] == 0.12

    def test_same_run_id_two_strategies_grouped(self):
        store = MarketDataStore(":memory:")
        r1 = build_backtest_run_row(_report(), run_id="r1", params={})
        r2 = dict(r1, strategy="micro_value")
        store.insert_backtest_runs([r1, r2])

        runs = store.load_backtest_runs()

        assert len(runs) == 1 and len(runs[0]["strategies"]) == 2
```

- [ ] **Step 8.2: 实现 mapper**

```python
"""BacktestReport → backtest_runs 行映射（持久化口径单一来源）。"""

from __future__ import annotations

import json

from src.domain.backtest.entities.backtest_report import BacktestReport


def build_backtest_run_row(report: BacktestReport, *, run_id: str,
                           params: dict) -> dict:
    curve = {
        "dates": [d.strftime("%Y-%m-%d") for d in report.dates],
        "values": list(report.equity_curve),
    }
    return {
        "run_id": run_id,
        "strategy": report.strategy_name or "unknown",
        "start_date": report.start_date.strftime("%Y-%m-%d"),
        "end_date": report.end_date.strftime("%Y-%m-%d"),
        "initial_capital": report.initial_capital,
        "params": json.dumps(params, ensure_ascii=False),
        "total_return": report.total_return,
        "annualized_return": report.annualized_return,
        "max_drawdown": report.max_drawdown,
        "sharpe_ratio": report.sharpe_ratio,
        "sortino_ratio": report.sortino_ratio,
        "calmar_ratio": report.calmar_ratio,
        "win_rate": report.win_rate,
        "trade_count": report.trade_count,
        "turnover_rate": report.turnover_rate,
        "equity_curve": json.dumps(curve),
    }
```

- [ ] **Step 8.3: `MarketDataStore` 加 DDL 与方法**（DDL 追加到既有 `_SCHEMA` 列表末尾；方法挨着 `insert_verdicts/load_verdict_runs`，同模式）

```python
    """CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id VARCHAR, created_at TIMESTAMP, strategy VARCHAR,
        start_date DATE, end_date DATE, initial_capital DOUBLE,
        params VARCHAR,
        total_return DOUBLE, annualized_return DOUBLE, max_drawdown DOUBLE,
        sharpe_ratio DOUBLE, sortino_ratio DOUBLE, calmar_ratio DOUBLE,
        win_rate DOUBLE, trade_count INTEGER, turnover_rate DOUBLE,
        equity_curve VARCHAR,
        PRIMARY KEY (run_id, strategy)
    )""",
```

```python
    _BACKTEST_COLS = (
        "strategy", "start_date", "end_date", "initial_capital", "params",
        "total_return", "annualized_return", "max_drawdown", "sharpe_ratio",
        "sortino_ratio", "calmar_ratio", "win_rate", "trade_count",
        "turnover_rate", "equity_curve",
    )

    def insert_backtest_runs(self, rows: list[dict]) -> None:
        """一次回测(可多策略)的结果入库, 同 (run_id, strategy) 重写幂等。"""
        if not rows:
            return
        created_at = datetime.now()
        for r in rows:
            self._conn.execute(
                f"""INSERT OR REPLACE INTO backtest_runs
                    (run_id, created_at, {', '.join(self._BACKTEST_COLS)})
                    VALUES (?, ?, {', '.join('?' for _ in self._BACKTEST_COLS)})""",
                [r["run_id"], created_at, *[r.get(c) for c in self._BACKTEST_COLS]],
            )

    def load_backtest_runs(self, limit: int = 100) -> list[dict]:
        """按 run 分组, created_at 倒序。equity_curve/params 保持 JSON 字符串。"""
        rows = self._conn.execute(
            f"""SELECT run_id, created_at, {', '.join(self._BACKTEST_COLS)}
                FROM backtest_runs ORDER BY created_at DESC, strategy LIMIT ?""",
            [limit],
        ).fetchall()
        runs: dict[str, dict] = {}
        for row in rows:
            run_id = row[0]
            if run_id not in runs:
                runs[run_id] = {"run_id": run_id, "created_at": str(row[1]),
                                "strategies": []}
            runs[run_id]["strategies"].append(
                dict(zip(self._BACKTEST_COLS, row[2:], strict=True)))
        return list(runs.values())
```

> DuckDB `INSERT OR REPLACE` 需主键支持（已建 PK），与 `factor_verdicts` 同款。`datetime`/`json` 已在该模块 import。

- [ ] **Step 8.4: 跑测试至绿**
- [ ] **Step 8.5: CLI 入库钩子**：`run_backtest.py` 在打印摘要后加（先 Read 该文件确认 args 解析处加 `--no-store` 与 `--db` 默认 `data/market.duckdb`）：

```python
    if not args.no_store:
        from datetime import datetime as _dt

        from src.infrastructure.persistence.backtest_run_mapper import build_backtest_run_row
        from src.infrastructure.persistence.market_data_store import MarketDataStore

        run_id = f"{_dt.now():%Y%m%d-%H%M%S}"
        rows = [build_backtest_run_row(
                    r, run_id=run_id,
                    params={"symbols": backtest_symbols, "timeframe": str(tf),
                            "source": "run_backtest"})
                for r in reports]
        try:
            store = MarketDataStore(args.db)
            store.insert_backtest_runs(rows)
            store.close()
            print(f"结果已入库: backtest_runs run_id={run_id} ({len(rows)} 策略)")
        except Exception as e:
            print(f"⚠ 入库失败(不影响回测结果): {e}")
```

`compare_strategies.py` 同款钩子：Read 文件找到 reports 产出点（对比服务返回的各策略 report 集合），用同一 `run_id` 逐 report `build_backtest_run_row` 后一次 `insert_backtest_runs`；同样加 `--no-store/--db` 参数。
- [ ] **Step 8.6: 回归** — `$WIN_PY -m pytest tests/infrastructure/persistence/ -q` 绿
- [ ] **Step 8.7: Commit** — `feat(backtest): 回测结果自动入库 backtest_runs (run_backtest/compare 同款钩子)`

---

### Task 9: 驾驶舱 API — 回测页 + 实盘页（DD-6）

**Files:**
- Modify: `src/interfaces/api/routes/research.py`（加 `/api/research/backtests`）
- Create: `src/interfaces/api/routes/live.py`
- Modify: `src/interfaces/api/app.py`（注册 live router）
- Create: `tests/interfaces/api/test_live_routes.py`
- Modify: `tests/interfaces/api/test_research_routes.py`（加 backtests 用例）

- [ ] **Step 9.1: 失败测试 — research backtests**（沿用该文件现有 TestClient + 临时 DuckDB 注入模式，先 Read 现有 fixture）

```python
class TestBacktests:
    def test_returns_runs_with_parsed_curve(self, client_with_store):
        client, store = client_with_store
        from src.infrastructure.persistence.backtest_run_mapper import build_backtest_run_row
        # 构造 report 同 test_backtest_run_store._report()
        store.insert_backtest_runs([build_backtest_run_row(_report(), run_id="r1", params={})])

        resp = client.get("/api/research/backtests")

        assert resp.status_code == 200
        runs = resp.json()["runs"]
        assert runs[0]["strategies"][0]["equity_curve"]["values"] == [100000.0, 100500.0]

    def test_empty_db_returns_empty_runs(self, client_with_store):
        client, _ = client_with_store
        assert client.get("/api/research/backtests").json() == {"runs": []}
```

- [ ] **Step 9.2: research.py 加端点**（在现有端点旁，复用 `get_research_store` 依赖；`equity_curve`/`params` JSON 解析后返回）

```python
@router.get("/api/research/backtests")
def backtests(store: MarketDataStore | None = Depends(get_research_store)) -> dict:
    """历次回测结果 (倒序, 同 run 多策略并排)。"""
    if store is None:
        return {"runs": []}
    runs = store.load_backtest_runs()
    for run in runs:
        for s in run["strategies"]:
            s["equity_curve"] = json.loads(s["equity_curve"]) if s["equity_curve"] else {}
            s["params"] = json.loads(s["params"]) if s["params"] else {}
    return {"runs": runs}
```

- [ ] **Step 9.3: 失败测试 — live 路由**

```python
"""实盘只读端点测试 — 临时 trading.db 注入。"""
from datetime import datetime

from fastapi.testclient import TestClient

from src.interfaces.api.app import app
from src.interfaces.api.routes.live import get_trading_db_path
from src.infrastructure.persistence.trading_store import TradingStore

T0 = datetime(2026, 6, 10, 9, 35)


def _client(tmp_path, populate=True):
    db = str(tmp_path / "trading.db")
    if populate:
        s = TradingStore(db)
        s.save_cycle_start(cycle_id="c1", cycle_time=T0.isoformat(),
                           mode="dry_run", strategy="dual_ma")
        s.finalize_cycle(cycle_id="c1", signals_generated=2, orders_submitted=1,
                         orders_rejected=1, orders_failed=0,
                         notional_submitted=500.0)
        s.save_execution({
            "order_id": "o1", "cycle_id": "c1", "mode": "dry_run",
            "symbol": "601006.SH", "direction": "BUY", "signal_price": 5.0,
            "exec_price": 5.0, "volume": 100, "notional": 500.0,
            "status": "DRY_RUN", "reject_reason": None, "strategy_name": "dual_ma",
            "confidence": 0.9, "submitted_at": T0.isoformat(),
            "final_status_at": None, "status_trail": "[]"})
        s.save_account_snapshot(snapshot_time=T0.isoformat(), mode="dry_run",
                                total_asset=146000.0, available_cash=140000.0,
                                frozen_cash=0.0, market_value=6000.0)
        s.save_position_snapshots(snapshot_time=T0.isoformat(), mode="dry_run",
                                  rows=[{"symbol": "601006.SH", "total_volume": 100,
                                         "available_volume": 0, "average_cost": 5.05,
                                         "last_price": None}])
        s.close()
    app.dependency_overrides[get_trading_db_path] = lambda: db
    return TestClient(app)


class TestLiveRoutes:
    def test_overview(self, tmp_path):
        resp = _client(tmp_path).get("/api/live/overview")
        body = resp.json()
        assert body["db_exists"] is True
        assert body["latest_account"]["total_asset"] == 146000.0
        assert body["today" if "today" in body else "cycles_today"] is not None

    def test_cycles_and_executions(self, tmp_path):
        c = _client(tmp_path)
        assert c.get("/api/live/cycles").json()["cycles"][0]["cycle_id"] == "c1"
        execs = c.get("/api/live/executions").json()["executions"]
        assert execs[0]["symbol"] == "601006.SH"

    def test_positions_and_equity(self, tmp_path):
        c = _client(tmp_path)
        assert c.get("/api/live/positions").json()["positions"][0]["symbol"] == "601006.SH"
        assert len(c.get("/api/live/equity").json()["series"]) == 1

    def test_missing_db_explicit_empty_state(self, tmp_path):
        c = _client(tmp_path, populate=False)
        body = c.get("/api/live/overview").json()
        assert body["db_exists"] is False
```

> 测试收尾用 `app.dependency_overrides.clear()`（fixture finally 或 autouse），与 research 测试同款。

- [ ] **Step 9.4: 实现 `live.py` 路由**

```python
"""实盘留痕只读端点 — 读 data/trading.db (SQLite, 与交易进程 WAL 并发安全)。

驾驶舱实盘页消费; 不触 QMT、不做写操作。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-6
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends

router = APIRouter()


def get_trading_db_path() -> str:
    return os.environ.get("GHQ_TRADING_DB", "data/trading.db")


def _connect_ro(path: str) -> sqlite3.Connection | None:
    if not Path(path).exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


@router.get("/api/live/overview")
def overview(db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"db_exists": False, "latest_account": None, "cycles_today": 0,
                "executions_today": 0}
    try:
        today = date.today().isoformat()
        acct = _rows(conn, "SELECT * FROM account_snapshots "
                           "ORDER BY snapshot_time DESC LIMIT 1")
        cycles = conn.execute(
            "SELECT COUNT(*) FROM trading_cycles WHERE date(cycle_time)=?",
            (today,)).fetchone()[0]
        execs = conn.execute(
            "SELECT COUNT(*) FROM execution_records WHERE date(submitted_at)=?",
            (today,)).fetchone()[0]
        return {"db_exists": True, "latest_account": acct[0] if acct else None,
                "cycles_today": cycles, "executions_today": execs}
    finally:
        conn.close()


@router.get("/api/live/cycles")
def cycles(limit: int = 50, db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"cycles": []}
    try:
        return {"cycles": _rows(
            conn, "SELECT * FROM trading_cycles ORDER BY cycle_time DESC LIMIT ?",
            (limit,))}
    finally:
        conn.close()


@router.get("/api/live/executions")
def executions(limit: int = 200, db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"executions": []}
    try:
        return {"executions": _rows(
            conn, "SELECT * FROM execution_records "
                  "ORDER BY submitted_at DESC LIMIT ?", (limit,))}
    finally:
        conn.close()


@router.get("/api/live/positions")
def positions(db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"positions": [], "snapshot_time": None}
    try:
        rows = _rows(conn, """SELECT * FROM position_snapshots WHERE snapshot_time=(
                                SELECT MAX(snapshot_time) FROM position_snapshots)
                              ORDER BY symbol""")
        return {"positions": rows,
                "snapshot_time": rows[0]["snapshot_time"] if rows else None}
    finally:
        conn.close()


@router.get("/api/live/equity")
def equity(limit: int = 500, db_path: str = Depends(get_trading_db_path)) -> dict:
    conn = _connect_ro(db_path)
    if conn is None:
        return {"series": []}
    try:
        rows = _rows(conn, """SELECT * FROM (
                                SELECT * FROM account_snapshots
                                ORDER BY snapshot_time DESC LIMIT ?
                              ) ORDER BY snapshot_time ASC""", (limit,))
        return {"series": rows}
    finally:
        conn.close()
```

- [ ] **Step 9.5: app.py 注册**：`from src.interfaces.api.routes import live` + `app.include_router(live.router)`（紧挨 research 的 include）
- [ ] **Step 9.6: 跑 API 测试至绿** — `$WIN_PY -m pytest tests/interfaces/api/ -q`
- [ ] **Step 9.7: Commit** — `feat(api): 驾驶舱回测/实盘只读端点 (/api/research/backtests + /api/live/*)`

---

### Task 10: 驾驶舱前端 — 回测/实盘两页签

**Files:**
- Modify: `src/interfaces/api/static/index.html`（导航 + 两个 section）
- Modify: `src/interfaces/api/static/app.js`（两个视图的 fetch + 渲染）
- Modify: `src/interfaces/api/static/style.css`（仅必要的小补充）

- [ ] **Step 10.1: 先 Read 三个静态文件全文**，沿用现有页签注册/hash 路由/表格渲染/ECharts 初始化模式。
- [ ] **Step 10.2: index.html** — 导航加 `<a href="#/backtests">回测</a>` 与 `<a href="#/live">实盘</a>`；按现有 section 模板加：

```html
    <section id="view-backtests" class="view" hidden>
      <h2>回测结果</h2>
      <div id="backtest-runs"></div>
      <div id="backtest-chart" style="height:380px"></div>
    </section>
    <section id="view-live" class="view" hidden>
      <h2>实盘 / 纸面前向</h2>
      <div id="live-overview" class="cards"></div>
      <h3>账户权益</h3>
      <div id="live-equity-chart" style="height:260px"></div>
      <h3>当前持仓</h3>
      <div id="live-positions"></div>
      <h3>交易循环</h3>
      <div id="live-cycles"></div>
      <h3>执行记录</h3>
      <div id="live-executions"></div>
    </section>
```

- [ ] **Step 10.3: app.js** — 按现有 `loadXxx` 模式实现（要点，落地时对齐现有工具函数名）：
  - `loadBacktests()`：GET `/api/research/backtests` → 每 run 一组：标题 `run_id · created_at`，策略行（strategy/区间/total_return/annualized/max_dd/sharpe/sortino/win_rate/trade_count，百分比格式化、正绿负红）；行点击 → ECharts 折线渲染该策略 `equity_curve`（x=dates, y=values），多策略同 run 叠加对比；空态文案「暂无回测入库 — 跑 `python -m src.interfaces.cli.run_backtest` 后刷新」。
  - `loadLive()`：并发 GET overview/cycles/executions/positions/equity → overview 卡片（总资产/可用/今日循环数/今日执行数 + `db_exists=false` 时空态「暂无交易留痕 — 运行 quant auto-trade 后生成」）；equity 折线（snapshot_time × total_asset，按 mode 分色）；三张表（cycles: 时刻/模式/策略/信号/提交/拒绝/失败/金额；executions: 时间/标的/方向/价格/数量/金额/状态/拒因，REJECTED 红、FILLED 绿、DRY_RUN 蓝；positions: 标的/总量/可用/成本）；页签激活期间 `setInterval(loadLive, 5000)` 轮询，离开清除。
  - hash 路由表注册两个新视图，复用现有切换逻辑。
- [ ] **Step 10.4: 冒烟**：`$WIN_PY -m src.interfaces.cli.quant dashboard` 后 `curl -s http://127.0.0.1:8501/api/live/overview` 与 `/api/research/backtests` 返回 JSON；浏览器手测两页签（无数据空态 + 造数后渲染）。
- [ ] **Step 10.5: Commit** — `feat(dashboard): 回测/实盘两页签 (净值曲线+循环/执行/持仓/权益)`

---

### Task 11: 文档 + 全量验证 + 收尾

**Files:**
- Create: `docs/feat/0611-closed-loop/2026-06-12-morning-runbook.md`
- Modify: `README.md`、`CLAUDE.md`（命令与数据库说明）
- Modify: `docs/feat/0611-closed-loop/2026-06-11-closed-loop-plan.md`（勾掉 checkbox、记偏差）

- [ ] **Step 11.1: 晨间运行手册**（内容骨架——前置检查：QMT 客户端在线、`quant data status` 数据新鲜；步骤 1 盘中 dry-run：`quant auto-trade --once --enable` → 驾驶舱实盘页核对留痕；步骤 2 守护 dry-run 观察一整天；步骤 3（可选，edge 验证前不建议）live 首跑三重确认与回滚动作：Ctrl+C 停守护、QMT 客户端手工撤单、`enabled: false` 关总闸；附常见拒单原因对照表=闸文案）。
- [ ] **Step 11.2: README/CLAUDE.md** — 常用命令补 `quant auto-trade --once [--enable] [--live]`；数据库段补 `data/trading.db`（交易留痕）与 `backtest_runs` 表；dashboard 段补两新页签。
- [ ] **Step 11.3: 全量验证**

```bash
$WIN_PY -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q   # 期望: 全绿
$WIN_PY -m ruff check src/                                            # 期望: 无告警
```

- [ ] **Step 11.4: 端到端冒烟**（QMT 在线时）：`$WIN_PY -m src.interfaces.cli.quant auto-trade --once --enable` → 检查 `data/trading.db` 出现 cycle/快照行；非交易时段执行则预期产出「时段闸拒单」循环——同样证明接线达标。
- [ ] **Step 11.5: Commit + push** — `docs(closed-loop): 晨间运行手册 + README/CLAUDE 命令同步` → `git push`

---

## 自检结果（写计划时已跑）

- **Spec 覆盖**：R1→Task 6/7；R2→Task 5/6/7；R3→Task 2/6;R4→Task 4/6；R5→Task 8；R6→Task 9/10；R7→Task 11。DD-1~DD-8 全部有对应任务。
- **占位符**：无 TBD；Task 8.5(compare)/10.3(前端) 为「先 Read 再按既定模式落地」的集成点，函数签名与数据契约均已在本计划内完整定义。
- **类型一致性**：`GateResult.reject_reason`（Task 2 定义,Task 6 使用）✓；`TradingStore` 方法签名（Task 4 定义,Task 6/9 使用）✓；`SignalDisplay` 字段（既有代码,Task 6 使用）✓；`resolve_mode`（Task 7 定义与测试）✓。
