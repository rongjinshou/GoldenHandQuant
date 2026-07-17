"""数据质量门禁 — `quant data status --check` 的检查引擎。

背景（2026-07-10 六西格玛体检 B3, 债务台账「面板级数据质量抽查未做」项）:
2025-11-25→2026-02-26 曾有 103,466 行特征 NULL 静默固化, 潜伏数周靠人肉偶然
发现。本模块把该事故的检测自动化为可挂验收链的门禁: 任一 FAIL 退出码非零。

阈值校准依据（2026-07-10 对生产 market.duckdb 实测）:
- 成熟区 NULL ma_20 = 0（修复后全年份为 0）→ 零容忍 FAIL 线;
- 预热区(距库内首根 bar < WARMUP_DAYS) NULL 属次新股合法, 不计。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from src.domain.market.services.feature_engine import WARMUP_DAYS

if TYPE_CHECKING:
    from src.infrastructure.persistence.market_data_store import MarketDataStore

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"  # 外部对照源不可用: 不判定也不失败(门禁不绑死 tushare 库存在)

# 近窗常数列检查覆盖的列（全市场 60 日方差为 0 = 计算/入库退化）
_VARIANCE_SENTINEL_COLUMNS = ("close", "volume", "ma_20", "rsi_14", "atr_14")


@dataclass(slots=True, kw_only=True)
class CheckResult:
    name: str
    status: str  # PASS / WARN / FAIL
    detail: str


def has_failure(results: list[CheckResult]) -> bool:
    return any(r.status == FAIL for r in results)


def run_quality_checks(
    store: MarketDataStore,
    *,
    today: date,
    warn_staleness_days: int = 6,
    fail_staleness_days: int = 10,
    ts_db_path: str = "data/tushare.duckdb",
) -> list[CheckResult]:
    """执行全部数据质量检查。today 注入以便测试与离线复核。"""
    conn = store._conn  # noqa: SLF001 — 同包内检查引擎, 复用店铺连接(只读查询)
    results: list[CheckResult] = []

    # 1) 固化事故哨兵: 成熟区(距库内首根 bar >= WARMUP_DAYS) NULL ma_20, 零容忍
    mature_null = conn.execute(
        f"""WITH firsts AS (SELECT symbol, MIN(date) AS d0 FROM bars GROUP BY symbol)
            SELECT COUNT(*) FROM stock_features f
            JOIN firsts b USING (symbol)
            WHERE f.date >= b.d0 + INTERVAL {int(WARMUP_DAYS)} DAY
              AND f.ma_20 IS NULL"""
    ).fetchone()[0]
    results.append(CheckResult(
        name="特征成熟区 NULL(固化哨兵)",
        status=PASS if mature_null == 0 else FAIL,
        detail=f"{mature_null} 行 (预热区次新股 NULL 不计; 零容忍)",
    ))

    # 2) bars 关键列完整性
    null_close = conn.execute(
        "SELECT COUNT(*) FROM bars WHERE close IS NULL"
    ).fetchone()[0]
    results.append(CheckResult(
        name="bars NULL close",
        status=PASS if null_close == 0 else FAIL,
        detail=f"{null_close} 行",
    ))

    # 3) 新鲜度（bars 最新日期距今）
    max_bar = conn.execute("SELECT MAX(date) FROM bars").fetchone()[0]
    if max_bar is None:
        results.append(CheckResult(
            name="数据新鲜度", status=FAIL, detail="bars 为空库"))
    else:
        staleness = (today - max_bar).days
        if staleness > fail_staleness_days:
            status = FAIL
        elif staleness > warn_staleness_days:
            status = WARN
        else:
            status = PASS
        results.append(CheckResult(
            name="数据新鲜度", status=status,
            detail=(f"bars 最新 {max_bar}, 滞后 {staleness} 天 "
                    f"(WARN>{warn_staleness_days}, FAIL>{fail_staleness_days})"),
        ))

    # 4) features 与 bars 对齐（bars 刷了、特征没跟上 → 提示重跑 refresh）
    max_feat = conn.execute("SELECT MAX(date) FROM stock_features").fetchone()[0]
    if max_bar is not None:
        if max_feat is None:
            results.append(CheckResult(
                name="features 对齐 bars", status=WARN, detail="stock_features 为空"))
        else:
            lag = (max_bar - max_feat).days
            results.append(CheckResult(
                name="features 对齐 bars",
                status=PASS if lag <= 3 else WARN,
                detail=f"features 最新 {max_feat}, 落后 bars {lag} 天",
            ))

    # 5) fundamentals 与 bars 对齐
    max_fund = conn.execute(
        "SELECT MAX(date) FROM fundamental_snapshots"
    ).fetchone()[0]
    if max_bar is not None:
        if max_fund is None:
            results.append(CheckResult(
                name="fundamentals 对齐 bars", status=WARN,
                detail="fundamental_snapshots 为空"))
        else:
            lag = (max_bar - max_fund).days
            results.append(CheckResult(
                name="fundamentals 对齐 bars",
                status=PASS if lag <= 3 else WARN,
                detail=f"fundamentals 最新 {max_fund}, 落后 bars {lag} 天",
            ))

    # 6) 近 60 日全市场常数列（方差=0/全 NULL = 退化, 台账「整窗方差=0 告警」项）
    if max_bar is not None and max_feat is not None:
        degenerate: list[str] = []
        for col in _VARIANCE_SENTINEL_COLUMNS:
            std = conn.execute(
                f"""SELECT stddev({col}) FROM stock_features
                    WHERE date >= ? - INTERVAL 60 DAY""",
                [max_feat],
            ).fetchone()[0]
            if std is None or std == 0:
                degenerate.append(col)
        results.append(CheckResult(
            name="近60日特征方差",
            status=PASS if not degenerate else WARN,
            detail="全部有效" if not degenerate else f"退化列: {', '.join(degenerate)}",
        ))

    # 7) 跨源重复（load 路径按 source 过滤, 重复无资金影响, 仅提示）
    cross_dup = conn.execute(
        """SELECT COUNT(*) FROM (
               SELECT symbol, date FROM bars GROUP BY 1, 2 HAVING COUNT(*) > 1)"""
    ).fetchone()[0]
    results.append(CheckResult(
        name="bars 跨源重复(symbol,date)",
        status=PASS if cross_dup == 0 else WARN,
        detail=f"{cross_dup} 组",
    ))

    # 8/9) 跨源对照(0712-mc1 DD-4): 市值口径漂移拦截 + 名称新鲜度观察
    results.append(check_cap_cross_source(conn, ts_db_path))
    results.append(check_name_freshness(conn, ts_db_path))

    return results


def _attach_ts(conn, ts_db_path: str, alias: str) -> bool:
    """挂载 tushare 对照库; 不可用返回 False(检查方 SKIP)。"""
    try:
        conn.execute(f"ATTACH '{ts_db_path}' AS {alias} (READ_ONLY)")
        return True
    except Exception:
        return False


def check_cap_cross_source(
    conn, ts_db_path: str = "data/tushare.duckdb", *,
    sample: int = 500, tol: float = 0.02, max_bad_ratio: float = 0.01,
) -> CheckResult:
    """C8 市值跨源偏差: 最新共同日抽样 |ours/theirs−1|>tol 的占比 > max_bad_ratio → FAIL。

    背景: MC-1(QMT 股本口径失真)由一次性审计发现, 此检查将其固化为常驻门禁——
    任一侧口径漂移回归(如 sync 断供后静默退回 QMT 值)在此被拦。
    """
    name = "市值跨源偏差(C8)"
    if not _attach_ts(conn, ts_db_path, "tsq"):
        return CheckResult(name=name, status=SKIP,
                           detail=f"对照库不可用({ts_db_path})")
    try:
        row = conn.execute(
            """WITH d AS (SELECT MAX(trade_date) AS md FROM tsq.ts_daily_basic),
               j AS (
                 SELECT f.market_cap / (t.total_mv * 10000.0) AS ratio
                 FROM fundamental_snapshots f
                 JOIN tsq.ts_daily_basic t
                   ON t.ts_code = f.symbol
                  AND t.trade_date = (SELECT md FROM d)
                  AND f.date = strptime(t.trade_date, '%Y%m%d')::DATE
                 WHERE f.market_cap > 0 AND t.total_mv > 0
                 ORDER BY random() LIMIT ?)
               SELECT COUNT(*),
                      SUM(CASE WHEN abs(ratio - 1) > ? THEN 1 ELSE 0 END)
               FROM j""",
            [sample, tol],
        ).fetchone()
        n, bad = int(row[0] or 0), int(row[1] or 0)
    finally:
        conn.execute("DETACH tsq")
    if n == 0:
        return CheckResult(name=name, status=SKIP, detail="无共同日可对照")
    ratio = bad / n
    return CheckResult(
        name=name,
        status=PASS if ratio <= max_bad_ratio else FAIL,
        detail=f"抽样 {n}, >{tol:.0%} 偏差 {bad} ({ratio:.1%}; 阈 {max_bad_ratio:.0%})",
    )


def check_name_freshness(
    conn, ts_db_path: str = "data/tushare.duckdb", *, warn_threshold: int = 50,
) -> CheckResult:
    """C9 名称新鲜度: instruments.name 落后交易所最新名的只数(观察级, 不 FAIL)。

    背景: 2026-04 戴帽潮 instruments 快照未跟上(228 只), 影响一切按当前名过滤的场景。
    """
    name = "instruments 名称新鲜度(C9)"
    if not _attach_ts(conn, ts_db_path, "tsn"):
        return CheckResult(name=name, status=SKIP,
                           detail=f"对照库不可用({ts_db_path})")
    try:
        stale = conn.execute(
            """SELECT COUNT(DISTINCT i.symbol)
               FROM instruments i
               JOIN tsn.ts_stock_basic s
                 ON s.ts_code = i.symbol AND s.list_status = 'L'
               WHERE i.delist_date IS NULL
                 AND replace(i.name, ' ', '') <> replace(s.name, ' ', '')"""
        ).fetchone()[0]
    except Exception as exc:
        conn.execute("DETACH tsn")
        return CheckResult(name=name, status=SKIP, detail=f"对照表不可用: {exc}")
    conn.execute("DETACH tsn")
    return CheckResult(
        name=name,
        status=PASS if stale <= warn_threshold else WARN,
        detail=f"{stale} 只名称落后交易所最新名(阈 {warn_threshold}; "
               f"scripts/refresh_instrument_names.py 可刷)",
    )
