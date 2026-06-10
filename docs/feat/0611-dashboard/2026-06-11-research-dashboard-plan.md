# 投研 Dashboard v1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans（本会话内联执行，
> 用户预授权）。步骤用 checkbox 跟踪。规格：同目录 `2026-06-11-research-dashboard-design.md`。
> 测试统一 Windows conda Python：`WIN_PY=/mnt/c/Users/11492/.conda/envs/goldenhandquant/python.exe`

**Goal:** `quant dashboard` 一键起本机投研驾驶舱（数据资产/因子判决/个股查看），判决入库，补 README。

**Architecture:** 复用既有 FastAPI app，新增只读 `/api/research/*` 路由（Depends 注入
read_only DuckDB store）+ 同进程托管原生 HTML/JS+ECharts 静态页。判决由 factor-test CLI
跑完 upsert 进 `factor_verdicts` 表。

**Tech Stack:** FastAPI 0.136 / uvicorn 0.46（已装）、DuckDB、ECharts 5.5.1（vendored）、纯原生前端。

---

### Task 1: factor_verdicts 表 + store 读写 + read_only 模式

**Files:**
- Modify: `src/infrastructure/persistence/market_data_store.py`
- Test: `tests/infrastructure/persistence/test_market_data_store.py`（增补类）

- [x] **Step 1 失败测试**（增补到现有测试文件）：

```python
class TestVerdicts:
    def _rows(self):
        return [{
            "factor_id": "F04", "factor_name": "低波动", "expression": "0 - volatility_20d",
            "ic_mean": 0.05, "ir": 0.31, "ic_positive_rate": 0.62,
            "monotonicity_score": 1.0, "long_short_return": 0.15,
            "score": 88.0, "grade": "A",
            "oos_ic_mean": 0.05, "oos_ir": 0.3, "oos_long_short_return": -0.01,
            "passed": False, "reasons": ["样本外多空收益<=0"],
        }]

    def test_insert_and_load_runs_grouped_desc(self, store):
        store.insert_verdicts("20260611-010000", {"start": "2021-01-01"}, self._rows())
        store.insert_verdicts("20260611-020000", {"start": "2021-01-01"}, self._rows())
        runs = store.load_verdict_runs()
        assert [r["run_id"] for r in runs] == ["20260611-020000", "20260611-010000"]
        assert runs[0]["params"]["start"] == "2021-01-01"
        f = runs[0]["factors"][0]
        assert f["factor_id"] == "F04" and f["passed"] is False
        assert f["reasons"] == ["样本外多空收益<=0"]

    def test_insert_idempotent(self, store):
        store.insert_verdicts("r1", {}, self._rows())
        store.insert_verdicts("r1", {}, self._rows())
        assert len(store.load_verdict_runs()) == 1

class TestReadOnly:
    def test_read_only_can_read(self, tmp_path):
        path = str(tmp_path / "m.duckdb")
        rw = MarketDataStore(path)
        rw.upsert_bars([_bar("A", "2024-01-02", 10.0)], "qmt")
        rw.close()
        ro = MarketDataStore(path, read_only=True)
        assert len(ro.load_bars_df(["A"], "2024-01-01", "2024-12-31", "qmt")) == 1
        ro.close()
```

- [x] **Step 2 跑挂**：`$WIN_PY -m pytest tests/infrastructure/persistence/test_market_data_store.py -q`
  预期 FAIL（insert_verdicts 不存在 / read_only 参数不存在）
- [x] **Step 3 实现**：DDL 追加 `factor_verdicts`（规格 §5）；
  `__init__(db_path, read_only=False)`：read_only 时 `duckdb.connect(db_path, read_only=True)`
  且**跳过 DDL**（只读连接不能建表；文件不存在时报 FileNotFoundError 由调用方处理）；
  `insert_verdicts(run_id, params: dict, rows: list[dict])`（created_at=datetime.now()，
  reasons/params json.dumps，INSERT OR REPLACE）；
  `load_verdict_runs() -> list[dict]`（按 run_id 分组，created_at 倒序，json.loads 还原）
- [x] **Step 4 跑绿** 同命令
- [x] **Step 5 提交**：`git add -A src/infrastructure/persistence tests/infrastructure/persistence && git commit -m "feat(store): factor_verdicts 判决入库 + read_only 连接模式"`

### Task 2: factor-test 跑完写库

**Files:**
- Modify: `src/interfaces/cli/commands/factor_test.py`（第 8 步 JSON 输出旁）

- [x] **Step 1 实现**（CLI 薄层，随 Task 3 集成测试覆盖）：run 开始处
  `run_id = datetime.now().strftime("%Y%m%d-%H%M%S")`；结果段构造
  `verdict_rows = [{...verdict 字段同规格 §5...} for r in results]`，
  `params = {"start": start_date, "end": end_date, "split": split_date,
  "rebalance_days": rebalance_days, "num_layers": num_layers,
  "feature_version": FEATURE_VERSION, "universe_count": len(symbols)}`，
  `wiring.store.insert_verdicts(run_id, params, verdict_rows)` 后打印 run_id；
  JSON 文件输出逻辑保留不动
- [x] **Step 2 提交**：`git commit -m "feat(factor-test): 判决自动入库 factor_verdicts"`

### Task 3: /api/research/* 路由 + 测试

**Files:**
- Create: `src/interfaces/api/routes/research.py`
- Modify: `src/interfaces/api/app.py`（include_router）
- Test: `tests/interfaces/api/test_research_routes.py`（新目录带 __init__.py）

- [x] **Step 1 失败测试**（核心断言，TestClient + 临时库 + dependency_overrides）：

