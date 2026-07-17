"""MC-1 历史迁移薄壳: fundamental_snapshots.market_cap → 时点总市值。

用法: python scripts/migrate_market_cap.py  (幂等; 设计 docs/feat/0712-mc1-cap-regime DD-2)
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import duckdb  # noqa: E402

from src.infrastructure.persistence.cap_regime import migrate_market_cap  # noqa: E402


def main() -> int:
    con = duckdb.connect("data/market.duckdb")
    stats = migrate_market_cap(con, "data/tushare.duckdb")
    total = stats["direct"] + stats["asof"] + stats["kept"]
    print(f"迁移完成: {stats} | 覆写率 {(stats['direct'] + stats['asof']) / max(total, 1):.2%}")

    # 审计复查: 与 tushare 直接对照的中位比值应≈1.000(直配行按构造=1)
    con.execute("ATTACH 'data/tushare.duckdb' AS ts (READ_ONLY)")
    audit = {}
    for d, ds in (("2026-07-10", "20260710"), ("2024-01-05", "20240105"), ("2022-06-01", "20220601")):
        row = con.execute(f"""
            SELECT COUNT(*), median(f.market_cap / (t.total_mv*10000.0)),
                   SUM(CASE WHEN abs(f.market_cap/(t.total_mv*10000.0) - 1) > 0.01 THEN 1 ELSE 0 END)
            FROM fundamental_snapshots f
            JOIN ts.ts_daily_basic t ON t.ts_code=f.symbol AND t.trade_date='{ds}'
            WHERE f.date=DATE '{d}' AND f.market_cap>0 AND t.total_mv>0""").fetchone()
        audit[d] = {"n": row[0], "median_ratio": round(row[1], 6), "gt1pct": row[2]}
        print(f"  审计 {d}: 对齐 {row[0]} | 中位比值 {row[1]:.6f} | >1%差 {row[2]}")
    con.execute("DETACH ts")

    Path("data/mc1_migration_report.json").write_text(
        json.dumps({"stats": stats, "audit": audit}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("报告 → data/mc1_migration_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
