# 长多重判漏斗 · 实现计划（2026-06-11）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或
> executing-plans 逐任务实现。步骤用 `- [ ]` 复选框跟踪。

**Goal:** 给因子判决引擎加 `objective=long_only` 记分牌（Top 层纯多头超额 vs 等权基准），
重判全部 field_ready 因子，验证第二轮「0/10」是否是用错记分牌的假阴性。

**Architecture:** 在 `LayerBacktester` 内并行合成"等权因子覆盖池"基准日收益，算 Top 层超额
（年化 / 信息比 / 正率），贯穿 Report → Verdict → Scorer → 入库 → 驾驶舱。新增 `objective`
开关，默认 `long_short`，旧链路零回归。设计见
`docs/feat/0611-longonly-rejudge/2026-06-11-longonly-rejudge-design.md`。

**Tech Stack:** Python 3.13, pytest(AAA), DuckDB, numpy/纯计算（domain 红线允许）。
测试用 WSL `python -m pytest`；实跑重判用 Windows `python.exe`（读 market.duckdb 离线）。

**关键事实（来自理解阶段图谱）:**
- `LayerBacktester.run` 已产出 `layer_daily_gross[top]`/`layer_daily_turnover[top]`/
  `layer_returns[-1]`（Top 层多头净收益，已扣换手成本，长仓口径）。Top 超额只需新增"基准腿"。
- 前向收益 `returns_by_date[cur][sym]`，`_next_date` 对齐 `factor@T → returns[next_date]`。
- 判决 `judge_factor` 全 AND；门槛常量在 `verdict.py:38-42`；多空闸在 L96/L120。
- factor_verdicts schema `market_data_store.py:67-80`，`_VERDICT_NUMERIC_COLS:101-104`，
  `load_verdict_runs` 用位置切片 `:412-417`（加列须同步 offset）。
- F01/F03/F04 表达式已定向，Top 层=想做多端，无需改 expression。

---

## 文件结构（改动面）

| 文件 | 责任 | 改动类型 |
|---|---|---|
| `src/infrastructure/factor_test/layer_backtest.py` | 分层回测 + Top 超额计算 | 改：Result 加字段 + run 加基准腿 + `_top_excess_net` |
| `src/domain/strategy/factor_test/report.py` | 报告 VO | 改：两个 VO 加 top_excess 字段 + 代理 |
| `src/infrastructure/factor_test/test_runner.py` | 编排器 | 改：透传 objective + 装配新字段 |
| `src/domain/strategy/factor_test/verdict.py` | 判决门槛 | 改：VO 加字段 + 常量 + judge_factor objective 分支 |
| `src/domain/strategy/factor_test/scorer.py` | 评分 | 改：score 加 objective + 变现项切换 |
| `src/application/factor_test_app.py` | 编排 | 改：run_batch/run_single 透传 objective/cost_rate |
| `src/infrastructure/persistence/market_data_store.py` | 留痕 | 改：schema 迁移 + 入库/读出加列 |
| `src/interfaces/cli/quant.py` | CLI 参数 | 改：加 `--objective`/`--cost-rate` |
| `src/interfaces/cli/commands/factor_test.py` | CLI 实现 | 改：透传 + verdict_rows + SUMMARY |
| `src/interfaces/api/static/app.js` + `index.html` | 驾驶舱 | 改：判决表加 top_excess 列 + 上色 |

测试镜像目录：`tests/infrastructure/factor_test/`、`tests/domain/strategy/factor_test/`、
`tests/application/`、`tests/infrastructure/persistence/`。新写测试前先读同目录现有 `test_*.py`
复用 StockSnapshot/fixture 构造法（domain 测试不 mock）。

---

## Task 1: LayerBacktester — Top 层超额 vs 等权基准（核心计算）

**Files:**
- Modify: `src/infrastructure/factor_test/layer_backtest.py`
- Test: `tests/infrastructure/factor_test/test_layer_backtest.py`

**设计要点:** 基准 = 每个调仓日因子覆盖池 `common` 的等权（与 Top 层同口径、costless 参考腿）；
基准成员随调仓更新、持有期内沿用，与各层成员并行累积。Top 日超额 `e_t =
(top_gross_t − top_turnover_t×cost) − bench_gross_t`，复利年化（套 `_long_short_net` 骨架）。

