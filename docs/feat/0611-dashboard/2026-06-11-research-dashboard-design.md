# 投研 Dashboard v1 设计文档（需求 + 设计）

> 状态：用户预授权（"自己规划需求完成落地，放开所有权限"，2026-06-11 夜）——
> 交互式澄清/批准门以本文档"决策记录"代替，晨间可补审，任何决策可推翻重做。
> 流程：superpowers brainstorming → writing-plans（实施计划见同目录 plan 文档）。

## 1. 背景与目标

项目已有：诚实因子测试引擎、DuckDB 市场数据库（5207 只 × 5.5 年行情/基本面/特征）、
统一 CLI。**没有**：任何前端、项目 README、判决结果的结构化存储（散落 JSON）。

目标（"不能再像个玩具项目"）：

1. **投研 Dashboard**：浏览器里看清三件事——数据资产有什么、因子判决结果如何、
   任意个股的行情与特征长什么样
2. **判决入库**：factor-test 结果写入 DuckDB `factor_verdicts` 表，历次可查可比
3. **项目 README**：定位、架构、快速开始、CLI 一览，对外可读

## 2. 范围

### 本期做

| # | 需求 | 验收标准 |
|---|---|---|
| R1 | `quant dashboard` 一键起服务 | 浏览器打开 `http://127.0.0.1:8501/ui/` 可用 |
| R2 | 数据资产页 | 四表行数/标的数/日期范围 + 特征版本一目了然 |
| R3 | 因子判决页 | 按 run 切换历次判决，门槛红绿灯着色，FAIL 原因可见 |
| R4 | 个股查看页 | 搜索 symbol → K 线 + 成交量 + 任选特征曲线叠加 |
| R5 | 判决入库 | factor-test 跑完自动 upsert `factor_verdicts`，JSON 输出保留兼容 |
| R6 | README.md | 新人 10 分钟能跑起回测/因子测试/dashboard |

### 明确不做（YAGNI，记录原因）

- **实盘监控页**：`/api/dashboard/*`（WS 推送/账户快照/token 鉴权）后端骨架已存在，
  属 Phase 3 实盘阶段需求，本期不接前端、不改其代码
- **写操作**：v1 纯只读，不从浏览器触发回测/刷数（命令行已覆盖，避免提权面）
- **鉴权/多用户**：仅绑定 127.0.0.1 的本机单人工具（决策 D4）
- **React/Vite 工具链**：见决策 D1
- **回测净值页**：`data/backtest.db` 尚无实数据，等回测持久化接通后加（future）
- **分钟线/实时行情**：数据库 v1 仅日线

## 3. 决策记录（代替交互澄清）

**D1 前端栈 = 原生 HTML/JS + ECharts（本地 vendored），FastAPI 托管静态文件。**
备选对比：(a) Streamlit——上手最快但重依赖、定制差、最像玩具，否；
(b) React + Vite——WSL 有 node v24 可行，但 v1 只有三个页签无组件复杂度，
引入构建链+依赖树在无人值守的过夜窗口风险不对称，否；
(c) 原生 + ECharts——零构建、单 python 进程交付、ECharts 覆盖 K 线/折线全部需求，
文件按 html/js/css 拆分保持可维护，**选 c**。ECharts 5.5.1 vendored 进仓库
（~1MB，离线可用），不依赖 CDN。

**D2 信息架构 = 单页三页签**：①数据资产 ②因子判决 ③个股查看。导航极简，
v1 不做路由库，hash 切换。

**D3 数据依赖 = `data/market.duckdb` 唯一数据源**（含新增 `factor_verdicts` 表）。
dashboard 不读散落 JSON、不调 QMT——离线可用，与数据刷新解耦。

**D4 安全边界 = 服务只绑 127.0.0.1，`/api/research/*` 不设鉴权。**
本机单人投研工具；既有 `/api/dashboard/*` 的 token 机制原样保留不动。
若未来要局域网访问，再加鉴权（记入 future）。

**D5 启动方式 = `quant dashboard [--port 8501] [--db data/market.duckdb]`**，
uvicorn 程序内起，Windows conda Python 运行（与其余 CLI 一致）。默认端口 8501
避开常见 8000 冲突。

**D6 判决入库 schema 见 §5**；`run_id = 启动时间戳(YYYYMMDD-HHMMSS)`，
参数（窗口/切分/调仓间隔/特征版本）作为 JSON 存 `params` 列。
factor-test 总是写库（与 `--no-store` 数据管道开关无关——判决是产出，必须留痕）。

**D7 README 范围**：定位/风险声明、四层架构图（文字版）、环境与快速开始
（WSL+Windows 双 Python 说明）、CLI 命令表、数据库说明、dashboard、测试、文档索引。

## 4. API 契约（`/api/research/*`，全部只读 GET）

