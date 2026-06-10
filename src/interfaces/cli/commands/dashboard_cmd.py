"""quant dashboard 子命令 — 启动本机投研驾驶舱。"""

import argparse
import os


def run_dashboard(args: argparse.Namespace) -> None:
    import uvicorn

    os.environ["GHQ_MARKET_DB"] = args.db
    print(f"投研驾驶舱: http://127.0.0.1:{args.port}/ui/  (数据库: {args.db}, Ctrl+C 退出)")
    uvicorn.run(
        "src.interfaces.api.app:app",
        host="127.0.0.1",  # 设计 D4: 仅本机, 不开放局域网
        port=args.port,
        log_level="info",
    )
