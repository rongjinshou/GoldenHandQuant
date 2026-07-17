"""一键验收链（2026-07-10 六西格玛体检 D3, Control 阶段核心交付物）。

背景: 项目无 CI, 六条质量门禁散落文档靠人记得跑——门禁的存在性 ≠ 强制性。
本脚本把验收链聚合为一条命令, 全绿才退出 0:

    $WIN_PYTHON scripts/verify_all.py              # 后端全链(推荐日常)
    $WIN_PYTHON scripts/verify_all.py --frontend   # 附加前端 vitest+typecheck(慢)
    $WIN_PYTHON scripts/verify_all.py --skip-data  # 跳过数据门禁(如库文件不在)

步骤:
  1. ruff check src/ tests/ scripts/     — 静态纪律(全仓, 含测试与脚本)
  2. pytest tests/                       — 全量测试(含 gateway, 不再 --ignore)
  3. check_frontend_fresh.py             — 前端产物哈希漂移防线
  4. quant data status --check           — 数据质量门禁(NULL固化哨兵/新鲜度)
  5. [--frontend] npm test + typecheck   — 前端测试与类型(Windows powershell)
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str], *, cwd: Path = ROOT) -> tuple[str, bool, float]:
    print(f"\n=== [{name}] {' '.join(str(c) for c in cmd)}")
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=cwd)
    elapsed = time.monotonic() - t0
    ok = proc.returncode == 0
    print(f"=== [{name}] {'✓ PASS' if ok else '✗ FAIL'} ({elapsed:.1f}s)")
    return name, ok, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="一键验收链")
    parser.add_argument("--frontend", action="store_true",
                        help="附加前端 vitest + vue-tsc(需 Windows node, 慢)")
    parser.add_argument("--skip-data", action="store_true",
                        help="跳过数据质量门禁")
    args = parser.parse_args()

    py = sys.executable
    results: list[tuple[str, bool, float]] = []

    results.append(run_step("ruff", [py, "-m", "ruff", "check", "src/", "tests/", "scripts/"]))
    results.append(run_step("pytest", [py, "-m", "pytest", "tests/", "-q"]))
    results.append(run_step("frontend-fresh", [py, "scripts/check_frontend_fresh.py"]))

    if args.skip_data:
        print("\n=== [data-quality] 跳过 (--skip-data)")
    elif not (ROOT / "data" / "market.duckdb").exists():
        print("\n=== [data-quality] 跳过 (data/market.duckdb 不存在)")
    else:
        results.append(run_step(
            "data-quality",
            [py, "-m", "src.interfaces.cli.quant", "data", "status", "--check"]))

    if args.frontend:
        ps = ["powershell.exe", "-NoProfile", "-Command"]
        results.append(run_step(
            "vitest", [*ps, "cd C:\\Codes\\GoldenHandQuant\\frontend; npm run test"]))
        results.append(run_step(
            "typecheck", [*ps, "cd C:\\Codes\\GoldenHandQuant\\frontend; npm run typecheck"]))

    print("\n" + "=" * 52)
    print("验收链汇总:")
    all_ok = True
    for name, ok, elapsed in results:
        print(f"  {'✓' if ok else '✗'} {name:<16} {elapsed:>7.1f}s")
        all_ok = all_ok and ok
    print("=" * 52)
    print("✓ 全绿" if all_ok else "✗ 存在失败项 — 修复后重跑")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
