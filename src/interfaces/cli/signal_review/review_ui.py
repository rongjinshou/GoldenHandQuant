"""Rich 终端信号审核界面。"""

import logging
from datetime import datetime

from src.application.live_signal_service import (
    LiveSignalService,
    OrderResult,
    SignalDisplay,
)
from src.domain.strategy.value_objects.review_action import ReviewAction
from src.domain.strategy.value_objects.signal import Signal
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.strategy.value_objects.signal_review_record import SignalReviewRecord
from src.interfaces.cli.signal_review.enhanced_display import (
    EnhancedSignalDisplay,
    calculate_risk_score,
)
from src.interfaces.cli.signal_review.review_store import ReviewStore

logger = logging.getLogger(__name__)

PAGE_SIZE = 20

# ANSI colors (fallback when rich unavailable)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class SignalReviewUI:
    """信号审核界面。"""

    def __init__(
        self,
        service: LiveSignalService,
        store: ReviewStore | None = None,
        *,
        quote_fetcher=None,
        max_notional: float = 1500.0,
        notional_ceiling: float = 5000.0,
    ) -> None:
        self.service = service
        self.store = store or ReviewStore()
        # M6: 盘前闸输入(未配置报价源时 place_confirmed_orders 一律拒单)
        self.quote_fetcher = quote_fetcher
        self.max_notional = max_notional
        self.notional_ceiling = notional_ceiling
        self.console = Console() if HAS_RICH else None

    def run(self, strategy_name: str, symbols: list[str]) -> list[OrderResult]:
        """主审核循环。返回下单结果列表。"""
        asset = self.service.account_gateway.get_asset()
        positions = self.service.account_gateway.get_positions()

        displays_raw = self.service.scan(strategy_name, symbols)
        if not displays_raw:
            self._print_plain(f"\n{YELLOW}当前无交易信号。{RESET}\n")
            return []

        # 增强展示
        enhanced = self._to_enhanced(displays_raw, positions, asset, strategy_name)

        # 审核循环
        approved: list[EnhancedSignalDisplay] = []
        rejected: list[EnhancedSignalDisplay] = []
        notes: dict[int, str] = {}  # index -> note

        page = 0
        total_pages = (len(enhanced) - 1) // PAGE_SIZE + 1

        while True:
            start = page * PAGE_SIZE
            end = min(start + PAGE_SIZE, len(enhanced))
            page_displays = enhanced[start:end]

            self._render_header(strategy_name, asset, len(positions), len(enhanced))
            self._render_table(page_displays, start, approved, rejected)

            if total_pages > 1:
                self._print_plain(f"  第 {page + 1}/{total_pages} 页")

            cmd = input(f"\n  {BOLD}>{RESET} ").strip()
            if not cmd:
                continue

            action, indices = self._parse_command(cmd, len(enhanced))

            if action == "quit":
                self._print_plain(f"{YELLOW}已退出，未执行任何交易。{RESET}")
                return []

            if action == "next_page":
                if page < total_pages - 1:
                    page += 1
                continue

            if action == "prev_page":
                if page > 0:
                    page -= 1
                continue

            if action == "approve_all":
                approved = [d for d in enhanced if d not in rejected]
                self._print_plain(f"{GREEN}已选择全部批准 ({len(approved)} 条)。{RESET}")
                break

            if action == "reject_all":
                rejected = [d for d in enhanced if d not in approved]
                self._print_plain(f"{RED}已选择全部拒绝 ({len(rejected)} 条)。{RESET}")
                break

            if action == "approve":
                for i in indices:
                    d = enhanced[i]
                    if d not in approved:
                        approved.append(d)
                    if d in rejected:
                        rejected.remove(d)
                self._print_plain(f"{GREEN}已选择批准 {len(indices)} 条。{RESET}")

            if action == "reject":
                for i in indices:
                    d = enhanced[i]
                    if d not in rejected:
                        rejected.append(d)
                    if d in approved:
                        approved.remove(d)
                self._print_plain(f"{RED}已选择拒绝 {len(indices)} 条。{RESET}")

            if action == "note":
                if len(indices) >= 1:
                    idx = indices[0]
                    note_text = cmd.split(" ", 2)[-1] if " " in cmd.split(" ", 2)[-1] else ""
                    # re-parse: "n 1 some note"
                    parts = cmd.split(" ", 2)
                    if len(parts) >= 3:
                        note_text = parts[2]
                    notes[idx] = note_text
                    self._print_plain(f"{CYAN}已为信号 #{idx + 1} 添加备注。{RESET}")

            if action == "detail":
                if indices:
                    self._render_detail(enhanced[indices[0]])

            if action == "confirm":
                break

        if not approved and not rejected:
            self._print_plain(f"{YELLOW}未选择任何信号。{RESET}")
            return []

        # 下单
        results: list[OrderResult] = []
        if approved:
            self._print_plain(f"\n{BOLD}正在下单 ({len(approved)} 条)...{RESET}")
            results = self.service.place_confirmed_orders(
                approved, quote_fetcher=self.quote_fetcher,
                max_notional=self.max_notional,
                notional_ceiling=self.notional_ceiling)

        # 持久化审核记录
        self._save_records(approved, rejected, notes, results, strategy_name)
        self._render_order_results(results)

        return results

    def _to_enhanced(
        self,
        displays: list[SignalDisplay],
        positions: list,
        asset,
        strategy_name: str,
    ) -> list[EnhancedSignalDisplay]:
        position_map = {p.ticker: p for p in positions}
        result: list[EnhancedSignalDisplay] = []
        for d in displays:
            pos = position_map.get(d.symbol)
            risk = calculate_risk_score(d, pos, asset)
            stats = self.store.get_strategy_stats(strategy_name)
            result.append(EnhancedSignalDisplay(
                symbol=d.symbol,
                direction=d.direction,
                current_price=d.current_price,
                suggested_price=d.suggested_price,
                suggested_volume=d.suggested_volume,
                required_capital=d.required_capital,
                reason=d.reason,
                strategy_name=d.strategy_name,
                confidence_score=d.confidence_score,
                risk_score=risk,
                ml_confidence=d.confidence_score,
                signal_age_hours=0.0,
                historical_win_rate=stats.get("win_rate", 0.0),
            ))
        return result

    def _render_header(
        self, strategy_name: str, asset, position_count: int, signal_count: int,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        available = asset.available_cash if asset else 0

        if HAS_RICH and self.console:
            header = Table.grid(padding=1)
            header.add_row(
                Text("GoldenHandQuant 信号审核", style="bold cyan"),
                Text(now, style="dim"),
            )
            info = (
                f"策略: {strategy_name}  |  "
                f"可用资金: {available:,.0f}  |  "
                f"持仓: {position_count} 只  |  "
                f"信号: {signal_count} 条"
            )
            header.add_row(Text(info, style="cyan"))
            self.console.print(Panel(header, border_style="cyan"))
        else:
            self._print_plain(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
            self._print_plain(f"{BOLD}{CYAN}  GoldenHandQuant 信号审核{' '*40}{now}{RESET}")
            self._print_plain(f"{BOLD}{CYAN}{'='*80}{RESET}")
            self._print_plain(
                f"{CYAN}策略: {strategy_name}  |  "
                f"可用资金: {available:,.0f}  |  "
                f"持仓: {position_count} 只  |  "
                f"信号: {signal_count} 条{RESET}"
            )

    def _render_table(
        self,
        displays: list[EnhancedSignalDisplay],
        offset: int,
        approved: list[EnhancedSignalDisplay],
        rejected: list[EnhancedSignalDisplay],
    ) -> None:
        if HAS_RICH and self.console:
            table = Table(show_header=True, header_style="bold", box=None)
            table.add_column("#", justify="right", width=4)
            table.add_column("标的", width=12)
            table.add_column("方向", width=6)
            table.add_column("当前价", justify="right", width=8)
            table.add_column("挂单价", justify="right", width=8)
            table.add_column("数量", justify="right", width=6)
            table.add_column("资金", justify="right", width=10)
            table.add_column("风险", justify="right", width=6)
            table.add_column("置信度", justify="right", width=6)
            table.add_column("状态", width=6)

            for i, d in enumerate(displays):
                idx = offset + i + 1
                dir_style = "green" if d.direction == SignalDirection.BUY else "red"
                dir_text = "BUY" if d.direction == SignalDirection.BUY else "SELL"

                status = ""
                if d in approved:
                    status = "[green]V[/green]"
                elif d in rejected:
                    status = "[red]X[/red]"

                risk_text = f"{d.risk_score:.1f}"
                if d.risk_score >= 0.6:
                    risk_text = f"[red]{risk_text}[/red]"
                elif d.risk_score >= 0.3:
                    risk_text = f"[yellow]{risk_text}[/yellow]"

                table.add_row(
                    str(idx),
                    d.symbol,
                    Text(dir_text, style=dir_style),
                    f"{d.current_price:.2f}",
                    f"{d.suggested_price:.2f}",
                    str(d.suggested_volume),
                    f"{d.required_capital:,.0f}",
                    risk_text,
                    f"{d.confidence_score:.2f}",
                    status,
                )
            self.console.print(table)

            # 触发原因
            reasons = []
            for i, d in enumerate(displays):
                reasons.append(f"{offset + i + 1}) {d.reason}")
            if reasons:
                self.console.print(f"  触发原因: {'  '.join(reasons)}")
        else:
            self._render_table_plain(displays, offset, approved, rejected)

    def _render_table_plain(
        self,
        displays: list[EnhancedSignalDisplay],
        offset: int,
        approved: list[EnhancedSignalDisplay],
        rejected: list[EnhancedSignalDisplay],
    ) -> None:
        header = (
            f"{'序号':>4}  {'标的':<12} {'方向':<6} {'当前价':>8} {'挂单价':>8} "
            f"{'数量':>6} {'资金':>10} {'风险':>6} {'置信度':>6} {'状态':>4}"
        )
        self._print_plain(f"\n{BOLD}{header}{RESET}")
        self._print_plain("-" * 80)

        for i, d in enumerate(displays):
            idx = offset + i + 1
            dir_color = GREEN if d.direction == SignalDirection.BUY else RED
            dir_text = "BUY " if d.direction == SignalDirection.BUY else "SELL"
            status = ""
            if d in approved:
                status = f"{GREEN}V{RESET}"
            elif d in rejected:
                status = f"{RED}X{RESET}"
            self._print_plain(
                f"{idx:>4}  {d.symbol:<12} {dir_color}{dir_text:<6}{RESET} "
                f"{d.current_price:>8.2f} {d.suggested_price:>8.2f} "
                f"{d.suggested_volume:>6} {d.required_capital:>10,.0f} "
                f"{d.risk_score:>6.1f} {d.confidence_score:>6.2f} {status:>4}"
            )
        self._print_plain("-" * 80)

        reasons = []
        for i, d in enumerate(displays):
            reasons.append(f"{offset + i + 1}) {d.reason}")
        if reasons:
            self._print_plain(f"  触发原因: {'  '.join(reasons)}")

    def _render_detail(self, d: EnhancedSignalDisplay) -> None:
        dir_text = "BUY" if d.direction == SignalDirection.BUY else "SELL"
        risk_level = "低" if d.risk_score < 0.3 else ("中" if d.risk_score < 0.6 else "高")

        if HAS_RICH and self.console:
            lines = [
                f"策略:      {d.strategy_name}",
                f"方向:      {dir_text}",
                f"当前价:    {d.current_price:.2f}",
                f"挂单价:    {d.suggested_price:.2f}",
                f"数量:      {d.suggested_volume} 股",
                f"所需资金:  {d.required_capital:,.0f}",
                f"置信度:    {d.confidence_score:.2f}",
                f"风险评分:  {d.risk_score:.1f} ({risk_level})",
                f"历史胜率:  {d.historical_win_rate:.1%}",
                f"触发原因:  {d.reason}",
                f"信号年龄:  {d.signal_age_hours:.1f} 小时",
            ]
            self.console.print(Panel("\n".join(lines), title=f"信号详情: {d.symbol}", border_style="cyan"))
        else:
            self._print_plain(f"\n{BOLD}--- 信号详情: {d.symbol} ---{RESET}")
            self._print_plain(f"  策略:      {d.strategy_name}")
            self._print_plain(f"  方向:      {dir_text}")
            self._print_plain(f"  当前价:    {d.current_price:.2f}")
            self._print_plain(f"  挂单价:    {d.suggested_price:.2f}")
            self._print_plain(f"  数量:      {d.suggested_volume} 股")
            self._print_plain(f"  所需资金:  {d.required_capital:,.0f}")
            self._print_plain(f"  置信度:    {d.confidence_score:.2f}")
            self._print_plain(f"  风险评分:  {d.risk_score:.1f} ({risk_level})")
            self._print_plain(f"  历史胜率:  {d.historical_win_rate:.1%}")
            self._print_plain(f"  触发原因:  {d.reason}")
            self._print_plain(f"  信号年龄:  {d.signal_age_hours:.1f} 小时")
            self._print_plain(f"{BOLD}{'---'}{RESET}")

    def _render_order_results(self, results: list[OrderResult]) -> None:
        if not results:
            return
        self._print_plain(f"\n{BOLD}{'--- 订单结果 ---'}{RESET}")
        for r in results:
            if r.success:
                self._print_plain(f"{GREEN}  {r.symbol} {r.direction.value} 订单已提交: {r.order_id}{RESET}")
            else:
                self._print_plain(f"{RED}  {r.symbol} {r.direction.value} 下单失败: {r.error_message}{RESET}")
        self._print_plain(f"{BOLD}{'---'}{RESET}\n")

    def _save_records(
        self,
        approved: list[EnhancedSignalDisplay],
        rejected: list[EnhancedSignalDisplay],
        notes: dict[int, str],
        results: list[OrderResult],
        strategy_name: str,
    ) -> None:
        order_map: dict[str, str] = {}
        for r in results:
            if r.success:
                order_map[r.symbol] = r.order_id

        now = datetime.now()
        for d in approved:
            signal = Signal(
                symbol=d.symbol,
                direction=d.direction,
                confidence_score=d.confidence_score,
                strategy_name=strategy_name,
                reason=d.reason,
            )
            record = SignalReviewRecord(
                record_id=_gen_id(),
                signal=signal,
                action=ReviewAction.APPROVED,
                reviewed_at=now,
                reviewer_note=notes.get(0, ""),
                order_id=order_map.get(d.symbol, ""),
                suggested_price=d.suggested_price,
                suggested_volume=d.suggested_volume,
                risk_score=d.risk_score,
                ml_confidence=d.ml_confidence,
                signal_age_hours=d.signal_age_hours,
            )
            self.store.append(record)

        for d in rejected:
            signal = Signal(
                symbol=d.symbol,
                direction=d.direction,
                confidence_score=d.confidence_score,
                strategy_name=strategy_name,
                reason=d.reason,
            )
            record = SignalReviewRecord(
                record_id=_gen_id(),
                signal=signal,
                action=ReviewAction.REJECTED,
                reviewed_at=now,
                reviewer_note="",
                suggested_price=d.suggested_price,
                suggested_volume=d.suggested_volume,
                risk_score=d.risk_score,
                ml_confidence=d.ml_confidence,
                signal_age_hours=d.signal_age_hours,
            )
            self.store.append(record)

    @staticmethod
    def _parse_command(cmd: str, total: int) -> tuple[str, list[int]]:
        """解析用户命令。

        Returns:
            (action, indices) - action 为命令类型，indices 为受影响的信号索引 (0-based)。
        """
        cmd = cmd.strip()
        lower = cmd.lower()

        if lower == "q":
            return "quit", []
        if lower == "a":
            return "approve_all", []
        if lower == "r":
            return "reject_all", []
        if lower in ("n", "next"):
            return "next_page", []
        if lower in ("p", "prev"):
            return "prev_page", []
        if lower == "confirm" or lower == "":
            return "confirm", []

        # "r 2,4" - reject specific
        if lower.startswith("r "):
            indices = _parse_indices(lower[2:], total)
            return "reject", indices

        # "n 1 note text" - add note
        if lower.startswith("n "):
            parts = cmd.split(" ", 2)
            if len(parts) >= 2:
                indices = _parse_indices(parts[1], total)
                return "note", indices
            return "note", []

        # "d 3" - detail
        if lower.startswith("d "):
            indices = _parse_indices(lower[2:], total)
            return "detail", indices[:1] if indices else []

        # "1,3,5" - approve specific
        indices = _parse_indices(lower, total)
        if indices:
            return "approve", indices

        return "confirm", []

    @staticmethod
    def _print_plain(msg: str) -> None:
        print(msg)


def _parse_indices(text: str, total: int) -> list[int]:
    """解析逗号分隔的序号列表 (1-based -> 0-based)。"""
    indices: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part) - 1
            if 0 <= idx < total:
                indices.append(idx)
        except ValueError:
            continue
    return indices


def _gen_id() -> str:
    from uuid import uuid4
    return uuid4().hex[:8]
