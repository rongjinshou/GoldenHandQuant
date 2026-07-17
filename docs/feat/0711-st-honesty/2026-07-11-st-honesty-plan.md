# ST 诚实债清偿（E3/DD-6）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给回测引擎接上时点正确的 ST 状态（深市官方简称变更流 + 沪市巨潮公告推断，带交叉验证准入），修齐撮合 ±5%、涨停破板、选股过滤三个消费点，并用 F01 重验产出过闸判据 G7。

**Architecture:** 数据侧：`st_status_periods` 区间表（market.duckdb）← 两条管道（纯函数推导，I/O 薄壳）；注入侧：loader 把区间稠密展开成既有 `StockStatusRegistry`（domain 零改动），沿 `BacktestAppService → CrossSectionalStrategyRunner → build_cross_section / LimitUpBreakPolicy / MockTradeGateway` 三点消费；实盘路径零改动。

**Tech Stack:** Python 3.13、akshare（`stock_info_sz_change_name` / `stock_zh_a_disclosure_report_cninfo`）、DuckDB、pytest AAA。

## Global Constraints

- **不 commit**（延续 1-3 轮：共享文件改动交错，提交由用户统一裁量）；"提交"步骤以"标记任务完成"替代
- 测试/脚本用 WSL python：`/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python`
- domain 纯净红线：`st_prefixes`/`suspension` 属 domain（纯）；akshare/duckdb 只出现在 infrastructure/scripts
- **实盘路径零改动**：`_auto_trade_wiring` / `live_signal_service` / QMT 网关不碰；`CrossSectionalStrategyRunner.status_registry` 默认 None（auto-trade 装配不传 → 行为不变）
- ST 前缀单一事实源：`("S*ST", "*ST", "SST", "ST")`（判定与剥除都按最长优先）
- 窗口常量：回填全史入库；loader 展开窗口 = 调用方回测窗口
- 沪市管道准入门：交叉验证 ≥90% 事件误差 ≤2 交易日且无 >1 天系统性偏差，不达标不入库

---

### Task 1: ST 前缀单一事实源 `st_prefixes`

**Files:**
- Create: `src/domain/market/value_objects/st_prefixes.py`
- Modify: `src/domain/strategy/services/filters/filter_st.py`（前缀改引常量）
- Modify: `src/domain/trade/services/pre_trade_checks.py:52`（同）
- Test: `tests/domain/market/test_st_prefixes.py`

**Interfaces:**
- Produces: `ST_NAME_PREFIXES: tuple[str, ...] = ("S*ST", "*ST", "SST", "ST")`；`is_st_name(name: str) -> bool`；`correct_st_name(name: str, is_st: bool) -> str`

- [ ] **Step 1: 失败测试**

```python
"""ST 前缀单一事实源: 判定/双向修正(设计 0711-st-honesty §4.4)。"""
from src.domain.market.value_objects.st_prefixes import (
    ST_NAME_PREFIXES,
    correct_st_name,
    is_st_name,
)


class TestIsStName:
    def test_all_prefixes_and_case(self):
        assert is_st_name("ST海虹")
        assert is_st_name("*ST金科")
        assert is_st_name("SST前锋")
        assert is_st_name("S*ST北亚")
        assert is_st_name("st小写")  # 与 filter_st 既有 upper() 口径一致

    def test_normal_names(self):
        assert not is_st_name("海虹控股")
        assert not is_st_name("金科股份")


class TestCorrectStName:
    def test_add_prefix_when_registry_says_st(self):
        assert correct_st_name("金科股份", is_st=True) == "ST金科股份"

    def test_strip_longest_prefix_when_registry_says_clean(self):
        assert correct_st_name("*ST金科", is_st=False) == "金科"
        assert correct_st_name("S*ST北亚", is_st=False) == "北亚"

    def test_noop_when_already_consistent(self):
        assert correct_st_name("ST海虹", is_st=True) == "ST海虹"
        assert correct_st_name("海虹控股", is_st=False) == "海虹控股"


def test_prefixes_longest_first():
    assert ST_NAME_PREFIXES == ("S*ST", "*ST", "SST", "ST")
```

- [ ] **Step 2: 跑红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/domain/market/test_st_prefixes.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""ST 风险警示名称前缀 — 单一事实源。

