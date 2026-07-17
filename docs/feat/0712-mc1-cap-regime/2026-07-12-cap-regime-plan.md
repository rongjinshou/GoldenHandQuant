# MC-1 市值口径统一 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `fundamental_snapshots.market_cap` 统一为时点总市值（历史迁移+日增量+门禁固化+重跑），周二首采前完成。

**Architecture:** 迁移与同步的核心逻辑放 `src/infrastructure/persistence/cap_regime.py`（接收 duckdb 连接/注入 fetcher，可测），脚本层薄壳；门禁扩 `data_quality.py`；编排器加一步。设计：同目录 design.md（DD-1..DD-6）。

**Tech Stack:** DuckDB（ATTACH 跨库 UPDATE/ASOF 思路用窗口 SQL 实现）、tushare/akshare 注入式 fetcher、pytest AAA。

## Global Constraints

- 不 commit（延续既定状态）；WSL python `/home/rongjinshou/miniconda3/envs/goldenhandquant/bin/python`
- 迁移幂等（备份列只初始化一次）；`market_cap_qmt` 永不被同步覆写
- sync 双源皆败必须退出码 1（口径漂移不许静默）
- 新旧基线禁跨口径比较：新 run 的 params 带 `"cap": "total_mv"`

---

### Task 1: 历史迁移核心 `cap_regime.migrate_market_cap`

**Files:**
- Create: `src/infrastructure/persistence/cap_regime.py`
- Create: `scripts/migrate_market_cap.py`（薄壳：连库→调函数→打印/落报告）
- Test: `tests/infrastructure/persistence/test_cap_regime.py`

**Interfaces:**
- Produces: `migrate_market_cap(con, ts_db_path: str, *, max_gap_days: int = 16) -> dict`（con=market.duckdb 可写连接；返回 `{"backed_up": int, "direct": int, "asof": int, "kept": int}`；幂等）

- [ ] **Step 1: 失败测试**

```python
"""市值口径迁移: 备份幂等/直配/as-of 回填(≤gap)/超 gap 保留(设计 DD-2)。"""
from datetime import date

import duckdb

from src.infrastructure.persistence.cap_regime import migrate_market_cap


def _mk_market(con):
    con.execute("""CREATE TABLE fundamental_snapshots (
        symbol VARCHAR, date DATE, source VARCHAR, name VARCHAR,
        list_date DATE, market_cap DOUBLE, roe_ttm DOUBLE, ocf_ttm DOUBLE,
        pe_ratio DOUBLE, pb_ratio DOUBLE, earnings_growth DOUBLE, revenue_growth DOUBLE)""")
    rows = [
        ("000021.SZ", date(2024, 1, 5), "qmt", 100e8),   # 直配日
        ("000021.SZ", date(2024, 1, 8), "qmt", 101e8),   # ts 缺该日 → as-of 回填(1/5 值)
        ("000021.SZ", date(2024, 3, 8), "qmt", 102e8),   # 距最近 ts 超 gap → 保留
    ]
    for sym, d, src, mc in rows:
        con.execute("INSERT INTO fundamental_snapshots VALUES (?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL)",
                    [sym, d, src, "深科技", date(2000, 1, 1), mc])


def _mk_ts(path):
    ts = duckdb.connect(path)
    ts.execute("CREATE TABLE ts_daily_basic (ts_code VARCHAR, trade_date VARCHAR, total_mv DOUBLE)")
    ts.execute("INSERT INTO ts_daily_basic VALUES ('000021.SZ','20240105', 1500000)")  # 万元→150亿
    ts.close()


def test_direct_asof_kept_and_idempotent(tmp_path):
    ts_path = str(tmp_path / "ts.duckdb")
    _mk_ts(ts_path)
    con = duckdb.connect(str(tmp_path / "m.duckdb"))
    _mk_market(con)

    stats = migrate_market_cap(con, ts_path)
    assert stats == {"backed_up": 3, "direct": 1, "asof": 1, "kept": 1}
    got = dict(con.execute(
        "SELECT date, market_cap FROM fundamental_snapshots WHERE symbol='000021.SZ'").fetchall())
    assert got[date(2024, 1, 5)] == 1500000 * 1e4          # 直配
    assert got[date(2024, 1, 8)] == 1500000 * 1e4          # as-of 前值
    assert got[date(2024, 3, 8)] == 102e8                   # 超 gap 保留 QMT
    backup = dict(con.execute(
        "SELECT date, market_cap_qmt FROM fundamental_snapshots WHERE symbol='000021.SZ'").fetchall())
    assert backup[date(2024, 1, 5)] == 100e8                # 原值入备份列

    stats2 = migrate_market_cap(con, ts_path)               # 幂等: 备份不重置
    assert stats2["backed_up"] == 0
    assert dict(con.execute(
        "SELECT date, market_cap_qmt FROM fundamental_snapshots WHERE symbol='000021.SZ'"
    ).fetchall())[date(2024, 1, 5)] == 100e8
```

