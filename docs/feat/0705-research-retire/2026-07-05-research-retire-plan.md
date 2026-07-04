# 研究记录退役机制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给判决/回测研究记录加删除能力（后端 DELETE + 前端删除入口 + 一次性清理脚本），解决用户发现的"39 轮残留数据无法清理"问题。

**Architecture:** Store 层加两个删除方法（按 run_id 全删关联行）→ API 层加两个 DELETE 端点（独立写连接依赖，复用现有写锁 503 语义）→ 前端两页加删除入口（NPopconfirm 二次确认，显示人话标题防误删）→ 一次性脚本批量清理存量残留（删前自动备份 JSON）。

**Tech Stack:** FastAPI + DuckDB（后端）；Vue3 + Naive UI NPopconfirm（前端）；纯 argparse 脚本（无新依赖）。

## Global Constraints

- 硬删除，不做软删/归档列/TTL 自动过期（设计 §1 D1/D2）
- 删除粒度 = 整轮 run_id（设计 §1 D6），不支持删单策略/单因子行
- DELETE 端点用独立写连接依赖，与现有只读依赖并存，不改动只读路径
- 不碰 trading.db；不新增鉴权（继承现有 127.0.0.1 绑定边界）
- 所有新增 Python 代码遵循项目规范：`list[X]`/`X | None`，测试 AAA 模式
- 前端遵循既有 GlossaryTip/ErrorBanner/card 视觉语言，不引入新 UI 库

---

### Task 1: Store 层删除方法

**Files:**
- Modify: `src/infrastructure/persistence/market_data_store.py`
- Test: `tests/infrastructure/persistence/test_backtest_run_store.py`（追加 `TestDeleteBacktestRun`）
- Test: `tests/infrastructure/persistence/test_market_data_store.py`（追加 `TestDeleteVerdictRun`，若判决相关测试已在此文件）

**Interfaces:**
- Produces: `MarketDataStore.delete_backtest_run(run_id: str) -> int`、`MarketDataStore.delete_verdict_run(run_id: str) -> int`（返回删除行数）

- [ ] **Step 1: 写失败测试 — 删除回测轮次**

在 `tests/infrastructure/persistence/test_backtest_run_store.py` 的 `TestBacktestRunStore` 类后追加：

```python
class TestDeleteBacktestRun:
    def test_delete_existing_run_removes_all_its_strategy_rows(self):
        store = MarketDataStore(":memory:")
        r1 = build_backtest_run_row(_report(), run_id="r1", params={})
        r2 = dict(r1, strategy="micro_value")
        other = build_backtest_run_row(_report(), run_id="r2", params={})
        store.insert_backtest_runs([r1, r2, other])

        deleted = store.delete_backtest_run("r1")

        assert deleted == 2
        remaining = store.load_backtest_runs()
        assert [r["run_id"] for r in remaining] == ["r2"]

    def test_delete_nonexistent_run_returns_zero(self):
        store = MarketDataStore(":memory:")
        store.insert_backtest_runs([build_backtest_run_row(_report(), run_id="r1", params={})])

        assert store.delete_backtest_run("does-not-exist") == 0
        assert len(store.load_backtest_runs()) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/infrastructure/persistence/test_backtest_run_store.py::TestDeleteBacktestRun -v`
Expected: FAIL with `AttributeError: 'MarketDataStore' object has no attribute 'delete_backtest_run'`

- [ ] **Step 3: 实现 delete_backtest_run**

在 `market_data_store.py` 的 `insert_backtest_runs` 方法后（`load_backtest_runs` 方法前或后均可，保持"backtest_runs（回测结果留痕, 闭环 v1 DD-5）"分节内）追加：

```python
    def delete_backtest_run(self, run_id: str) -> int:
        """删除整轮回测(该 run_id 下全部策略行)。返回删除行数。"""
        result = self._conn.execute(
            "DELETE FROM backtest_runs WHERE run_id = ?", [run_id]
        )
        return result.fetchone()[0] if result.description else 0
```

