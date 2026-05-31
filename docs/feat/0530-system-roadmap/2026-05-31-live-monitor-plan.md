# 实盘监控面板 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现实盘监控面板 -- 连接 QMT 获取实时数据，计算持仓盈亏和风险指标，通过 rich 终端面板定时刷新展示，支持异常告警。

**Architecture:** 在现有 DDD 四层架构上增量扩展。Domain 层新增监控值对象和告警引擎；Application 层新增监控编排服务；Infrastructure 层新增快照持久化；Interfaces 层新增 CLI 监控入口。复用现有 `QmtTradeGateway`、`QmtMarketGateway` 和 `load_trading_config()`。

**Tech Stack:** Python 3.13+, pytest, ruff, dataclasses, rich, PyYAML, QMT/xtquant

**Spec:** `docs/feat/0530-system-roadmap/2026-05-31-live-monitor-design.md`

---

## 文件结构总览

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/domain/account/value_objects/position_detail.py` | 持仓明细值对象（含实时盈亏） |
| `src/domain/account/value_objects/monitor_snapshot.py` | 监控快照值对象 |
| `src/domain/risk/value_objects/risk_metrics.py` | 风险指标值对象 |
| `src/domain/risk/value_objects/alert.py` | 告警值对象 |
| `src/domain/risk/services/alert_engine.py` | 告警规则引擎 |
| `src/domain/risk/services/alert_rules/daily_loss_rule.py` | 单日亏损告警规则 |
| `src/domain/risk/services/alert_rules/stock_loss_rule.py` | 单只亏损告警规则 |
| `src/domain/risk/services/alert_rules/position_ratio_rule.py` | 仓位比例告警规则 |
| `src/domain/risk/services/alert_rules/concentration_rule.py` | 集中度告警规则 |
| `src/application/monitor_service.py` | 监控编排服务 |
| `src/interfaces/cli/live_monitor.py` | CLI 监控面板入口 |
| `src/infrastructure/snapshot/snapshot_store.py` | 快照持久化 |
| `tests/domain/risk/test_alert_engine.py` | 告警引擎单元测试 |
| `tests/application/test_monitor_service.py` | 监控服务单元测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/infrastructure/config/settings.py` | 新增 `MonitorSettings`、`MonitorAlertSettings` |
| `pyproject.toml` | 新增 `rich` 依赖 |
| `resources/trading.yaml` | 新增 `monitor` 配置节 |

---

## Task 1: 新增 rich 依赖 + 扩展配置

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/infrastructure/config/settings.py`
- Modify: `resources/trading.yaml`

- [ ] **Step 1: 在 pyproject.toml 中新增 rich 依赖**

在 `dependencies` 列表末尾追加：

```toml
"rich>=13.0",
```

- [ ] **Step 2: 新增 MonitorSettings 数据类**

在 `src/infrastructure/config/settings.py` 中新增：

```python
@dataclass(slots=True, kw_only=True)
class MonitorAlertSettings:
    daily_loss_threshold: float = 0.03
    stock_loss_threshold: float = 0.05
    position_ratio_max: float = 0.80
    position_ratio_min: float = 0.10
    concentration_max: float = 0.30


@dataclass(slots=True, kw_only=True)
class MonitorSettings:
    refresh_interval: int = 3
    snapshot_dir: str = "data/snapshots/"
    alerts: MonitorAlertSettings = field(default_factory=MonitorAlertSettings)
```

并在 `AppSettings` 中新增字段：

```python
monitor: MonitorSettings = field(default_factory=MonitorSettings)
```

同时在 `load_trading_config` 中加载 `monitor` 节：

```python
monitor_data = data.get("monitor", {})
alerts_data = monitor_data.pop("alerts", {})
monitor = MonitorSettings(
    alerts=MonitorAlertSettings(**alerts_data),
    **monitor_data,
)
```

并将其传入 `AppSettings(monitor=monitor, ...)`.

- [ ] **Step 3: 更新 resources/trading.yaml**

```yaml
monitor:
  refresh_interval: 3
  snapshot_dir: "data/snapshots/"
  alerts:
    daily_loss_threshold: 0.03
    stock_loss_threshold: 0.05
    position_ratio_max: 0.80
    position_ratio_min: 0.10
    concentration_max: 0.30
```

- [ ] **Step 4: 运行现有测试确认不破坏**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```

Expected: all pass

- [ ] **Step 5: 安装 rich**

```bash
pip install "rich>=13.0"
```

- [ ] **Step 6: 运行 lint**

```bash
ruff check src/infrastructure/config/settings.py
```

