"""前端产物新鲜度检查（设计 0704 DD-4 漂移防线; 2026-07-10 六西格玛 D1 哈希化）。

对比 frontend 源码（src/** + index.html + vite.config.ts + package.json）的
**内容哈希**与 src/interfaces/api/static/.build-stamp 里记录的构建时哈希——
源码改了而未重新 build 时退出码 1。进验收链。

为什么不用 mtime: git checkout/clone 不保留 mtime, 旧版 mtime 比对在检出后
必然误报(2026-07-10 实测 exit 1 假失败)。内容哈希跨 clone/checkout 稳定。

stamp 格式: JSON {"builtAt": ISO时间, "srcHash": "sha256:..."}
（frontend/scripts/write-stamp.js 在 npm run build 末尾写入, 与本脚本同规格）；
旧版纯 ISO 字符串 stamp 回退 mtime 比对并提示重新 build 升级。

用法:
    python scripts/check_frontend_fresh.py            # 校验(验收链)
    python scripts/check_frontend_fresh.py --write-stamp
        # 以当前源码重写 stamp — 仅限「确认 static/ 就是当前源码构建产物」时使用
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
STAMP = ROOT / "src" / "interfaces" / "api" / "static" / ".build-stamp"

# 旧格式(mtime 模式)的宽限: build 期间源码 mtime 与 stamp 的时钟粒度差
GRACE_SECONDS = 5.0


def _source_files() -> list[Path]:
    candidates = [FRONTEND / "src", FRONTEND / "index.html",
                  FRONTEND / "vite.config.ts", FRONTEND / "package.json"]
    files: list[Path] = []
    for base in candidates:
        if base.is_dir():
            files.extend(p for p in base.rglob("*") if p.is_file())
        elif base.is_file():
            files.append(base)
    return files


def source_hash() -> str:
    """sha256(相对路径 + 内容 的有序清单)。须与 write-stamp.js 同规格。"""
    h = hashlib.sha256()
    entries = sorted(
        (p.relative_to(FRONTEND).as_posix(), p) for p in _source_files()
    )
    for rel, p in entries:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return f"sha256:{h.hexdigest()}"


def latest_source_mtime() -> tuple[float, Path | None]:
    latest = 0.0
    latest_path: Path | None = None
    for p in _source_files():
        mtime = p.stat().st_mtime
        if mtime > latest:
            latest, latest_path = mtime, p
    return latest, latest_path


def _check_legacy(stamp_text: str) -> int:
    stamp_time = datetime.fromisoformat(stamp_text).timestamp()
    src_time, src_path = latest_source_mtime()
    if src_time > stamp_time + GRACE_SECONDS:
        dt = datetime.fromtimestamp(src_time, tz=UTC).isoformat(timespec="seconds")
        print(f"[fresh] FAIL: {src_path} ({dt}) 晚于 build stamp — 改了 frontend/ 未重新 build"
              " (旧格式 mtime 比对, git checkout 后会误报; 重新 npm run build 升级为哈希)")
        return 1
    print("[fresh] OK: 产物不落后于源码 (旧格式 mtime 比对; 建议重新 build 升级为哈希)")
    return 0


def main() -> int:
    if not FRONTEND.exists():
        print("[fresh] frontend/ 不存在, 跳过")
        return 0

    if "--write-stamp" in sys.argv:
        STAMP.parent.mkdir(parents=True, exist_ok=True)
        STAMP.write_text(json.dumps({
            "builtAt": datetime.now(tz=UTC).isoformat(timespec="milliseconds"),
            "srcHash": source_hash(),
        }) + "\n", encoding="utf-8")
        print(f"[fresh] stamp 已按当前源码重写: {STAMP}")
        return 0

    if not STAMP.exists():
        print(f"[fresh] FAIL: 缺 {STAMP} — 从未 build 过? 先 npm run build")
        return 1

    stamp_text = STAMP.read_text(encoding="utf-8").strip()
    try:
        stamp = json.loads(stamp_text)
    except json.JSONDecodeError:
        return _check_legacy(stamp_text)

    expected = stamp.get("srcHash", "")
    actual = source_hash()
    if actual != expected:
        print("[fresh] FAIL: frontend 源码内容与 build stamp 哈希不一致 — "
              "改了 frontend/ 未重新 npm run build")
        print(f"        stamp: {expected}")
        print(f"        当前:  {actual}")
        return 1
    print(f"[fresh] OK: 源码哈希与构建戳一致 (builtAt={stamp.get('builtAt', '?')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
