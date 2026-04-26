from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.market.interfaces.gateways.market_gateway import IMarketGateway
from src.domain.market.value_objects.bar import Bar


class IBacktestMarketGateway(IMarketGateway, Protocol):
    def load_bars(self, bars: list[Bar]) -> None:
        ...

    def set_current_time(self, dt: datetime) -> None:
        ...

