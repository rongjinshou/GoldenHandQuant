from dataclasses import dataclass, field

from src.domain.account.entities.asset import Asset
from src.domain.account.entities.position import Position


@dataclass(slots=True, kw_only=True)
class AccountRepository:
    """管理多个交易账户的资金与持仓。

    每个 account_id 对应独立的 Asset 和 Position 集合，
    实现物理级别的资金隔离。
    """
    _assets: dict[str, Asset] = field(default_factory=dict)
    _positions: dict[str, dict[str, Position]] = field(default_factory=dict)

    def create_account(self, account_id: str, initial_capital: float) -> Asset:
        if account_id in self._assets:
            raise ValueError(f"Account '{account_id}' already exists")
        asset = Asset(
            account_id=account_id,
            total_asset=initial_capital,
            available_cash=initial_capital,
            frozen_cash=0.0,
        )
        self._assets[account_id] = asset
        self._positions[account_id] = {}
        return asset

    def get_asset(self, account_id: str) -> Asset | None:
        return self._assets.get(account_id)

    def get_positions(self, account_id: str) -> list[Position]:
        return list(self._positions.get(account_id, {}).values())

    def get_position(self, account_id: str, ticker: str) -> Position | None:
        return self._positions.get(account_id, {}).get(ticker)

    def upsert_position(self, account_id: str, position: Position) -> None:
        if account_id not in self._positions:
            self._positions[account_id] = {}
        self._positions[account_id][position.ticker] = position

    def remove_position(self, account_id: str, ticker: str) -> None:
        positions = self._positions.get(account_id, {})
        positions.pop(ticker, None)

    def list_accounts(self) -> list[str]:
        return list(self._assets.keys())