消费方: domain/strategy filter_st(选股过滤)、domain/trade check_st_name(实时闸)、
回测截面名称修正(0711-st-honesty §4.4)。判定与剥除均按最长优先。
"""

ST_NAME_PREFIXES: tuple[str, ...] = ("S*ST", "*ST", "SST", "ST")


def is_st_name(name: str) -> bool:
    return name.upper().startswith(ST_NAME_PREFIXES)


def correct_st_name(name: str, *, is_st: bool) -> str:
    """按 as-of ST 状态修正名称前缀(名称仅作 ST 布尔语义载体)。"""
    if is_st:
        return name if is_st_name(name) else f"ST{name}"
    upper = name.upper()
    for prefix in ST_NAME_PREFIXES:
        if upper.startswith(prefix):
            return name[len(prefix):]
    return name
```

`filter_st.py` 改为：

```python
from src.domain.market.value_objects.st_prefixes import is_st_name
from src.domain.market.value_objects.stock_snapshot import StockSnapshot


def filter_st(snapshots: list[StockSnapshot]) -> list[StockSnapshot]:
    """剔除 ST 或 *ST 等风险警示股。"""
    return [s for s in snapshots if not is_st_name(s.name)]
```

`pre_trade_checks.py:52` 的 `if name.upper().startswith(("ST", "*ST", "SST", "S*ST")):` 改为 `if is_st_name(name):`（顶部加 import；该函数上方注释"前缀口径同 filter_st"改为"前缀口径=st_prefixes 单一事实源"）。

- [ ] **Step 4: 跑绿 + 既有过滤/闸测试回归**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/domain/market/test_st_prefixes.py tests/domain/strategy -k "st" tests/domain/trade/services -q`
Expected: 全 PASS

- [ ] **Step 5: 标记完成（不 commit）**

---

### Task 2: `is_tradable` 语义修正（拆"注入即吞 *ST 卖单"地雷）

**Files:**
- Modify: `src/domain/market/value_objects/suspension.py:14-16`
- Test: `tests/domain/market/test_suspension.py:16-18`（既有断言按新语义翻转，留理由）

**Interfaces:**
- Consumes: 无
- Produces: `StockStatus.is_tradable()` 语义 = `not is_suspended`（*ST 可交易，仅幅度 ±5%）

**背景**：`BacktestAppService` 已把 `status_registry` 透传给 `SingleStrategyRunner`（`backtest_app.py:163`），其 `strategy_runner.py:114` 用 `is_tradable()` 过滤信号。旧语义 `is_star_st → False` 会在注册表灌入后**静默吞掉 *ST 的卖出信号**（现实中 *ST 可交易）。规避 *ST 属策略职责（`filter_st` 已做），不是市场事实。

- [ ] **Step 1: 改既有测试为新语义（这是行为变更的红）**

`test_suspension.py` 中 `test_star_st_stock_is_not_tradable` 整体替换为：

```python
def test_star_st_stock_is_tradable_only_limit_narrowed():
    """*ST 可正常交易(±5% 幅度), 不可交易的是停牌——旧语义把策略偏好错标成
    市场事实, 注册表灌入后会静默吞掉 *ST 卖出信号(0711-st-honesty Task2)。"""
    status = StockStatus(symbol="000001.SZ", date=datetime(2024, 1, 3), is_star_st=True)
    assert status.is_tradable() is True
```

同文件 `test_registry_tracks_status_by_date`（26-33 行）构造的不可交易日改用 `is_suspended=True`（如原用 is_star_st）。

- [ ] **Step 2: 跑红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/domain/market/test_suspension.py -q`
Expected: 新断言 FAIL（旧实现返回 False）

- [ ] **Step 3: 实现**

`suspension.py` 的 `is_tradable` 改为：

```python
    def is_tradable(self) -> bool:
        """是否可交易。*ST 可交易(仅涨跌幅收窄至 ±5%), 停牌才不可交易;
        规避 *ST 属策略/过滤器职责(filter_st), 非市场事实。"""
        return not self.is_suspended
```

- [ ] **Step 4: 跑绿**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/domain/market/test_suspension.py tests/application/test_backtest_app* -q`
Expected: 全 PASS

---

### Task 3: 深市管道 — 简称变更流 → ST 区间（纯函数）

**Files:**
- Create: `src/infrastructure/gateway/st_status_source.py`
- Test: `tests/infrastructure/gateway_offline/test_st_status_source.py`

**Interfaces:**
- Consumes: Task 1 `is_st_name`
- Produces: `@dataclass StPeriod(symbol, start: date, end: date | None, label: str, source: str, evidence: str)`；`derive_periods_from_sz_feed(rows: list[dict]) -> list[StPeriod]`（rows 键：`变更日期/证券代码/变更前简称/变更后简称`，日期字符串 YYYY-MM-DD）；`_label_of(name) -> str`（'*ST' 若 upper 以 `*ST`/`S*ST` 开头，否则 'ST'）

- [ ] **Step 1: 失败测试**

```python
"""深市简称变更流 → ST 区间推导(设计 0711-st-honesty §3.2)。"""
from datetime import date

from src.infrastructure.gateway.st_status_source import (
    StPeriod,
    derive_periods_from_sz_feed,
)


def _row(d: str, code: str, before: str, after: str) -> dict:
    return {"变更日期": d, "证券代码": code, "变更前简称": before, "变更后简称": after}


class TestDerivePeriodsFromSzFeed:
    def test_enter_and_exit(self):
        rows = [
            _row("2022-05-06", "000021", "深科技", "ST深科技"),
            _row("2023-06-01", "000021", "ST深科技", "深科技"),
        ]
        periods = derive_periods_from_sz_feed(rows)
        assert periods == [StPeriod(
            symbol="000021.SZ", start=date(2022, 5, 6), end=date(2023, 6, 1),
            label="ST", source="szse_name_change",
            evidence="2022-05-06 深科技→ST深科技 | 2023-06-01 ST深科技→深科技",
        )]

    def test_open_interval_when_still_st(self):
        rows = [_row("2024-05-06", "000595", "宝塔实业", "*ST宝实")]
        [p] = derive_periods_from_sz_feed(rows)
        assert p.end is None and p.label == "*ST"

    def test_downgrade_star_to_plain_produces_two_periods(self):
        rows = [
            _row("2022-05-06", "002731", "萃华珠宝", "*ST萃华"),
            _row("2023-05-06", "002731", "*ST萃华", "ST萃华"),
            _row("2024-05-06", "002731", "ST萃华", "萃华珠宝"),
        ]
        p1, p2 = derive_periods_from_sz_feed(rows)
        assert (p1.label, p1.start, p1.end) == ("*ST", date(2022, 5, 6), date(2023, 5, 6))
        assert (p2.label, p2.start, p2.end) == ("ST", date(2023, 5, 6), date(2024, 5, 6))

    def test_initial_listing_name_st_counts_from_first_before_name(self):
        # 首条记录的 变更前简称 是该股已知最早名称: 若带 ST, 区间自"已知史前"起 —— 用首条变更日期前一天不可知,
        # 裁定: 以 date.min 哨兵表示"窗口起点前已在册", loader 展开时按窗口起点截断
        rows = [_row("2021-03-01", "000004", "ST国华", "国华网安")]
        [p] = derive_periods_from_sz_feed(rows)
        assert p.start == date.min and p.end == date(2021, 3, 1) and p.label == "ST"

    def test_name_change_without_st_transition_ignored(self):
        rows = [_row("2022-01-04", "000012", "南玻Ａ", "南玻集团")]
        assert derive_periods_from_sz_feed(rows) == []

    def test_symbol_suffix_by_code(self):
        rows = [_row("2022-05-06", "001202", "炬申股份", "ST炬申"),
                _row("2022-07-06", "001202", "ST炬申", "炬申股份")]
        [p] = derive_periods_from_sz_feed(rows)
        assert p.symbol == "001202.SZ"
```

- [ ] **Step 2: 跑红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/infrastructure/gateway_offline/test_st_status_source.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""ST 状态数据源 — 深市官方简称变更流推导 + 沪市巨潮公告分类推断。

设计: docs/feat/0711-st-honesty §3.2/§3.3/§3.4。纯函数可离线测试;
akshare I/O 只在 fetch_* 薄壳(scripts/backfill_st_status.py 调用)。
"""

from dataclasses import dataclass
from datetime import date, datetime

from src.domain.market.value_objects.st_prefixes import is_st_name

SOURCE_SZSE = "szse_name_change"
SOURCE_CNINFO = "cninfo_notice"


@dataclass(slots=True, kw_only=True, frozen=True)
class StPeriod:
    symbol: str
    start: date            # date.min = 窗口起点前已在册(史前哨兵)
    end: date | None       # None = 至今仍 ST
    label: str             # 'ST' | '*ST'
    source: str
    evidence: str


def _label_of(name: str) -> str:
    upper = name.upper()
    return "*ST" if upper.startswith(("S*ST", "*ST")) else "ST"


def _sz_symbol(code: str) -> str:
    return f"{code}.SZ"


def derive_periods_from_sz_feed(rows: list[dict]) -> list[StPeriod]:
    """深市简称变更时间线 → ST 区间。同一 symbol 按日期扫描名称序列。"""
    by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        by_symbol.setdefault(str(r["证券代码"]), []).append(r)

    periods: list[StPeriod] = []
    for code, items in sorted(by_symbol.items()):
        items.sort(key=lambda r: str(r["变更日期"]))
        symbol = _sz_symbol(code)
        open_start: date | None = None
        open_label = ""
        trail: list[str] = []

        first_before = str(items[0]["变更前简称"]).replace(" ", "")
        if is_st_name(first_before):
            open_start = date.min
            open_label = _label_of(first_before)

        for r in items:
            day = datetime.strptime(str(r["变更日期"]), "%Y-%m-%d").date()
            after = str(r["变更后简称"]).replace(" ", "")
            trail.append(f"{r['变更日期']} {str(r['变更前简称']).replace(' ', '')}→{after}")
            now_st = is_st_name(after)
            now_label = _label_of(after) if now_st else ""

            if open_start is not None and (not now_st or now_label != open_label):
                periods.append(StPeriod(
                    symbol=symbol, start=open_start, end=day, label=open_label,
                    source=SOURCE_SZSE, evidence=" | ".join(trail),
                ))
                open_start = None
            if now_st and open_start is None:
                open_start, open_label = day, now_label

        if open_start is not None:
            periods.append(StPeriod(
                symbol=symbol, start=open_start, end=None, label=open_label,
                source=SOURCE_SZSE, evidence=" | ".join(trail),
            ))
    return periods