注意：DuckDB 的 `DELETE` 语句 `.execute()` 返回值需确认实际行为——若 DuckDB 版本不支持从 DELETE 直接拿行数，改用前置 COUNT 查询：

```python
    def delete_backtest_run(self, run_id: str) -> int:
        """删除整轮回测(该 run_id 下全部策略行)。返回删除行数。"""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM backtest_runs WHERE run_id = ?", [run_id]
        ).fetchone()[0]
        if count:
            self._conn.execute("DELETE FROM backtest_runs WHERE run_id = ?", [run_id])
        return count
```

用第二种写法（COUNT-then-DELETE），不依赖 DuckDB DELETE 返回值的版本行为，更稳。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/infrastructure/persistence/test_backtest_run_store.py::TestDeleteBacktestRun -v`
Expected: PASS（2 项）

- [ ] **Step 5: 写失败测试 — 删除判决轮次**

先读 `tests/infrastructure/persistence/test_market_data_store.py` 确认判决相关测试的既有 fixture 写法（`insert_verdicts` 调用签名），再在合适位置追加：

```python
class TestDeleteVerdictRun:
    def test_delete_existing_run_removes_all_its_factor_rows(self):
        store = MarketDataStore(":memory:")
        store.insert_verdicts("run1", {"split": "2024-06-30"}, [
            {"factor_id": "F01", "passed": True, "reasons": []},
            {"factor_id": "F02", "passed": False, "reasons": []},
        ])
        store.insert_verdicts("run2", {}, [{"factor_id": "F01", "passed": True, "reasons": []}])

        deleted = store.delete_verdict_run("run1")

        assert deleted == 2
        remaining = store.load_verdict_runs()
        assert [r["run_id"] for r in remaining] == ["run2"]

    def test_delete_nonexistent_run_returns_zero(self):
        store = MarketDataStore(":memory:")
        store.insert_verdicts("run1", {}, [{"factor_id": "F01", "passed": True, "reasons": []}])

        assert store.delete_verdict_run("does-not-exist") == 0
        assert len(store.load_verdict_runs()) == 1
```

- [ ] **Step 6: 运行测试确认失败, 然后实现 delete_verdict_run**

Run: `python -m pytest tests/infrastructure/persistence/test_market_data_store.py::TestDeleteVerdictRun -v`
Expected: FAIL（无此方法）

在 `market_data_store.py` 的 `insert_verdicts`/`load_verdict_runs` 所在的 "factor_verdicts（判决留痕）" 分节追加：

```python
    def delete_verdict_run(self, run_id: str) -> int:
        """删除整轮判决(该 run_id 下全部因子行)。返回删除行数。"""
        count = self._conn.execute(
            "SELECT COUNT(*) FROM factor_verdicts WHERE run_id = ?", [run_id]
        ).fetchone()[0]
        if count:
            self._conn.execute("DELETE FROM factor_verdicts WHERE run_id = ?", [run_id])
        return count
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/infrastructure/persistence/test_backtest_run_store.py tests/infrastructure/persistence/test_market_data_store.py -v`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add src/infrastructure/persistence/market_data_store.py tests/infrastructure/persistence/test_backtest_run_store.py tests/infrastructure/persistence/test_market_data_store.py
git commit -m "feat(research): MarketDataStore 加整轮删除方法(delete_backtest_run/delete_verdict_run)"
```

---

### Task 2: API DELETE 端点

**Files:**
- Modify: `src/interfaces/api/routes/research.py`
- Test: `tests/interfaces/api/test_research_routes.py`

**Interfaces:**
- Consumes: Task 1 的 `store.delete_backtest_run(run_id)` / `store.delete_verdict_run(run_id)`
- Produces: `DELETE /api/research/backtests/{run_id}` → `{"deleted": int}`；`DELETE /api/research/verdicts/{run_id}` → `{"deleted": int}`；两者 404（run 不存在或库不存在）、503（写锁占用）

- [ ] **Step 1: 写失败测试**

