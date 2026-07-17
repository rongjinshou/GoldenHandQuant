"""影子盘周二编排器(设计 0711-shadow-control SC-3)。

人只负责开 QMT 极简端; 其余步骤机器编排: 看护提醒→refresh→采样→(收盘)比对→净值→台账。
全部依赖注入(subprocess/时钟/探针/通知), application 层可完全离线测试。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

_QUANT = ("-m", "src.interfaces.cli.quant")
_PROBE_RETRY_SECONDS = 60.0
_OPEN_WAIT_SECONDS = 30.0


@dataclass(slots=True, kw_only=True)
class StepResult:
    name: str
    ok: bool
    output_tail: str = ""


class ShadowTuesdayOrchestrator:
    def __init__(
        self,
        *,
        run_step: Callable[[str, list[str]], StepResult],
        probe_qmt: Callable[[], bool],
        notify: Callable[[str, str, str], None],
        now: Callable[[], datetime],
        sleep: Callable[[float], None],
        python_exe: str,
        verify_snapshot_today: Callable[[], bool],
        auto_trade_mode: Callable[[], str],
        force: bool = False,
        deadline: time = time(14, 30),
        market_open: time = time(9, 35),
    ) -> None:
        self._run_step = run_step
        self._probe_qmt = probe_qmt
        self._notify = notify
        self._now = now
        self._sleep = sleep
        self._python = python_exe
        self._verify_snapshot_today = verify_snapshot_today
        self._auto_trade_mode = auto_trade_mode
        self._force = force
        self._deadline = deadline
        self._market_open = market_open

    # ---- 公共入口 ----

    def run_morning(self) -> int:
        guarded = self._guards()
        if guarded is not None:
            return guarded
        if not self._await_qmt():
            return 1
        self._await_market_open()
        today = self._now().date()
        if not self._run_chain(self._refresh_steps(today)
                               + [self._sync_cap_step(), self._auto_trade_step()]):
            return 1
        if not self._verify_snapshot_today():
            self._notify(
                "影子盘采样失败",
                "auto-trade 已执行但当日 signal_snapshot 未落库, 请查 trading_cycles.note",
                "critical",
            )
            return 1
        self._notify(
            "影子盘采样完成",
            f"{today} 决策快照已落库; 收盘后跑 --post-close(或任务计划自动)",
            "info",
        )
        return 0

    def run_post_close(self) -> int:
        guarded = self._guards()
        if guarded is not None:
            return guarded
        today = self._now().date()
        steps = self._refresh_steps(today) + [
            ("consistency-check",
             [self._python, "scripts/shadow_consistency_check.py", "--date", today.isoformat()]),
            ("paper-equity", [self._python, "scripts/shadow_paper_equity.py"]),
        ]
        if not self._run_chain(steps):
            return 1
        status = self._run_step(
            "shadow-status",
            [self._python, *_QUANT, "shadow", "status", "--gate"],
        )
        # shadow status 的退出码承载"过程健康"(含历史 MISSED), 不作为收盘链失败;
        # 其输出并入通知摘要供人复核。
        self._notify(
            "影子盘收盘链完成",
            f"{today} 比对一致, 纸面净值已入库。台账摘要:\n{status.output_tail}",
            "info",
        )
        return 0

    # ---- 内部 ----

    def _guards(self) -> int | None:
        mode = self._auto_trade_mode()
        if mode != "dry_run":
            self._notify(
                "影子盘编排器拒绝运行",
                f"auto_trade.mode={mode}, 本工具只服务 dry_run 影子盘(安全律)",
                "critical",
            )
            return 2
        if self._now().date().weekday() != 1 and not self._force:
            self._notify("非调仓日", "今天不是周二, 影子盘无采样任务(--force 可越过)", "info")
            return 0
        return None

    def _await_qmt(self) -> bool:
        reminded = False
        while not self._probe_qmt():
            if not reminded:
                self._notify(
                    "请打开 QMT 极简端",
                    "影子盘采样等待中: 请登录 QMT 极简模式并确认行情面板有跳动数据",
                    "warning",
                )
                reminded = True
            if self._now().time() >= self._deadline:
                self._notify(
                    "影子盘 MISSED",
                    f"QMT 截至 {self._deadline:%H:%M} 未上线, 今日采样脱靶(live 快照不可补), "
                    "台账将如实记录",
                    "critical",
                )
                return False
            self._sleep(_PROBE_RETRY_SECONDS)
        return True

    def _await_market_open(self) -> None:
        # 任务计划 09:20 拉起提醒, 采样动作等 09:35 开盘价定型(阶段 1 比对口径)
        while self._now().time() < self._market_open:
            self._sleep(_OPEN_WAIT_SECONDS)

    def _refresh_steps(self, today: date) -> list[tuple[str, list[str]]]:
        return [
            ("data-refresh",
             [self._python, *_QUANT, "data", "refresh",
              "--start-date", (today - timedelta(days=14)).isoformat(),
              "--end-date", today.isoformat()]),
            ("index-bars", [self._python, "scripts/fetch_index_bars.py"]),
        ]

    def _sync_cap_step(self) -> tuple[str, list[str]]:
        # MC-1(0712): 决策前把最新交易日 market_cap 覆写为时点总市值(双源兜底, 双败即链停)
        return ("sync-market-cap", [self._python, "scripts/sync_market_cap.py"])

    def _auto_trade_step(self) -> tuple[str, list[str]]:
        return ("auto-trade-once",
                [self._python, *_QUANT, "auto-trade", "--once", "--enable"])

    def _run_chain(self, steps: list[tuple[str, list[str]]]) -> bool:
        for name, argv in steps:
            result = self._run_step(name, argv)
            if not result.ok:
                self._notify(
                    f"影子盘步骤失败: {name}",
                    f"命令: {' '.join(argv)}\n输出尾部:\n{result.output_tail}",
                    "critical",
                )
                return False
        return True