- [ ] **Step 2: 跑红** `pytest tests/infrastructure/persistence/test_cap_regime.py -q` → FAIL(模块不存在)

- [ ] **Step 3: 实现**

```python
"""市值口径统一(MC-1, 设计 docs/feat/0712-mc1-cap-regime DD-2/DD-3)。"""
import logging

logger = logging.getLogger(__name__)


def migrate_market_cap(con, ts_db_path: str, *, max_gap_days: int = 16) -> dict:
    """历史迁移: 备份(幂等)→直配→as-of 回填(≤max_gap_days 日历日≈10 交易日)→保留计数。"""
    cols = {r[1] for r in con.execute("PRAGMA table_info('fundamental_snapshots')").fetchall()}
    if "market_cap_qmt" not in cols:
        con.execute("ALTER TABLE fundamental_snapshots ADD COLUMN market_cap_qmt DOUBLE")
    backed_up = con.execute(
        """UPDATE fundamental_snapshots SET market_cap_qmt = market_cap
           WHERE market_cap_qmt IS NULL"""
    ).fetchone()
    backed_up_n = int(backed_up[0]) if backed_up else 0

    con.execute(f"ATTACH '{ts_db_path}' AS ts (READ_ONLY)")
    try:
        direct = con.execute(
            """UPDATE fundamental_snapshots AS f
               SET market_cap = t.total_mv * 10000.0
               FROM ts.ts_daily_basic AS t
               WHERE t.ts_code = f.symbol
                 AND strptime(t.trade_date, '%Y%m%d')::DATE = f.date
                 AND t.total_mv > 0"""
        ).fetchone()
        direct_n = int(direct[0]) if direct else 0

        # as-of 回填: 未直配(仍等于备份值)的行, 取该股 ≤date 的最近 ts 值且间隔 ≤ gap
        asof = con.execute(
            f"""UPDATE fundamental_snapshots AS f
                SET market_cap = x.mv
                FROM (
                  SELECT f2.symbol, f2.date,
                         (SELECT t.total_mv * 10000.0 FROM ts.ts_daily_basic t
                          WHERE t.ts_code = f2.symbol AND t.total_mv > 0
                            AND strptime(t.trade_date, '%Y%m%d')::DATE <= f2.date
                            AND strptime(t.trade_date, '%Y%m%d')::DATE
                                >= f2.date - INTERVAL {max_gap_days} DAY
                          ORDER BY t.trade_date DESC LIMIT 1) AS mv
                  FROM fundamental_snapshots f2
                  WHERE f2.market_cap = f2.market_cap_qmt
                ) AS x
                WHERE x.symbol = f.symbol AND x.date = f.date AND x.mv IS NOT NULL
                  AND f.market_cap = f.market_cap_qmt"""
        ).fetchone()
        asof_n = int(asof[0]) if asof else 0
    finally:
        con.execute("DETACH ts")

    kept_n = con.execute(
        "SELECT COUNT(*) FROM fundamental_snapshots WHERE market_cap = market_cap_qmt"
    ).fetchone()[0]
    stats = {"backed_up": backed_up_n, "direct": direct_n, "asof": asof_n, "kept": int(kept_n)}
    logger.info("market_cap 迁移: %s", stats)
    return stats
```

（注：DuckDB `UPDATE ... RETURNING` 不可用时，用 `con.execute(...); con.execute("SELECT changes()")` 兜底——实现时以实际 API 为准，测试锁行为不锁实现。"直配后仍等于备份值"作为未迁移判定的前提：total_mv 与 QMT 值恰好相等的概率按浮点视为可忽略，可接受。）