- [ ] **Step 7: 提交**

```bash
git add pyproject.toml src/infrastructure/config/settings.py resources/trading.yaml
git commit -m "feat: 新增 rich 依赖和监控配置 (MonitorSettings)"
```

---

## Task 2: Domain 值对象

**Files:**
- Create: `src/domain/account/value_objects/position_detail.py`
- Create: `src/domain/account/value_objects/monitor_snapshot.py`
- Create: `src/domain/risk/value_objects/risk_metrics.py`
- Create: `src/domain/risk/value_objects/alert.py`

- [ ] **Step 1: 实现 PositionDetail 值对象**

```python
# src/domain/account/value_objects/position_detail.py
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class PositionDetail:
    """持仓明细 — 包含实时盈亏计算。"""

    ticker: str
    total_volume: int
    available_volume: int
    average_cost: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.total_volume * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.average_cost) * self.total_volume

    @property
    def pnl_ratio(self) -> float:
        if self.average_cost <= 0:
            return 0.0
        return (self.current_price - self.average_cost) / self.average_cost
```

- [ ] **Step 2: 实现 RiskMetrics 值对象**

```python
# src/domain/risk/value_objects/risk_metrics.py
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class RiskMetrics:
    """风险指标快照。"""

    total_position_ratio: float    # market_value / total_asset
    max_concentration: float       # max(单只市值) / total_asset
    position_count: int
    today_drawdown: float = 0.0    # 当日回撤
```

- [ ] **Step 3: 实现 Alert 值对象**

```python
# src/domain/risk/value_objects/alert.py
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class Alert:
    """告警信息。"""

    level: str          # "WARNING" | "CRITICAL"
    category: str       # "LOSS" | "CONCENTRATION" | "POSITION"
    message: str
    value: float = 0.0
    threshold: float = 0.0
```

- [ ] **Step 4: 实现 MonitorSnapshot 值对象**

```python
# src/domain/account/value_objects/monitor_snapshot.py
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.risk.value_objects.alert import Alert
from src.domain.risk.value_objects.risk_metrics import RiskMetrics


@dataclass(slots=True, kw_only=True)
class MonitorSnapshot:
    """监控面板快照 — 聚合账户、持仓、风险的实时状态。"""

    timestamp: datetime
    asset: Asset
    positions: list[PositionDetail] = field(default_factory=list)
    risk_metrics: RiskMetrics = field(default_factory=lambda: RiskMetrics(
        total_position_ratio=0.0, max_concentration=0.0, position_count=0,
    ))
    alerts: list[Alert] = field(default_factory=list)
    yesterday_asset: float = 0.0

    @property
    def today_pnl(self) -> float:
        if self.yesterday_asset <= 0:
            return 0.0
        return self.asset.total_asset - self.yesterday_asset

    @property
    def today_pnl_ratio(self) -> float:
        if self.yesterday_asset <= 0:
            return 0.0
        return self.today_pnl / self.yesterday_asset

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions)
```

- [ ] **Step 5: 运行 lint**

```bash
ruff check src/domain/account/value_objects/ src/domain/risk/value_objects/
```

- [ ] **Step 6: 提交**

```bash
git add src/domain/account/value_objects/position_detail.py \
        src/domain/account/value_objects/monitor_snapshot.py \
        src/domain/risk/value_objects/risk_metrics.py \
        src/domain/risk/value_objects/alert.py
git commit -m "feat: 新增监控值对象 (PositionDetail, MonitorSnapshot, RiskMetrics, Alert)"
```

---

## Task 3: 告警规则引擎

**Files:**
- Create: `src/domain/risk/services/alert_engine.py`
- Create: `src/domain/risk/services/alert_rules/daily_loss_rule.py`
- Create: `src/domain/risk/services/alert_rules/stock_loss_rule.py`
- Create: `src/domain/risk/services/alert_rules/position_ratio_rule.py`
- Create: `src/domain/risk/services/alert_rules/concentration_rule.py`
- Create: `tests/domain/risk/test_alert_engine.py`

- [ ] **Step 1: 编写告警引擎单元测试**

