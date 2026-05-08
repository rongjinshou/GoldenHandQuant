import logging

logger = logging.getLogger(__name__)

try:
    import xtquant.xtconstant as xtconstant
    import xtquant.xtdata as xtdata
    import xtquant.xttrader as xttrader
    import xtquant.xttype as xttype

    XtQuantTrader = xttrader.XtQuantTrader
    XtQuantTraderCallback = xttrader.XtQuantTraderCallback
    StockAccount = xttype.StockAccount
except ImportError as e:
    raise ImportError(
        "xtquant SDK not found. Install via: pip install xtquant"
    ) from e

__all__ = [
    "xtdata",
    "xtconstant",
    "xttrader",
    "xttype",
    "XtQuantTrader",
    "XtQuantTraderCallback",
    "StockAccount",
]