薄壳 `scripts/migrate_market_cap.py`：连 `data/market.duckdb` → 调函数 → 打印 stats + 复跑审计 SQL（07-10 中位比值）→ 报告 `data/mc1_migration_report.json`。

- [ ] **Step 4: 跑绿 + ruff**

---

### Task 2: 日增量 `sync_latest_market_cap` + 编排器接线

**Files:**
- Modify: `src/infrastructure/persistence/cap_regime.py`（追加）
- Create: `scripts/sync_market_cap.py`
- Modify: `src/application/shadow_ops.py`（上午段 index-bars 与 auto-trade 之间插 `("sync-market-cap", [python, "scripts/sync_market_cap.py"])`）
- Test: `tests/infrastructure/persistence/test_cap_regime.py`（追加）、`tests/application/test_shadow_ops.py`（步骤序列断言更新）

**Interfaces:**
- Produces: `sync_latest_market_cap(con, *, fetch_primary, fetch_fallback) -> dict`：`fetch_*() -> dict[symbol, float(元)] | None`（None/空=该源不可用）；返回 `{"day": str, "updated": int, "source": "tushare"|"akshare"}`；双源皆败 → `raise RuntimeError`（脚本层转退出码 1）

- [ ] **Step 1: 追加失败测试**

```python
def _mk_market_today(con):
    _mk_market(con)  # 复用
    con.execute("INSERT INTO fundamental_snapshots VALUES ('000021.SZ', DATE '2024-03-11', 'qmt', '深科技', DATE '2000-01-01', 103e8, NULL,NULL,NULL,NULL,NULL,NULL)")


def test_sync_primary_then_fallback_then_fail(tmp_path):
    from src.infrastructure.persistence.cap_regime import sync_latest_market_cap
    con = duckdb.connect(str(tmp_path / "m2.duckdb"))
    _mk_market_today(con)
    con.execute("CREATE TABLE bars (symbol VARCHAR, date DATE, source VARCHAR)")
    con.execute("INSERT INTO bars VALUES ('000021.SZ', DATE '2024-03-11', 'qmt')")

    r = sync_latest_market_cap(con, fetch_primary=lambda day: {"000021.SZ": 155e8},
                               fetch_fallback=lambda: None)
    assert r["source"] == "tushare" and r["updated"] == 1 and r["day"] == "2024-03-11"
    assert con.execute("SELECT market_cap FROM fundamental_snapshots WHERE date=DATE '2024-03-11'").fetchone()[0] == 155e8

    r2 = sync_latest_market_cap(con, fetch_primary=lambda day: None,
                                fetch_fallback=lambda: {"000021.SZ": 156e8})
    assert r2["source"] == "akshare" and r2["updated"] == 1

    import pytest
    with pytest.raises(RuntimeError):
        sync_latest_market_cap(con, fetch_primary=lambda day: None, fetch_fallback=lambda: None)
```

`test_shadow_ops.py` 的 `test_step_order_and_argv`/`test_chain_and_digest` 期望序列改为
`["data-refresh", "index-bars", "sync-market-cap", "auto-trade-once"]`（收盘链不加 sync——比对用当日快照已含正确市值；仅上午段决策前需要）。

- [ ] **Step 2: 跑红 → Step 3: 实现**

```python
def sync_latest_market_cap(con, *, fetch_primary, fetch_fallback) -> dict:
    """把 bars 最新交易日的 market_cap 覆写为时点总市值(设计 DD-3)。

    fetch_primary(day: str YYYYMMDD) -> dict[symbol, 元] | None (tushare daily_basic)
    fetch_fallback() -> dict[symbol, 元] | None (akshare spot, 盘后≈收盘)
    双源皆败 raise RuntimeError —— 口径漂移必须显性。market_cap_qmt 不动。
    """
    day = con.execute("SELECT MAX(date) FROM bars").fetchone()[0]
    if day is None:
        raise RuntimeError("bars 为空, 无法确定最新交易日")
    caps = fetch_primary(day.strftime("%Y%m%d"))
    source = "tushare"
    if not caps:
        caps = fetch_fallback()
        source = "akshare"
    if not caps:
        raise RuntimeError(f"{day} 市值同步双源皆不可用(tushare/akshare), 拒绝静默回退 QMT 口径")
    con.execute("CREATE TEMP TABLE _caps (symbol VARCHAR, mv DOUBLE)")
    con.executemany("INSERT INTO _caps VALUES (?, ?)", list(caps.items()))
    n = con.execute(
        """UPDATE fundamental_snapshots AS f SET market_cap = c.mv
           FROM _caps c WHERE c.symbol = f.symbol AND f.date = ?""", [day]).fetchone()
    con.execute("DROP TABLE _caps")
    return {"day": day.isoformat(), "updated": int(n[0]) if n else 0, "source": source}
```

