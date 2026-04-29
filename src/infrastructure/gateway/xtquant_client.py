import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _setup_xtquant_path() -> None:
    """Setup DLL and Python paths for xtquant if it's in libs/xtquant."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    xtquant_dir = project_root / "libs" / "xtquant"

    if xtquant_dir.exists():
        # Add to Python path
        libs_dir = str(xtquant_dir.parent)
        if libs_dir not in sys.path:
            sys.path.insert(0, libs_dir)

        # Add to DLL path (Windows)
        if sys.platform == "win32":
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(xtquant_dir))
            os.environ["PATH"] = str(xtquant_dir) + os.pathsep + os.environ.get("PATH", "")


# Set up the paths before attempting to import
_setup_xtquant_path()

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
        "xtquant SDK not found. Install via: pip install xtquant "
        "or place xtquant in the libs/ directory."
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
