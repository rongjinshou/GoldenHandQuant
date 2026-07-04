# 研究记录退役机制 — 设计与决策记录

> 状态: **已实现**（2026-07-05）。后端 delete_backtest_run/delete_verdict_run +
> DELETE 端点、前端两页删除入口、一次性脚本均已落地并通过 pytest 1379 例 +
> vitest 122 例 + ui_smoke 全绿验证。**存量清理尚未执行**——dry-run 已验证
> `--before 2026-07-01 --keep MFCOMBO-20210101-20260613` 精确命中 27 轮回测
> + 9 轮判决, 待用户确认后手动加 `--yes` 执行(数据删除操作不自动执行)。
> 起因: 用户发现判决/回测列表被调测残留淹没, 且全仓库无任何删除/清理机制, 问"没有数据的退役机制吗，之前调测残留的数据也在？"（2026-07-05）。经查证:
> - `factor_verdicts` 10 轮中 9 轮为 2026-06-11~14 调测（其中 3 轮连 objective 参数都没有）
> - `backtest_runs` 29 轮中 27 轮为调测（18 轮 compare_strategies 挤在 30 小时内, 9 轮 f01 挤在 1.5 小时内）
> - 全仓库无 DELETE/purge/prune/TTL；`load_verdict_runs()` 无条件全表返回连 LIMIT 都没有
> - 用户看到的"切分 2024-06-30 / 5207 只 / v1 全轮相同"即此残留的直接后果——同一批参数反复调测

## 1. 决策

| # | 决策 | 理由 |
|---|------|------|
| D1 | **硬删除**（非软删/归档列） | 表结构不加状态位保持简单；"留痕"诉求由删除前备份满足——脚本自动整行备份 JSON, UI 删除弹确认并显示人话标题 |
| D2 | **不做自动过期（TTL）** | 研究记录价值不随时间衰减（回溯"当时为什么 FAIL"）, 垃圾与否只有人能判定 |
| D3 | 长期入口 = **UI 单条删除**；存量清理 = **一次性脚本** | 39 行残留逐条点太累→脚本批量+备份；日后零星清理用 UI 顺手删 |
| D4 | DELETE 端点用**独立写连接依赖** `get_research_write_store`, 只读依赖不动 | DuckDB 单写者: factor-test/refresh 持写锁期间, 写连接会失败→503（复用前端已有"写锁占用"转写文案）; 只读端点不受影响 |
| D5 | 不碰 trading.db, 不加新鉴权 | 交易侧只读红线无涉——两张表都在 market.duckdb 研究侧, 网页本就能写入（提交任务即写 backtest_runs）; 服务仅绑 127.0.0.1, 删除操作继承同一鉴权边界 |
| D6 | 删除粒度 = **整轮 run_id**（非单策略/单因子行） | 用户心智模型是"这轮调测是垃圾", 不存在删半轮的场景; 两表主键分别为 (run_id, strategy)/(run_id, factor_id), 按 run_id 删全部关联行 |

## 2. 接口与行为契约

### Store（`market_data_store.py`）

```python
def delete_backtest_run(self, run_id: str) -> int: ...   # 返回删除行数(该 run 的策略行数)
def delete_verdict_run(self, run_id: str) -> int: ...    # 返回删除行数(该 run 的因子行数)
```
- 参数绑定防注入; run_id 不存在 → 返回 0（不抛错, 由调用方语义化）
- read_only 连接上调用 → DuckDB 自然抛错（写端点不会用只读连接, 不额外防御）

### API（`routes/research.py`）

| 端点 | 成功 | run 不存在 | 写锁被占 |
|---|---|---|---|
| `DELETE /api/research/backtests/{run_id}` | 200 `{"deleted": n}` | 404 `detail="run 不存在: <id>"` | 503（依赖注入时连接失败, 文案同现有 get_research_store） |
| `DELETE /api/research/verdicts/{run_id}` | 同上 | 同上 | 同上 |

