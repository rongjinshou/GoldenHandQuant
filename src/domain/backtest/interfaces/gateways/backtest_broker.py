from __future__ import annotations

from typing import Protocol

from src.domain.account.entities.asset import Asset
from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.entities.order import Order
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway


class IBacktestBroker(ITradeGateway, IAccountGateway, Protocol):
    def list_orders(self) -> list[Order]:
        ...

    def list_trade_records(self) -> list[TradeRecord]:
        ...

    def create_sub_account(self, account_id: str, initial_capital: float) -> Asset:
        """创建子账户用于多策略分仓。"""
        ...

    def activate_account(self, account_id: str) -> None:
        """切换当前活跃账户。"""
        ...