```

- [ ] **Step 4: 跑绿**（同 Step 2 命令，全 PASS）

---

### Task 4: 沪市管道 — 公告分类 → 事件 → 区间 + 交叉验证器（纯函数）

**Files:**
- Modify: `src/infrastructure/gateway/st_status_source.py`（追加）
- Test: `tests/infrastructure/gateway_offline/test_st_status_source.py`（追加）

**Interfaces:**
- Produces: `@dataclass StEvent(symbol, effective: date, kind: str['enter'|'exit'], label: str, evidence: str)`；`classify_sh_notices(rows: list[dict], next_trading_day: Callable[[date], date]) -> list[StEvent]`（rows 键：`代码/公告标题/公告时间/公告链接`）；`events_to_periods(events: list[StEvent]) -> list[StPeriod]`（source='cninfo_notice'）；`cross_validate(official: list[StPeriod], inferred: list[StPeriod], trading_days: list[date]) -> dict`（返回 `{"matched": int, "total_official": int, "within_2td": int, "mean_signed_td": float, "pass": bool, "details": [...]}`，准入 `within_2td/matched ≥ 0.9 且 |mean_signed_td| ≤ 1`，start/end 事件分别对齐）

- [ ] **Step 1: 追加失败测试**

```python
from datetime import timedelta

from src.infrastructure.gateway.st_status_source import (
    StEvent,
    classify_sh_notices,
    cross_validate,
    events_to_periods,
)


def _next_td(d):
    n = d + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n


def _notice(code: str, title: str, ts: str) -> dict:
    return {"代码": code, "公告标题": title, "公告时间": ts, "公告链接": "http://x"}


class TestClassifyShNotices:
    def test_four_decisive_titles(self):
        rows = [
            _notice("600186", "关于公司股票实施退市风险警示的公告", "2022-05-05 00:00:00"),
            _notice("600186", "关于撤销公司股票退市风险警示的公告", "2023-06-01 00:00:00"),
            _notice("600696", "关于公司股票实施其他风险警示的公告", "2022-07-01 00:00:00"),
            _notice("600696", "关于撤销其他风险警示的公告", "2023-07-03 00:00:00"),
        ]
        events = classify_sh_notices(rows, _next_td)
        kinds = [(e.symbol, e.kind, e.label) for e in events]
        assert ("600186.SH", "enter", "*ST") in kinds
        assert ("600186.SH", "exit", "*ST") in kinds
        assert ("600696.SH", "enter", "ST") in kinds
        assert ("600696.SH", "exit", "ST") in kinds
        # 生效日 = 公告日次交易日: 2022-05-05(周四) -> 05-06(周五)
        enter = next(e for e in events if e.symbol == "600186.SH" and e.kind == "enter")
        assert enter.effective.isoformat() == "2022-05-06"

    def test_noise_titles_excluded(self):
        rows = [
            _notice("600100", "关于公司股票被实施其他风险警示相关事项的进展公告", "2022-01-04 00:00:00"),
            _notice("600100", "关于公司股票交易可能被实施退市风险警示的提示性公告", "2022-01-05 00:00:00"),
            _notice("600100", "关于公司股票继续实施其他风险警示的公告", "2022-01-06 00:00:00"),
            _notice("600100", "关于实施其他风险警示期间所采取的措施的公告", "2022-01-07 00:00:00"),
        ]
        assert classify_sh_notices(rows, _next_td) == []

    def test_non_sh_mainboard_excluded(self):
        rows = [_notice("300555", "关于公司股票实施其他风险警示的公告", "2022-01-04 00:00:00")]
        assert classify_sh_notices(rows, _next_td) == []

    def test_dedupe_same_kind_within_5_notices_days(self):
        rows = [
            _notice("600200", "关于公司股票实施其他风险警示的公告", "2022-03-01 00:00:00"),
            _notice("600200", "关于公司股票实施其他风险警示的公告", "2022-03-03 00:00:00"),
        ]
        assert len(classify_sh_notices(rows, _next_td)) == 1

    def test_downgrade_double_pattern_title(self):
        rows = [_notice("600300", "关于撤销退市风险警示并实施其他风险警示的公告", "2022-06-01 00:00:00")]
        events = classify_sh_notices(rows, _next_td)
        assert [(e.kind, e.label) for e in events] == [("exit", "*ST"), ("enter", "ST")]


class TestEventsToPeriods:
    def test_pairing_and_open_interval(self):
        from datetime import date
        events = [
            StEvent(symbol="600186.SH", effective=date(2022, 5, 6), kind="enter", label="*ST", evidence="a"),
            StEvent(symbol="600186.SH", effective=date(2023, 6, 2), kind="exit", label="*ST", evidence="b"),
            StEvent(symbol="600696.SH", effective=date(2024, 1, 4), kind="enter", label="ST", evidence="c"),
        ]
        p1, p2 = events_to_periods(events)
        assert (p1.symbol, p1.start, p1.end) == ("600186.SH", date(2022, 5, 6), date(2023, 6, 2))
        assert p2.end is None

    def test_exit_without_enter_ignored_with_note(self):
        from datetime import date
        events = [StEvent(symbol="600400.SH", effective=date(2022, 1, 4), kind="exit", label="ST", evidence="x")]
        assert events_to_periods(events) == []


class TestCrossValidate:
    def test_pass_within_tolerance(self):
        from datetime import date
        tds = [date(2022, 5, 4) + timedelta(days=i) for i in range(40)]
        tds = [d for d in tds if d.weekday() < 5]
        official = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 6), end=date(2022, 6, 6),
                             label="ST", source="szse_name_change", evidence="")]
        inferred = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 9), end=date(2022, 6, 7),
                             label="ST", source="cninfo_notice", evidence="")]
        report = cross_validate(official, inferred, tds)
        assert report["pass"] is True and report["within_2td"] == report["matched"] == 2

    def test_fail_when_deviation_large(self):
        from datetime import date
        tds = [date(2022, 5, 2) + timedelta(days=i) for i in range(60)]
        tds = [d for d in tds if d.weekday() < 5]
        official = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 6), end=None,
                             label="ST", source="szse_name_change", evidence="")]
        inferred = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 20), end=None,
                             label="ST", source="cninfo_notice", evidence="")]
        assert cross_validate(official, inferred, tds)["pass"] is False
