"""前端产物新鲜度检查（设计 0704 DD-4 漂移防线）。

对比 frontend/src/** 与 vite.config.ts/package.json 的最新 mtime 和
src/interfaces/api/static/.build-stamp 的构建时间——源码更新而未重新
build 时退出码 1。进验收链（改了 frontend/ 必须重新 build 才能过）。

用法: python scripts/check_frontend_fresh.py
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
STAMP = ROOT / "src" / "interfaces" / "api" / "static" / ".build-stamp"

# 允许的宽限: build 期间源码 mtime 与 stamp 的时钟粒度差
GRACE_SECONDS = 5.0


def latest_source_mtime() -> tuple[float, Path | None]:
    latest = 0.0
    latest_path: Path | None = None
    candidates = [FRONTEND / "src", FRONTEND / "index.html",
                  FRONTEND / "vite.config.ts", FRONTEND / "package.json"]
    for base in candidates:
        paths = base.rglob("*") if base.is_dir() else [base]
        for p in paths:
            if p.is_file():
                mtime = p.stat().st_mtime
                if mtime > latest:
                    latest, latest_path = mtime, p
    return latest, latest_path


def main() -> int:
    if not FRONTEND.exists():
        print("[fresh] frontend/ 不存在, 跳过")
        return 0
    if not STAMP.exists():
        print(f"[fresh] FAIL: 缺 {STAMP} — 从未 build 过? 先 npm run build")
        return 1
    stamp_time = datetime.fromisoformat(STAMP.read_text().strip()).timestamp()
    src_time, src_path = latest_source_mtime()
    if src_time > stamp_time + GRACE_SECONDS:
        dt = datetime.fromtimestamp(src_time, tz=UTC).isoformat(timespec="seconds")
        print(f"[fresh] FAIL: {src_path} ({dt}) 晚于 build stamp — 改了 frontend/ 未重新 build")
        return 1
    print("[fresh] OK: 产物不落后于源码")
    return 0


if __name__ == "__main__":
    sys.exit(main())
