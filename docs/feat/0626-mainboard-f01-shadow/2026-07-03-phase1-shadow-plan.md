# 主板 F01 影子盘 · 阶段 1 实施计划

> **For agentic workers:** 按批次任务卡执行，TDD（测试先行→跑失败→实现→跑绿→commit）。
> 测试命令一律 `$WIN_PYTHON -m pytest ...`（WSL 无项目依赖），`WIN_PYTHON=/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`。
> golden 基线 ~1333 全绿；`ruff check src/` 干净。design：同目录 `2026-07-03-phase1-shadow-design.md`。

**Goal:** F01+趋势闸 dry-run 影子盘：主板宇宙装配、top_n=20 口径、风控闸重标定、数据健康守卫、决策快照留痕、离线一致性比对。

**Architecture:** 全部改动在 interfaces/application/infrastructure 装配与守卫层 + 2 处最小 domain 扩展（`FundamentalRegistry` 别名方法、`pre_trade_checks` ceiling 参数化、`IMarketGateway.ensure_ready`）。共享决策核心 `CrossSectionalStrategyRunner.evaluate` 仅加一个显式指数注入口（无行为变化）。

---

## 批次依赖

```
批A（并行，文件不相交）: A1 settings+DataHealthError | A2 pre_trade_checks ceiling | A3 registry 别名 | A4 qmt_market prev_close+ensure_ready+Protocol
批B（串行，依赖批A）:     先 B2 LiveSignalService params+clock+守卫+快照 → 后 B1 wiring 主板过滤+别名+fail-fast（B1 调用 B2 的新构造签名 strategy_params/assembly_meta，接口耦合不可并行）
批C（串行，依赖批B）:     C1 TradingStore 快照表 + auto_trade_app/CLI 全部接线
批D（并行，依赖批C）:     D1 trading.yaml 影子盘配置 | D2 shadow_consistency_check.py
批E（串行）:              E1 对抗验证+全量回归 → E2 端到端冒烟 → E3 runbook/report/memory
```

---

### A1 · AutoTradeSettings 新字段 + DataHealthError

**Files:** Modify `src/infrastructure/config/settings.py`；Create `src/application/data_health.py`；Test `tests/infrastructure/config/test_settings.py`

1. 失败测试（test_settings.py 加）：
```python
def test_auto_trade_new_fields_defaults():
    at = AutoTradeSettings()
    assert at.strategy_params == {}
    assert at.mainboard_only is False
    assert at.per_order_notional_ceiling == 5000.0

def test_load_trading_config_parses_shadow_fields(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text(
        "auto_trade:\n  strategy: micro_value\n  strategy_params:\n    top_n: 20\n"
        "  mainboard_only: true\n  per_order_notional_ceiling: 10000.0\n",
        encoding="utf-8")
    s = load_trading_config(str(p))
    assert s.auto_trade.strategy_params == {"top_n": 20}
    assert s.auto_trade.mainboard_only is True
    assert s.auto_trade.per_order_notional_ceiling == 10000.0
```
2. 实现：`AutoTradeSettings`（settings.py:150）加三字段（放 `db_path` 前）：
```python
    strategy_params: dict = field(default_factory=dict)   # 截面策略参数(如 top_n), 覆盖 registry 默认
    mainboard_only: bool = False                           # 宇宙装配层主板过滤(check_symbol_scope 口径)
    per_order_notional_ceiling: float = 5000.0             # 单笔金额硬顶(默认保持 0611 安全值)
```
`load_trading_config` 无需改（`**auto_trade_data` 透传）。
3. Create `src/application/data_health.py`：
```python
"""数据健康异常 — 区分「数据故障」与「策略无信号/合法清仓」(0626 阶段1 DD-4)。"""


class DataHealthError(RuntimeError):
    """宇宙/基本面/指数数据不满足决策前提: 本周期拒绝执行(不买不卖), 留痕收口。"""
```
4. 跑绿 → commit `feat(shadow): AutoTradeSettings 影子盘字段 + DataHealthError`

### A2 · pre_trade_checks ceiling 参数化

**Files:** Modify `src/domain/trade/services/pre_trade_checks.py`；Test `tests/domain/trade/services/test_pre_trade_checks.py`