```

（顶部补 `from src.infrastructure.gateway.st_status_source import StPeriod` 已有。）

- [ ] **Step 2: 跑红**（命令同前，新用例 FAIL）

- [ ] **Step 3: 实现（追加到 st_status_source.py）**

```python
_ENTER_STAR = "实施退市风险警示"
_ENTER_PLAIN = "实施其他风险警示"
_EXIT_STAR = "撤销退市风险警示"
_EXIT_PLAIN = ("撤销其他风险警示", "撤销公司股票其他风险警示")
_NOISE = ("进展", "提示", "可能", "继续", "期间")
_DEDUPE_DAYS = 5


@dataclass(slots=True, kw_only=True, frozen=True)
class StEvent:
    symbol: str
    effective: date
    kind: str      # 'enter' | 'exit'
    label: str     # 'ST' | '*ST'
    evidence: str


def _clean_title(title: str) -> str:
    return title.replace("<em>", "").replace("</em>", "")


def classify_sh_notices(rows: list[dict], next_trading_day) -> list[StEvent]:
    """巨潮公告标题 → 决定性 ST 事件(沪市主板 60 开头)。

    生效日 = 公告日次一交易日(交易所规则: 实施/撤销于公告后首个交易日生效)。
    降档公告("撤销退市风险警示并实施其他风险警示")拆成 exit(*ST)+enter(ST)。
    """
    raw: list[StEvent] = []
    for r in rows:
        code = str(r["代码"])
        if not code.startswith("60"):
            continue
        title = _clean_title(str(r["公告标题"]))
        if any(w in title for w in _NOISE):
            continue
        ann_day = datetime.strptime(str(r["公告时间"])[:10], "%Y-%m-%d").date()
        eff = next_trading_day(ann_day)
        ev = f"{title} @{r['公告时间']} {r.get('公告链接', '')}"
        symbol = f"{code}.SH"

        has_exit_star = _EXIT_STAR in title
        has_exit_plain = any(p in title for p in _EXIT_PLAIN)
        has_enter_star = _ENTER_STAR in title and not has_exit_star
        has_enter_plain = _ENTER_PLAIN in title and not has_exit_plain

        if has_exit_star:
            raw.append(StEvent(symbol=symbol, effective=eff, kind="exit", label="*ST", evidence=ev))
        if has_exit_plain:
            raw.append(StEvent(symbol=symbol, effective=eff, kind="exit", label="ST", evidence=ev))
        if has_enter_star:
            raw.append(StEvent(symbol=symbol, effective=eff, kind="enter", label="*ST", evidence=ev))
        if has_enter_plain:
            raw.append(StEvent(symbol=symbol, effective=eff, kind="enter", label="ST", evidence=ev))

    # 同 symbol 同 kind+label 在 _DEDUPE_DAYS 内去重取首条
    raw.sort(key=lambda e: (e.symbol, e.kind, e.label, e.effective))
    out: list[StEvent] = []
    for e in raw:
        if out and out[-1].symbol == e.symbol and out[-1].kind == e.kind \
                and out[-1].label == e.label \
                and (e.effective - out[-1].effective).days <= _DEDUPE_DAYS:
            continue
        out.append(e)
    out.sort(key=lambda e: (e.symbol, e.effective, 0 if e.kind == "exit" else 1))
    return out


def events_to_periods(events: list[StEvent]) -> list[StPeriod]:
    """enter/exit 事件配对成区间; 无 enter 的 exit 丢弃(窗口前已在册的沪市情形
    由回填脚本用『窗口起点日仍带 ST 前缀的当前名』终态核对兜底, 见 §3.4)。"""
    periods: list[StPeriod] = []
    open_map: dict[str, StEvent] = {}
    for e in events:
        if e.kind == "enter":
            if e.symbol not in open_map:
                open_map[e.symbol] = e
        else:
            start = open_map.pop(e.symbol, None)
            if start is not None:
                periods.append(StPeriod(
                    symbol=e.symbol, start=start.effective, end=e.effective,
                    label=start.label, source=SOURCE_CNINFO,
                    evidence=f"{start.evidence} || {e.evidence}",
                ))
    for e in open_map.values():
        periods.append(StPeriod(
            symbol=e.symbol, start=e.effective, end=None, label=e.label,
            source=SOURCE_CNINFO, evidence=e.evidence,
        ))
    periods.sort(key=lambda p: (p.symbol, p.start))
    return periods


def cross_validate(official: list[StPeriod], inferred: list[StPeriod],
                   trading_days: list[date]) -> dict:
    """公告法(inferred)对官方(official)的日期误差分布。准入: ≥90% 事件 ≤2 交易日
    且平均带符号误差 |mean| ≤ 1 天。start/end 分别作为独立事件对齐。"""
    idx = {d: i for i, d in enumerate(sorted(trading_days))}

    def td_dist(a: date, b: date) -> int | None:
        ka = min((d for d in idx if d >= a), default=None)
        kb = min((d for d in idx if d >= b), default=None)
        if ka is None or kb is None:
            return None
        return idx[kb] - idx[ka]

    inferred_map: dict[tuple[str, str], list[date]] = {}
    for p in inferred:
        inferred_map.setdefault((p.symbol, "start"), []).append(p.start)
        if p.end is not None:
            inferred_map.setdefault((p.symbol, "end"), []).append(p.end)

    details = []
    matched = within = 0
    signed_sum = 0
    total_official = 0
    for p in official:
        for kind, day in (("start", p.start), ("end", p.end)):
            if day is None or day == date.min:
                continue
            total_official += 1
            cands = inferred_map.get((p.symbol, kind), [])
            if not cands:
                details.append({"symbol": p.symbol, "kind": kind, "official": day.isoformat(),
                                "inferred": None, "td_error": None})
                continue
            best = min(cands, key=lambda c: abs((c - day).days))
            err = td_dist(day, best)
            if err is None:
                continue
            matched += 1
            signed_sum += err
            if abs(err) <= 2:
                within += 1
            details.append({"symbol": p.symbol, "kind": kind, "official": day.isoformat(),
                            "inferred": best.isoformat(), "td_error": err})

    mean_signed = signed_sum / matched if matched else 0.0
    ok = matched > 0 and within / matched >= 0.9 and abs(mean_signed) <= 1.0
    return {"matched": matched, "total_official": total_official, "within_2td": within,
            "mean_signed_td": round(mean_signed, 2), "pass": ok, "details": details}
```

- [ ] **Step 4: 跑绿 + ruff**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/infrastructure/gateway_offline/test_st_status_source.py -q && /home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m ruff check src/infrastructure/gateway/st_status_source.py`
Expected: 全 PASS / 0 违规

---

### Task 5: 存储 + Registry 装载器（区间 → 稠密逐日）

**Files:**
- Modify: `src/infrastructure/persistence/market_data_store.py`（`_DDL_STATEMENTS` 追加表；类尾追加两方法）
- Create: `src/infrastructure/persistence/status_registry_loader.py`
- Test: `tests/infrastructure/persistence/test_st_periods_store.py`、`tests/infrastructure/persistence/test_status_registry_loader.py`