```python
@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "m.duckdb")
    s = MarketDataStore(db)
    s.upsert_instruments([{"symbol": "000001.SZ", "name": "平安银行",
                           "list_date": "1991-04-03", "delist_date": None}], "qmt")
    s.upsert_bars([_bar("000001.SZ", f"2024-01-{d:02d}", 10.0 + d) for d in range(2, 12)], "qmt")
    s.upsert_features_df(_feature_df("000001.SZ", "2024-01-05"), feature_version=FEATURE_VERSION)
    s.insert_verdicts("r1", {"start": "2021-01-01"}, _verdict_rows())
    s.close()
    app.dependency_overrides[get_research_store] = lambda: MarketDataStore(db, read_only=True)
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_overview(client):           # tables 统计 + verdict_runs 数
def test_verdicts_grouped(client)    # runs[0].factors[0].factor_id == "F04"
def test_symbols_prefix_search(client)   # q=000 命中, q=999 空
def test_bars_echarts_shape(client)  # dates/ohlc[[o,c,l,h]]/volume 等长
def test_features_series(client)     # names=return_20d → series.return_20d
def test_features_unknown_name_422(client)
def test_empty_db_overview_zero(tmp_path)  # 新建空库 → rows 全 0
```

- [x] **Step 2 跑挂**：`$WIN_PY -m pytest tests/interfaces/api/test_research_routes.py -q` → import error
- [x] **Step 3 实现** `research.py`：`get_research_store()`（env `GHQ_MARKET_DB` 默认
  `data/market.duckdb`；文件不存在 → 返回 None，端点对 None 给空态）；五端点按规格 §4；
  `finally: store.close()`；`app.py` `include_router(research.router, prefix="/api/research", tags=["research"])`
- [x] **Step 4 跑绿** 同命令
- [x] **Step 5 提交**：`git commit -m "feat(api): /api/research 只读投研端点(概览/判决/标的/K线/特征)"`

### Task 4: 静态前端（三页签 + ECharts）

**Files:**
- Create: `src/interfaces/api/static/index.html`（页签骨架 + 空态文案）
- Create: `src/interfaces/api/static/style.css`（深色主题 CSS 变量）
- Create: `src/interfaces/api/static/app.js`（fetch 五端点渲染；K 线 candlestick+量柱
  上下 grid；特征曲线右轴叠加；判决表门槛着色：IC≥0.02/IR≥0.3/单调≥0.6/多空>0/OOS多空>0 绿否则红；
  run 下拉切换；reasons 折叠行）
- Create: `src/interfaces/api/static/vendor/echarts.min.js`（5.5.1，已下载于 /tmp/echarts.min.js）
- Modify: `src/interfaces/api/app.py`（mount `/ui` StaticFiles(html=True)，`GET /` 302 → `/ui/`）

- [x] **Step 1 实现四文件 + 挂载**（前端无单测；行为由 Task 5 冒烟覆盖）
- [x] **Step 2 提交**：`git commit -m "feat(dashboard): 投研驾驶舱前端(数据资产/因子判决/个股查看)"`

### Task 5: quant dashboard 子命令 + 冒烟

**Files:**
- Create: `src/interfaces/cli/commands/dashboard_cmd.py`
- Modify: `src/interfaces/cli/quant.py`（子命令注册 + case 分发）

- [x] **Step 1 实现**：`run_dashboard(args)`：set env `GHQ_MARKET_DB=args.db`，
  `uvicorn.run("src.interfaces.api.app:app", host="127.0.0.1", port=args.port, log_level="info")`；
  quant.py 增 `dashboard` 子命令（`--port 8501`、`--db data/market.duckdb`）
- [x] **Step 2 冒烟**（实跑验证，不能只看启动日志）：后台起服务 →
  `curl http://127.0.0.1:8501/health` 200、`/api/research/overview` 含 tables、
  `/ui/` 返回 HTML、`/` 302 → 杀进程
- [x] **Step 3 提交**：`git commit -m "feat(cli): quant dashboard 子命令(uvicorn 127.0.0.1)"`

### Task 6: README.md

**Files:**
- Create: `README.md`

- [x] **Step 1 写作**（章节）：项目定位与风险声明 / 架构（四层依赖方向图）/
  环境准备（conda + WSL/Windows 双 Python + QMT 说明）/ 快速开始（refresh →
  factor-test → dashboard 三步）/ CLI 命令表（list/backtest/factor-test/data/
  dashboard/ml-*/monitor）/ 市场数据库（五表+履约机制一段）/ 测试与 lint /
  文档索引（docs/feat 列表 + docs/rules）
- [x] **Step 2 提交**：`git commit -m "docs: 项目 README(架构/快速开始/CLI/数据库/dashboard)"`

### Task 7: 全量验证收尾

- [x] `$WIN_PY -m pytest tests/ --ignore=tests/infrastructure/gateway/ -q` 全绿
- [x] `$WIN_PY -m ruff check src/` 仅存量 fetch_account.py E501（不在范围）；新增测试文件 ruff 干净
- [x] 计划 checkbox 全勾 + progress 文档更新（含 v2 判决对比，另行提交）

## Self-Review 结论

- 规格覆盖：R1→T5、R2/R3/R4→T3+T4、R5→T1+T2、R6→T6；§7 read_only→T1；§8 测试→T1/T3/T5
- 无占位符；类型一致（insert_verdicts/load_verdict_runs/get_research_store 签名前后一致）
- 前端无单测为有意决策（原生静态页，由 API 测试 + 冒烟覆盖），记录于 T4