```python
# tests/domain/risk/test_alert_engine.py
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.risk.services.alert_engine import AlertEngine
from src.domain.risk.services.alert_rules.concentration_rule import ConcentrationRule
from src.domain.risk.services.alert_rules.daily_loss_rule import DailyLossRule
from src.domain.risk.services.alert_rules.position_ratio_rule import PositionRatioRule
from src.domain.risk.services.alert_rules.stock_loss_rule import StockLossRule
from src.domain.risk.value_objects.risk_metrics import RiskMetrics


def _make_snapshot(
    total_asset: float = 1_000_000,
    yesterday_asset: float = 1_000_000,
    positions: list[PositionDetail] | None = None,
) -> MonitorSnapshot:
    return MonitorSnapshot(
        timestamp=datetime.now(),
        asset=Asset(account_id="test", total_asset=total_asset, available_cash=500_000),
        positions=positions or [],
        risk_metrics=RiskMetrics(
            total_position_ratio=0.5, max_concentration=0.1, position_count=1,
        ),
        yesterday_asset=yesterday_asset,
    )


class TestDailyLossRule:
    def test_no_alert_when_loss_below_threshold(self):
        rule = DailyLossRule(threshold=0.03)
        snapshot = _make_snapshot(total_asset=980_000, yesterday_asset=1_000_000)
        alert = rule.evaluate(snapshot)
        assert alert is None

    def test_alert_when_loss_exceeds_threshold(self):
        rule = DailyLossRule(threshold=0.03)
        snapshot = _make_snapshot(total_asset=960_000, yesterday_asset=1_000_000)
        alert = rule.evaluate(snapshot)
        assert alert is not None
        assert alert.level == "CRITICAL"
        assert alert.category == "LOSS"


class TestStockLossRule:
    def test_alert_when_stock_loss_exceeds_threshold(self):
        rule = StockLossRule(threshold=0.05)
        pos = PositionDetail(
            ticker="600000.SH", total_volume=500, available_volume=500,
            average_cost=10.0, current_price=9.0,
        )
        snapshot = _make_snapshot(positions=[pos])
        alert = rule.evaluate(snapshot)
        assert alert is not None
        assert "600000.SH" in alert.message


class TestPositionRatioRule:
    def test_alert_when_position_too_high(self):
        rule = PositionRatioRule(max_ratio=0.80, min_ratio=0.10)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.90, max_concentration=0.1, position_count=3,
        )
        alerts = rule.evaluate(snapshot)
        assert len(alerts) == 1
        assert alerts[0].category == "POSITION"

    def test_alert_when_position_too_low(self):
        rule = PositionRatioRule(max_ratio=0.80, min_ratio=0.10)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.05, max_concentration=0.05, position_count=1,
        )
        alerts = rule.evaluate(snapshot)
        assert len(alerts) == 1

    def test_no_alert_when_position_normal(self):
        rule = PositionRatioRule(max_ratio=0.80, min_ratio=0.10)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.50, max_concentration=0.1, position_count=3,
        )
        alerts = rule.evaluate(snapshot)
        assert len(alerts) == 0


class TestConcentrationRule:
    def test_alert_when_concentration_too_high(self):
        rule = ConcentrationRule(threshold=0.30)
        snapshot = _make_snapshot()
        snapshot.risk_metrics = RiskMetrics(
            total_position_ratio=0.5, max_concentration=0.35, position_count=2,
        )
        alert = rule.evaluate(snapshot)
        assert alert is not None
        assert alert.category == "CONCENTRATION"


class TestAlertEngine:
    def test_engine_aggregates_alerts_from_all_rules(self):
        engine = AlertEngine(rules=[
            DailyLossRule(threshold=0.03),
            StockLossRule(threshold=0.05),
        ])
        pos = PositionDetail(
            ticker="600000.SH", total_volume=500, available_volume=500,
            average_cost=10.0, current_price=9.0,
        )
        snapshot = _make_snapshot(
            total_asset=960_000, yesterday_asset=1_000_000, positions=[pos],
        )
        alerts = engine.check(snapshot)
        assert len(alerts) >= 2  # daily loss + stock loss
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/domain/risk/test_alert_engine.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: 实现告警规则**

先创建 `__init__.py`：

```bash
mkdir -p src/domain/risk/services/alert_rules
touch src/domain/risk/services/alert_rules/__init__.py
```

**DailyLossRule:**

```python
# src/domain/risk/services/alert_rules/daily_loss_rule.py
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class DailyLossRule:
    """单日亏损告警规则。"""

    def __init__(self, threshold: float = 0.03) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None:
        if snapshot.yesterday_asset <= 0:
            return None
        pnl_ratio = snapshot.today_pnl_ratio
        if pnl_ratio < -self._threshold:
            return Alert(
                level="CRITICAL",
                category="LOSS",
                message=f"单日亏损 {pnl_ratio:.2%}，超过阈值 {-self._threshold:.2%}",
                value=pnl_ratio,
                threshold=-self._threshold,
            )
        return None