先读 `tests/interfaces/api/test_research_routes.py` 顶部的 fixture（临时 DuckDB 注入方式、`app.dependency_overrides[get_research_store]` 用法），仿照其风格在文件末尾追加：

```python
class TestDeleteBacktestRun:
    def test_delete_existing_run_returns_deleted_count(self, tmp_path):
        db_path = str(tmp_path / "test.duckdb")
        store = MarketDataStore(db_path)
        store.insert_backtest_runs([{
            "run_id": "r1", "strategy": "dual_ma", "start_date": "2024-01-01",
            "end_date": "2024-12-31", "initial_capital": 1e6, "params": "{}",
            "total_return": 0.1, "annualized_return": 0.1, "max_drawdown": 0.05,
            "sharpe_ratio": 1.0, "sortino_ratio": 1.0, "calmar_ratio": 1.0,
            "win_rate": 0.5, "trade_count": 1, "turnover_rate": 0.01,
            "equity_curve": "{}", "trades": "[]",
        }])
        store.close()

        client = TestClient(app)
        resp = client.delete(f"/api/research/backtests/r1", headers={"X-Test-DB": db_path})
        # 若路由用环境变量/依赖覆盖注入库路径, 按现有测试文件实际方式改写此处而非 header

    def test_delete_nonexistent_run_returns_404(self):
        ...  # 具体写法对齐本文件已有测试对 get_research_store 依赖覆盖的方式
```

**重要**：上面是示意骨架。实现前必须先读 `test_research_routes.py` 全文，确认该文件是通过 `app.dependency_overrides[get_research_store] = lambda: <store>` 还是环境变量 `GHQ_MARKET_DB` 注入临时库——按文件里已有测试的真实模式改写，不要凭空假设。写完后测试函数名参考：
- `test_delete_existing_backtest_run_returns_count`
- `test_delete_nonexistent_backtest_run_returns_404`
- `test_delete_existing_verdict_run_returns_count`
- `test_delete_nonexistent_verdict_run_returns_404`
- `test_delete_when_db_missing_returns_404`

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/interfaces/api/test_research_routes.py -k delete -v`
Expected: FAIL（404，路由不存在）

- [ ] **Step 3: 实现写连接依赖 + 两个 DELETE 端点**

在 `research.py` 的 `get_research_store` 函数后追加一个独立的写连接依赖：

```python
def get_research_write_store() -> Iterator[MarketDataStore]:
    """删除端点用的独立写连接依赖 — 短生命周期, 每请求一个, 与只读依赖并存。

    库文件不存在 → 404(没有库谈不上删除); 写锁被 factor-test/data-refresh
    占用 → 503(同 get_research_store 的转写文案)。
    """
    path = _db_path()
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail="研究数据库不存在")
    try:
        store = MarketDataStore(path, read_only=False)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail="market.duckdb 正被写进程占用（factor-test / data refresh 运行中），"
                   f"请稍后重试。底层错误: {e}",
        ) from e
    try:
        yield store
    finally:
        store.close()
