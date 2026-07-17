"""gateway 测试目录守卫（2026-07-10 六西格玛体检 D4）。

本目录测试全部用 mock 打桩 SDK, 逻辑上不需要真 QMT——但被测模块顶层
`from .xtquant_client import ...` 在无 xtquant 的环境(WSL Python)导入即抛,
历史上因此整目录被 `--ignore` 连坐, 30 个覆盖实盘防腐层的用例从不进验收链。

守卫语义: xtquant 可导入(Windows Python) → 全跑; 不可导入(WSL) → 优雅跳过。
标准命令已去掉 --ignore, 见 CLAUDE.md。
"""

import pytest

# 探测 xttrader 而非顶层包: xtquant 的 PyPI 包在 Linux 也能 pip 装(顶层 import 可过),
# 但 datacenter C 扩展无 Linux 版, xttrader 链导入即抛 —— 以真实可用性为准
pytest.importorskip(
    "xtquant.xttrader",
    reason="gateway 测试需可用的 xtquant SDK(仅 Windows Python), WSL 下跳过",
)