- [ ] **Step 1: 写失败测试**（构造 Top 明显跑赢等权的确定性数据）

```python
# 读现有 test_layer_backtest.py 的 _snap(...) / 构造法后照搬；要点:
# 10 只票, 因子=可排序字段(如 market_cap=i), 高分票日收益高于低分票。
def test_long_only_top_excess_positive():
    # AAA: 高因子值股票每日 +2%, 低因子值 0%; num_layers=5
    snapshots_by_date, returns_by_date = _make_monotone_universe(
        n_symbols=10, n_days=6, high_ret=0.02, low_ret=0.0, factor_field="market_cap")
    bt = LayerBacktester()
    res = bt.run(_expr("market_cap"), snapshots_by_date, returns_by_date, num_layers=5)
    assert res.top_layer_return > res.benchmark_return        # Top 跑赢等权
    assert res.top_excess_return > 0                          # 超额为正
    assert res.excess_positive_rate >= 0.8                    # 多数日 Top 跑赢
    assert res.excess_ir > 0                                  # 信息比为正

def test_long_only_excess_zero_when_top_equals_market():
    # 所有票同收益 → Top 超额≈0
    snapshots_by_date, returns_by_date = _make_flat_universe(n_symbols=10, n_days=6, ret=0.01)
    res = LayerBacktester().run(_expr("market_cap"), snapshots_by_date, returns_by_date, num_layers=5)
    assert abs(res.top_excess_return) < 1e-6
```

- [ ] **Step 2: 跑测试确认失败** — `python -m pytest tests/infrastructure/factor_test/test_layer_backtest.py -k long_only -v` → FAIL（`LayerBacktestResult` 无 `top_excess_return`）

- [ ] **Step 3: 改 `LayerBacktestResult`**（加 5 字段，默认 0.0 向后兼容）

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class LayerBacktestResult:
    layer_count: int
    layer_returns: list[float]
    long_short_return: float
    layer_cumulative: list[list[float]]
    monotonicity_score: float
    # --- long-only 记分牌 (默认 0.0, 向后兼容) ---
    top_layer_return: float = 0.0       # Top 层年化净收益(长仓)
    benchmark_return: float = 0.0       # 等权覆盖池年化(costless 参考)
    top_excess_return: float = 0.0      # Top 层年化超额(扣 Top 腿换手成本)
    excess_ir: float = 0.0              # 年化超额信息比 mean/std×√244
    excess_positive_rate: float = 0.0   # Top 日超额>0 占比
```

- [ ] **Step 4: 改 `run()` 累积基准腿**

在 `run()` 主循环初始化处（L50-54 旁）加：
```python
        bench_daily: list[float] = []
        bench_members: set[str] = set()
```
在成功调仓块内（L86 `members[layer_idx] = new_members` 之后、`has_membership = True` 之前）加：
```python
                    bench_members = set(common)
```
在每日各层累积块之后（L98 之后、L99 `days_held += 1` 之前）加：
```python
            b_rets = [next_returns[s] for s in bench_members if s in next_returns]
            bench_daily.append(sum(b_rets) / len(b_rets) if b_rets else 0.0)
```
在 `long_short = self._long_short_net(...)`（L123-126）之后加：
```python
        top_layer_ret, bench_ret, top_excess, excess_ir, excess_pos = self._top_excess_net(
            layer_daily_gross, layer_daily_turnover, bench_daily, num_layers,
            cost_rate, trading_days_per_year, layer_annual_returns,
        )