1. 失败测试：
```python
def test_notional_cap_ceiling_default_unchanged():
    assert check_notional_cap(5001.0, cap=9000.0) is not None      # 默认硬顶 5000 仍生效

def test_notional_cap_ceiling_raised():
    assert check_notional_cap(7300.0, cap=9000.0, ceiling=10000.0) is None
    assert check_notional_cap(9500.0, cap=9000.0, ceiling=10000.0) is not None  # cap 仍约束

def test_run_pre_trade_gates_passes_ceiling():  # 用现有 gates 测试的 quote fixture, notional≈7300
    ...  # gate = run_pre_trade_gates(..., max_notional=9000.0, notional_ceiling=10000.0) → passed
```
2. 实现：`check_notional_cap(notional, *, cap, ceiling: float = MAX_NOTIONAL_CEILING)`，`effective = min(cap, ceiling)`；`run_pre_trade_gates` 加 kw 参数 `notional_ceiling: float = MAX_NOTIONAL_CEILING`，透传。既有调用零改动（默认值等价）。
3. 跑绿（含既有 pre_trade_checks 全部用例回归）→ commit

### A3 · FundamentalRegistry 别名方法

**Files:** Modify `src/domain/market/services/fundamental_registry.py`；Test `tests/domain/market/services/test_fundamental_registry.py`

1. 失败测试：`latest_date_at_or_before`（有更早日→返回最近一日；无→None；恰好当日→当日）；`alias_date`（别名后 `get_all_at_date(dst)` 返回同 symbol 集、snapshot.date == dst；src 无行→no-op；不污染 src 日数据）。
2. 实现（domain 纯逻辑，`dataclasses.replace` 复制快照改 date）：
```python
    def latest_date_at_or_before(self, date: datetime) -> datetime | None:
        """<= date 的最近快照日; 无则 None。live 装配 as-of 别名用(0626 阶段1 DD-5)。"""
        date_key = date.replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = [d for d in self._by_date if d <= date_key]
        return max(candidates) if candidates else None

    def alias_date(self, src: datetime, dst: datetime) -> int:
        """把 src 日快照以 dst 日期别名注册(live as-of 回退, 不动既有数据); 返回行数。"""
        rows = self.get_all_at_date(src)
        for snap in rows:
            self.register(replace(snap, date=dst))
        return len(rows)
```
（确认 `FundamentalSnapshot` 可 `replace`；若 frozen dataclass 直接可用。）
3. 跑绿 → commit

### A4 · QmtMarketGateway prev_close + ensure_ready + Protocol

**Files:** Modify `src/domain/market/interfaces/gateways/market_gateway.py`、`src/infrastructure/gateway/qmt_market.py`

1. Protocol（market_gateway.py）加默认方法（显式继承者自动获得）：
```python
    def ensure_ready(self) -> None:
        """行情源健康探针: 不可用抛 RuntimeError。默认无操作(Mock/回测源恒可用)。"""
        return None
```
2. qmt_market.py：
   - `get_recent_bars` 构造 Bar 处加 `prev_close=bars[-1].close if bars else 0.0`（前复权序列内前根 close，与 DuckDB 历史 bars 口径自洽；窗口首根 0.0 无碍——决策只用窗口内后段。消 LimitUpBreakPolicy 静默失效，design K9/DD-9）。
   - 加 `ensure_ready`：
```python
    def ensure_ready(self) -> None:
        """xtdata 服务健康探针(同 scripts/test_qmt_connection.py Step1 口径, 轻量不触发下载)。"""
        try:
            detail = xtdata.get_instrument_detail("000001.SZ")
        except Exception as e:
            raise RuntimeError(f"xtdata 行情服务探针异常: {e}") from e
        if not detail:
            raise RuntimeError(
                "xtdata 行情服务不可用(xtdatacenter 58610 未起?): "
                "诊断 $WIN_PYTHON scripts/test_qmt_connection.py; "
                "恢复: QMT 极简端确认行情面板有数据(非仅交易登录), 必要时重启重登")
```
3. gateway 测试目录在 golden ignore 内 → 无新单测（E2 冒烟验证）。`ruff check src/` → commit

### B1 · wiring：主板过滤 + as-of 别名 + fail-fast + strategy_params

**Files:** Modify `src/interfaces/cli/_auto_trade_wiring.py`；Test `tests/interfaces/cli/test_auto_trade_wiring.py`

