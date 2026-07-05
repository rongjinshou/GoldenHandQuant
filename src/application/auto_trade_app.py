"""自动交易循环编排 — 扫描→过滤→三层防线→下单→轮询→撤单→留痕。

脊柱复用已实测的 LiveSignalService(quant live 同路径), 安全闸复用
domain pre_trade_checks(与首单 ticket 同一实现)。
设计: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md DD-1/DD-2
夜审加固(2026-06-11): docs/feat/0611-closed-loop/2026-06-11-night-review.md
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from src.application.live_signal_service import LiveSignalService, SignalDisplay
from src.domain.common.services.audit_service import AuditService
from src.domain.market.value_objects.quote import Quote
from src.domain.strategy.value_objects.signal_direction import SignalDirection
from src.domain.trade.entities.order import Order
from src.domain.trade.exceptions import OrderSubmitError
from src.domain.trade.services.pre_trade_checks import (
    CASH_FEE_BUFFER,
    check_daily_loss_block_buys,
    run_pre_trade_gates,
)
from src.domain.trade.value_objects.order_direction import OrderDirection
from src.domain.trade.value_objects.order_type import OrderType
from src.infrastructure.persistence.trading_store import TradingStore

logger = logging.getLogger(__name__)

_AUDIT_USER = "auto-trade"


@dataclass(slots=True, kw_only=True)
class AutoTradeConfig:
    mode: str = "dry_run"               # dry_run | live
    strategy: str = "dual_ma"
    symbols: list[str] = field(default_factory=list)
    min_confidence: float = 0.6
    max_orders_per_cycle: int = 3
    per_order_notional_cap: float = 1500.0
    per_order_notional_ceiling: float = 5000.0   # 单笔金额硬顶(默认保持 0611 安全值)
    daily_notional_cap: float = 3000.0
    daily_loss_limit_ratio: float = 0.02
    poll_timeout_seconds: float = 30.0


@dataclass(slots=True, kw_only=True)
class CycleSummary:
    cycle_id: str
    mode: str
    signals_generated: int = 0
    orders_submitted: int = 0
    orders_rejected: int = 0
    orders_failed: int = 0
    notional_submitted: float = 0.0
    note: str = ""


class AutoTradeAppService:
    """单次循环可独立调用(--once), 守护模式由 TradingScheduler 周期触发。

    装配不变量: config.mode 必须与 trade_gateway 的真实性配对
    (dry_run ↔ is_dry_run 网关), 构造时强制校验, 防止「标注 dry_run
    实际真单」的审计灾难。
    """

    def __init__(
        self,
        *,
        signal_service: LiveSignalService,
        quote_fetcher,
        trade_gateway,
        account_gateway,
        store: TradingStore,
        audit: AuditService,
        config: AutoTradeConfig,
        clock: Callable[[], datetime] = datetime.now,
        sleep: Callable[[float], None] = time.sleep,
        notification_hub=None,
    ) -> None:
        if config.mode not in ("dry_run", "live"):
            raise ValueError(f"非法 mode: {config.mode!r} (仅 dry_run/live)")
        gateway_is_dry = bool(trade_gateway.is_dry_run)
        if (config.mode == "dry_run") != gateway_is_dry:
            raise ValueError(
                f"mode={config.mode} 与网关真实性不一致 (gateway.is_dry_run={gateway_is_dry})"
            )
        self._signals = signal_service
        self._quotes = quote_fetcher
        self._trade = trade_gateway
        self._account = account_gateway
        self._store = store
        self._audit = audit
        self._cfg = config
        self._clock = clock
        self._sleep = sleep
        self._hub = notification_hub

    def _notify(self, title: str, body: str, level: str = "info") -> None:
        """通过 NotificationHub 发送通知 — 静默失败不阻塞交易。"""
        if self._hub is None:
            return
        try:
            from src.domain.notification.value_objects.notification_message import (
                NotificationLevel,
                NotificationMessage,
            )
            lvl = getattr(NotificationLevel, level.upper(), NotificationLevel.INFO)
            self._hub.notify(NotificationMessage(
                title=title, body=body, level=lvl, category="trade",
            ))
        except Exception as e:
            logger.debug("通知发送失败(忽略): %s", e)

    # ------------------------------------------------------------------ cycle
    def run_cycle(self) -> CycleSummary:
        now = self._clock()
        cycle_id = f"{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        summary = CycleSummary(cycle_id=cycle_id, mode=self._cfg.mode)
        self._store.save_cycle_start(
            cycle_id=cycle_id, cycle_time=now.isoformat(),
            mode=self._cfg.mode, strategy=self._cfg.strategy,
        )
        self._audit.log_action(
            user_id=_AUDIT_USER, action="cycle_start", resource_type="TradingCycle",
            resource_id=cycle_id, details={"mode": self._cfg.mode,
                                           "strategy": self._cfg.strategy},
        )

        try:
            displays = self._signals.scan(self._cfg.strategy, self._cfg.symbols)
        except Exception as e:  # 扫描失败不杀循环, 留痕收口(含 DataHealthError 拒绝决策)
            logger.error("信号扫描失败: %s", e, exc_info=True)
            summary.note = f"scan failed: {e}"
            self._save_scan_snapshot(cycle_id)  # 守卫命中的 fault 快照(B2 已填充)
            self._finalize(summary)
            return summary

        summary.signals_generated = len(displays)
        self._save_scan_snapshot(cycle_id)
        try:
            candidates = self._select(displays, now)
            block_buys, asset = self._prepare_baseline_and_loss_check(now)
            cash_available = asset.available_cash if asset else 0.0

            # 债D4修复: 循环前一次性批量拉取候选行情快照(单次API调用)，
            # 替代逐候选串行 subscribe_first_tick(每单最坏3秒等待推送)。
            # 批量调用异常不得炸穿整循环: 退化为空报价, 各候选走"拿不到有效报价"闸拒单。
            quotes: dict[str, Quote] = {}
            if candidates:
                try:
                    quotes = self._quotes.get_quotes([d.symbol for d in candidates])
                except Exception as e:
                    logger.error("批量行情拉取失败(本循环全部候选按无报价处理): %s", e, exc_info=True)

            for d in candidates:
                record = self._execute_one(d, cycle_id, now, block_buys, cash_available, quotes)
                self._store.save_execution(record)
                match record["status"]:
                    case "REJECTED":
                        summary.orders_rejected += 1
                        self._notify(
                            f"订单拒绝: {record['symbol']}",
                            f"方向: {record['direction']} | 原因: {record.get('reject_reason', '未知')}",
                            level="warning",
                        )
                    case "FAILED":
                        summary.orders_failed += 1
                        self._notify(
                            f"订单失败: {record['symbol']}",
                            f"方向: {record['direction']} | 异常: {record.get('reject_reason', '未知')}",
                            level="warning",
                        )
                    case _:
                        summary.orders_submitted += 1
                        self._notify(
                            f"订单提交: {record['symbol']}",
                            f"方向: {record['direction']} | 金额: ¥{record.get('notional', 0):.2f}",
                        )
                        notional = record["notional"] or 0.0
                        summary.notional_submitted += notional
                        if record["direction"] == OrderDirection.BUY.value:
                            # 同循环资金游标: 后续买单的资金闸用扣减后的余额
                            cash_available -= notional * CASH_FEE_BUFFER
        finally:
            # 快照与 finalize 必达: 即便循环中段异常, 留痕也要收口
            try:
                self._snapshot(now)
            except Exception as e:
                logger.error("循环末快照失败: %s", e, exc_info=True)
                summary.note = (summary.note + f" snapshot failed: {e}").strip()
            self._finalize(summary)
        return summary

    def _save_scan_snapshot(self, cycle_id: str) -> None:
        """截面决策快照落库(0626 阶段1 DD-7) — 自身异常不得杀循环。

        序列化约定(D2 比对脚本反序列化同此): datetime → isoformat 字符串;
        positions/selection/targets → json.dumps(ensure_ascii=False);
        gate_passed → int(0/1)。落库后清空 last_snapshot 防跨周期陈旧快照。
        """
        snap = getattr(self._signals, "last_snapshot", None)
        if snap is None:
            return
        try:
            self._store.save_signal_snapshot({
                "cycle_id": cycle_id,
                "snapshot_time": snap.snapshot_time.isoformat(),
                "mode": self._cfg.mode,
                "strategy": snap.strategy,
                "universe_size": snap.universe_size,
                "filtered_size": snap.filtered_size,
                "fundamental_date": (snap.fundamental_date.isoformat()
                                     if snap.fundamental_date else None),
                "fundamental_rows": snap.fundamental_rows,
                "staleness_days": snap.staleness_days,
                "index_bars_count": snap.index_bars_count,
                "gate_passed": int(snap.gate_passed),
                "positions_json": json.dumps(snap.positions, ensure_ascii=False),
                "total_asset": snap.total_asset,
                "selection_json": json.dumps(snap.selection, ensure_ascii=False),
                "targets_json": json.dumps(snap.targets, ensure_ascii=False),
                "data_health": snap.data_health,
                "note": snap.note,
            })
        except Exception as e:
            logger.error("决策快照落库失败 (循环继续): %s", e, exc_info=True)
        finally:
            self._signals.last_snapshot = None

    # ------------------------------------------------------------- selection
    def _select(self, displays: list[SignalDisplay], now: datetime) -> list[SignalDisplay]:
        passed = [d for d in displays if d.confidence_score >= self._cfg.min_confidence]
        done = self._store.today_traded_keys(today=now.date().isoformat(),
                                             mode=self._cfg.mode)
        fresh = [d for d in passed if f"{d.symbol}:{d.direction.value}" not in done]
        fresh.sort(key=lambda d: (0 if d.direction == SignalDirection.SELL else 1,
                                  -d.confidence_score))
        return fresh[: self._cfg.max_orders_per_cycle]

    def _prepare_baseline_and_loss_check(self, now: datetime):
        """当日首循环先落盘前基准快照(交易前权益), 再做亏损禁买判定。"""
        asset = self._account.get_asset()
        today = now.date().isoformat()
        day_start = self._store.day_start_equity(today=today)
        if day_start is None and asset is not None:
            self._write_account_snapshot(now, asset)
            day_start = asset.total_asset
        if asset is None or day_start is None:
            logger.warning("无法获取账户资产或当日基准, 亏损闸本循环跳过 (fail-open)")
            return False, asset
        blocked = check_daily_loss_block_buys(
            day_start, asset.total_asset, limit_ratio=self._cfg.daily_loss_limit_ratio)
        if blocked:
            logger.warning("当日权益回撤超 %.1f%% (基准 %.2f → 当前 %.2f), 本循环禁买",
                           self._cfg.daily_loss_limit_ratio * 100,
                           day_start, asset.total_asset)
        return blocked, asset

    # ------------------------------------------------------------- execution
    def _execute_one(self, d: SignalDisplay, cycle_id: str, now: datetime,
                     block_buys: bool, cash_available: float,
                     quotes: dict[str, Quote]) -> dict:
        """单笔执行(异常自隔离): 任何异常以 FAILED 留痕, 不波及循环内其他订单。"""
        direction = (OrderDirection.BUY if d.direction == SignalDirection.BUY
                     else OrderDirection.SELL)
        record = {
            "order_id": f"pre-{uuid.uuid4().hex[:10]}", "cycle_id": cycle_id,
            "mode": self._cfg.mode, "symbol": d.symbol,
            "direction": direction.value, "signal_price": d.suggested_price,
            "exec_price": None, "volume": d.suggested_volume, "notional": None,
            "status": "REJECTED", "reject_reason": None,
            "strategy_name": d.strategy_name, "confidence": d.confidence_score,
            "submitted_at": now.isoformat(), "final_status_at": None,
            "status_trail": "[]",
        }
        try:
            return self._execute_guarded(d, record, now, direction,
                                         block_buys, cash_available, quotes)
        except Exception as e:
            logger.error("订单执行异常: %s - %s", d.symbol, e, exc_info=True)
            record.update({"status": "FAILED", "reject_reason": f"执行异常: {e}"})
            self._audit_order(record, "execute_failed")
            return record

    def _execute_guarded(self, d: SignalDisplay, record: dict, now: datetime,
                         direction: OrderDirection, block_buys: bool,
                         cash_available: float, quotes: dict[str, Quote]) -> dict:
        if block_buys and direction == OrderDirection.BUY:
            return self._reject(record, "当日亏损超限禁买 (仅放行卖出)")

        quote = quotes.get(d.symbol)
        # 实时 ST 闸输入(DD-3): 名称仅买入需要; fetcher 无此能力/非 str 一律视为不可得
        instrument_name: str | None = None
        if direction == OrderDirection.BUY:
            name_of = getattr(self._quotes, "get_instrument_name", None)
            if callable(name_of):
                raw = name_of(d.symbol)
                instrument_name = raw if isinstance(raw, str) else None
        available_volume = 0
        if direction == OrderDirection.SELL:
            positions = {p.ticker: p for p in self._account.get_positions()}
            pos = positions.get(d.symbol)
            available_volume = pos.available_volume if pos else 0
        gate = run_pre_trade_gates(
            symbol=d.symbol, direction=direction, volume=d.suggested_volume,
            quote=quote, now=now, max_notional=self._cfg.per_order_notional_cap,
            instrument_name=instrument_name,
            notional_ceiling=self._cfg.per_order_notional_ceiling,
            available_cash=cash_available,
            available_volume=available_volume,
        )
        if not gate.passed:
            return self._reject(record, gate.reject_reason)

        spent = self._store.today_submitted_notional(today=now.date().isoformat(),
                                                      mode=self._cfg.mode)
        if spent + gate.notional > self._cfg.daily_notional_cap:
            return self._reject(
                record,
                f"当日预算耗尽: 已提交 {spent:.2f} + 本单 {gate.notional:.2f} "
                f"> 上限 {self._cfg.daily_notional_cap:.2f}")

        order = Order(
            order_id=f"auto-{uuid.uuid4().hex[:8]}", account_id="",
            ticker=d.symbol, direction=direction, price=gate.limit_price,
            volume=d.suggested_volume, type=OrderType.LIMIT,
            remark="auto-trade-v1",
        )
        record.update({"exec_price": gate.limit_price, "notional": gate.notional})
        try:
            order_id = str(self._trade.place_order(order))
        except OrderSubmitError as e:
            record.update({"status": "FAILED", "reject_reason": str(e)})
            self._audit_order(record, "place_order_failed")
            return record

        record["order_id"] = order_id
        self._audit_order(record, "place_order")
        final, trail = self._poll(order_id)
        record.update({
            "status": final, "status_trail": json.dumps(trail, ensure_ascii=False),
            "final_status_at": self._clock().isoformat(),
        })
        return record

    def _poll(self, order_id: str) -> tuple[str, list[dict]]:
        """轮询订单状态至终态/超时, 超时后自动撤单。"""
        from src.domain.trade.services.order_poller import poll_order_until_terminal

        result = poll_order_until_terminal(
            order_id,
            query_status=self._trade.query_order_status,
            cancel_order=self._trade.cancel_order,
            timeout_seconds=self._cfg.poll_timeout_seconds,
            clock=lambda: self._clock().timestamp(),
            sleep=self._sleep,
            cancel_on_timeout=True,  # auto-trade 超时撤单
        )
        if result.canceled:
            self._audit.log_action(
                user_id=_AUDIT_USER, action="cancel_order", resource_type="Order",
                resource_id=order_id, details={"reason": "poll timeout"})
        elif result.final_status == "TIMEOUT_UNCANCELED":
            logger.error("订单 %s 超时且撤单未受理, 需人工处理!", order_id)
        return result.final_status, result.trail

    # ----------------------------------------------------------- persistence
    def _reject(self, record: dict, reason: str | None) -> dict:
        record.update({"status": "REJECTED", "reject_reason": reason})
        self._audit_order(record, "reject_order")
        return record

    def _audit_order(self, record: dict, action: str) -> None:
        self._audit.log_action(
            user_id=_AUDIT_USER, action=action, resource_type="Order",
            resource_id=record["order_id"],
            details={"symbol": record["symbol"], "direction": record["direction"],
                     "notional": record["notional"], "mode": record["mode"],
                     "reason": record["reject_reason"]})

    def _write_account_snapshot(self, now: datetime, asset) -> None:
        self._store.save_account_snapshot(
            snapshot_time=now.isoformat(), mode=self._cfg.mode,
            total_asset=asset.total_asset, available_cash=asset.available_cash,
            frozen_cash=asset.frozen_cash,
            market_value=asset.total_asset - asset.available_cash - asset.frozen_cash)

    def _snapshot(self, now: datetime) -> None:
        asset = self._account.get_asset()
        if asset is not None:
            # 循环末快照与盘前基准用不同时间戳, 避免同 ts 排序歧义
            self._write_account_snapshot(self._clock(), asset)
        positions = self._account.get_positions()
        if positions:
            self._store.save_position_snapshots(
                snapshot_time=now.isoformat(), mode=self._cfg.mode,
                rows=[{"symbol": p.ticker, "total_volume": p.total_volume,
                       "available_volume": p.available_volume,
                       "average_cost": p.average_cost, "last_price": None}
                      for p in positions])

    def _finalize(self, s: CycleSummary) -> None:
        self._store.finalize_cycle(
            cycle_id=s.cycle_id, signals_generated=s.signals_generated,
            orders_submitted=s.orders_submitted, orders_rejected=s.orders_rejected,
            orders_failed=s.orders_failed,
            notional_submitted=round(s.notional_submitted, 2), note=s.note)
        self._audit.log_action(
            user_id=_AUDIT_USER, action="cycle_end", resource_type="TradingCycle",
            resource_id=s.cycle_id,
            details={"submitted": s.orders_submitted, "rejected": s.orders_rejected,
                     "failed": s.orders_failed, "note": s.note})
        logger.info("循环 %s 完成: 信号=%d 提交=%d 拒绝=%d 失败=%d",
                    s.cycle_id, s.signals_generated, s.orders_submitted,
                    s.orders_rejected, s.orders_failed)