| 端点 | 入参 | 返回（形状） |
|---|---|---|
| `/api/research/overview` | - | `{db_path, feature_version, tables: {bars: {rows, symbols, min_date, max_date}, ...}, verdict_runs: N}` |
| `/api/research/verdicts` | - | `{runs: [{run_id, created_at, params: {...}, factors: [{factor_id, factor_name, expression, ic_mean, ir, ic_positive_rate, monotonicity_score, long_short_return, score, grade, oos_ic_mean, oos_ir, oos_long_short_return, passed, reasons: [...]}]}]}`，按 created_at 倒序 |
| `/api/research/symbols` | `q`（前缀，可空）`limit=50` | `[{symbol, name}]` |
| `/api/research/bars/{symbol}` | `start, end`（默认近 1 年） | `{dates: [...], ohlc: [[open,close,low,high],...], volume: [...]}`（ECharts K 线格式） |
| `/api/research/features/{symbol}` | `names`（逗号分隔）`start, end` | `{dates: [...], series: {name: [...]}}`；`names` 校验白名单 = TECHNICAL_COLUMNS |

错误约定：库文件不存在/表空 → 200 + 空数据结构（前端渲染空态文案）；
symbol 不存在 → 200 空序列；未知特征名 → 422。

依赖注入：路由通过 FastAPI `Depends(get_research_store)` 获取
`MarketDataStore`（每请求开/关连接，DuckDB 本地连接毫秒级；
db 路径取 `GHQ_MARKET_DB` 环境变量，默认 `data/market.duckdb`）——
测试用 `dependency_overrides` 注入临时库。

## 5. `factor_verdicts` 表

```sql
CREATE TABLE IF NOT EXISTS factor_verdicts (
    run_id     VARCHAR NOT NULL,          -- YYYYMMDD-HHMMSS（CLI 启动时刻）
    created_at TIMESTAMP NOT NULL,
    factor_id  VARCHAR NOT NULL,
    factor_name VARCHAR, expression VARCHAR,
    ic_mean DOUBLE, ir DOUBLE, ic_positive_rate DOUBLE,
    monotonicity_score DOUBLE, long_short_return DOUBLE,
    score DOUBLE, grade VARCHAR,
    oos_ic_mean DOUBLE, oos_ir DOUBLE, oos_long_short_return DOUBLE,
    passed BOOLEAN,
    reasons VARCHAR,                      -- JSON array 文本
    params  VARCHAR,                      -- JSON: {start,end,split,rebalance_days,num_layers,feature_version,universe_count}
    PRIMARY KEY (run_id, factor_id)
);
```

`MarketDataStore` 新增：`insert_verdicts(run_id, created_at, params, rows)`、
`load_verdict_runs() -> list[dict]`（按 run 分组、倒序）。
CLI `factor-test` 第 8 步：写 JSON（既有逻辑不动）+ upsert 入库。

## 6. 前端结构

```
src/interfaces/api/static/
  index.html        # 三页签骨架
  app.js            # fetch + 渲染 + ECharts 初始化（无框架, ~300 行）
  style.css         # 深色投研风, CSS 变量
  vendor/echarts.min.js   # 5.5.1 vendored
```

- 挂载：`app.mount("/ui", StaticFiles(html=True))`；`GET /` → 302 `/ui/`
- 判决页着色规则（与 §7 硬门槛一致）：IC≥0.02 绿 / IR≥0.3 绿 / 单调性≥0.6 绿 /
  多空>0 绿 / OOS 多空>0 绿；PASS 行高亮，FAIL 显示 reasons 列表
- 个股页：candlestick + 量柱（grid 上下分区）；特征多选 checkbox 叠加右轴折线

## 7. 错误处理

- store 打开失败（文件锁/路径错）→ 500 + `{detail}`，前端顶栏红条提示
- 全部端点 try/finally 关连接；DuckDB 单写者锁与 factor-test 并跑时：
  dashboard 只读连接（`read_only=True`）避免锁冲突——**设计点**：
  `MarketDataStore(db_path, read_only=True)` 新增参数，研究端点用只读模式
- 空库/未刷数：overview 正常返回 0 行统计，前端显示"先运行 quant data refresh"

## 8. 测试策略

- `tests/interfaces/api/test_research_routes.py`：TestClient + 临时 DuckDB
  （dependency_overrides 注入）——overview/verdicts/symbols/bars/features
  各端点 200 + 形状断言；features 白名单 422；空库空态
- `tests/infrastructure/persistence/test_market_data_store.py` 增补：
  verdicts upsert 幂等 + 分组读取 + read_only 模式可读
- 冒烟：`quant dashboard` 启动后 `GET /health` 200（实施计划中以脚本验证）

## 9. Future（记录不做）

实盘监控页接 `/api/dashboard/*` WS（Phase 3）；回测净值页（等 backtest 持久化）；
run 间 Δ 对比视图；分钟线；局域网鉴权；前端打包工具链。

## 10. 自审结论

无占位符；范围聚焦单一实施计划可承载；与既有实盘 API 边界清晰（路径前缀隔离）；
read_only 连接解决与后台 factor-test 并跑的锁冲突，已在 §7 显式化。