```

**StockLossRule:**

```python
# src/domain/risk/services/alert_rules/stock_loss_rule.py
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class StockLossRule:
    """单只亏损告警规则。"""

    def __init__(self, threshold: float = 0.05) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None:
        for pos in snapshot.positions:
            if pos.pnl_ratio < -self._threshold:
                return Alert(
                    level="WARNING",
                    category="LOSS",
                    message=f"{pos.ticker} 亏损 {pos.pnl_ratio:.2%}，超过阈值 {-self._threshold:.2%}",
                    value=pos.pnl_ratio,
                    threshold=-self._threshold,
                )
        return None
```

**PositionRatioRule** (返回 list[Alert]):

```python
# src/domain/risk/services/alert_rules/position_ratio_rule.py
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class PositionRatioRule:
    """仓位比例告警规则。"""

    def __init__(self, max_ratio: float = 0.80, min_ratio: float = 0.10) -> None:
        self._max_ratio = max_ratio
        self._min_ratio = min_ratio

    def evaluate(self, snapshot: MonitorSnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        ratio = snapshot.risk_metrics.total_position_ratio
        if ratio > self._max_ratio:
            alerts.append(Alert(
                level="WARNING",
                category="POSITION",
                message=f"总仓位 {ratio:.1%} 超过上限 {self._max_ratio:.1%}",
                value=ratio,
                threshold=self._max_ratio,
            ))
        elif ratio < self._min_ratio:
            alerts.append(Alert(
                level="WARNING",
                category="POSITION",
                message=f"总仓位 {ratio:.1%} 低于下限 {self._min_ratio:.1%}",
                value=ratio,
                threshold=self._min_ratio,
            ))
        return alerts
```

**ConcentrationRule:**

```python
# src/domain/risk/services/alert_rules/concentration_rule.py
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class ConcentrationRule:
    """集中度告警规则。"""

    def __init__(self, threshold: float = 0.30) -> None:
        self._threshold = threshold

    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | None:
        concentration = snapshot.risk_metrics.max_concentration
        if concentration > self._threshold:
            return Alert(
                level="WARNING",
                category="CONCENTRATION",
                message=f"最大集中度 {concentration:.1%} 超过阈值 {self._threshold:.1%}",
                value=concentration,
                threshold=self._threshold,
            )
        return None
```

- [ ] **Step 4: 实现告警引擎**

```python
# src/domain/risk/services/alert_engine.py
from typing import Protocol

from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.alert import Alert


class AlertRule(Protocol):
    """告警规则协议。"""
    def evaluate(self, snapshot: MonitorSnapshot) -> Alert | list[Alert] | None: ...


class AlertEngine:
    """告警规则引擎 — 检查监控快照并生成告警列表。"""

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules = rules or []

    def check(self, snapshot: MonitorSnapshot) -> list[Alert]:
        alerts: list[Alert] = []
        for rule in self._rules:
            result = rule.evaluate(snapshot)
            if result is None:
                continue
            if isinstance(result, list):
                alerts.extend(result)
            else:
                alerts.append(result)
        return alerts
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/domain/risk/test_alert_engine.py -v
```

Expected: all pass

- [ ] **Step 6: 运行 lint**

```bash
ruff check src/domain/risk/services/alert_engine.py src/domain/risk/services/alert_rules/
```

- [ ] **Step 7: 提交**

```bash
git add src/domain/risk/services/alert_engine.py \
        src/domain/risk/services/alert_rules/ \
        tests/domain/risk/test_alert_engine.py
git commit -m "feat: 新增告警规则引擎 (AlertEngine + 4 条内置规则)"
```

---

## Task 4: 快照持久化

**Files:**
- Create: `src/infrastructure/snapshot/snapshot_store.py`

- [ ] **Step 1: 实现 SnapshotStore**

```python
# src/infrastructure/snapshot/snapshot_store.py
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SnapshotStore:
    """账户快照持久化 — 以 JSON 文件存储每日快照。"""

    def __init__(self, snapshot_dir: str = "data/snapshots/") -> None:
        self._dir = Path(snapshot_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, date: datetime, data: dict) -> None:
        """保存快照。"""
        path = self._dir / f"{date.strftime('%Y-%m-%d')}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Snapshot saved: %s", path)

    def load_latest(self) -> dict | None:
        """加载最近一个快照。"""
        files = sorted(self._dir.glob("*.json"), reverse=True)
        if not files:
            return None
        with open(files[0], encoding="utf-8") as f:
            return json.load(f)

    def load_by_date(self, date: datetime) -> dict | None:
        """按日期加载快照。"""
        path = self._dir / f"{date.strftime('%Y-%m-%d')}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
