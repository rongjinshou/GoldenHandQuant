"""架构分层纯度守卫（2026-07-11 六西格玛 Control）。

把 docs/rules/architecture.md 的依赖红线固化为自动门禁——此前纯度靠人肉
grep 勘察, 本轮 T4 把 application 顶层 infra import 清零后, 用本测试防回退。

红线（AST 静态扫描, 只看模块顶层 import; 函数内延迟导入是接受的运行期装配惯例）:
1. domain 不得 import application/infrastructure/interfaces;
2. domain 不得 import 数据源 SDK/存储引擎/Web/可视化/ML训练库
   (允许 numpy/pandas/scipy 纯计算, 见 0611-market-data-store 变更记录);
3. application 顶层不得 import infrastructure(TYPE_CHECKING 块除外)与 interfaces。
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

DOMAIN_FORBIDDEN_PREFIXES = (
    "src.application", "src.infrastructure", "src.interfaces",
)
DOMAIN_FORBIDDEN_LIBS = (
    "xtquant", "tushare", "akshare", "duckdb", "sqlite3", "fastapi",
    "uvicorn", "flask", "matplotlib", "plotly", "lightgbm", "sklearn",
    "torch", "optuna", "requests", "httpx",
)
APP_FORBIDDEN_PREFIXES = ("src.infrastructure", "src.interfaces")


def _toplevel_imports(path: Path) -> list[tuple[str, int]]:
    """模块顶层 import 名单(排除 if TYPE_CHECKING 块与函数/类体内)。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[str, int]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            out.extend((a.name, node.lineno) for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append((node.module, node.lineno))
    return out


def _violations(root: Path, forbidden: tuple[str, ...]) -> list[str]:
    bad: list[str] = []
    for py in sorted(root.rglob("*.py")):
        for mod, lineno in _toplevel_imports(py):
            if any(mod == f or mod.startswith(f + ".") for f in forbidden):
                bad.append(f"{py.relative_to(SRC.parent)}:{lineno} imports {mod}")
    return bad


class TestLayerPurity:
    def test_domain_never_imports_outer_layers(self):
        bad = _violations(SRC / "domain", DOMAIN_FORBIDDEN_PREFIXES)
        assert bad == [], "domain 依赖方向违规:\n" + "\n".join(bad)

    def test_domain_never_imports_forbidden_libs(self):
        bad = _violations(SRC / "domain", DOMAIN_FORBIDDEN_LIBS)
        assert bad == [], "domain 禁用库违规:\n" + "\n".join(bad)

    def test_application_toplevel_never_imports_infra_or_interfaces(self):
        """T4 达成的纯度基线: 顶层 0 违规(延迟导入/TYPE_CHECKING 不计)。"""
        bad = _violations(SRC / "application", APP_FORBIDDEN_PREFIXES)
        assert bad == [], "application 顶层耦合违规:\n" + "\n".join(bad)