**Interfaces:**
- Consumes: Task 3/4 `StPeriod`
- Produces: `MarketDataStore.save_st_periods(periods: list[StPeriod]) -> int`（全删全建，返回行数；`date.min` 起点原样入库）；`MarketDataStore.load_st_periods() -> list[StPeriod]`；`build_status_registry(store, *, start: date, end: date) -> StockStatusRegistry | None`（表空 → None + warning；区间∩[start,end] 在 `store.trading_dates()` 上稠密展开为 `StockStatus(is_st=label=='ST', is_star_st=label=='*ST')`）

- [ ] **Step 1: 失败测试（两文件）**

`test_st_periods_store.py`：

```python
"""st_status_periods 表: 全删全建往返(设计 §3.1/§3.5)。"""
from datetime import date

from src.infrastructure.gateway.st_status_source import StPeriod
from src.infrastructure.persistence.market_data_store import MarketDataStore


def _mk(symbol="000021.SZ", start=date(2022, 5, 6), end=date(2023, 6, 1),
        label="ST", source="szse_name_change"):
    return StPeriod(symbol=symbol, start=start, end=end, label=label,
                    source=source, evidence="ev")


def test_save_and_load_roundtrip_including_sentinels():
    store = MarketDataStore(":memory:")
    n = store.save_st_periods([
        _mk(),
        _mk(symbol="600186.SH", start=date.min, end=date(2021, 3, 1), source="cninfo_notice"),
        _mk(symbol="600696.SH", start=date(2024, 1, 4), end=None, label="*ST",
            source="cninfo_notice"),
    ])
    assert n == 3
    loaded = store.load_st_periods()
    assert {p.symbol for p in loaded} == {"000021.SZ", "600186.SH", "600696.SH"}
    open_p = next(p for p in loaded if p.symbol == "600696.SH")
    assert open_p.end is None and open_p.label == "*ST"
    sentinel = next(p for p in loaded if p.symbol == "600186.SH")
    assert sentinel.start == date.min


def test_save_is_full_replace():
    store = MarketDataStore(":memory:")
    store.save_st_periods([_mk()])
    store.save_st_periods([_mk(symbol="000100.SZ")])
    assert [p.symbol for p in store.load_st_periods()] == ["000100.SZ"]
```

`test_status_registry_loader.py`：

```python
"""区间 → StockStatusRegistry 稠密展开(设计 §4.1)。"""
from datetime import date, datetime

from src.infrastructure.gateway.st_status_source import StPeriod
from src.infrastructure.persistence.status_registry_loader import build_status_registry


class FakeStore:
    def __init__(self, periods, tds):
        self._periods = periods
        self._tds = tds

    def load_st_periods(self):
        return self._periods

    def trading_dates(self, source="qmt"):
        return self._tds


TDS = [date(2022, 5, 5), date(2022, 5, 6), date(2022, 5, 9), date(2022, 5, 10)]


def test_expand_closed_interval_on_trading_days_only():
    periods = [StPeriod(symbol="000021.SZ", start=date(2022, 5, 6), end=date(2022, 5, 10),
                        label="ST", source="szse_name_change", evidence="")]
    reg = build_status_registry(FakeStore(periods, TDS), start=date(2022, 5, 1), end=date(2022, 5, 31))
    assert reg.get_status("000021.SZ", datetime(2022, 5, 6)).is_st is True
    assert reg.get_status("000021.SZ", datetime(2022, 5, 9)).is_st is True
    assert reg.get_status("000021.SZ", datetime(2022, 5, 10)) is None   # end 不含
    assert reg.get_status("000021.SZ", datetime(2022, 5, 7)) is None    # 非交易日不展开
    assert reg.get_status("000021.SZ", datetime(2022, 5, 5)) is None


def test_open_interval_and_star_label_and_window_clip():
    periods = [StPeriod(symbol="600696.SH", start=date.min, end=None,
                        label="*ST", source="cninfo_notice", evidence="")]
    reg = build_status_registry(FakeStore(periods, TDS), start=date(2022, 5, 6), end=date(2022, 5, 9))
    s = reg.get_status("600696.SH", datetime(2022, 5, 9))
    assert s is not None and s.is_star_st is True and s.is_st is False
    assert reg.get_status("600696.SH", datetime(2022, 5, 5)) is None    # 窗口裁剪
    assert reg.get_status("600696.SH", datetime(2022, 5, 10)) is None


def test_empty_table_returns_none():
    assert build_status_registry(FakeStore([], TDS), start=date(2022, 1, 1), end=date(2022, 12, 31)) is None
```

- [ ] **Step 2: 跑红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/infrastructure/persistence/test_st_periods_store.py tests/infrastructure/persistence/test_status_registry_loader.py -q`
Expected: FAIL

- [ ] **Step 3: 实现**

`_DDL_STATEMENTS` 追加（backtest_runs 条目后）：

```python
    """CREATE TABLE IF NOT EXISTS st_status_periods (
        symbol      VARCHAR NOT NULL,
        start_date  DATE    NOT NULL,
        end_date    DATE,
        label       VARCHAR NOT NULL,
        source      VARCHAR NOT NULL,
        evidence    VARCHAR,
        fetched_at  TIMESTAMP NOT NULL,
        PRIMARY KEY (symbol, start_date, source)
    )""",
```

`MarketDataStore` 类尾追加（import 区补 `from src.infrastructure.gateway.st_status_source import StPeriod`——infrastructure 内互引合法）：

```python
    # ---- ST 状态区间(0711-st-honesty §3.1) ----

    def save_st_periods(self, periods: list[StPeriod]) -> int:
        """全删全建(千行级, 幂等), 区间全史入库不裁剪。"""
        self._conn.execute("DELETE FROM st_status_periods")
        for p in periods:
            self._conn.execute(
                """INSERT INTO st_status_periods
                   (symbol, start_date, end_date, label, source, evidence, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, now())""",
                [p.symbol, p.start, p.end, p.label, p.source, p.evidence],
            )
        return len(periods)

    def load_st_periods(self) -> list[StPeriod]:
        rows = self._conn.execute(
            """SELECT symbol, start_date, end_date, label, source, COALESCE(evidence, '')
               FROM st_status_periods ORDER BY symbol, start_date"""
        ).fetchall()
        return [StPeriod(symbol=r[0], start=r[1], end=r[2], label=r[3],
                         source=r[4], evidence=r[5]) for r in rows]
```

`status_registry_loader.py`：

```python
"""区间 → StockStatusRegistry 稠密展开(设计 0711-st-honesty §4.1)。

registry 是精确日期索引(domain 不动): 区间∩回测窗口按交易日逐日展开。
量级: 窗口 ~1350 交易日 × 在册 ST 股 ~200 → ~20 万条内存条目, 可接受。
"""
import logging
from datetime import date, datetime, time

from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry

logger = logging.getLogger(__name__)


def build_status_registry(store, *, start: date, end: date) -> StockStatusRegistry | None:
    """从 market.duckdb 的 st_status_periods 构建注册表; 表空返回 None(调用方回退旧行为)。"""
    periods = store.load_st_periods()
    if not periods:
        logger.warning("st_status_periods 为空: ST 涨跌停幅度回退普通口径(先跑 scripts/backfill_st_status.py)")
        return None
    trading_days = [d for d in store.trading_dates() if start <= d <= end]
    registry = StockStatusRegistry()
    for p in periods:
        p_end = p.end or date.max
        for d in trading_days:
            if p.start <= d < p_end:
                registry.add(StockStatus(
                    symbol=p.symbol,
                    date=datetime.combine(d, time.min),
                    is_st=p.label == "ST",
                    is_star_st=p.label == "*ST",
                ))
    return registry
