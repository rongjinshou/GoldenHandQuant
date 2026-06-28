# R1 网关接口契约补全 — 实施计划

> **For agentic workers:** 用 superpowers:subagent-driven-development 或 executing-plans 逐任务实施。步骤用 `- [ ]` 跟踪。

**Goal:** 把 `is_dry_run` / `query_order_status` / `cancel_order` 补进 `ITradeGateway` Protocol，`MockTradeGateway` 与 `QmtTradeGateway` 实现齐全，去掉 `auto_trade_app` 对 `is_dry_run` 的 `getattr` duck-typing —— 使任一 `ITradeGateway` 实现（含 Mock）都能跑 `AutoTradeAppService` 循环（同编排可测）。

**Architecture:** 纯增量扩展 domain Protocol + 各网关实现补齐 + 一处去 getattr。无业务行为变更，回归守门（现有测试逐位不变）。

**Tech Stack:** Python 3.13 `Protocol`，pytest，`$WIN_PYTHON`（WSL 调 Windows conda python）。

**回归基线命令（贯穿全程）:** `$WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q`

---

### Task 1: `ITradeGateway` Protocol 扩展三个成员

**Files:**
- Modify: `src/domain/trade/interfaces/gateways/trade_gateway.py`

- [ ] **Step 1: 改 Protocol** —— 全文替换为：

```python
from typing import Protocol

from src.domain.trade.entities.order import Order


class ITradeGateway(Protocol):
    """交易网关接口。

    负责向外部交易系统下单 / 查单 / 撤单。
    `is_dry_run` 标识该网关是否「不触达真实券商」（dry-run 包装、Mock 撮合 = True；
    QMT 实盘 = False），供 AutoTradeAppService 装配一致性校验用。
    """

    is_dry_run: bool

    def place_order(self, order: Order) -> str:
        """提交订单，返回委托编号；失败抛 OrderSubmitError。"""
        ...

    def query_order_status(self, order_id: str) -> str | None:
        """查询订单状态字符串（FILLED/CANCELED/REJECTED/...）；查不到返回 None。"""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """撤销委托，受理返回 True，否则 False。"""
        ...
```

- [ ] **Step 2: 验证 import 不破** —— Run: `$WIN_PYTHON -c "from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway; print('ok')"` —— Expected: `ok`

---

### Task 2: `MockTradeGateway` 实现 `is_dry_run` / `query_order_status` / `cancel_order`

**Files:**
- Modify: `src/infrastructure/mock/mock_trade.py`（类 `MockTradeGateway`，`self.orders: dict[str, Order]` 已存在于 `__init__`）
- Test: `tests/infrastructure/mock/test_mock_trade.py`

- [ ] **Step 1: 写失败测试**（追加到 `tests/infrastructure/mock/test_mock_trade.py`；若文件无 helper 则用现有 fixture 风格构造一个已成交订单）：

```python
def test_is_dry_run_true():
    gw = _make_gateway()  # 现有构造 MockTradeGateway 的 helper/fixture
    assert gw.is_dry_run is True

def test_query_order_status_returns_status_of_known_order(filled_order_id, gw):
    # filled_order_id: 经 gw.place_order 同步撮合后的订单 id
    assert gw.query_order_status(filled_order_id) == "FILLED"

def test_query_order_status_unknown_returns_none(gw):
    assert gw.query_order_status("nonexistent") is None

def test_cancel_order_returns_false_no_open_orders(filled_order_id, gw):
    # Mock 同步撮合, 提交即终态, 无挂单可撤
    assert gw.cancel_order(filled_order_id) is False
```

> 实施者注：`tests/infrastructure/mock/test_mock_trade.py` 已有构造 `MockTradeGateway`（注入 `MockMarketGateway` + 资金）并 `place_order` 成交的现成模式 —— 复用它产出 `gw` 与一个 `filled_order_id`，不要新造一套 fixture。

- [ ] **Step 2: 跑测试确认失败** —— Run: `$WIN_PYTHON -m pytest tests/infrastructure/mock/test_mock_trade.py -k "is_dry_run or query_order_status or cancel_order" -v` —— Expected: FAIL（`AttributeError: 'MockTradeGateway' object has no attribute 'is_dry_run'` / 无 `query_order_status`）

- [ ] **Step 3: 实现** —— 在 `MockTradeGateway` 类体加类属性（紧跟 `class MockTradeGateway(ITradeGateway, IAccountGateway):` 的 docstring 后）：

```python
    is_dry_run = True  # Mock 是模拟撮合, 不触达真实券商
```