```

- [ ] **Step 2: 运行 lint**

```bash
ruff check src/infrastructure/snapshot/snapshot_store.py
```

- [ ] **Step 3: 提交**

```bash
git add src/infrastructure/snapshot/
git commit -m "feat: 新增快照持久化 (SnapshotStore)"
```

---

## Task 5: 监控编排服务

**Files:**
- Create: `src/application/monitor_service.py`
- Create: `tests/application/test_monitor_service.py`

- [ ] **Step 1: 编写监控服务单元测试**

```python
# tests/application/test_monitor_service.py
from datetime import datetime
from unittest.mock import MagicMock

from src.application.monitor_service import MonitorService
from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe


def _make_bar(symbol: str, close: float) -> Bar:
    return Bar(
        symbol=symbol, timeframe=Timeframe.DAY_1,
        timestamp=datetime.now(), open=close, high=close,
        low=close, close=close, volume=1000,
    )


class TestMonitorService:
    def _make_service(self):
        account_gw = MagicMock()
        market_gw = MagicMock()
        account_gw.get_asset.return_value = Asset(
            account_id="test", total_asset=1_000_000, available_cash=500_000,
        )
        account_gw.get_positions.return_value = [
            Position(
                account_id="test", ticker="600000.SH",
                total_volume=500, available_volume=500, average_cost=12.0,
            ),
        ]
        market_gw.get_recent_bars.return_value = [_make_bar("600000.SH", 13.0)]
        service = MonitorService(
            account_gateway=account_gw,
            market_gateway=market_gw,
            yesterday_asset=990_000,
        )
        return service, account_gw, market_gw

    def test_take_snapshot_should_return_valid_snapshot(self):
        service, _, _ = self._make_service()
        snapshot = service.take_snapshot()
        assert snapshot.asset.total_asset == 1_000_000
        assert len(snapshot.positions) == 1
        assert snapshot.positions[0].current_price == 13.0
        assert snapshot.positions[0].unrealized_pnl == 500.0  # (13-12)*500

    def test_take_snapshot_should_calculate_risk_metrics(self):
        service, _, _ = self._make_service()
        snapshot = service.take_snapshot()
        # market_value = 500 * 13 = 6500, total_asset = 1_000_000
        assert snapshot.risk_metrics.total_position_ratio == pytest.approx(0.0065, abs=0.001)
        assert snapshot.risk_metrics.position_count == 1

    def test_take_snapshot_no_market_data_should_use_cost(self):
        service, _, market_gw = self._make_service()
        market_gw.get_recent_bars.return_value = []
        snapshot = service.take_snapshot()
        # 无行情时应使用成本价
        assert snapshot.positions[0].current_price == 12.0

    def test_take_snapshot_should_include_today_pnl(self):
        service, _, _ = self._make_service()
        snapshot = service.take_snapshot()
        assert snapshot.today_pnl == 10_000  # 1_000_000 - 990_000
```

(注意：测试文件顶部需要 `import pytest`)

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/application/test_monitor_service.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 MonitorService**

```python
# src/application/monitor_service.py
import logging
from datetime import datetime

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.alert_engine import AlertEngine
from src.domain.risk.value_objects.risk_metrics import RiskMetrics

logger = logging.getLogger(__name__)