1. 失败测试（现有 3 例保持绿；stub `registry_builder` 返回可控 (registry, universe)）：
```python
def test_mainboard_only_filters_universe_and_reports_sizes():
    # universe=['600000.SH','300001.SZ','000001.SZ','688001.SH'] + mainboard_only=True
    # → symbols == ['600000.SH','000001.SZ']; service.assembly_meta.universe_size==4, filtered_size==2

def test_mainboard_off_keeps_full_universe():  # 默认 False 行为回归

def test_strategy_params_top_n_overrides_registry_default():
    # at.strategy_params={'top_n':20} → sizer._n_symbols==20 且 service.strategy_params['top_n']==20

def test_fundamental_alias_when_today_missing():
    # registry 只有 D-3 行 → 装配后 registry.get_all_at_date(today) 非空; meta.staleness_days==3

def test_empty_universe_after_filter_raises_data_health():
    # 全宇宙无主板票 + mainboard_only=True → pytest.raises(DataHealthError)

def test_stale_fundamental_raises_data_health():
    # registry 最近行在 today-10d → DataHealthError(>7天)
```
2. 实现要点（cross_section 分支，按序）：
```python
    merged_params = {**config.default_params, **at.strategy_params}
    top_n = int(merged_params.get("top_n", 9))
    ...
    if at.mainboard_only:
        full_size = len(universe)
        universe = [s for s in universe if check_symbol_scope(s) is None]
    # as-of 别名(DD-5): 当日无 fundamental 行则回退最近一期
    today_dt = datetime.combine(end, time())      # end = today or date.today()
    staleness_days = 0
    fundamental_date = today_dt
    if not registry.get_all_at_date(today_dt):
        latest = registry.latest_date_at_or_before(today_dt)
        if latest is None:
            raise DataHealthError("fundamental registry 为空: market.duckdb 无可用基本面")
        staleness_days = (today_dt - latest).days
        if staleness_days > _MAX_FUNDAMENTAL_STALENESS_DAYS:   # = 7
            raise DataHealthError(f"基本面滞后 {staleness_days} 天(>{_MAX_FUNDAMENTAL_STALENESS_DAYS}), 先 data refresh")
        registry.alias_date(latest, today_dt)
        fundamental_date = latest
    if not symbols:
        raise DataHealthError("有效宇宙为空(过滤后/交集后): 数据故障或配置错误, 拒绝装配")
```
   `AssemblyMeta` dataclass（放本文件）：`universe_size, filtered_size, fundamental_date, staleness_days`；传 `LiveSignalService(assembly_meta=..., strategy_params=merged_params, ...)`。模块 docstring 更新（主板过滤/别名语义）。
3. 跑绿 → commit

### B2 · LiveSignalService：params/clock 注入 + scan 守卫 + ScanSnapshot

**Files:** Modify `src/application/live_signal_service.py`、`src/application/strategy_runner.py`（+3 行注入口）；Test `tests/application/test_live_signal_service.py`