并在 `place_order` 方法之后、`_calculate_costs` 之前加两个方法：

```python
    def query_order_status(self, order_id: str) -> str | None:
        order = self.orders.get(order_id)
        return order.status.value if order else None

    def cancel_order(self, order_id: str) -> bool:
        # 同步撮合: place_order 提交即进终态(FILLED/REJECTED/PARTIAL_CANCELED),
        # 无 SUBMITTED 挂单可撤 → 恒 False。
        return False
```

- [ ] **Step 4: 跑测试确认通过** —— Run: `$WIN_PYTHON -m pytest tests/infrastructure/mock/test_mock_trade.py -v` —— Expected: PASS（含新增 4 例）

---

### Task 3: `QmtTradeGateway` 补 `is_dry_run = False`

**Files:**
- Modify: `src/infrastructure/gateway/qmt_trade.py`（类 `QmtTradeGateway`，已有 `query_order_status`/`cancel_order`/`place_order`）

- [ ] **Step 1: 加类属性** —— 在 `QmtTradeGateway` 类 docstring 后加：

```python
    is_dry_run = False  # QMT 实盘网关, 触达真实券商
```

- [ ] **Step 2: 验证** —— Run: `$WIN_PYTHON -c "from src.infrastructure.gateway.qmt_trade import QmtTradeGateway; print(QmtTradeGateway.is_dry_run)"` —— Expected: `False`（若该 import 触发 xtquant 缺失，改用 `grep -n 'is_dry_run = False' src/infrastructure/gateway/qmt_trade.py` 确认存在即可）

---

### Task 4: `auto_trade_app` 去 `getattr` duck-typing

**Files:**
- Modify: `src/application/auto_trade_app.py:87`

- [ ] **Step 1: 替换** —— 把：

```python
        gateway_is_dry = bool(getattr(trade_gateway, "is_dry_run", False))
```

改为：

```python
        gateway_is_dry = bool(trade_gateway.is_dry_run)
```

- [ ] **Step 2: 跑 auto_trade 相关测试** —— Run: `$WIN_PYTHON -m pytest tests/application/test_auto_trade_app.py -v`（若文件名不同，先 `ls tests/application/ | grep auto_trade`）—— Expected: PASS

---

### Task 5: 全套回归 + Mock 跑 AutoTradeAppService 冒烟 + commit

- [ ] **Step 1: 全套回归** —— Run: `$WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q` —— Expected: 全绿，例数 = 基线 + 4（新增）

- [ ] **Step 2: 接口契约冒烟**（确认 Mock 现在满足完整 ITradeGateway 的三方法 + 属性，能被 auto_trade 消费）—— Run:

```bash
$WIN_PYTHON -c "
from src.infrastructure.mock.mock_trade import MockTradeGateway
for m in ('is_dry_run','place_order','query_order_status','cancel_order'):
    assert hasattr(MockTradeGateway, m), m
print('ITradeGateway 契约齐备')
"
```
Expected: `ITradeGateway 契约齐备`

- [ ] **Step 3: ruff** —— Run: `$WIN_PYTHON -m ruff check src/` —— Expected: All checks passed

- [ ] **Step 4: commit**:

```bash
git add src/domain/trade/interfaces/gateways/trade_gateway.py src/infrastructure/mock/mock_trade.py src/infrastructure/gateway/qmt_trade.py src/application/auto_trade_app.py tests/infrastructure/mock/test_mock_trade.py
git commit -m "refactor(R1): ITradeGateway 补 is_dry_run/query/cancel 契约 + Mock/QMT 实现 — 去 auto_trade getattr"
```

---

## 自审记录

- **Spec 覆盖**：对应 design DD-2（网关接口契约补全）。`get_stock_snapshots` 已在 `IMarketGateway` 接口、归一后死亡 → **不在 R1 处理**（R3 删 LiveSignalService 决策重写时一并评估移除），已在 design §六/§八注明。
- **签名一致**：`query_order_status -> str | None` 与现有 QMT(`str | None`)/DryRun(`str`) 兼容（`str` 是 `str | None` 子集）；`cancel_order -> bool` 三网关一致；`is_dry_run: bool` 三网关齐备（Mock=True/QMT=False/DryRun=True）。
- **无占位**：每步含真实代码/命令/预期。`_make_gateway`/`filled_order_id` 明确要求复用现有测试模式（非新造）。
- **回归守门**：Task 5 Step 1 全套例数 = 基线+4，纯增量不改业务行为。