class MonitorService:
    """实盘监控编排服务。

    流程: 获取数据 → 计算盈亏 → 计算风险 → 触发告警 → 产出 MonitorSnapshot。
    """

    def __init__(
        self,
        account_gateway: IAccountGateway,
        market_gateway: IMarketGateway,
        alert_engine: AlertEngine | None = None,
        yesterday_asset: float = 0.0,
    ) -> None:
        self._account_gw = account_gateway
        self._market_gw = market_gateway
        self._alert_engine = alert_engine or AlertEngine()
        self._yesterday_asset = yesterday_asset

    def take_snapshot(self) -> MonitorSnapshot:
        """获取一次完整的监控快照。"""
        asset = self._account_gw.get_asset()
        if asset is None:
            asset = Asset(account_id="unknown")

        positions = self._account_gw.get_positions()
        position_details = self._build_position_details(positions)
        risk_metrics = self._calc_risk_metrics(asset, position_details)

        snapshot = MonitorSnapshot(
            timestamp=datetime.now(),
            asset=asset,
            positions=position_details,
            risk_metrics=risk_metrics,
            yesterday_asset=self._yesterday_asset,
        )

        snapshot.alerts = self._alert_engine.check(snapshot)
        return snapshot

    def _build_position_details(self, positions: list[Position]) -> list[PositionDetail]:
        """构建持仓明细，获取实时行情。"""
        details: list[PositionDetail] = []
        for pos in positions:
            current_price = self._fetch_price(pos.ticker, pos.average_cost)
            details.append(PositionDetail(
                ticker=pos.ticker,
                total_volume=pos.total_volume,
                available_volume=pos.available_volume,
                average_cost=pos.average_cost,
                current_price=current_price,
            ))
        return details

    def _fetch_price(self, ticker: str, fallback: float) -> float:
        """获取最新价，失败时回退到成本价。"""
        try:
            bars = self._market_gw.get_recent_bars(ticker, Timeframe.DAY_1, limit=1)
            if bars:
                return bars[-1].close
        except Exception:
            logger.debug("Failed to fetch price for %s, using cost", ticker)
        return fallback

    def _calc_risk_metrics(
        self, asset: Asset, positions: list[PositionDetail],
    ) -> RiskMetrics:
        """计算风险指标。"""
        total_asset = asset.total_asset
        if total_asset <= 0:
            return RiskMetrics(
                total_position_ratio=0.0, max_concentration=0.0,
                position_count=len(positions),
            )

        market_value = sum(p.market_value for p in positions)
        total_ratio = market_value / total_asset

        max_single = max((p.market_value for p in positions), default=0.0)
        concentration = max_single / total_asset

        return RiskMetrics(
            total_position_ratio=total_ratio,
            max_concentration=concentration,
            position_count=len(positions),
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/application/test_monitor_service.py -v
```

Expected: all pass

- [ ] **Step 5: 运行 lint**

```bash
ruff check src/application/monitor_service.py tests/application/test_monitor_service.py
```

- [ ] **Step 6: 提交**

```bash
git add src/application/monitor_service.py tests/application/test_monitor_service.py
git commit -m "feat: 新增监控编排服务 (MonitorService)"
```

---

## Task 6: CLI 监控面板入口

**Files:**
- Create: `src/interfaces/cli/live_monitor.py`

- [ ] **Step 1: 实现 CLI 监控面板**

```python
# src/interfaces/cli/live_monitor.py
"""
实盘监控面板。

使用方式:
    python -m src.interfaces.cli.live_monitor
    python -m src.interfaces.cli.live_monitor --interval 5
    python -m src.interfaces.cli.live_monitor --no-alert
"""

import argparse
import signal
import sys
import time
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.application.monitor_service import MonitorService
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.infrastructure.config.settings import load_trading_config
from src.infrastructure.snapshot.snapshot_store import SnapshotStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GoldenHandQuant 实盘监控面板")
    parser.add_argument(
        "--config", type=str, default="resources/trading.yaml",
        help="配置文件路径",
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=None,
        help="刷新间隔（秒），默认从配置读取",
    )
    parser.add_argument(
        "--yesterday-asset", type=float, default=None,
        help="昨日总资产（不读快照文件时使用）",
    )
    parser.add_argument(
        "--no-alert", action="store_true",
        help="禁用告警检查",
    )
    return parser.parse_args()


def _pnl_text(value: float, ratio: float = 0.0, show_ratio: bool = True) -> Text:
    """格式化盈亏文本，带颜色。"""
    color = "green" if value > 0 else ("red" if value < 0 else "white")
    sign = "+" if value > 0 else ""
    text = Text(f"{sign}{value:,.0f}", style=color)
    if show_ratio:
        text.append(f"  ({sign}{ratio:.2%})", style=color)
    return text


def _build_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return Panel(
        Text(f"GoldenHandQuant 实盘监控    {now}", style="bold cyan"),
        style="cyan",
    )


def _build_overview(snapshot: MonitorSnapshot) -> Panel:
    """构建账户概览面板。"""
    table = Table(show_header=True, header_style="bold", expand=True, box=None)
    table.add_column("总资产", justify="right")
    table.add_column("可用资金", justify="right")
    table.add_column("持仓市值", justify="right")
    table.add_column("今日盈亏", justify="right")

    pnl_val = snapshot.today_pnl
    pnl_ratio = snapshot.today_pnl_ratio
    pnl = _pnl_text(pnl_val, pnl_ratio)

    table.add_row(
        f"{snapshot.asset.total_asset:,.0f}",
        f"{snapshot.asset.available_cash:,.0f}",
        f"{snapshot.total_market_value:,.0f}",
        pnl,
    )
    return Panel(table, title="账户概览", border_style="cyan")


def _build_positions(snapshot: MonitorSnapshot) -> Panel:
    """构建持仓明细面板。"""
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("标的", style="cyan")
    table.add_column("数量", justify="right")
    table.add_column("可用", justify="right")
    table.add_column("成本价", justify="right")
    table.add_column("现价", justify="right")
    table.add_column("市值", justify="right")
    table.add_column("浮动盈亏", justify="right")
    table.add_column("盈亏%", justify="right")

    if not snapshot.positions:
        table.add_row("[dim]无持仓[/dim]", "", "", "", "", "", "", "")
    else:
        for pos in snapshot.positions:
            pnl_style = "green" if pos.unrealized_pnl > 0 else (
                "red" if pos.unrealized_pnl < 0 else "white"
            )
            sign = "+" if pos.unrealized_pnl > 0 else ""
            table.add_row(
                pos.ticker,
                f"{pos.total_volume:,}",
                f"{pos.available_volume:,}",
                f"{pos.average_cost:.2f}",
                f"{pos.current_price:.2f}",
                f"{pos.market_value:,.0f}",
                Text(f"{sign}{pos.unrealized_pnl:,.0f}", style=pnl_style),
                Text(f"{sign}{pos.pnl_ratio:.2%}", style=pnl_style),
            )

    return Panel(table, title="持仓明细", border_style="cyan")


def _build_risk(snapshot: MonitorSnapshot) -> Panel:
    """构建风险指标面板。"""
    rm = snapshot.risk_metrics
    table = Table(show_header=True, header_style="bold", expand=True, box=None)
    table.add_column("指标")
    table.add_column("数值", justify="right")

    table.add_row("总仓位", f"{rm.total_position_ratio:.1%}")
    table.add_row("最大集中度", f"{rm.max_concentration:.1%}")
    table.add_row("持仓数量", str(rm.position_count))
    if snapshot.yesterday_asset > 0:
        table.add_row("当日回撤", f"{snapshot.today_pnl_ratio:.2%}")

    return Panel(table, title="风险指标", border_style="yellow")


def _build_alerts(snapshot: MonitorSnapshot) -> Panel | None:
    """构建告警面板。"""
    if not snapshot.alerts:
        return None

    table = Table(show_header=False, expand=True, box=None)
    for alert in snapshot.alerts:
        style = "bold red" if alert.level == "CRITICAL" else "yellow"
        table.add_row(Text(f"[{alert.level}] {alert.message}", style=style))

    return Panel(table, title="告警", border_style="red")


def build_dashboard(snapshot: MonitorSnapshot) -> Layout:
    """构建完整监控面板布局。"""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_column(
        Layout(name="overview", size=7),
        Layout(name="positions"),
        Layout(name="bottom"),
    )
    layout["bottom"].split_row(
        Layout(name="risk", ratio=1),
        Layout(name="alerts", ratio=1),
    )

    layout["header"].update(_build_header())
    layout["overview"].update(_build_overview(snapshot))
    layout["positions"].update(_build_positions(snapshot))
    layout["risk"].update(_build_risk(snapshot))

    alert_panel = _build_alerts(snapshot)
    if alert_panel:
        layout["alerts"].update(alert_panel)
    else:
        layout["alerts"].update(Panel("[dim]无告警[/dim]", title="告警", border_style="green"))

    now = datetime.now().strftime("%H:%M:%S")
    layout["footer"].update(
        Panel(
            Text(f"刷新间隔: {parse_args.__wrapped_interval if hasattr(parse_args, '__wrapped_interval') else 3}s  |  "
                 f"按 Ctrl+C 退出  |  最后更新: {now}"),
            style="dim",
        )
    )

    return layout


def _load_yesterday_asset(args, settings, snapshot_store: SnapshotStore) -> float:
    """加载昨日总资产。"""
    if args.yesterday_asset is not None:
        return args.yesterday_asset

    data = snapshot_store.load_latest()
    if data and "total_asset" in data:
        return data["total_asset"]

    return 0.0


def main() -> None:
    args = parse_args()

    try:
        settings = load_trading_config(args.config)
    except FileNotFoundError:
        print(f"配置文件未找到: {args.config}")
        sys.exit(1)

    monitor_cfg = settings.monitor
    interval = args.interval or monitor_cfg.refresh_interval

    # 初始化基础设施
    from src.infrastructure.gateway.qmt_market import QmtMarketGateway
    from src.infrastructure.gateway.qmt_trade import QmtTradeGateway

    qmt = settings.qmt
    if not qmt.userdata_path:
        print("QMT 路径未配置。请在配置文件中设置 qmt.userdata_path。")
        sys.exit(1)

    print("连接 QMT...")
    try:
        market_gw = QmtMarketGateway()
        trade_gw = QmtTradeGateway(
            path=qmt.userdata_path,
            session_id=qmt.session_id,
            account_id=qmt.account_id,
            account_type=qmt.account_type,
        )
    except Exception as e:
        print(f"QMT 连接失败: {e}")
        sys.exit(1)

    # 初始化告警引擎
    from src.domain.risk.services.alert_engine import AlertEngine
    from src.domain.risk.services.alert_rules.concentration_rule import ConcentrationRule
    from src.domain.risk.services.alert_rules.daily_loss_rule import DailyLossRule
    from src.domain.risk.services.alert_rules.position_ratio_rule import PositionRatioRule
    from src.domain.risk.services.alert_rules.stock_loss_rule import StockLossRule

    alert_engine: AlertEngine
    if args.no_alert:
        alert_engine = AlertEngine(rules=[])
    else:
        acfg = monitor_cfg.alerts
        alert_engine = AlertEngine(rules=[
            DailyLossRule(threshold=acfg.daily_loss_threshold),
            StockLossRule(threshold=acfg.stock_loss_threshold),
            PositionRatioRule(max_ratio=acfg.position_ratio_max, min_ratio=acfg.position_ratio_min),
            ConcentrationRule(threshold=acfg.concentration_max),
        ])

    # 加载昨日资产
    snapshot_store = SnapshotStore(snapshot_dir=monitor_cfg.snapshot_dir)
    yesterday_asset = _load_yesterday_asset(args, settings, snapshot_store)

    # 初始化监控服务
    service = MonitorService(
        account_gateway=trade_gw,
        market_gateway=market_gw,
        alert_engine=alert_engine,
        yesterday_asset=yesterday_asset,
    )

    # 优雅退出
    running = True

    def _stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    # 首次快照
    snapshot = service.take_snapshot()

    console = Console()
    with Live(build_dashboard(snapshot), console=console, refresh_per_second=1) as live:
        while running:
            try:
                snapshot = service.take_snapshot()
                live.update(build_dashboard(snapshot))
            except Exception as e:
                console.print(f"[red]刷新失败: {e}[/red]")
            time.sleep(interval)

    # 退出时保存快照
    try:
        snapshot_store.save(datetime.now(), {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_asset": snapshot.asset.total_asset,
            "available_cash": snapshot.asset.available_cash,
            "market_value": snapshot.total_market_value,
            "positions": [
                {"ticker": p.ticker, "volume": p.total_volume,
                 "average_cost": p.average_cost, "close_price": p.current_price}
                for p in snapshot.positions
            ],
        })
    except Exception:
        pass

    print("监控已退出。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行 lint**

```bash
ruff check src/interfaces/cli/live_monitor.py
```

- [ ] **Step 3: 运行全量测试确认不破坏**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q
```

Expected: all pass

- [ ] **Step 4: 干运行 CLI 确认参数解析正常**

```bash
python -m src.interfaces.cli.live_monitor --help
```

Expected: 显示帮助信息

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/cli/live_monitor.py
git commit -m "feat: 新增实盘监控面板 CLI (live_monitor)"
```

---

## Task 7: 集成验证

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest tests/ --ignore=tests/infrastructure/gateway/ -v
```

Expected: all pass

- [ ] **Step 2: 运行 ruff lint**

```bash
ruff check src/
```

Expected: no errors

- [ ] **Step 3: 确认 rich 已安装**

```bash
python -c "import rich; print(rich.__version__)"
```

Expected: 版本号 >= 13.0

- [ ] **Step 4: 确认所有新模块可导入**

```bash
python -c "
from src.domain.account.value_objects.position_detail import PositionDetail
from src.domain.account.value_objects.monitor_snapshot import MonitorSnapshot
from src.domain.risk.value_objects.risk_metrics import RiskMetrics
from src.domain.risk.value_objects.alert import Alert
from src.domain.risk.services.alert_engine import AlertEngine
from src.domain.risk.services.alert_rules.daily_loss_rule import DailyLossRule
from src.domain.risk.services.alert_rules.stock_loss_rule import StockLossRule
from src.domain.risk.services.alert_rules.position_ratio_rule import PositionRatioRule
from src.domain.risk.services.alert_rules.concentration_rule import ConcentrationRule
from src.application.monitor_service import MonitorService
from src.infrastructure.snapshot.snapshot_store import SnapshotStore
from src.infrastructure.config.settings import MonitorSettings
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: 实盘监控面板完整实现"
```
