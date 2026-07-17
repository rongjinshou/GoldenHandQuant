"""市值口径统一(MC-1): 历史迁移 + 日增量同步。

设计: docs/feat/0712-mc1-cap-regime DD-2/DD-3。
`market_cap` 语义 = 时点总市值; 原 QMT 口径备份于 `market_cap_qmt`(永不被同步覆写)。
"""
import logging

logger = logging.getLogger(__name__)


def _changed(result) -> int:
    """duckdb UPDATE 的受影响行数(结果集单行单列)。"""
    row = result.fetchone()
    return int(row[0]) if row else 0


def migrate_fundamental_field(
    con, ts_db_path: str, *,
    field: str, ts_col: str, backup_col: str,
    scale: float = 1.0, max_gap_days: int = 16,
) -> dict:
    """通用历史迁移(幂等): 备份→直配→as-of 回填(≤max_gap_days 日历日)→保留计数。

    field/ts_col/backup_col 为受控标识符(调用方硬编码, 非用户输入), 直接内插 SQL。
    MC-1(market_cap←total_mv×1e4) 与 MC-2(pe_ratio←pe_ttm, pb_ratio←pb) 共用。
    """
    cols = {r[1] for r in con.execute("PRAGMA table_info('fundamental_snapshots')").fetchall()}
    if backup_col not in cols:
        con.execute(f"ALTER TABLE fundamental_snapshots ADD COLUMN {backup_col} DOUBLE")
    backed_up = _changed(con.execute(
        f"UPDATE fundamental_snapshots SET {backup_col} = {field} "
        f"WHERE {backup_col} IS NULL"))

    con.execute(f"ATTACH '{ts_db_path}' AS ts (READ_ONLY)")
    try:
        direct = _changed(con.execute(
            f"""UPDATE fundamental_snapshots AS f
               SET {field} = t.{ts_col} * {float(scale)}
               FROM ts.ts_daily_basic AS t
               WHERE t.ts_code = f.symbol
                 AND strptime(t.trade_date, '%Y%m%d')::DATE = f.date
                 AND t.{ts_col} > 0"""))

        # as-of 回填: 未被直配(仍等于备份值或双 NULL)的行, 取该股 ≤date 最近 ts 值且间隔 ≤ gap
        asof = _changed(con.execute(
            f"""UPDATE fundamental_snapshots AS f
                SET {field} = x.mv
                FROM (
                  SELECT f2.symbol, f2.date,
                         (SELECT t.{ts_col} * {float(scale)} FROM ts.ts_daily_basic t
                          WHERE t.ts_code = f2.symbol AND t.{ts_col} > 0
                            AND strptime(t.trade_date, '%Y%m%d')::DATE <= f2.date
                            AND strptime(t.trade_date, '%Y%m%d')::DATE
                                >= f2.date - INTERVAL {int(max_gap_days)} DAY
                          ORDER BY t.trade_date DESC LIMIT 1) AS mv
                  FROM fundamental_snapshots f2
                  WHERE f2.{field} IS NOT DISTINCT FROM f2.{backup_col}
                ) AS x
                WHERE x.symbol = f.symbol AND x.date = f.date AND x.mv IS NOT NULL
                  AND f.{field} IS NOT DISTINCT FROM f.{backup_col}"""))
    finally:
        con.execute("DETACH ts")

    kept = con.execute(
        f"SELECT COUNT(*) FROM fundamental_snapshots WHERE {field} IS NOT DISTINCT FROM {backup_col}"
    ).fetchone()[0]
    stats = {"backed_up": backed_up, "direct": direct, "asof": asof, "kept": int(kept)}
    logger.info("%s 迁移: %s", field, stats)
    return stats


def migrate_market_cap(con, ts_db_path: str, *, max_gap_days: int = 16) -> dict:
    """MC-1: market_cap ← 时点总市值(total_mv 万元 ×1e4)。见 migrate_fundamental_field。"""
    return migrate_fundamental_field(
        con, ts_db_path, field="market_cap", ts_col="total_mv",
        backup_col="market_cap_qmt", scale=10000.0, max_gap_days=max_gap_days)


def sync_latest_market_cap(con, *, fetch_primary, fetch_fallback,
                           max_back_days: int = 4) -> dict:
    """把最近可得交易日的 market_cap 覆写为时点总市值(设计 DD-3 + 0713 彩排修订)。

    fetch_primary(day: str YYYYMMDD) -> dict[symbol, 元] | None   (tushare daily_basic)
    fetch_fallback() -> dict[symbol, 元] | None                    (akshare spot, 盘后≈收盘)

    盘中语义(0713 彩排实证): tushare 当日数据盘后才发布 → 从 bars 最新日起向前回退
    (≤max_back_days 个交易日)找最近有数据的一天——决策消费的本就是 as-of T-1 行,
    昨日覆写即达目的; 当日行留待盘后/次晨链自然覆盖。
    双源皆败 raise RuntimeError —— 口径漂移必须显性; market_cap_qmt 不动。
    """
    days = [r[0] for r in con.execute(
        "SELECT DISTINCT date FROM bars ORDER BY date DESC LIMIT ?",
        [int(max_back_days)]).fetchall()]
    if not days:
        raise RuntimeError("bars 为空, 无法确定最新交易日")
    day = caps = None
    source = "tushare"
    for candidate in days:
        got = fetch_primary(candidate.strftime("%Y%m%d"))
        if got:
            day, caps = candidate, got
            break
    if not caps:
        caps = fetch_fallback()
        source = "akshare"
        day = days[0]  # spot≈当前时点, 归到最新交易日
    if not caps:
        raise RuntimeError(
            f"{days[0]} 市值同步双源皆不可用(tushare 近{len(days)}日无数据+akshare 失败), "
            "拒绝静默回退 QMT 口径")
    con.execute("CREATE OR REPLACE TEMP TABLE _caps (symbol VARCHAR, mv DOUBLE)")
    con.executemany("INSERT INTO _caps VALUES (?, ?)", list(caps.items()))
    updated = _changed(con.execute(
        """UPDATE fundamental_snapshots AS f SET market_cap = c.mv
           FROM _caps c WHERE c.symbol = f.symbol AND f.date = ?""", [day]))
    con.execute("DROP TABLE _caps")
    return {"day": day.isoformat(), "updated": updated, "source": source}
