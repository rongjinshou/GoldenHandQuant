"""研究记录退役清理 — 一次性/按需批量删除 backtest_runs/factor_verdicts 调测残留。

背景: 判决/回测列表长期无清理机制, 调测阶段的反复试跑残留会淹没真实研究记录
(见 docs/feat/0705-research-retire/2026-07-05-research-retire-design.md)。

用法:
    python scripts/prune_research_runs.py                                    # dry-run: 列出全部轮次
    python scripts/prune_research_runs.py --before 2026-07-01                # dry-run: 标注选中集
    python scripts/prune_research_runs.py --before 2026-07-01 --keep RUN_ID  # dry-run: 标注+排除保留项
    python scripts/prune_research_runs.py --ids id1,id2 --yes                # 执行: 精确删除
    python scripts/prune_research_runs.py --before 2026-07-01 --yes          # 执行: 批量删除

删除前自动把选中轮次的完整行(含 equity_curve/trades/reasons)备份到
data/backups/research_prune_<时间戳>.json, 备份失败则中止不删。
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, os.getcwd())

from src.infrastructure.persistence.market_data_store import MarketDataStore  # noqa: E402

DB_PATH = "data/market.duckdb"
BACKUP_DIR = Path("data/backups")


def select_runs(
    runs: list[dict], before: str | None, ids: set[str] | None, keep: set[str]
) -> list[dict]:
    """纯函数: 按 before(created_at 早于)/ids(精确) 选择, keep 始终排除。"""
    if ids is not None:
        selected = [r for r in runs if r["run_id"] in ids]
    elif before is not None:
        selected = [r for r in runs if r["created_at"] < before]
    else:
        selected = []
    return [r for r in selected if r["run_id"] not in keep]


def backup(selected_backtests: list[dict], selected_verdicts: list[dict]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = BACKUP_DIR / f"research_prune_{ts}.json"
    path.write_text(
        json.dumps(
            {"backtest_runs": selected_backtests, "factor_verdicts": selected_verdicts},
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--before", help="删除 created_at 早于此日期(YYYY-MM-DD)的轮次")
    parser.add_argument("--ids", help="精确指定要删除的 run_id, 逗号分隔")
    parser.add_argument("--keep", default="", help="即使命中选择器也保留的 run_id, 逗号分隔")
    parser.add_argument("--yes", action="store_true", help="执行删除(默认只预览)")
    args = parser.parse_args()

    ids = set(args.ids.split(",")) if args.ids else None
    keep = {k for k in args.keep.split(",") if k}

    # 列表阶段一律只读连接(纯查看不该抢写锁); --yes 时删除阶段单独开写连接
    store = MarketDataStore(DB_PATH, read_only=True)
    try:
        all_backtests = store.load_backtest_runs(limit=10_000)
        all_verdicts = store.load_verdict_runs()
    finally:
        store.close()

    sel_bt = select_runs(all_backtests, args.before, ids, keep)
    sel_vd = select_runs(all_verdicts, args.before, ids, keep)

    print(f"回测: 共 {len(all_backtests)} 轮, 选中 {len(sel_bt)} 轮删除")
    for r in sel_bt:
        print(f"  - {r['run_id']:<28} {r['created_at']}")
    print(f"判决: 共 {len(all_verdicts)} 轮, 选中 {len(sel_vd)} 轮删除")
    for r in sel_vd:
        print(f"  - {r['run_id']:<28} {r['created_at']}")

    if not (sel_bt or sel_vd):
        print("无匹配轮次, 结束。")
        return 0

    if not args.yes:
        print("\n(预览模式, 未执行删除; 加 --yes 执行, 执行前会先备份到 data/backups/)")
        return 0

    backup_path = backup(sel_bt, sel_vd)
    print(f"已备份至 {backup_path}")

    store = MarketDataStore(DB_PATH, read_only=False)
    try:
        for r in sel_bt:
            store.delete_backtest_run(r["run_id"])
        for r in sel_vd:
            store.delete_verdict_run(r["run_id"])
    finally:
        store.close()
    print(f"已删除 回测 {len(sel_bt)} 轮 / 判决 {len(sel_vd)} 轮。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