```
并把这些传入 `return LayerBacktestResult(... top_layer_return=top_layer_ret,
benchmark_return=bench_ret, top_excess_return=top_excess, excess_ir=excess_ir,
excess_positive_rate=excess_pos)`。

- [ ] **Step 5: 加 `_top_excess_net` 方法**（仿 `_long_short_net`，Bottom 腿换基准腿）

```python
    @staticmethod
    def _top_excess_net(
        layer_daily_gross: list[list[float]],
        layer_daily_turnover: list[list[float]],
        bench_daily: list[float],
        num_layers: int,
        cost_rate: float,
        trading_days_per_year: int,
        layer_annual_returns: list[float],
    ) -> tuple[float, float, float, float, float]:
        """返回 (top_layer_return, benchmark_return, top_excess_return,
        excess_ir, excess_positive_rate)。基准为 costless 参考腿。"""
        import math
        top = num_layers - 1
        n = min(len(layer_daily_gross[top]), len(bench_daily))
        if n == 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        excess_series: list[float] = []
        cum_bench = 1.0
        for t in range(n):
            top_net = layer_daily_gross[top][t] - layer_daily_turnover[top][t] * cost_rate
            e = top_net - bench_daily[t]
            excess_series.append(e)
            cum_bench *= 1 + bench_daily[t]
        # 年化超额: 复利 Top 超额日序列
        cum_excess = 1.0
        for e in excess_series:
            cum_excess *= 1 + e
        top_excess = (cum_excess ** (trading_days_per_year / n) - 1) if cum_excess > 0 else -1.0
        bench_ret = (cum_bench ** (trading_days_per_year / n) - 1) if cum_bench > 0 else -1.0
        top_layer_ret = layer_annual_returns[top]
        # 信息比(年化) + 正率
        mean_e = sum(excess_series) / n
        if n > 1:
            var = sum((x - mean_e) ** 2 for x in excess_series) / (n - 1)
            std_e = math.sqrt(var)
        else:
            std_e = 0.0
        excess_ir = (mean_e / std_e * math.sqrt(trading_days_per_year)) if std_e > 0 else 0.0
        excess_pos = sum(1 for x in excess_series if x > 0) / n
        return top_layer_ret, bench_ret, top_excess, excess_ir, excess_pos
```

- [ ] **Step 6: 跑测试通过** — `pytest tests/infrastructure/factor_test/test_layer_backtest.py -v` → 全 PASS（含原有用例，确认无回归）

- [ ] **Step 7: Commit**
```bash
git add src/infrastructure/factor_test/layer_backtest.py tests/infrastructure/factor_test/test_layer_backtest.py
git commit -m "feat(factor-test): LayerBacktester 加 Top 层纯多头超额(对等权覆盖池基准)"
```

---

## Task 2: Report VO 携带 top_excess + Runner 透传 objective

**Files:**
- Modify: `src/domain/strategy/factor_test/report.py`, `src/infrastructure/factor_test/test_runner.py`
- Test: `tests/infrastructure/factor_test/test_test_runner.py`

- [ ] **Step 1: 写失败测试** — runner.run(objective="long_only") 后 report 带 top_excess_return

```python
def test_runner_populates_top_excess_when_long_only():
    snapshots_by_date, returns_by_date, prices_by_date = _make_monotone_universe_with_prices(...)
    scored = FactorTestRunner().run(
        "market_cap", snapshots_by_date, returns_by_date, prices_by_date,
        num_layers=5, objective="long_only")
    assert scored.top_excess_return > 0
    assert scored.report.top_excess_return == scored.top_excess_return
```

- [ ] **Step 2: 确认失败** — FAIL（`ScoredFactorTestReport` 无 `top_excess_return`）

- [ ] **Step 3: `FactorTestReport` 加字段**（report.py:26 `layer_cumulative` 旁，默认 0.0）

```python
    long_short_return: float = 0.0
    layer_cumulative: list[list[float]] = field(default_factory=list)
    # --- long-only 记分牌 ---
    top_layer_return: float = 0.0
    benchmark_return: float = 0.0
    top_excess_return: float = 0.0
    excess_ir: float = 0.0
    excess_positive_rate: float = 0.0
```
`ScoredFactorTestReport` 加 5 个 @property 代理（仿 L99-105 `long_short_return`）：
```python
    @property
    def top_layer_return(self) -> float: return self.report.top_layer_return
    @property
    def benchmark_return(self) -> float: return self.report.benchmark_return
    @property
    def top_excess_return(self) -> float: return self.report.top_excess_return
    @property
    def excess_ir(self) -> float: return self.report.excess_ir
    @property
    def excess_positive_rate(self) -> float: return self.report.excess_positive_rate
```

- [ ] **Step 4: `test_runner.py` 透传 objective + 装配字段**

`run()` 签名加 `objective: str = "long_short"`；`self._layer_backtester.run(...)` 传
`objective=objective`（Task 1 的 run 已能算 top_excess，无需 objective 参数即可算；
objective 仅向下游 scorer/verdict 传递，**layer_backtester 始终计算 top_excess**——
保持引擎纯计算、judge 决定用哪个记分牌）。`FactorTestReport(...)` 增 5 个 top_excess 字段：
```python
            long_short_return=layer_result.long_short_return,
            layer_cumulative=layer_result.layer_cumulative,
            top_layer_return=layer_result.top_layer_return,
            benchmark_return=layer_result.benchmark_return,
            top_excess_return=layer_result.top_excess_return,
            excess_ir=layer_result.excess_ir,
            excess_positive_rate=layer_result.excess_positive_rate,
