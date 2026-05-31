import os
import tempfile

from src.infrastructure.config.settings import (
    BacktestSettings,
    LiveTradeSettings,
    QmtSettings,
    load_backtest_config,
    load_trading_config,
)


def test_load_backtest_config_defaults():
    """加载不存在的文件时应使用默认值（通过临时 YAML 文件测试）。"""
    yaml_content = """
backtest:
  symbols:
    - "000001.SZ"
    - "600000.SH"
  start_date: "2020-01-01"
  end_date: "2023-12-31"
  initial_capital: 500000.0
strategy:
  name: "TestStrategy"
position_sizing:
  type: "FixedRatioSizer"
  ratio: 0.3
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        settings = load_backtest_config(tmp_path)
        assert settings.backtest.symbols == ["000001.SZ", "600000.SH"]
        assert settings.backtest.initial_capital == 500000.0
        assert settings.strategy.name == "TestStrategy"
        assert settings.position_sizing.ratio == 0.3
    finally:
        os.unlink(tmp_path)


def test_load_trading_config():
    yaml_content = """
qmt:
  userdata_path: "/test/path"
  session_id: 999
  account_id: "12345678"
  account_type: "STOCK"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        settings = load_trading_config(tmp_path)
        assert settings.qmt.userdata_path == "/test/path"
        assert settings.qmt.session_id == 999
        assert settings.qmt.account_id == "12345678"
    finally:
        os.unlink(tmp_path)


def test_backtest_settings_defaults():
    settings = BacktestSettings()
    assert settings.symbols == ["000021.SZ"]
    assert settings.initial_capital == 1_000_000.0
    assert settings.plot is True


def test_qmt_settings_defaults():
    settings = QmtSettings()
    assert settings.account_type == "STOCK"
    assert settings.session_id == 0


def test_live_trade_settings_defaults():
    settings = LiveTradeSettings()
    assert settings.strategy == "dual_ma"
    assert settings.symbols == []
    assert settings.position_ratio == 0.1
    assert settings.slippage_buy == 0.001
    assert settings.slippage_sell == 0.001
    assert settings.bar_lookback == 100


def test_load_trading_config_with_live_trade():
    yaml_content = """
qmt:
  userdata_path: "/test/path"
  session_id: 999
  account_id: "12345678"
  account_type: "STOCK"
live_trade:
  strategy: "custom_strategy"
  symbols:
    - "600519.SH"
  position_ratio: 0.2
  slippage_buy: 0.002
  slippage_sell: 0.002
  bar_lookback: 200
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        tmp_path = f.name

    try:
        settings = load_trading_config(tmp_path)
        assert settings.qmt.userdata_path == "/test/path"
        assert settings.live_trade.strategy == "custom_strategy"
        assert settings.live_trade.symbols == ["600519.SH"]
        assert settings.live_trade.position_ratio == 0.2
        assert settings.live_trade.slippage_buy == 0.002
        assert settings.live_trade.bar_lookback == 200
    finally:
        os.unlink(tmp_path)
