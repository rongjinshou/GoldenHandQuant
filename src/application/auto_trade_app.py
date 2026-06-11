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

_TERMINAL = ("FILLED", "CANCELED", "REJECTED", "DRY_RUN")
_AUDIT_USER = "auto-trade"


@dataclass(slots=True, kw_only=True)
class AutoTradeConfig:
    mode: str = "dry_run"               # dry_run | live
    strategy: str = "dual_ma"
    symbols: list[str] = field(default_factory=list)
    min_confidence: float = 0.6
    max_orders_per_cycle: int = 3
    per_order_notional_cap: float = 1500.0
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
    ) -> None:
        if config.mode not in ("dry_run", "live"):
            raise ValueError(f"非法 mode: {config.mode!r} (仅 dry_run/live)")
        gateway_is_dry = bool(getattr(trade_gateway, "is_dry_run", False))
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
        except Exception as e:  # 扫描失败不杀循环, 留痕收口
            logger.error("信号扫描失败: %s", e, exc_info=True)
            summary.note = f"scan failed: {e}"
            self._finalize(summary)
            return summary

        summary.signals_generated = len(displays)
        try:
            candidates = self._select(displays, now)
            block_buys, asset = self._prepare_baseline_and_loss_check(now)
            cash_available = asset.available_cash if asset else 0.0

            for d in candidates:
                record = self._execute_one(d, cycle_id, now, block_buys, cash_available)
                self._store.save_execution(record)
                match record["status"]:
                    case "REJECTED":
                        summary.orders_rejected += 1
                    case "FAILED":
                        summary.orders_failed += 1
                    case _:
                        summary.orders_submitted += 1
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

    # ------------------------------------------------------------- selection
    def _select(self, displays: list[SignalDisplay], now: datetime) -> list[SignalDisplay]:
        passed = [d for d in displays if d.confidence_score >= self._cfg.min_confidence]
        done = self._store.today_traded_keys(today=now.date().isoformat())
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
                     block_buys: bool, cash_available: float) -> dict:
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
                                         block_buys, cash_available)
        except Exception as e:
            logger.error("订单执行异常: %s - %s", d.symbol, e, exc_info=True)
            record.update({"status": "FAILED", "reject_reason": f"执行异常: {e}"})
            self._audit_order(record, "execute_failed")
            return record

    def _execute_guarded(self, d: SignalDisplay, record: dict, now: datetime,
                         direction: OrderDirection, block_buys: bool,
                         cash_available: float) -> dict:
        if block_buys and direction == OrderDirection.BUY:
            return self._reject(record, "当日亏损超限禁买 (仅放行卖出)")

        quote = self._quotes.subscribe_first_tick(d.symbol)
        available_volume = 0
        if direction == OrderDirection.SELL:
            positions = {p.ticker: p for p in self._account.get_positions()}
            pos = positions.get(d.symbol)
            available_volume = pos.available_volume if pos else 0
        gate = run_pre_trade_gates(
            symbol=d.symbol, direction=direction, volume=d.suggested_volume,
            quote=quote, now=now, max_notional=self._cfg.per_order_notional_cap,
            available_cash=cash_available,
            available_volume=available_volume,
        )
        if not gate.passed:
            return self._reject(record, gate.reject_reason)

        spent = self._store.today_submitted_notional(today=now.date().isoformat())
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
        trail: list[dict] = []
        deadline = self._clock().timestamp() + self._cfg.poll_timeout_seconds
        last: str | None = None
        while True:
            state = self._trade.query_order_status(order_id)
            if state and state != last:
                trail.append({"t": self._clock().isoformat(), "status": state})
                last = state
            if state in _TERMINAL:
                return state, trail
            if self._clock().timestamp() >= deadline:
                break
            self._sleep(2.0)
        # 超时: 主动撤单 (不留收盘前意外敞口; 网关撤单是异步受理)
        if self._trade.cancel_order(order_id):
            self._audit.log_action(
                user_id=_AUDIT_USER, action="cancel_order", resource_type="Order",
                resource_id=order_id, details={"reason": "poll timeout"})
            return "TIMEOUT_CANCELED", trail
        logger.error("订单 %s 超时且撤单未受理, 需人工处理!", order_id)
        return "TIMEOUT_UNCANCELED", trail

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