```
`self._scorer.score(report)` → `self._scorer.score(report, objective=objective)`（Task 4 实现）。

> 注：objective 在 runner 仅透传给 scorer；引擎始终算 top_excess（成本低、便于并排对照）。

- [ ] **Step 5: 跑测试通过** — `pytest tests/infrastructure/factor_test/test_test_runner.py -v` → PASS

- [ ] **Step 6: Commit**
```bash
git commit -am "feat(factor-test): Report VO 携带 top_excess + Runner 透传 objective"
```

---

## Task 3: judge_factor — objective=long_only 门槛分支（核心判决）

**Files:**
- Modify: `src/domain/strategy/factor_test/verdict.py`
- Test: `tests/domain/strategy/factor_test/test_verdict.py`

**门槛（long_only，全 AND，跑前 pre-register）:** IC≥0.02 / 单调≥0.6 / 中性化|IC|≥0.02（非控制类）/
OOS IC 不翻转 **保留**；**excess_ir≥0.50（替 IR）/ excess_positive_rate≥0.52（替 IC 正率）/
top_excess_return>0（替多空 IS）/ oos_top_excess_return>0（替多空 OOS）**。

- [ ] **Step 1: 写失败测试**（构造各门槛通过/卡点的 ScoredFactorTestReport）

```python
def test_long_only_passes_when_top_excess_and_ir_ok():
    is_r = _scored(ic_mean=0.03, monotonicity=0.8, top_excess_return=0.06,
                   excess_ir=0.7, excess_positive_rate=0.6)
    oos_r = _scored(ic_mean=0.025, top_excess_return=0.04, excess_ir=0.5)
    v = judge_factor(is_r, oos_report=oos_r, objective="long_only", neutralized_ic=None)
    assert v.passed
    assert v.top_excess_return == 0.06 and v.oos_top_excess_return == 0.04

def test_long_only_fails_on_low_excess_ir():
    is_r = _scored(ic_mean=0.03, monotonicity=0.8, top_excess_return=0.06,
                   excess_ir=0.30, excess_positive_rate=0.6)   # ir<0.5
    v = judge_factor(is_r, objective="long_only", neutralized_ic=None)
    assert not v.passed
    assert any("超额信息比" in r for r in v.reasons)

def test_long_only_fails_on_negative_oos_excess():
    is_r = _scored(ic_mean=0.03, monotonicity=0.8, top_excess_return=0.06,
                   excess_ir=0.7, excess_positive_rate=0.6)
    oos_r = _scored(ic_mean=0.02, top_excess_return=-0.05, excess_ir=0.1)
    v = judge_factor(is_r, oos_report=oos_r, objective="long_only", neutralized_ic=None)
    assert not v.passed

def test_long_short_default_unchanged():
    # 旧记分牌零回归: 不传 objective 即 long_short, 仍用 long_short_return 闸
    is_r = _scored(ic_mean=0.03, ir=0.4, ic_positive_rate=0.6, monotonicity=0.8,
                   long_short_return=0.10)
    v = judge_factor(is_r, neutralized_ic=None)
    assert v.passed
```

- [ ] **Step 2: 确认失败** — FAIL（judge_factor 无 objective 参数）

- [ ] **Step 3: 加常量 + VO 字段**（verdict.py:38-42 旁、VO L25 旁）

```python
IC_MIN = 0.02
IR_MIN = 0.30
MONOTONICITY_MIN = 0.6
LONG_SHORT_MIN = 0.0
OOS_IC_SIGN_FLIP = False
# --- long-only 记分牌门槛 (pre-registered) ---
EXCESS_IR_MIN = 0.50
EXCESS_POSITIVE_RATE_MIN = 0.52
TOP_EXCESS_MIN = 0.0
```
`FactorVerdict` 加字段（L25 `oos_long_short_return` 旁，默认 0.0）：
```python
    oos_long_short_return: float = 0.0
    # --- long-only 记分牌 ---
    objective: str = "long_short"
    top_excess_return: float = 0.0
    oos_top_excess_return: float = 0.0
    excess_ir: float = 0.0
    excess_positive_rate: float = 0.0