1. `CrossSectionalStrategyRunner` 加显式指数注入口（无行为变化，避免守卫层与 runner 重复拉指数 bars，[[reuse-not-recompute]]）：
```python
    def prime_index_data(self, index_bars: list[Bar], as_of: datetime) -> None:
        """外部已拉取指数 bars 时显式注入, 跳过 evaluate 内的重复拉取。"""
        if index_bars:
            self.system_gate.set_index_data(index_bars)
        self._index_cache_date = as_of
```
2. `LiveSignalService.__init__` 加：`strategy_params: dict | None = None`、`clock: Callable[[], datetime] = datetime.now`、`assembly_meta=None`、`index_symbol: str = "000852.SH"`、`min_fundamental_rows: int = 500`；`self.last_snapshot: ScanSnapshot | None = None`。`scan`：`create_strategy(strategy_name, self.strategy_params)`（None 时不传，保持既有行为）。
3. `ScanSnapshot` dataclass（本文件）：`snapshot_time, strategy, universe_size, filtered_size, fundamental_date, fundamental_rows, staleness_days, index_bars_count, gate_passed, positions(list[dict]), total_asset, selection(list[str]), targets(list[dict]), data_health, note`。
4. `_scan_cross_sectional` 重写为守卫→注入→评估→快照（关键骨架）：
```python
    now = self.clock()
    # ---- DD-4 数据健康守卫(任一命中: 快照留痕 fault + 抛 DataHealthError, 本周期不买不卖)
    if not symbols:
        self._snapshot_fault(now, "宇宙为空")
        raise DataHealthError("宇宙为空: 装配失败或配置错误")
    rows = self.fundamental_registry.get_all_at_date(now) if self.fundamental_registry else []
    if len(rows) < self.min_fundamental_rows:
        self._snapshot_fault(now, f"当日基本面行数 {len(rows)} < {self.min_fundamental_rows}")
        raise DataHealthError(...)
    index_bars = self.market_gateway.get_recent_bars(self.index_symbol, Timeframe.DAY_1, 100)
    if len(index_bars) < 20:
        self._snapshot_fault(now, f"趋势闸指数 bars {len(index_bars)} < 20, 将静默 fail-open")
        raise DataHealthError(...)
    # ---- 决策(与原逻辑一致, 注入指数避免重拉; gate_passed 用同一 SystemRiskGate 判定)
    runner = CrossSectionalStrategyRunner(...)          # 原参数不变
    runner.prime_index_data(index_bars, now)
    gate_passed = runner.system_gate.check_gate(now).pass_buy
    targets, prices = runner.evaluate(DayContext(current_time=now, symbols=symbols, ...))
    # ---- 快照(决策的完整输入+输出, DD-7)
    positions = self.trade_gateway.get_positions()      # 与 runner 同源(dry_run 透传真账户)
    asset = self.trade_gateway.get_asset()
    self.last_snapshot = ScanSnapshot(..., gate_passed=gate_passed,
        positions=[{"symbol": p.ticker, "total_volume": p.total_volume,
                    "available_volume": p.available_volume, "average_cost": p.average_cost} ...],
        total_asset=asset.total_asset if asset else 0.0,
        selection=sorted({t.symbol for t in targets if t.direction == OrderDirection.BUY}),
        targets=[{"symbol": t.symbol, "direction": t.direction.value, "volume": t.volume,
                  "price": t.price, "strategy_name": t.strategy_name} for t in targets],
        data_health="ok", note="")
    return [self._target_to_display(t, prices) for t in targets]
```
   `check_gate` 幂等（纯读），先判后 evaluate 不改变行为；`universe_size/filtered_size/fundamental_date/staleness_days` 从 `assembly_meta` 取（None 时置 len(symbols)/0）。
5. 失败测试（复用现有 R4 测试的 fixture 风格；Mock gateways）：
   - `test_scan_empty_universe_raises_and_snapshots_fault`
   - `test_scan_insufficient_fundamental_rows_raises`（registry 行数 < min，构造 service 时 `min_fundamental_rows=3`、registry 只 2 行）
   - `test_scan_insufficient_index_bars_raises`（指数只 10 根 → fault 快照 + raises；**断言不产生任何 SELL display**）
   - `test_scan_gate_blocked_liquidation_allowed`（指数 25 根末根 < MA20、数据完好、有持仓 → 产出清仓 SELL、`last_snapshot.gate_passed is False`、`data_health == "ok"`——合法路径回归）
   - `test_scan_snapshot_captures_inputs_and_outputs`（正常调仓日：positions/total_asset/selection/targets 与 runner 输出一致）
   - `test_strategy_params_control_top_n`（params top_n=2 → selection ≤ 2）
   - `test_clock_injection`（clock 返回固定周二 → 与 datetime.now() 无关地复现选股；比对脚本的前提）
   - 既有 `test_scan_signal_consistency_with_backtest_runner` 保持绿（fixture 需补 min_fundamental_rows/指数 bars：给 MockMarketGateway 加 25 根指数 bars 或传 `min_fundamental_rows=1`——**选后者 + 显式指数 bars**，避免改变该测试的趋势闸语义：原 fixture 无指数 bars 是 fail-open，现在会触发守卫 → 补 25 根平走指数 bars 保持 pass_buy=True）
6. 跑绿（全部 test_live_signal_service.py）→ commit

### C1 · TradingStore 快照表 + 全链接线

**Files:** Modify `src/infrastructure/persistence/trading_store.py`、`src/application/auto_trade_app.py`、`src/interfaces/cli/auto_trade.py`；Test `tests/infrastructure/persistence/test_trading_store.py`、`tests/application/test_auto_trade_app.py`

