"""WSL 侧 gateway 测试驱动（2026-07-11 六西格玛 T2/Control）。

gateway 测试逻辑上全 mock、不需真 QMT, 但被测模块顶层 import xtquant 在
WSL 崩(datacenter 无 Linux 二进制), conftest 因此整目录跳过。本驱动预注入
假 xtquant 模块后直跑, 让 WSL 也能回归 gateway 逻辑。
Windows 侧 `$WIN_PYTHON scripts/verify_all.py`(真 SDK)仍是权威验证。

用法: python scripts/run_gateway_tests_wsl.py

保真度要点: XtQuantTraderCallback 必须是真类(生产代码 GhqTraderCallback 继承它),
MagicMock 不能当基类; 顶层假包属性须与子模块对象一致(import a.b as x 取的是
getattr(a, "b"))。
"""
import sys
from unittest.mock import MagicMock


class _FakeCallbackBase:
    """xtquant 回调基类替身(可被继承, 方法全为空实现)。"""

    def on_disconnected(self): ...
    def on_stock_order(self, order): ...
    def on_order_error(self, order_error): ...


xttrader = MagicMock()
xttrader.XtQuantTraderCallback = _FakeCallbackBase
pkg = MagicMock()
xtconstant, xtdata, xttype = MagicMock(), MagicMock(), MagicMock()
# `import xtquant.xttrader as x` 实际绑定 getattr(顶层包, "xttrader") ——
# 顶层假包属性必须指向同一对象, 否则拿到自动生成的子 mock
pkg.xttrader, pkg.xtconstant, pkg.xtdata, pkg.xttype = (
    xttrader, xtconstant, xtdata, xttype)
for name, mod in (
    ("xtquant", pkg),
    ("xtquant.xtconstant", xtconstant),
    ("xtquant.xtdata", xtdata),
    ("xtquant.xttrader", xttrader),
    ("xtquant.xttype", xttype),
):
    sys.modules[name] = mod

import pytest  # noqa: E402

sys.exit(pytest.main([
    "tests/infrastructure/gateway/",
    "-q", "--tb=short", "-p", "no:cacheprovider",
]))