```

- [ ] **Step 4: judge_factor 加 objective 分支**

签名加 `objective: str = "long_short"`。把现有门槛 2/4/5 改为按 objective 切换：
```python
    # 2. 稳定性: long_short→IC-IR; long_only→超额信息比
    if objective == "long_only":
        if r.excess_ir < EXCESS_IR_MIN:
            passed = False
            reasons.append(f"超额信息比={r.excess_ir:.2f} < {EXCESS_IR_MIN} (稳定性不足)")
        else:
            reasons.append(f"超额信息比={r.excess_ir:.2f} >= {EXCESS_IR_MIN} ✓")
    else:
        if r.ir < IR_MIN: ...  # 原 IC-IR 逻辑不变
```
正率门槛（原 L82）同理：long_only 用 `r.excess_positive_rate < EXCESS_POSITIVE_RATE_MIN`
（文案"超额正率"）；long_short 保持 `r.ic_positive_rate < 0.52`。
变现 IS（原 L96）：long_only 用 `r.top_excess_return <= TOP_EXCESS_MIN`（文案"Top超额"）。
变现 OOS（原 L120）：long_only 用 `oos_r.top_excess_return <= 0`。
IC 门槛(1)、单调(3)、OOS IC 不翻转、中性化(6) **不变**。
返回 `FactorVerdict(...)` 增 `objective=objective, top_excess_return=r.top_excess_return,
oos_top_excess_return=oos_te, excess_ir=r.excess_ir, excess_positive_rate=r.excess_positive_rate`
（`oos_te` 仿 `oos_ls` 从 oos_report 取，默认 0.0）。

- [ ] **Step 5: 跑测试通过** — `pytest tests/domain/strategy/factor_test/test_verdict.py -v` → 全 PASS（含旧 long_short 回归）

- [ ] **Step 6: Commit**
```bash
git commit -am "feat(factor-test): judge_factor 加 long_only 门槛分支(超额信息比/正率/Top超额 IS&OOS)"
```

---

## Task 4: Scorer — objective 感知的变现项

**Files:** Modify `src/domain/strategy/factor_test/scorer.py`；Test `tests/domain/strategy/factor_test/test_scorer.py`

- [ ] **Step 1: 写失败测试**
```python
def test_scorer_long_only_uses_top_excess():
    rep = _report(ic_mean=0.03, ir=0.2, long_short_return=0.0, top_excess_return=0.05,
                  monotonicity_score=1.0)
    score, grade, reasons = FactorScorer().score(rep, objective="long_only")
    assert any("Top超额" in r for r in reasons)   # 变现项改记 Top 超额
    assert score > 0
```

- [ ] **Step 2: 确认失败** — FAIL（score 无 objective 参数）

- [ ] **Step 3: 改 `score()`** — 签名加 `objective: str = "long_short"`；变现项(L43-44)切换：
```python
        # 3. 变现 (20%): long_short→多空 0.03→0.15; long_only→Top 超额 0.0→0.05
        if objective == "long_only":
            mon_part = _linear_score(report.top_excess_return, 0.0, 0.05) * 20
            reasons.append(f"Top超额 (20%): {mon_part:.0f}/20  年化 {report.top_excess_return:.1%}")
        else:
            mon_part = _linear_score(report.long_short_return, 0.03, 0.15) * 20
            reasons.append(f"多空收益 (20%): {mon_part:.0f}/20  年化 {report.long_short_return:.1%}")
```
（把 `ls_part` 改名 `mon_part`，`total = ic_part + ir_part + mon_part + mono_part + decay_part`）

- [ ] **Step 4: 跑测试通过** — `pytest tests/domain/strategy/factor_test/test_scorer.py -v` → PASS

- [ ] **Step 5: Commit** — `git commit -am "feat(factor-test): Scorer 变现项按 objective 切换(long_only 记 Top 超额)"`

---

## Task 5: App service — run_batch/run_single 透传 objective/cost_rate

**Files:** Modify `src/application/factor_test_app.py`；Test `tests/application/test_factor_test_app.py`

- [ ] **Step 1: 写失败测试** — run_batch(objective="long_only") 端到端，verdict 带 top_excess

```python
def test_run_batch_long_only_end_to_end():
    svc = FactorTestAppService(history_fetcher=..., fundamental_fetcher=..., market_data=None)
    snap, ret, prices = _make_monotone_universe_with_prices(...)
    results = svc.run_batch([_hyp("F01","小市值","market_cap","规模")], snap, ret, prices,
                            test_period=("2024-01-01","2024-12-31"),
                            objective="long_only", num_layers=5)
    assert results[0].verdict.objective == "long_only"
    assert results[0].verdict.top_excess_return != 0.0