```

- [ ] **Step 4: 跑绿 + 架构守卫**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/infrastructure/persistence/test_st_periods_store.py tests/infrastructure/persistence/test_status_registry_loader.py tests/architecture -q`
Expected: 全 PASS

---

### Task 6: 消费端接线（撮合 ±5% / 涨停破板 / 选股名称修正 / 11 处构造点）

**Files:**
- Modify: `src/domain/strategy/services/cross_section_builder.py`（加 `status_registry` 参数 + 名称修正）
- Modify: `src/domain/risk/services/risk_policies/limit_up_break_policy.py`（注入 `is_st_fn`）
- Modify: `src/application/strategy_runner.py`（`CrossSectionalStrategyRunner` 加 `status_registry`，穿透两处 `build_cross_section` 与 `LimitUpBreakPolicy`）
- Modify: `src/application/backtest_app.py:147`（透传 `status_registry=self.status_registry`）
- Modify: 11 处构造点（`run_backtest.py:66` / `commands/backtest.py:80` / `compare_strategies.py:114` / `scripts/{b1_delisted_sensitivity,b2_trend_gate_ab,b2_trend_gate_oos,mainboard_f01_gate,run_f01_investability,shadow_paper_equity,seed_paper_trading}.py`）：`registry = build_status_registry(...)` 后传 `MockTradeGateway(..., stock_status_registry=registry)` 与 `BacktestAppService(..., status_registry=registry)`
- Test: `tests/infrastructure/mock/test_mock_trade_st_limit.py`、`tests/domain/strategy/services/test_cross_section_st_correction.py`、`tests/domain/risk/test_limit_up_break_st.py`

**Interfaces:**
- Consumes: Task 1 `correct_st_name`、Task 5 `build_status_registry`、既有 `StockStatusRegistry.get_status`
- Produces: `CrossSectionBuilder.build_cross_section(..., status_registry: StockStatusRegistry | None = None)`；`LimitUpBreakPolicy(is_st_fn: Callable[[str, datetime], bool] | None = None)`；`CrossSectionalStrategyRunner(..., status_registry: StockStatusRegistry | None = None)`

- [ ] **Step 1: 三个失败测试**

`test_mock_trade_st_limit.py`（复用既有 fixture 模式）：

```python
"""ST 日 ±5% 撮合闸(DD-6 主体): 带注册表拒 6% 买单, 无注册表按 ±10% 放行。"""
from datetime import datetime

import pytest

from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.mock.mock_market import MockMarketGateway
from src.infrastructure.mock.mock_trade import MockTradeGateway

D1, D2 = datetime(2023, 1, 2), datetime(2023, 1, 3)


def _bar(ts, px):
    return Bar(symbol="000021.SZ", timeframe=Timeframe.DAY_1, timestamp=ts,
               open=px, high=px * 1.06, low=px * 0.95, close=px, volume=1_000_000.0)


@pytest.fixture
def market():
    gw = MockMarketGateway()
    gw.add_bars("000021.SZ", [_bar(D1, 10.0), _bar(D2, 10.6)])
    gw.set_current_time(D2)
    return gw


def _buy(price):
    return Order(order_id="t1", account_id="MOCK_ACCOUNT", ticker="000021.SZ",
                 direction=OrderDirection.BUY, price=price, volume=100,
                 type=OrderType.LIMIT)


def test_st_day_rejects_buy_beyond_5pct(market):
    registry = StockStatusRegistry()
    registry.add(StockStatus(symbol="000021.SZ", date=D2, is_st=True))
    gw = MockTradeGateway(market_gateway=market, initial_capital=1_000_000.0,
                          stock_status_registry=registry)
    with pytest.raises(OrderSubmitError, match="limit up"):
        gw.place_order(_buy(10.6))  # prev_close 10.0, ST 限 10.5, exec 10.6*1.001 超限


def test_without_registry_same_order_passes_10pct(market):
    gw = MockTradeGateway(market_gateway=market, initial_capital=1_000_000.0)
    order_id = gw.place_order(_buy(10.6))  # 普通限 11.0, 放行
    assert order_id
```

`test_cross_section_st_correction.py`：

```python
"""截面名称按 as-of ST 状态修正(设计 §4.4): 摘帽股历史期恢复 ST 前缀→filter_st 可拦。"""
from datetime import datetime

from src.domain.market.services.fundamental_registry import FundamentalRegistry
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.fundamental_snapshot import FundamentalSnapshot
from src.domain.market.value_objects.suspension import StockStatus, StockStatusRegistry
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.strategy.services.cross_section_builder import CrossSectionBuilder

D = datetime(2022, 5, 6)


def _setup():
    reg = FundamentalRegistry()
    reg.register(FundamentalSnapshot(symbol="000021.SZ", date=D, name="深科技",
                                     market_cap=1e9, list_date=datetime(2000, 1, 1)))
    bars = {"000021.SZ": Bar(symbol="000021.SZ", timeframe=Timeframe.DAY_1, timestamp=D,
                             open=10, high=10, low=10, close=10, volume=1000.0)}
    return reg, bars


def test_name_gains_st_prefix_when_registry_says_st():
    reg, bars = _setup()
    status = StockStatusRegistry()
    status.add(StockStatus(symbol="000021.SZ", date=D, is_st=True))
    [snap] = CrossSectionBuilder.build_cross_section(D, bars, reg, status_registry=status)
    assert snap.name == "ST深科技"


def test_name_untouched_without_registry():
    reg, bars = _setup()
    [snap] = CrossSectionBuilder.build_cross_section(D, bars, reg)
    assert snap.name == "深科技"
```

（若 `FundamentalSnapshot` 构造字段名不同，以 `src/domain/market/value_objects/fundamental_snapshot.py` 实际必填字段为准调整 fixture，断言不变。）

`test_limit_up_break_st.py`：

```python
"""LimitUpBreakPolicy 注入 is_st_fn 后, ST 股按 5% 涨停价判破板(设计 §4.3)。"""
from datetime import datetime

from src.domain.account.entities.position import Position
from src.domain.market.value_objects.bar import Bar
from src.domain.market.value_objects.timeframe import Timeframe
from src.domain.risk.services.risk_policies.limit_up_break_policy import LimitUpBreakPolicy

D = datetime(2023, 1, 3)


def _pos():
    return Position(ticker="000021.SZ", total_volume=100, available_volume=100,
                    average_cost=10.0)


def _bar(high, close):
    return Bar(symbol="000021.SZ", timeframe=Timeframe.DAY_1, timestamp=D,
               open=10.0, high=high, low=9.9, close=close, volume=1000.0,
               prev_close=10.0)


def test_st_5pct_limit_touched_and_broken_triggers_sell():
    policy = LimitUpBreakPolicy(is_st_fn=lambda sym, ts: True)
    # 5% 涨停 10.5: 高点触及、收盘回落 → 破板卖出
    signals = policy.evaluate_positions([_pos()], {"000021.SZ": _bar(high=10.5, close=10.2)})
    assert len(signals) == 1

def test_same_bar_without_st_fn_no_signal():
    policy = LimitUpBreakPolicy()
    # 普通 10% 涨停 11.0: 高点 10.5 未触及 → 无信号(既有行为回归)
    signals = policy.evaluate_positions([_pos()], {"000021.SZ": _bar(high=10.5, close=10.2)})
    assert signals == []
```