```

在 `backtests` 端点函数后追加：

```python
@router.delete("/backtests/{run_id}")
async def delete_backtest(
    run_id: str,
    store: MarketDataStore = Depends(get_research_write_store),
):
    """删除整轮回测(该 run_id 下全部策略行) — 设计 docs/feat/0705-research-retire。"""
    deleted = store.delete_backtest_run(run_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
    return {"deleted": deleted}
```

在 `verdicts` 端点函数后追加：

```python
@router.delete("/verdicts/{run_id}")
async def delete_verdict(
    run_id: str,
    store: MarketDataStore = Depends(get_research_write_store),
):
    """删除整轮判决(该 run_id 下全部因子行) — 设计 docs/feat/0705-research-retire。"""
    deleted = store.delete_verdict_run(run_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"run 不存在: {run_id}")
    return {"deleted": deleted}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/interfaces/api/test_research_routes.py -v`
Expected: 全部 PASS（含此前既有测试不受影响）

- [ ] **Step 5: 全量 pytest 回归**

Run: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/interfaces/api/routes/research.py tests/interfaces/api/test_research_routes.py
git commit -m "feat(research): DELETE /api/research/{backtests,verdicts}/{run_id} 端点"
```

---

### Task 3: 前端 deleteJSON + 回测页删除入口

**Files:**
- Modify: `frontend/src/api/fetch.ts`
- Modify: `frontend/src/pages/Backtests.vue`
- Test: `frontend/src/api/__tests__/fetch.spec.ts`

**Interfaces:**
- Consumes: Task 2 的 `DELETE /api/research/backtests/{run_id}`
- Produces: `deleteJSON<T>(url: string): Promise<T>`（供 Task 4 判决页复用）

- [ ] **Step 1: 写失败测试 — deleteJSON**

先读 `frontend/src/api/fetch.ts` 现有 `postJSON` 实现与 `fetch.spec.ts` 现有测试风格（mock fetch 方式），在 `fetch.spec.ts` 追加对齐同款 mock 模式的测试：

```typescript
describe('deleteJSON', () => {
  it('2xx 解析 JSON body', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ deleted: 1 }),
    })
    const result = await deleteJSON<{ deleted: number }>('/api/research/backtests/r1')
    expect(result.deleted).toBe(1)
    expect(global.fetch).toHaveBeenCalledWith('/api/research/backtests/r1', { method: 'DELETE' })
  })

  it('404 抛出包含状态码与 body 的 Error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 404, text: async () => '{"detail":"run 不存在: x"}',
    })
    await expect(deleteJSON('/api/research/backtests/x')).rejects.toThrow('404')
  })

  it('503 写锁占用 + 有活跃任务 → 转写文案(同 fetchJSON 语义)', async () => {
    // 对齐 fetchJSON 现有 503+activeCount 测试用例的 mock 方式(jobsStore)
  })
})
```

写之前先读 `fetch.spec.ts` 里 `fetchJSON` 的 503 测试用例完整代码，`deleteJSON` 的 503 测试照抄其 mock jobsStore 的方式。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- fetch.spec.ts`
Expected: FAIL（`deleteJSON` 未导出）

- [ ] **Step 3: 实现 deleteJSON**

在 `frontend/src/api/fetch.ts` 的 `postJSON` 函数后追加（复用 `lockAwareError`）：

```typescript
export async function deleteJSON<T>(url: string): Promise<T> {
  const resp = await fetch(url, { method: 'DELETE' })
  if (!resp.ok) {
    const body = await resp.text()
    throw lockAwareError(resp.status, url, body)
  }
  return resp.json() as Promise<T>
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm run test -- fetch.spec.ts`
Expected: PASS

- [ ] **Step 5: 回测页加删除入口**

读当前 `Backtests.vue` 的 `run-row` 模板（左轨行）与 script 部分（`loadBacktests`/`selectRun` 等），在 script 里追加：

```typescript
import { NPopconfirm } from 'naive-ui'
// ... 在既有 import { fetchJSON } from '@/api/fetch' 处一并加:
import { deleteJSON, fetchJSON } from '@/api/fetch'

const deletingId = ref<string | null>(null)

async function deleteRun(runId: string): Promise<void> {
  deletingId.value = runId
  try {
    await deleteJSON(`/api/research/backtests/${runId}`)
    await loadBacktests() // 重载后按既有语义自动选中最新一条
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    deletingId.value = null
  }
}
```

模板改动：给 `.run-row` 内追加删除触发（用 NPopconfirm 包裹一个 hover 才显的 ✕ 按钮）：

```html
<button
  v-for="r in runs"
  :key="r.run_id"
  type="button"
  class="run-row"
  :class="{ active: r.run_id === selectedRunId }"
  data-testid="bt-run-row"
  :title="r.run_id"
  @click="selectRun(r.run_id)"
>
  <span class="run-title">{{ runLabels.get(r.run_id)?.title }}</span>
  <span class="run-row-bottom">
    <span class="run-subtitle">{{ runLabels.get(r.run_id)?.subtitle }}</span>
    <span class="run-id num">{{ r.run_id }}</span>
  </span>
  <NPopconfirm
    :positive-text="'删除'"
    :negative-text="'取消'"
    @positive-click.stop="deleteRun(r.run_id)"
  >
    <template #trigger>
      <span
        class="run-delete"
        data-testid="bt-run-delete"
        :title="`删除这轮回测: ${runLabels.get(r.run_id)?.title}`"
        @click.stop
      >✕</span>
    </template>
    删除这轮回测？<br />
    <b>{{ runLabels.get(r.run_id)?.title }}</b><br />
    <span class="t-muted">{{ r.run_id }} · 不可恢复</span>
  </NPopconfirm>
</button>
```

注意：`<button>` 内嵌套可交互元素（NPopconfirm trigger）在 HTML 语义上不合法（button 不能嵌 button/复杂交互块）。若 NPopconfirm 内部渲染出嵌套 button 导致 DOM 警告或点击冒泡问题，改为：**把外层 `.run-row` 从 `<button>` 改成 `<div role="button" tabindex="0" @click @keydown.enter>`**，保持可访问性但避免嵌套按钮的 HTML 校验问题。实现时先跑一次浏览器 console 检查有无 `<button> cannot appear as a descendant of <button>` 警告，若有则做此改动。

CSS 追加（`run-row` 需要 `position: relative` 已有或补上，删除按钮默认透明 hover 显现）：

```css
.run-row {
  position: relative; /* 若已存在则不重复加 */
}

.run-delete {
  border-radius: var(--radius-sm);
  color: var(--text-3);
  cursor: pointer;
  font-size: 13px;
  opacity: 0;
  padding: 2px 6px;
  position: absolute;
  right: 6px;
  top: 6px;
  transition: opacity var(--dur-fast) var(--ease-out), color var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out);
}

.run-row:hover .run-delete {
  opacity: 1;
}

.run-delete:hover {
  background: color-mix(in srgb, var(--c-fail) 14%, transparent);
  color: var(--c-fail);
}
```

- [ ] **Step 6: typecheck + build 验证无回归**

Run: `cd frontend && npm run typecheck && npm run test && npm run build`
Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/fetch.ts frontend/src/api/__tests__/fetch.spec.ts frontend/src/pages/Backtests.vue src/interfaces/api/static
git commit -m "feat(ui): 回测页轮次删除入口(hover✕ + 二次确认)"
```

---

### Task 4: 判决页删除入口

**Files:**
- Modify: `frontend/src/pages/Verdicts.vue`

**Interfaces:**
- Consumes: Task 3 的 `deleteJSON`；`DELETE /api/research/verdicts/{run_id}`

- [ ] **Step 1: 加删除按钮**

读当前 `Verdicts.vue` 的页头（`run-select` NSelect 所在行）与 script 部分。在 script 追加：

```typescript
import { deleteJSON, fetchJSON, postJSON } from '@/api/fetch'
// ...
const deleting = ref(false)

async function deleteCurrentRun(): Promise<void> {
  const id = run.value?.run_id
  if (!id) return
  deleting.value = true
  try {
    await deleteJSON(`/api/research/verdicts/${id}`)
    await loadVerdicts()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    deleting.value = false
  }
}
```

模板在 `run-select` NSelect 旁追加次级删除按钮（非 primary，避免与"提交检验"CTA 争焦点）：

```html
<header class="page-head">
  <h2>因子判决</h2>
  <NSelect v-if="runOptions.length" ... />
  <NPopconfirm
    v-if="run"
    :positive-text="'删除'"
    :negative-text="'取消'"
    @positive-click="deleteCurrentRun"
  >
    <template #trigger>
      <NButton size="small" quaternary :loading="deleting" data-testid="verdict-delete">删除本轮</NButton>
    </template>
    删除这轮判决？<br />
    <b>{{ runOptions[selectedIdx]?.label }}</b><br />
    <span class="t-muted">不可恢复</span>
  </NPopconfirm>
</header>
```

- [ ] **Step 2: typecheck + test + build**

Run: `cd frontend && npm run typecheck && npm run test && npm run build`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Verdicts.vue src/interfaces/api/static
git commit -m "feat(ui): 判决页轮次删除入口"
```

---

### Task 5: 一次性清理脚本

**Files:**
- Create: `scripts/prune_research_runs.py`
- Test: `tests/scripts/test_prune_research_runs.py`（若项目已有 `tests/scripts/` 目录；否则读 `scripts/` 下其他脚本是否有对应测试先例，没有则该脚本仅做手工验证，跳过单测——多数 `scripts/*.py` 是手工运维脚本无测试, 遵循现状）

**Interfaces:**
- Consumes: Task 1 的 `delete_backtest_run`/`delete_verdict_run`、`load_backtest_runs`/`load_verdict_runs`

- [ ] **Step 1: 先确认项目里 scripts/ 下是否有测试先例**

Run: `ls tests/ | grep -i script` 与 `find scripts -name "*.py" | xargs -I{} basename {} .py | while read f; do find tests -iname "test_$f*"; done`

若无先例（预期结果），本脚本按项目惯例只做手工验证（对齐 `scripts/shadow_paper_equity.py` 等既有脚本无测试的模式），跳过单测步骤，直接进入 Step 2 实现。

- [ ] **Step 2: 实现脚本**

创建 `scripts/prune_research_runs.py`：

```python
"""研究记录退役清理 — 一次性/按需批量删除 backtest_runs/factor_verdicts 调测残留。

背景: 判决/回测列表长期无清理机制, 调测阶段的反复试跑残留会淹没真实研究记录
(见 docs/feat/0705-research-retire/2026-07-05-research-retire-design.md)。

用法:
    python scripts/prune_research_runs.py                                    # dry-run: 列出全部轮次
    python scripts/prune_research_runs.py --before 2026-07-01                # dry-run: 标注选中集
    python scripts/prune_research_runs.py --before 2026-07-01 --keep RUN_ID  # dry-run: 标注+排除保留项
    python scripts/prune_research_runs.py --ids id1,id2 --yes                # 执行: 精确删除
    python scripts/prune_research_runs.py --before 2026-07-01 --yes          # 执行: 批量删除

删除前自动把选中轮次的完整行(含 equity_curve/trades/reasons)备份到
data/backups/research_prune_<时间戳>.json, 备份失败则中止不删。
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.infrastructure.persistence.market_data_store import MarketDataStore

DB_PATH = "data/market.duckdb"
BACKUP_DIR = Path("data/backups")


def select_runs(runs: list[dict], before: str | None, ids: set[str] | None, keep: set[str]) -> list[dict]:
    """纯函数: 按 before(created_at 早于)/ids(精确) 选择, keep 始终排除。"""
    if ids is not None:
        selected = [r for r in runs if r["run_id"] in ids]
    elif before is not None:
        selected = [r for r in runs if r["created_at"] < before]
    else:
        selected = []
    return [r for r in selected if r["run_id"] not in keep]


def backup(selected_backtests: list[dict], selected_verdicts: list[dict]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = BACKUP_DIR / f"research_prune_{ts}.json"
    path.write_text(
        json.dumps(
            {"backtest_runs": selected_backtests, "factor_verdicts": selected_verdicts},
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--before", help="删除 created_at 早于此日期(YYYY-MM-DD)的轮次")
    parser.add_argument("--ids", help="精确指定要删除的 run_id, 逗号分隔")
    parser.add_argument("--keep", default="", help="即使命中选择器也保留的 run_id, 逗号分隔")
    parser.add_argument("--yes", action="store_true", help="执行删除(默认只预览)")
    args = parser.parse_args()

    ids = set(args.ids.split(",")) if args.ids else None
    keep = {k for k in args.keep.split(",") if k}

    store = MarketDataStore(DB_PATH, read_only=not args.yes)
    try:
        all_backtests = store.load_backtest_runs(limit=10_000)
        all_verdicts = store.load_verdict_runs()
    finally:
        store.close()

    sel_bt = select_runs(all_backtests, args.before, ids, keep)
    sel_vd = select_runs(all_verdicts, args.before, ids, keep)

    print(f"回测: 共 {len(all_backtests)} 轮, 选中 {len(sel_bt)} 轮删除")
    for r in sel_bt:
        print(f"  - {r['run_id']:<28} {r['created_at']}")
    print(f"判决: 共 {len(all_verdicts)} 轮, 选中 {len(sel_vd)} 轮删除")
    for r in sel_vd:
        print(f"  - {r['run_id']:<28} {r['created_at']}")

    if not (sel_bt or sel_vd):
        print("无匹配轮次, 结束。")
        return 0

    if not args.yes:
        print("\n(预览模式, 未执行删除; 加 --yes 执行, 执行前会先备份到 data/backups/)")
        return 0

    backup_path = backup(sel_bt, sel_vd)
    print(f"已备份至 {backup_path}")

    store = MarketDataStore(DB_PATH, read_only=False)
    try:
        for r in sel_bt:
            store.delete_backtest_run(r["run_id"])
        for r in sel_vd:
            store.delete_verdict_run(r["run_id"])
    finally:
        store.close()
    print(f"已删除 回测 {len(sel_bt)} 轮 / 判决 {len(sel_vd)} 轮。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: dry-run 手工验证**

Run: `$WIN_PYTHON scripts/prune_research_runs.py`
Expected: 列出 29 轮回测 + 10 轮判决, 不执行任何删除

Run: `$WIN_PYTHON scripts/prune_research_runs.py --before 2026-07-01 --keep MFCOMBO-20210101-20260613`
Expected: 回测选中 27 轮(排除 07-04 的两轮), 判决选中 9 轮(排除 keep 指定的最新轮), 仍为预览

- [ ] **Step 4: 若用户确认, 执行清理并验证**

Run: `$WIN_PYTHON scripts/prune_research_runs.py --before 2026-07-01 --keep MFCOMBO-20210101-20260613 --yes`
Expected: 打印备份路径, 打印删除计数; 之后 `curl http://127.0.0.1:8501/api/research/backtests` 只剩 2 轮, `curl http://127.0.0.1:8501/api/research/verdicts` 只剩 1 轮

**此步为数据变更操作, 执行前需征得用户明确同意(不可逆的生产数据删除), 不可自动执行。**

- [ ] **Step 5: Commit（脚本本身, 不含 --yes 执行结果）**

```bash
git add scripts/prune_research_runs.py
git commit -m "feat(scripts): 研究记录清理脚本(dry-run默认/备份后删/before或ids选择器)"
```

---

### Task 6: 全量验收

**Files:** 无新文件

- [ ] **Step 1: 后端全量回归**

Run: `python -m pytest tests/ --ignore=tests/infrastructure/gateway/`
Expected: 全部 PASS

- [ ] **Step 2: 前端全量验证**

Run: `cd frontend && npm run typecheck && npm run lint && npm run test && npm run build`
Expected: 全部通过, vitest 新增 deleteJSON 相关用例

- [ ] **Step 3: UI 冒烟 + 读图**

Run: `$WIN_PYTHON scripts/ui_smoke.py --out data/ui_screenshots`
Expected: PASS, 零 console 错误

用截图/浏览器验证: 回测左轨 hover 出现 ✕、点击弹出确认框(含人话标题)、确认后列表刷新且选中最新；判决页"删除本轮"按钮同理。双主题各看一次。

- [ ] **Step 4: 漂移防线**

Run: `$WIN_PYTHON scripts/check_frontend_fresh.py`
Expected: `[fresh] OK`

- [ ] **Step 5: 更新设计文档状态**

把 `docs/feat/0705-research-retire/2026-07-05-research-retire-design.md` 顶部状态行从"设计定稿, 按 plan.md 实施"改为"已实现"，一句话记录实施日期与是否已执行过存量清理。

- [ ] **Step 6: Commit**

```bash
git add docs/feat/0705-research-retire/
git commit -m "docs(0705): 研究记录退役机制 实施完成记录"
```