```

- [ ] **Step 2: 确认失败** — FAIL（run_batch 无 objective）

- [ ] **Step 3: 改 `run_batch`** — 签名加 `objective: str = "long_short"`, `cost_rate: float = 0.003`；
`run_single(...)` 调用加传 `objective, cost_rate`（IS 与 OOS 两处，L212/L225）；
`judge_factor(...)` 调用加 `objective=objective`（L238）。

- [ ] **Step 4: 改 `run_single`** — 签名加 `objective`/`cost_rate`；`FactorTestRunner.run(...)` 传
`objective=objective`（cost_rate 透传到 layer_backtester：runner.run 也需加 cost_rate 形参→
layer_backtester.run，默认 0.003；最小改动可只透 objective，cost_rate 暂用默认，见 Task 7 CLI）。

> 决策：cost_rate 透传链 CLI→app→runner→backtester 一并加 default=0.003 形参，便于 `--cost-rate`。

- [ ] **Step 5: 跑测试通过** — `pytest tests/application/test_factor_test_app.py -v` → PASS

- [ ] **Step 6: Commit** — `git commit -am "feat(factor-test): app run_batch/run_single 透传 objective/cost_rate"`

---

## Task 6: Store — factor_verdicts schema 迁移 + 入库/读出加列

**Files:** Modify `src/infrastructure/persistence/market_data_store.py`；
Test `tests/infrastructure/persistence/test_market_data_store.py`

- [ ] **Step 1: 写失败测试**（旧表迁移 + 新列入库 + 混读不错位）
```python
def test_verdict_migration_and_longonly_roundtrip(tmp_path):
    store = MarketDataStore(str(tmp_path / "m.duckdb"))
    store.insert_verdicts("run-lo", {"objective": "long_only"}, [{
        "factor_id": "F01", "factor_name": "小市值", "expression": "0 - log(market_cap)",
        "ic_mean": 0.03, "ir": 0.1, "ic_positive_rate": 0.55, "monotonicity_score": 0.8,
        "long_short_return": 0.0, "score": 70, "grade": "B",
        "oos_ic_mean": 0.02, "oos_ir": 0.1, "oos_long_short_return": 0.0,
        "objective": "long_only", "top_excess_return": 0.06, "oos_top_excess_return": 0.04,
        "excess_ir": 0.7, "excess_positive_rate": 0.6, "passed": True, "reasons": ["ok"],
    }])
    runs = store.load_verdict_runs()
    f = runs[0]["factors"][0]
    assert f["top_excess_return"] == 0.06 and f["objective"] == "long_only"
    assert f["factor_id"] == "F01"   # 位置切片未错位
```

- [ ] **Step 2: 确认失败** — FAIL（列不存在 / KeyError）

- [ ] **Step 3: 扩 `_VERDICT_NUMERIC_COLS`**（L101-104，追加 4 个数值列）
```python
_VERDICT_NUMERIC_COLS = (
    "ic_mean", "ir", "ic_positive_rate", "monotonicity_score", "long_short_return",
    "score", "oos_ic_mean", "oos_ir", "oos_long_short_return",
    "top_excess_return", "oos_top_excess_return", "excess_ir", "excess_positive_rate",
)
```

- [ ] **Step 4: 加幂等迁移**（store `__init__` 建表后，对存量库 ALTER 加列）

在 `_DDL_STATEMENTS` 执行后调 `self._migrate_verdict_columns()`：
```python
    def _migrate_verdict_columns(self) -> None:
        cols = {
            "top_excess_return": "DOUBLE", "oos_top_excess_return": "DOUBLE",
            "excess_ir": "DOUBLE", "excess_positive_rate": "DOUBLE",
            "objective": "VARCHAR",
        }
        for col, typ in cols.items():
            try:
                self._conn.execute(f"ALTER TABLE factor_verdicts ADD COLUMN IF NOT EXISTS {col} {typ}")
            except Exception:
                pass
        # 存量 run 的 objective 回填
        self._conn.execute("UPDATE factor_verdicts SET objective='long_short' WHERE objective IS NULL")