1. `_SCHEMA` 加表：
```sql
CREATE TABLE IF NOT EXISTS signal_snapshots (
    cycle_id TEXT PRIMARY KEY, snapshot_time TEXT NOT NULL, mode TEXT NOT NULL,
    strategy TEXT NOT NULL, universe_size INTEGER, filtered_size INTEGER,
    fundamental_date TEXT, fundamental_rows INTEGER, staleness_days INTEGER,
    index_bars_count INTEGER, gate_passed INTEGER,
    positions_json TEXT DEFAULT '[]', total_asset REAL,
    selection_json TEXT DEFAULT '[]', targets_json TEXT DEFAULT '[]',
    data_health TEXT DEFAULT 'ok', note TEXT DEFAULT ''
)
```
   `save_signal_snapshot(row: dict)`（INSERT OR REPLACE，模式同 save_execution）、`load_signal_snapshots(limit=20)`、`load_signal_snapshot_by_date(date_str) -> dict | None`（`date(snapshot_time)=?` 最新一条）。TDD。
2. `AutoTradeConfig` 加 `per_order_notional_ceiling: float = 5000.0`；`_execute_guarded` 的 `run_pre_trade_gates(...)` 加 `notional_ceiling=self._cfg.per_order_notional_ceiling`。
3. `run_cycle`：scan 成功后与 except 分支均落快照：
```python
    def _save_scan_snapshot(self, cycle_id: str) -> None:
        snap = getattr(self._signals, "last_snapshot", None)
        if snap is None:
            return
        self._store.save_signal_snapshot({"cycle_id": cycle_id, ...json.dumps 序列化...})
        self._signals.last_snapshot = None    # 防跨周期陈旧快照重复落库
```
   成功路径在 `summary.signals_generated = len(displays)` 后调用；except 分支在 `summary.note = f"scan failed: {e}"` 后调用（fault 快照已由 B2 填充）。
4. CLI `_build_service`：`market_gateway = QmtMarketGateway()` 后**立即** `market_gateway.ensure_ready()`（fail-fast 早于 DuckDB 装配）；`AutoTradeConfig(..., per_order_notional_ceiling=at.per_order_notional_ceiling)`。
5. auto_trade_app 测试：mock signal_service 带 `last_snapshot` → run_cycle 后 store 里有快照行、cycle 正常 finalize；scan 抛 `DataHealthError` → note 含原因 + fault 快照落库 + 零下单。
6. 跑绿 → commit

### D1 · trading.yaml 影子盘配置

**Files:** Modify `resources/trading.yaml`（只动 `auto_trade:` 节；legacy `trading:` 节是死配置，勿动）
```yaml
auto_trade:
  enabled: false              # 双保险: 跑时 --enable
  mode: dry_run
  strategy: micro_value       # F01 影子盘(0626 阶段1); dual_ma 路径保留未删
  symbols: []                 # 必须留空→DuckDB 全市场宇宙(mainboard_only 过滤); 非空会交集缩宇宙!
  strategy_params:
    top_n: 20                 # gate PASS 口径(阶段0 report), 勿用 registry 默认 9
  mainboard_only: true        # 宇宙装配层主板过滤(check_symbol_scope 60/000/001)
  execution_times: ["09:35", "14:50"]
  min_confidence: 0.6         # 截面信号恒 1.0, 此闸对影子盘无效(只约束 bar 策略)
  max_orders_per_cycle: 48    # 调仓日 ≤20买+≤20+卖
  per_order_notional_cap: 9000.0        # ¥146k/20≈7.3k+余量
  per_order_notional_ceiling: 10000.0   # 显式抬硬顶(默认 5000 是 0611 首单安全值)
  daily_notional_cap: 320000.0          # 调仓日双向 ~2×146k+余量
  daily_loss_limit_ratio: 0.02
  poll_timeout_seconds: 30
  position_ratio: 0.1
  bar_lookback: 100
  db_path: data/trading.db
```
验证：`$WIN_PYTHON -c "from src.infrastructure.config.settings import load_trading_config; s=load_trading_config(); print(s.auto_trade)"` → commit

### D2 · scripts/shadow_consistency_check.py

**Files:** Create `scripts/shadow_consistency_check.py`

