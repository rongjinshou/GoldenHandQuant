from __future__ import annotations

from typing import Protocol

from src.domain.account.interfaces.gateways.account_gateway import IAccountGateway
from src.domain.backtest.value_objects.trade_record import TradeRecord
from src.domain.trade.entities.order import Order
from src.domain.trade.interfaces.gateways.trade_gateway import ITradeGateway


class IBacktestBroker(ITradeGateway, IAccountGateway, Protocol):
    def list_orders(self) -> list[Order]:
        ...

    def list_trade_records(self) -> list[TradeRecord]:
        ...