```
（新建库的 CREATE TABLE DDL 也同步加这 5 列，避免新库 ALTER 冗余；DDL 加：
`top_excess_return DOUBLE, oos_top_excess_return DOUBLE, excess_ir DOUBLE,
excess_positive_rate DOUBLE, objective VARCHAR`。）

- [ ] **Step 5: 改 `insert_verdicts`** — `objective` 是 VARCHAR 非数值列，单独处理。把 SQL 列表加
`objective`，VALUES 加 `r.get("objective", "long_short")`（放 grade 旁，与 _VERDICT_NUMERIC_COLS
数值列分开）。

- [ ] **Step 6: 改 `load_verdict_runs`** — SELECT 加 `objective`；因 `_VERDICT_NUMERIC_COLS` 已扩，
位置切片 `row[5:5+len(...)]`/`row[5+len]`(grade)/`row[6+len]`(passed)/`row[7+len]`(reasons) 自动随
`len(_VERDICT_NUMERIC_COLS)` 调整（已用 `len()` 非硬编码，安全）；objective 放 SELECT 末尾
`params` 之前，factor dict 加 `"objective": row[<idx>]`。**仔细核对 SELECT 列序与切片 offset 一致。**

- [ ] **Step 7: 跑测试通过** — `pytest tests/infrastructure/persistence/test_market_data_store.py -v` → PASS（含旧 long_short 入库回归）

- [ ] **Step 8: Commit** — `git commit -am "feat(persistence): factor_verdicts 迁移加 top_excess/objective 列 + 入库读出"`

---

## Task 7: CLI — --objective/--cost-rate + verdict_rows + SUMMARY

**Files:** Modify `src/interfaces/cli/quant.py`, `src/interfaces/cli/commands/factor_test.py`；
Test `tests/interfaces/cli/test_factor_test_command.py`（若无则新建，测 args 解析 + verdict_rows 组装）

- [ ] **Step 1: 写失败测试** — `--objective long_only` 解析 + verdict_rows 含 top_excess 键

- [ ] **Step 2: 确认失败**

- [ ] **Step 3: `quant.py` 加参数**（L70 `--no-store` 旁）
```python
    p_ft.add_argument("--objective", choices=["long_short", "long_only"],
                       default="long_short", help="判决记分牌: long_short(多空) / long_only(Top纯多头超额)")
    p_ft.add_argument("--cost-rate", type=float, default=0.003, help="单边换手往返成本率")