（`Position` 构造字段以实际实体为准调整。）

- [ ] **Step 2: 跑红**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/infrastructure/mock/test_mock_trade_st_limit.py tests/domain/strategy/services/test_cross_section_st_correction.py tests/domain/risk/test_limit_up_break_st.py -q`
Expected: mock 用例 1 红（撮合已实现应绿——若绿说明 DD-6 撮合分支本就正确，只是没数据；其余两文件红）

- [ ] **Step 3: 实现**

`cross_section_builder.py`：签名加 `status_registry=None`（类型 `"StockStatusRegistry | None"`，顶部 import `StockStatusRegistry` 与 `correct_st_name`）；snapshot 构造前：

```python
            name = fund.name
            if status_registry is not None:
                status = status_registry.get_status(symbol, date)
                st_now = status is not None and (status.is_st or status.is_star_st)
                name = correct_st_name(name, is_st=st_now)
```

（`StockSnapshot(... name=name ...)` 替换原 `fund.name`。）

`limit_up_break_policy.py`：

```python
class LimitUpBreakPolicy(BaseRiskSignalPolicy):
    def __init__(self, is_st_fn=None) -> None:
        # is_st_fn(symbol, timestamp) -> bool; None = 普通幅度(既有行为)
        self._is_st_fn = is_st_fn
```

`evaluate_positions` 内 `ratio = get_price_limit_ratio(pos.ticker)` 改为：

```python
            is_st = bool(self._is_st_fn and self._is_st_fn(pos.ticker, bar.timestamp))
            ratio = get_price_limit_ratio(pos.ticker, is_st=is_st)
```

`strategy_runner.py` `CrossSectionalStrategyRunner.__init__`：签名加 `status_registry: StockStatusRegistry | None = None`；`self.status_registry = status_registry`；`RiskSignalGenerator([LimitUpBreakPolicy(), ...])` 改：

```python
        is_st_fn = None
        if status_registry is not None:
            def is_st_fn(symbol, ts, _reg=status_registry):
                s = _reg.get_status(symbol, ts)
                return s is not None and (s.is_st or s.is_star_st)
        self.risk_signal_gen = RiskSignalGenerator([
            LimitUpBreakPolicy(is_st_fn=is_st_fn),
            HardStopLossPolicy(max_loss_ratio=max_loss),
        ])
```

两处 `CrossSectionBuilder.build_cross_section(...)`（行 226/233）都加 `status_registry=self.status_registry,`。

`backtest_app.py:147` 的 `CrossSectionalStrategyRunner(...)` 调用加 `status_registry=self.status_registry,`。

11 处构造点统一模式（以 `run_f01_investability.py` 为例；各文件的 store/窗口变量名以现场为准）：

```python
from src.infrastructure.persistence.status_registry_loader import build_status_registry
...
    status_registry = build_status_registry(store, start=start_date, end=end_date)  # store=MarketDataStore
    trade = MockTradeGateway(market_gateway=mkt, initial_capital=cap,
                             stock_status_registry=status_registry)
    app = BacktestAppService(..., status_registry=status_registry, ...)
```

无 `MarketDataStore` 在手的脚本（如 `seed_paper_trading.py` 演示路径）：`build_status_registry(MarketDataStore("data/market.duckdb", read_only=True), ...)`；表空返回 None → 行为不变。

- [ ] **Step 4: 跑绿 + golden 全量回归**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -m pytest tests/ -q 2>&1 | tail -2`
Expected: 全 PASS（不带 registry 的既有路径零漂移）

---

### Task 7: 回填脚本 + 实跑（网络）+ 交叉验证准入

**Files:**
- Create: `scripts/backfill_st_status.py`

**Interfaces:**
- Consumes: Task 3/4/5 全部；akshare `stock_info_sz_change_name(symbol="简称变更")`、`stock_zh_a_disclosure_report_cninfo(symbol="", market="沪深京", keyword="风险警示", category="", start_date, end_date)`
- Produces: CLI（`--check-only` 只验证不入库；`--start 2020-01-01`）；报告 `data/st_backfill_report.json`

- [ ] **Step 1: 写脚本**

```python
"""ST 状态全市场回填(设计 0711-st-honesty §3.5)。WSL 可跑(纯 HTTP)。

流程: 深市官方简称变更→区间; 沪市巨潮公告(按季度窗口)→事件→区间;
交叉验证(深市双源, 准入门 §3.4)→ 终态自洽检查 → 入库 + 报告。
"""
import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.domain.market.value_objects.st_prefixes import is_st_name  # noqa: E402
from src.infrastructure.gateway.st_status_source import (  # noqa: E402
    SOURCE_CNINFO,
    classify_sh_notices,
    cross_validate,
    derive_periods_from_sz_feed,
    events_to_periods,
)
from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402


def _quarter_windows(start: date, end: date):
    cur = date(start.year, ((start.month - 1) // 3) * 3 + 1, 1)
    while cur <= end:
        nxt_month = cur.month + 3
        nxt = date(cur.year + (nxt_month - 1) // 12, (nxt_month - 1) % 12 + 1, 1)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


def main() -> int:
    parser = argparse.ArgumentParser(description="ST 状态回填")
    parser.add_argument("--db", default="data/market.duckdb")
    parser.add_argument("--start", default="2020-01-01", help="沪市公告检索起点")
    parser.add_argument("--check-only", action="store_true", help="只跑交叉验证不入库")
    args = parser.parse_args()

    import akshare as ak

    print("① 深市官方简称变更 …")
    sz_feed = ak.stock_info_sz_change_name(symbol="简称变更")
    sz_rows = sz_feed.rename(columns=str).to_dict("records")
    sz_periods = derive_periods_from_sz_feed(sz_rows)
    print(f"   {len(sz_rows)} 行变更 → {len(sz_periods)} 个 ST 区间")

    store = MarketDataStore(args.db)
    tds = store.trading_dates()
    td_sorted = sorted(tds)

    def next_td(d: date) -> date:
        for t in td_sorted:
            if t > d:
                return t
        return d + timedelta(days=1)  # 超出已知区: 日历近似(仅影响最新事件 ±1 天)

    print(f"② 沪深公告检索(风险警示, {args.start}→today, 按季度) …")
    start = date.fromisoformat(args.start)
    notices = []
    for lo, hi in _quarter_windows(start, date.today()):
        df = ak.stock_zh_a_disclosure_report_cninfo(
            symbol="", market="沪深京", keyword="风险警示", category="",
            start_date=lo.strftime("%Y%m%d"), end_date=hi.strftime("%Y%m%d"))
        rows = df.to_dict("records") if df is not None and not df.empty else []
        notices.extend(rows)
        print(f"   {lo}~{hi}: {len(rows)} 条")

    sh_events = classify_sh_notices(notices, next_td)
    sh_periods = events_to_periods(sh_events)
    print(f"   沪市: {len(sh_events)} 决定性事件 → {len(sh_periods)} 区间")

    print("③ 交叉验证(深市双源) …")
    sz_codes = {r["代码"] if "代码" in r else None for r in notices}
    def _sz_notices():
        return [r for r in notices if str(r.get("代码", "")).startswith(("000", "001", "002", "003"))]
    sz_inferred_events = classify_sh_notices(
        [{**r, "代码": str(r["代码"])} for r in _sz_notices()], next_td) if False else []
    # classify_sh_notices 只收 60 开头 → 为交叉验证做一个 SZ 版: 复用同函数改闸门
    from src.infrastructure.gateway import st_status_source as sss
    sz_infer_rows = [{**r, "代码": f"__SH_TRICK__"} for r in []]
    # —— 直接调用内部逻辑不可取; 改为: classify 接受 prefix 参数(见实现注记)
    validation = {"skipped": True}
    ...
```

