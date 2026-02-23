import pytest
from src.domain.account.entities.asset import Asset

class TestAsset:
    def test_init_should_set_default_values(self):
        # Arrange
        account_id = "test_account"

        # Act
        asset = Asset(account_id=account_id)

        # Assert
        assert asset.account_id == account_id
        assert asset.total_asset == 0.0
        assert asset.available_cash == 0.0
        assert asset.frozen_cash == 0.0

    def test_deposit_should_increase_available_cash_and_total_asset(self):
        # Arrange
        asset = Asset(account_id="test_account")
        amount = 10000.0

        # Act
        asset.deposit(amount)

        # Assert
        assert asset.available_cash == 10000.0
        assert asset.total_asset == 10000.0
        assert asset.frozen_cash == 0.0

    def test_deposit_negative_amount_should_raise_error(self):
        # Arrange
        asset = Asset(account_id="test_account")

        # Act & Assert
        with pytest.raises(ValueError, match="Deposit amount must be positive"):
            asset.deposit(-100.0)

    def test_freeze_cash_should_move_cash_from_available_to_frozen(self):
        # Arrange
        asset = Asset(account_id="test_account", available_cash=10000.0, total_asset=10000.0)
        freeze_amount = 2000.0

        # Act
        asset.freeze_cash(freeze_amount)

        # Assert
        assert asset.available_cash == 8000.0
        assert asset.frozen_cash == 2000.0
        assert asset.total_asset == 10000.0

    def test_freeze_cash_insufficient_funds_should_raise_error(self):
        # Arrange
        asset = Asset(account_id="test_account", available_cash=100.0)

        # Act & Assert
        with pytest.raises(ValueError, match="Insufficient available cash"):
            asset.freeze_cash(200.0)

    def test_unfreeze_cash_should_move_cash_from_frozen_to_available(self):
        # Arrange
        asset = Asset(account_id="test_account", available_cash=8000.0, frozen_cash=2000.0, total_asset=10000.0)
        unfreeze_amount = 1000.0

        # Act
        asset.unfreeze_cash(unfreeze_amount)

        # Assert
        assert asset.available_cash == 9000.0
        assert asset.frozen_cash == 1000.0
        assert asset.total_asset == 10000.0

    def test_unfreeze_cash_more_than_frozen_should_raise_error(self):
        # Arrange
        asset = Asset(account_id="test_account", frozen_cash=100.0)

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot unfreeze more than frozen cash"):
            asset.unfreeze_cash(200.0)

    def test_deduct_frozen_cash_should_decrease_frozen_cash(self):
        # Arrange
        asset = Asset(account_id="test_account", frozen_cash=2000.0, total_asset=10000.0)
        deduct_amount = 2000.0

        # Act
        asset.deduct_frozen_cash(deduct_amount)

        # Assert
        assert asset.frozen_cash == 0.0
        # total_asset is NOT automatically deducted as per business rule (cash -> position)
        assert asset.total_asset == 10000.0

    def test_deduct_frozen_cash_more_than_frozen_should_raise_error(self):
        # Arrange
        asset = Asset(account_id="test_account", frozen_cash=100.0)

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot deduct more than frozen cash"):
            asset.deduct_frozen_cash(200.0)