```

- [ ] **Step 4: `commands/factor_test.py` 透传 + 输出**
  - 读 `objective = args.objective`, `cost_rate = args.cost_rate`；打印行加 `print(f"Objective: {objective}")`。
  - `service.run_batch(..., objective=objective, cost_rate=cost_rate)`。
  - SUMMARY 表头/行按 objective 切换变现列：long_only 显示 `Excess`/`ExIR` 列（`v.top_excess_return`/
    `v.excess_ir`），long_short 显示原 `L/S` 列。
  - `verdict_rows` 每行加 `"objective": v.objective, "top_excess_return": v.top_excess_return,
    "oos_top_excess_return": v.oos_top_excess_return, "excess_ir": v.excess_ir,
    "excess_positive_rate": v.excess_positive_rate`。
  - `run_params` 加 `"objective": objective, "cost_rate": cost_rate`。

- [ ] **Step 5: 跑测试通过** + 烟测 `--help`：`python -m src.interfaces.cli.quant factor-test --help` 显示新参数

- [ ] **Step 6: Commit** — `git commit -am "feat(cli): factor-test 加 --objective/--cost-rate + long_only SUMMARY"`

---

## Task 8: 驾驶舱 — 判决表 top_excess 列 + 上色

**Files:** Modify `src/interfaces/api/static/app.js`, `src/interfaces/api/static/index.html`

- [ ] **Step 1: app.js GATES 加 long_only 阈值副本**（L80-86 旁，注释标"与 verdict.py 同步, 债 D2"）
```js
const GATES_LONGONLY = {
  ic_mean: v => v >= 0.02, excess_ir: v => v >= 0.50,
  excess_positive_rate: v => v >= 0.52, top_excess_return: v => v > 0,
  oos_top_excess_return: v => v > 0, monotonicity_score: v => v >= 0.6,
};
```
- [ ] **Step 2: renderRun 按 `run.params.objective` 选列集**：long_only run 显示
`top_excess_return/excess_ir/excess_positive_rate` 列（gateCell 上色用 GATES_LONGONLY），
long_short run 显示原 `long_short_return` 列。index.html 表头相应条件渲染或加列。
- [ ] **Step 3: 烟测** — 启动 dashboard，因子判决页 long_short 旧 run 显示不变（回归），
新 long_only run（Task 9 跑出后）显示 top_excess 列且上色正确。
- [ ] **Step 4: Commit** — `git commit -am "feat(dashboard): 判决页 long_only run 显示 Top 超额列 + 上色"`

---

## Task 9: 实跑长多重判 + 产出报告

**Files:** Create `docs/feat/0611-longonly-rejudge/2026-06-11-longonly-rejudge-report.md`
**环境:** Windows `python.exe`（读 market.duckdb 离线；先确认 universe 走离线回退或显式符号集）

- [ ] **Step 1: 全量回归** — WSL `python -m pytest tests/ --ignore=tests/infrastructure/gateway/` 全绿；`ruff check src/` 干净
- [ ] **Step 2: 主判决** — 全 field_ready 因子，long_only，5 分位，5 日调仓：
```bash
$WIN_PY -m src.interfaces.cli.quant factor-test --factors all \
  --start-date 2021-01-01 --end-date 2026-06-11 --split-date 2024-06-30 \
  --objective long_only --num-layers 5 --rebalance-days 5
```
（`all` 解析会含 F10 field_ready=False→catalog 应已排除；若未排除则显式 `--factors F01,F02,F03,F04,F05,F06,F07,F08,F09,F11`）
- [ ] **Step 3: 敏感性** — F01/F03/F04 调仓 1/5/20 日（各一次 `--rebalance-days`）+ 分位集中度
  `--num-layers 10`（Top 十分位）。
- [ ] **Step 4: 核对入库** — 驾驶舱因子判决页应见新 long_only run（top_excess 列）。
- [ ] **Step 5: 写报告** — 含：long_only 真实过闸数 + 完整指标表（IC/excess_ir/excess_pos/
  top_excess IS&OOS/passed）；与第二轮多空记分牌**并排对照**（翻盘/仍不过/新发现）；F01/F03/F04
  敏感性+集中度小表；结论（是否找到首个可长多变现候选；若无,分裂结构在长多口径是否仍存,主线下一岔口）。
- [ ] **Step 6: Commit** — `git commit -am "docs(longonly-rejudge): 长多重判报告 — 全因子 long_only 判决 + 多空对照"`

---

## Self-Review（计划 vs 设计）

- **Spec 覆盖**：§三 记分牌数学→Task1；§四 门槛→Task3；scorer 重标→Task4；§五 改动面 10 文件
  →Task1-8；§六 迁移+驾驶舱→Task6/8；§七 运行矩阵→Task9；§九 验收→Task9 Step1/5。全覆盖。
- **占位符**：核心新逻辑（基准腿/超额年化/门槛/迁移）均给真实代码；fixture 构造法指向同目录现有
  test（执行者读后照搬），非占位。
- **类型一致**：`top_excess_return/excess_ir/excess_positive_rate/benchmark_return/top_layer_return`
  五字段名贯穿 Result→Report→Verdict→DB 列→verdict_rows 全程一致；`objective` 字符串
  `"long_short"|"long_only"` 全程一致。
- **TDD/提交**：每 Task 测试先行 + 独立 commit；Task9 前全量回归门。

## 执行说明（本会话, ultracode）

实现按 Task1→8 顺序 TDD（强依赖、需精确，主控顺序执行最稳）；Task9 实跑用 Windows python。
**多智能体增值放在验证**：实现完成后跑①对全 diff 的对抗式代码审查 workflow，②对重判数值的
独立复核 workflow（与第二轮对账、口径合理性）。设计/计划/报告三文档留痕直推 main（WSL 无法 push,
留 Windows 侧）。