**实现注记（脚本定稿前先做的小重构）**：`classify_sh_notices` 的 60 前缀闸改为参数 `code_prefixes: tuple[str, ...] = ("60",)`（默认沪市主板，测试零改动），交叉验证时以 `code_prefixes=("000","001","002","003")` + `_sz_symbol` 后缀对深市公告跑同一管道，与 `sz_periods`（官方）比对。脚本主体（续）：

```python
    sz_inferred = events_to_periods(classify_sh_notices(
        notices, next_td, code_prefixes=("000", "001", "002", "003"), suffix=".SZ"))
    validation = cross_validate(sz_periods, sz_inferred, td_sorted)
    print(f"   官方事件 {validation['total_official']} | 对齐 {validation['matched']}"
          f" | ≤2td {validation['within_2td']} | 均值 {validation['mean_signed_td']}"
          f" | 准入 {'PASS' if validation['pass'] else 'FAIL'}")

    print("④ 终态自洽检查(开区间 symbol 当前名须仍带 ST) …")
    current_names = dict(store._conn.execute(
        "SELECT symbol, ANY_VALUE(name) FROM instruments GROUP BY symbol").fetchall())
    suspects = [p.symbol for p in (sz_periods + sh_periods)
                if p.end is None and not is_st_name(str(current_names.get(p.symbol, "")))]
    print(f"   SUSPECT: {len(suspects)} → {suspects[:10]}")

    report = {
        "sz_periods": len(sz_periods), "sh_periods": len(sh_periods),
        "validation": {k: v for k, v in validation.items() if k != "details"},
        "validation_details_sample": validation.get("details", [])[:50],
        "suspects": suspects,
    }
    Path("data/st_backfill_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("   报告 → data/st_backfill_report.json")

    if args.check_only:
        return 0 if validation["pass"] else 1
    if not validation["pass"]:
        print("✗ 交叉验证未达准入门, 沪市区间不入库(设计 §3.4); 深市官方区间照常入库")
        n = store.save_st_periods(sz_periods)
    else:
        n = store.save_st_periods(sz_periods + sh_periods)
    print(f"⑤ 入库 st_status_periods: {n} 行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

（`classify_sh_notices` 增加 `code_prefixes=("60",)` 与 `suffix=".SH"` 两个默认参数——Task 4 测试不改仍绿；脚本内伪代码段落以此定稿，去掉上面探索性残句。）

- [ ] **Step 2: 实跑（网络, ~2 分钟）**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python scripts/backfill_st_status.py`
Expected: 交叉验证打印误差分布；准入 PASS → 深沪区间全入库；报告 JSON 落盘。**若 FAIL：只入深市官方区间，并把误差分布贴进 report 文档，设计 §3.4 回炉条款生效（G7 只能给出深市口径的部分结论，如实标注）**

- [ ] **Step 3: 抽查已知案例**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python -c "
from src.infrastructure.persistence.market_data_store import MarketDataStore
s = MarketDataStore('data/market.duckdb', read_only=True)
rows = [p for p in s.load_st_periods() if p.symbol in ('000656.SZ','002731.SZ')]
[print(p) for p in rows]"`
Expected: 000656（*ST金科→金科股份 2026-07-02 摘帽）、002731（ST萃华→*ST萃华 2026-07-07 升档）与官方流一致

---

### Task 8: G7 重验（F01 重跑 + gate 重跑）+ 文档收编

**Files:**
- Create: `docs/feat/0711-st-honesty/2026-07-11-st-honesty-report.md`
- Modify: `docs/rules/debt-ledger.md`（DD-6 行核销/更新 + G7 结论）、`docs/feat/0710-six-sigma-evolution/2026-07-10-six-sigma-evolution-design.md` §11（E3 状态）

- [ ] **Step 1: F01 全窗口重跑（WSL 离线, ~15 分钟）**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python scripts/run_f01_investability.py`
Expected: top_n {20,10,30} 三组入库 `backtest_runs`（params 自带 repro 块）；与 2026-07-10 基线（run_id `20260710-23*`）逐项对照 total_return/max_drawdown/sharpe

- [ ] **Step 2: gate 口径重跑**

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python scripts/mainboard_f01_gate.py`
Expected: 输出 OOS Sharpe/回撤 判据结论——**PASS/FAIL 都是合法结果**（FAIL = 不上真钱回研究阶段，判据的存在意义）

- [ ] **Step 3: 报告 + 台账 + verify_all**

报告内容：区间统计（深/沪各多少、SUSPECT 清单）、交叉验证误差分布、F01 三组 Δ 表、gate 结论 → G7 判定；台账 DD-6 行按结论核销或更新；0710 §11 E3 行标注状态。

Run: `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python scripts/verify_all.py`
Expected: 全绿

---

## Self-Review 记录

1. **Spec coverage**：§3.1→Task5 DDL；§3.2→Task3；§3.3→Task4；§3.4 交叉验证+终态自洽→Task4(纯函数)+Task7(实跑准入)；§3.5→Task7；§4.1→Task5 loader；§4.2→Task6(11 构造点)；§4.3→Task6(policy 注入)；§4.4→Task6(builder 修正, 实盘零改动=auto_trade 装配不传)；§五 G7→Task8；§六测试策略→Task1-6 各红绿；is_tradable 地雷（设计§4.1 勘误）→Task2。无缺口。
2. **Placeholder scan**：Task7 Step1 中段探索性残句已由"实现注记"定稿条款替换（classify 加 `code_prefixes/suffix` 参数）；其余无 TBD。
3. **Type consistency**：`StPeriod(symbol,start,end,label,source,evidence)` 贯穿 3/4/5/7；`build_status_registry(store,*,start,end)` 5/6/7 一致；`is_st_fn(symbol, ts)->bool` 6 内一致；`correct_st_name(name,*,is_st)` 1/6 一致（关键字调用）。