复用 `build_live_signal_service` 走**同一条装配+scan 路径**（零重复实现），仅换数据源与账户源：
```python
"""影子盘一致性比对 — dry-run 决策快照 vs DuckDB 离线同输入决策(0626 阶段1 DD-8)。

用法: $WIN_PYTHON scripts/shadow_consistency_check.py [--date 2026-07-08] [--db data/trading.db]
前提: market.duckdb 已 refresh 覆盖快照日(bars 到该日)。
唯一自由变量 = bars 源(QMT 实时 vs DuckDB 存量); fundamental/宇宙/持仓/资金/时钟均按快照重放。
"""
# 骨架:
# 1. TradingStore(db).load_signal_snapshot_by_date(date) → snap(无则报错退出; data_health!='ok' 提示跳过)
# 2. settings = load_trading_config(); at = settings.auto_trade  (同一配置重演装配口径)
# 3. 离线网关:
#    mkt = MockMarketGateway(); fetcher = DuckDBHistoryDataFetcher()
#    先 build_live_signal_service(at, market_gateway=mkt, account_gateway=stub, trade_gateway=stub,
#        today=快照日, clock 经 service 属性覆盖)  → (service, symbols)
#    for sym in symbols + [service.index_symbol]: mkt.load_bars(fetcher.fetch_history_bars(sym, start, 快照日))
#      (套路同 scripts/mainboard_f01_gate.py run(); start=快照日-1年足够 120 根窗口)
# 4. stub gateways(脚本内类): get_positions→由 snap.positions_json 重建 Position;
#    get_asset→Asset(total_asset=snap.total_asset, ...); is_dry_run→True; place_order 不会被调用
# 5. service.clock = lambda: datetime.fromisoformat(snap.snapshot_time)
#    displays = service.scan(at.strategy, symbols) → offline = service.last_snapshot
# 6. diff:
#    sel_diff = set(snap.selection) ^ set(offline.selection)
#    tgt_diff = 逐位比 (symbol, direction, volume)  [price 不比: 前复权基准日漂移, design DD-8 白名单]
#    gate_diff = snap.gate_passed != offline.gate_passed
# 7. 报告: 打印 + json.dump 到 data/shadow_checks/{date}.json
#    exit 0 = 全一致; exit 1 = 有 diff(打印白名单提示: 别名滞后/盘中bar/复权基准)
```
Position/Asset 构造字段以 domain 实体定义为准（`Position(ticker=..., total_volume=..., available_volume=..., average_cost=...)`）。验证：脚本 `--help` 可跑、对无快照日给出清晰报错 → commit

### E1 · 对抗验证 + 全量回归

1. 3 维对抗审查（并行）：①回归审计（改动是否破坏既有 bar 路径/R4 一致性/gate 脚本）②决策正确性（守卫是否漏路径：universe 空但 registry 有行？别名与比对脚本口径互洽？ceiling 生效链路完整？）③边界（非周二/空仓月/闸阻断/QMT 断连各落哪条路径，快照与留痕是否可辨识）。发现即修。
2. `$WIN_PYTHON -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q` 全绿（基线 ~1333 + 新增）；`ruff check src/` 干净 → commit（若有修复）

### E2 · 端到端冒烟（QMT 已在线）

1. `$WIN_PYTHON -m src.interfaces.cli.quant data refresh --start-date 2026-06-12 --end-date 2026-07-03`（增量补 bars+fundamental 缺口）
2. `$WIN_PYTHON -m src.interfaces.cli.quant auto-trade --once --enable`（dry_run）——预期：探针过 → 装配（主板宇宙 ~1885、别名滞后 ≤1）→ 今天周四非调仓日 → hold 语义 targets → 快照落库 data_health=ok
3. `$WIN_PYTHON scripts/shadow_consistency_check.py` → diff 报告（预期 0 diff 或白名单内）
4. 负路径验证（可选）：断言 fault 快照机制 —— 用 `--config` 指向 tmp yaml（symbols 交集空）确认 DataHealthError 留痕不清仓

### E3 · runbook + report + memory

1. `docs/feat/0611-closed-loop/2026-06-12-morning-runbook.md` 补「影子盘周二流程」（design DD-10 五步）+「行情断/交易通」故障条目（症状=探针 fail-fast 文案，处置=test_qmt_connection→极简端行情重连）
2. 阶段 1 report：`docs/feat/0626-mainboard-f01-shadow/2026-07-03-phase1-shadow-report.md`（成果/验证/冒烟数据/已知白名单差异/下一步=攒周二样本→真单 Spec 前置）
3. memory 更新：`factor-funnel-status`（阶段 1 落地）、`architecture-unification`（如涉及）
4. 最终 commit
