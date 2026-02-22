import os
import sys
from pathlib import Path

# Add xtquant libs to DLL search path for Windows
if sys.platform == "win32":
    # Get the directory of this file
    current_dir = Path(__file__).parent
    # The libs directory is ../libs/xtquant relative to this file (infrastructure/gateway)
    xtquant_dir = current_dir.parent / "libs" / "xtquant"
    
    if xtquant_dir.exists():
        # Python 3.8+ requires explicit DLL directory adding
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(xtquant_dir))
        # Also add to PATH just in case
        os.environ["PATH"] = str(xtquant_dir) + os.pathsep + os.environ["PATH"]

from .qmt_market import QmtMarketGateway
from .qmt_trade import QmtTradeGateway

__all__ = ["QmtMarketGateway", "QmtTradeGateway"]
