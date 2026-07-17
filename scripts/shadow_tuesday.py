"""影子盘周二编排器入口(Windows python 运行; 设计 0711-shadow-control SC-3/SC-4)。

用法:
  $WIN_PYTHON scripts/shadow_tuesday.py                # 上午段: QMT 看护→refresh→采样
  $WIN_PYTHON scripts/shadow_tuesday.py --post-close   # 收盘段: refresh→比对→净值→台账
  任务计划注册(周二 09:20/15:10 自动): scripts/windows/register_shadow_tasks.ps1
"""
import argparse
import subprocess
import sys
import time as time_mod
from datetime import datetime, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.application.shadow_ops import (  # noqa: E402
    ShadowTuesdayOrchestrator,
    StepResult,
)


def _probe_qmt() -> bool:
    try:
        from xtquant import xtdata  # Windows 侧才可用; WSL 下 ImportError -> False
        return bool(xtdata.get_instrument_detail("000001.SZ"))
    except Exception:
        return False


def _run_step(name: str, argv: list[str]) -> StepResult:
    print(f"[shadow-tuesday] ▶ {name}: {' '.join(argv)}", flush=True)
    proc = subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().splitlines()[-15:])
    print(tail, flush=True)
    return StepResult(name=name, ok=proc.returncode == 0, output_tail=tail)


def _build_notify(config_path: str):
    gateway = None
    try:
        from src.infrastructure.config.settings import load_trading_config
        from src.infrastructure.notification.factory import create_notification_gateway
        gateway = create_notification_gateway(load_trading_config(config_path).risk.notification)
    except Exception as exc:
        print(f"[shadow-tuesday] 通知网关装配失败(仅控制台): {exc}", flush=True)

    def notify(title: str, body: str, level: str) -> None:
        print(f"[shadow-tuesday][{level.upper()}] {title}\n{body}", flush=True)
        if gateway is None:
            return
        try:
            from src.domain.notification.value_objects.notification_message import (
                NotificationLevel,
                NotificationMessage,
            )
            gateway.send(NotificationMessage(
                title=title, body=body,
                level=NotificationLevel(level), category="system",
            ))
        except Exception as exc:  # 通知失败不阻断(SC-4)
            print(f"[shadow-tuesday] 通知发送失败: {exc}", flush=True)

    return notify


def _verify_snapshot_today() -> bool:
    from src.infrastructure.persistence.trading_store import TradingStore
    store = TradingStore(db_path="data/trading.db")
    try:
        row = store.load_signal_snapshot_by_date(datetime.now().date().isoformat())
        return bool(row and row.get("mode") == "dry_run")
    finally:
        store.close()


def _auto_trade_mode(config_path: str) -> str:
    try:
        from src.infrastructure.config.settings import load_trading_config
        return str(load_trading_config(config_path).auto_trade.mode)
    except Exception as exc:
        print(f"[shadow-tuesday] 配置读取失败: {exc}", flush=True)
        return f"unreadable({exc.__class__.__name__})"  # 非 dry_run -> 安全律拒绝


def main() -> int:
    parser = argparse.ArgumentParser(description="影子盘周二编排器")
    parser.add_argument("--post-close", action="store_true", help="收盘段: 比对+净值+台账")
    parser.add_argument("--morning", action="store_true", help="上午段(默认)")
    parser.add_argument("--force", action="store_true",
                        help="非周二也执行(2026-07-14 起日频采样的常规入口, 任务计划经 bat 传入)")
    parser.add_argument("--config", default="resources/trading.yaml")
    parser.add_argument("--deadline", default="14:30", help="QMT 看护截止(HH:MM)")
    args = parser.parse_args()

    hh, mm = args.deadline.split(":")
    orch = ShadowTuesdayOrchestrator(
        run_step=_run_step,
        probe_qmt=_probe_qmt,
        notify=_build_notify(args.config),
        now=datetime.now,
        sleep=time_mod.sleep,
        python_exe=sys.executable,
        verify_snapshot_today=_verify_snapshot_today,
        auto_trade_mode=lambda: _auto_trade_mode(args.config),
        force=args.force,
        deadline=time(int(hh), int(mm)),
    )
    return orch.run_post_close() if args.post_close else orch.run_morning()


if __name__ == "__main__":
    sys.exit(main())