脚本薄壳：真实 fetcher（tushare env 注入同 harvest；akshare `stock_zh_a_spot_em` 取 `代码/总市值` 列，代码补后缀）；`--db` 参数；打印结果。编排器插步 + 既有测试序列更新。

- [ ] **Step 4: 跑绿（含 shadow_ops 全量）+ ruff**

---

### Task 3: 门禁 C8/C9 + 名称刷新

**Files:**
- Modify: `src/infrastructure/persistence/data_quality.py`（追加两检查，挂进 run_quality_checks）
- Create: `scripts/refresh_instrument_names.py`
- Test: `tests/infrastructure/persistence/test_data_quality.py`（追加，沿用该文件既有 fixture 风格）

**Interfaces:**
- Produces: `check_cap_cross_source(con, ts_db_path="data/tushare.duckdb", *, sample=500, tol=0.02, max_bad_ratio=0.01) -> CheckResult(status in PASS/FAIL/SKIP)`；`check_name_freshness(con, ts_db_path=..., warn_threshold=50) -> CheckResult(PASS/WARN/SKIP)`（CheckResult 沿用 data_quality 既有结构；ts 库不可达 → SKIP）

- [ ] **Step 1: 失败测试（tmp duckdb 双库 fixture：一致→PASS；植入 3% 偏差×2% 样本→FAIL；无 ts 库→SKIP；名称不一致 60 只→WARN）**
- [ ] **Step 2: 红 → Step 3: 实现（抽样 = 最新共同日 ORDER BY random() LIMIT sample；名称对照 = instruments.name vs ts_stock_basic.name(L 状态) 优先、bak 末日名兜底）→ Step 4: 绿 + ruff**

`refresh_instrument_names.py`：`UPDATE instruments SET name = 新名 FROM (ts_stock_basic L ∪ bak 末日名) WHERE 不一致`，打印更新数与样例；幂等。

---

### Task 4: 迁移实跑 + 重跑三件套 + 等价性

- [ ] 实跑 `migrate_market_cap.py`：覆写率 ≥99%、审计中位→1.000、报告落盘
- [ ] 实跑 `refresh_instrument_names.py` + `quant data status --check`（C8/C9 生效）
- [ ] 主 gate 重跑（`mainboard_f01_gate.py`）：PASS 且与 overlay 版四格容差 ±2pp
- [ ] `quant factor-test --factors P0 --split-date 2024-06-30`（WSL 向量化离线）新 verdict 入库
- [ ] `run_f01_investability.py` 三组新基线（脚本 params 加 `"cap": "total_mv"` 标签——改 run_f01 的 params 组装一行）
- [ ] `verify_all` 全绿

### Task 5: 文档收编

- [ ] design/plan/report（含迁移统计+等价性数字）
- [ ] debt-ledger：MC-1 核销、**MC-2 挂账**（pe/pb 同族失真，研究线重启前必审）
- [ ] decision-log 增行；CLAUDE.md（sync/migrate 命令）；runbook §5（编排器新步骤说明）；0710 §11 状态

## Self-Review 记录

1. 覆盖：DD-1/2→T1；DD-3→T2；DD-4(+名称刷新)→T3；DD-5→T4；DD-6(零代码)+文档→T5。
2. 占位符：无 TBD；T3 Step1 的 fixture 细节以既有 test_data_quality 风格现场对齐（该文件已有同构造模式，不属未定义引用）。
3. 类型一致：`migrate_market_cap(con, ts_db_path, *, max_gap_days)` / `sync_latest_market_cap(con, *, fetch_primary, fetch_fallback)` / CheckResult 复用既有——贯穿一致。