- `get_research_write_store`: 每请求短生命周期 `MarketDataStore(path, read_only=False)`; 库文件不存在 → 404（没有库谈不上删除）
- run_id 含 `/` 等特殊字符: FastAPI path 参数默认不匹配 `/`, 现有 run_id 字符集（字母数字连字符）无此问题, 不做额外转义

### 前端

- **回测页左轨行**: hover 时右上浮现 ✕ 按钮（NPopconfirm 确认, 文案含人话标题:
  「删除这轮回测？\n微盘价值质量增强策略 · 全市场 · 2021→2026\n20260614-103252 · 不可恢复」）
  - 确认 → `DELETE` → 成功后 `loadBacktests()` 刷新（列表重载后自动选中最新一条, 已有语义）
  - 删除的是当前选中项 → 同上, 自然落到最新, 无需特判
  - 失败（503/404）→ 顶部 ErrorBanner 显示（走现有 error ref 通道）
- **判决页**: 轮次下拉右侧一个「删除本轮」次级按钮（非 primary, 不与提交检验争焦点）, 同款 NPopconfirm; 成功后 `loadVerdicts()`
- `api/fetch.ts` 新增 `deleteJSON<T>(url)`: 语义同 postJSON 的错误处理（503 转写/非 2xx 抛 Error）

### 一次性脚本（`scripts/prune_research_runs.py`）

```
$WIN_PYTHON scripts/prune_research_runs.py                       # dry-run: 列出两表全部轮次(序号/时间/来源/行数)
$WIN_PYTHON scripts/prune_research_runs.py --before 2026-07-01   # dry-run: 标注将删除 created_at < 该日的轮次
$WIN_PYTHON scripts/prune_research_runs.py --before 2026-07-01 --keep MFCOMBO-20210101-20260613 --yes
                                                                  # 执行: 删除选中集但保留 --keep 指定的 run(逗号分隔)
$WIN_PYTHON scripts/prune_research_runs.py --ids 20260611-191905,20260611-192433 --yes   # 精确指定
```
- 选择器: `--before DATE`（created_at 严格早于）与 `--ids`（精确, 逗号分隔）二选一; `--keep` 在两者上均生效
- **备份**: 执行删除前, 把被删轮次的完整行（含 equity_curve/trades/reasons 大 JSON）写入
  `data/backups/research_prune_<YYYYMMDD-HHMMSS>.json`, 结构 `{"backtest_runs": [...], "factor_verdicts": [...]}`;
  备份写盘成功才执行 DELETE（写失败则中止）。备份可能数 MB（trades 截断上限 2000 笔/策略）, 属预期
- 无 `--yes` 一律只预览; 预览也显示"将备份到"路径
- 写锁被占 → 明确报错退出 1（提示先停 factor-test/refresh 任务）
- 针对本次 39 行残留的推荐命令（保留 07-04 两轮回测 + 最新判决轮）:
  `--before 2026-07-01 --keep MFCOMBO-20210101-20260613`
  （回测侧 07-04 的两轮 created_at ≥ 07-01 天然不在选中集）

## 3. 测试清单

- store: 删除存在的 run 返回行数且他轮不受影响 / 删除不存在的 run 返回 0 / 多策略(多因子)同 run 全删
- routes: 200+deleted 计数 / 404（run 不存在、库不存在）/ 删除后 GET 列表不再含该 run
- 脚本: 纯函数（选择器过滤 before/ids/keep）单测; 备份-后-删除顺序以集成方式在临时库验证
- 前端: typecheck/lint/vitest 全绿（deleteJSON 单测: 200 解析/非 2xx 抛错）; ui_smoke 零 console 错误; 读图验收 hover ✕ 与确认弹窗

## 4. 非目标

- 不做回收站/恢复功能（备份 JSON 手工可查, 真要恢复是罕见事件, 手工 INSERT 即可）
- 不做批量多选 UI（存量靠脚本, 日后零星靠单删; 若未来高频批删再议）
- 不动 `load_verdict_runs` 的无 LIMIT 问题（数据清干净后 10 轮量级无性能问题; 若未来轮次上千再加分页）
