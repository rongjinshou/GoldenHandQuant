# 交互式投研驾驶舱设计 — 从只读 demo 到可操作 GUI

日期: 2026-06-12
状态: 已定稿（全权委托模式，决策理由见各 DD）
前置: docs/feat/0611-closed-loop/2026-06-11-closed-loop-design.md（只读驾驶舱 v1）

## 1. 问题

现有 `/ui/` 驾驶舱是纯只读展示：5 个页签的数据全部依赖先在终端跑 CLI（回测/因子检验/数据刷新），唯一的"触发"端点 `POST /api/backtest/run` 是 501 占位。用户要的是**可交互 GUI**：在浏览器里直接触发后端已具备的能力、看进度、看结果。

后端能力盘点结论（2026-06-12 五子系统并行盘点）：

| 能力 | 入口 | 结果留痕 | QMT 依赖 |
|---|---|---|---|
| 回测/多策略对比 | `compare_strategies.py`（支持 --strategies/--symbols/--params/起止日） | backtest_runs 自动入库 | 否（DuckDB fetcher） |
| 因子检验漏斗 | `quant factor-test`（--factors/--split-date/--objective/...） | factor_verdicts 自动入库 | 数据已履约时否 |
| 数据刷新 | `quant data refresh` | bars/fundamentals/features | **是**（生产口径 QMT） |
| ML 训练/评估 | `quant ml-train` / `ml-evaluate` | models/ 目录 | 否 |
| 实盘留痕 | trading.db 5 表 | — | 否（只读） |

关键事实：**CLI 命令本身就会把结果落库，Web 已有读取这些库的端点**。所以交互化的最小完备闭环 = 「Web 触发 CLI 子进程 + 任务状态/日志反馈 + 完成后前端刷新既有列表」。

## 2. 方案对比与选定

- **A. 子进程复用 CLI（选定）** — Web 进程内 JobManager 以白名单 argv 拉起 `python -m src.interfaces.cli.*` 子进程。复用已实战的装配与入库逻辑；崩溃隔离（numpy/duckdb 段错误不连累 Web）；DuckDB 写锁天然隔离在子进程；stdout 即任务日志；服务器跑在 Windows conda python 时 QMT 任务可用。
- B. 进程内线程直调 application 服务 — 进度回调虽顺手，但 BacktestProgress/factor-test 的 stdout 打印需大改、重计算占住 Web 进程、QMT 配置下 `build_data_wiring` eager import xtquant 在 WSL 直接炸。
- C. Celery/RQ — 单机单用户引入 broker，过度设计（YAGNI）。

### 设计决策

- **DD-1 任务执行模型**：JobManager 单 worker 线程串行消费队列（对齐 DuckDB 单写者约束——所有任务都可能写 market.duckdb）。子进程 `sys.executable -m ...`，argv 白名单拼装、无 shell、`PYTHONUNBUFFERED=1`、cwd=项目根。
- **DD-2 任务状态不持久化**：jobs 注册表在内存（重启即空），完整日志落 `data/job_logs/{job_id}.log`，结果以 DuckDB/models 留痕为准。崩溃恢复链路 YAGNI。
- **DD-3 前端延续无构建链**：原生 JS + ECharts（沿用 0611 D1），单文件 app.js 拆为 ES modules（`static/js/`）。不引入框架。
- **DD-4 交易安全红线不动摇**：Web 永不暴露——下单/撤单、修改 trading.yaml、触发 auto-trade/live 链路、写 trading.db。实盘页只做只读扩展。研究侧触发（回测/因子/刷新/ML）写的只是研究库，明确豁免 0611 DD-6"Web 全只读"（该决策针对交易侧；本次为用户明确要求的范围变更）。
- **DD-5 鉴权延续 0611 D4**：uvicorn 绑 127.0.0.1，无 token。顺手清理死代码：`routes/dashboard.py`、`routes/account_routes.py`（Bearer token + 未接线服务 + mock 网关三宗罪）连同 `application/dashboard_app.py`、WS 骨架及其测试一并删除，app.py 去挂载。
- **DD-6 QMT 任务的环境约定**：data refresh（及有缺口的 factor-test）要求服务进程 = Windows conda python 且 QMT 客户端在线；WSL 下任务失败时日志可见 ImportError。前端表单就地标注"需 QMT 客户端在线"。
- **DD-7 回测与对比统一入口**：`compare_strategies` 模块支持 1..N 策略 + --symbols + --params，回测=单策略对比。需验证单策略路径可用（不行则最小补丁放开）；补 `--initial-capital` 可选覆盖（CLI 同步受益）。
- **DD-8 multi_factor 权重字典不做表单编辑**：--params 仅支持标量覆盖；权重走配置文件选择（backtest.yaml / backtest_multi_factor.yaml 下拉）。

## 3. 架构

```
interfaces/api/
  routes/jobs.py          # POST /api/jobs/{type} + GET list/detail + cancel
  routes/meta.py          # GET /api/meta/strategies, /api/meta/factors
  routes/live.py          # 扩展: audit/budget/cycle钻取/mode过滤/config/tickets
  job_commands.py         # 任务类型 → argv 构建器（白名单, 纯函数, 可测）
  static/                 # index.html + js/ 模块 + style.css
infrastructure/jobs/
  job_manager.py          # Job/JobStatus/JobManager（队列+worker+子进程+日志环）
```

依赖方向不变：routes → infrastructure/jobs；job_commands 是 interfaces 层纯函数（编码 CLI 知识）。domain/application 零改动（除 DD-5 删除）。

### 3.1 JobManager（infrastructure/jobs/job_manager.py）

```python
@dataclass(slots=True, kw_only=True)
class Job:
    job_id: str            # uuid4 hex 前 12 位
    job_type: str          # backtest|factor_test|data_refresh|ml_train|ml_evaluate
    params: dict           # 原始请求参数（展示用）
    argv: list[str]
    status: JobStatus      # QUEUED→RUNNING→SUCCEEDED|FAILED|CANCELED
    created_at/started_at/finished_at: datetime|None
    return_code: int|None
    log_tail: deque[str]   # maxlen=400 行环形缓冲
    log_path: str
```

- `submit(job_type, params, argv) -> Job`：入队；单 worker 线程顺序执行。
- 执行：`subprocess.Popen(argv, stdout=PIPE, stderr=STDOUT, env={**os.environ, PYTHONUNBUFFERED:'1'}, cwd=root)`，逐行读 → 环形缓冲 + 日志文件。
- `cancel(job_id)`：QUEUED→直接标 CANCELED；RUNNING→`terminate()`（5s 后 `kill()`）。
- 线程安全：注册表 dict + Lock；worker 是 daemon 线程，FastAPI 进程退出即终止。
- 状态机用 `match/case`。

### 3.2 任务 API（routes/jobs.py + job_commands.py）

| 端点 | 说明 |
|---|---|
| `POST /api/jobs/backtest` | {strategies:[str], start_date, end_date, symbols?:[str], params?:{strat:{k:v}}, config?:str, initial_capital?:float} → compare_strategies argv |
| `POST /api/jobs/factor-test` | {factors:str, start_date, end_date, split_date?, objective, num_layers, rebalance_days, cost_rate} → quant factor-test argv |
| `POST /api/jobs/data-refresh` | {start_date, end_date} → quant data refresh argv |
| `POST /api/jobs/ml-train` | {start_date, end_date, symbols?, model_name?, label_horizon?, n_trials?} → quant ml-train argv |
| `POST /api/jobs/ml-evaluate` | {model_name, eval_start, eval_end} → quant ml-evaluate argv |
| `GET /api/jobs?limit=50` | 列表（倒序），含每个 job 的状态/耗时/参数摘要 |
| `GET /api/jobs/{id}?tail=200` | 详情 + 日志尾部 |
| `POST /api/jobs/{id}/cancel` | 取消 |

全部 202/200 JSON；Pydantic 请求模型负责校验（日期格式、objective 枚举、策略名 ∈ registry、因子串可被 resolve_factors 解析——解析失败 422）。config 参数只接受白名单 {resources/backtest.yaml, resources/backtest_multi_factor.yaml}，杜绝路径注入。

JobManager 经 `Depends(get_job_manager)` 注入（模块级单例 + 测试 dependency_overrides）。

### 3.3 元数据 API（routes/meta.py）

- `GET /api/meta/strategies`：registry → [{name, strategy_type, description, default_params}]，前端据此生成策略选择 + 参数表单。
- `GET /api/meta/factors`：factor_catalog → {groups:{P0:[...],P1:[...],P2:[...]}, factors:[{factor_id, name, category, expression, direction_note, evidence_strength, field_ready, priority}]}。F10 field_ready=false 前端置灰。

### 3.4 实盘只读扩展（routes/live.py，延续 \_connect_ro 模式）

- `GET /api/live/audit?limit=&action=`：audit_logs 倒序 + action 过滤。
- `GET /api/live/budget`：今日 `SUM(notional)`（口径镜像 TradingStore.today_submitted_notional，跨 mode 不拆——dry/live 同一真实账户）+ trading.yaml auto_trade 的 per_order/daily cap → 余额。
- `GET /api/live/cycles/{cycle_id}/executions`：循环钻取。
- `GET /api/live/positions?mode=` / `equity?mode=`：服务端 mode 过滤（缺省保持现行为）。
- `GET /api/live/config`：trading.yaml auto_trade 段只读摘要（enabled/mode/strategy/symbols/execution_times/各 cap）+ 守护活性推断（今日预期槽位 vs trading_cycles 实际覆盖）。
- `GET /api/live/tickets`：data/trade_logs/*.json 列表+内容。
- trading.yaml 路径经 `Depends(get_trading_config_path)`（env `GHQ_TRADING_CONFIG`）注入，只读 safe_load。

### 3.5 前端（static/）

模块拆分：`js/api.js`（fetch 封装+错误横幅）、`js/charts.js`（ECharts 公共配置）、`js/jobs.js`（任务面板+轮询）、`js/pages/{overview,verdicts,explorer,backtests,live}.js`、`js/main.js`（路由/装配）。`<script type="module">`，风格 token 全沿用现有 style.css。

交互增量（按页签）：

1. **回测页**：顶部「新建回测」折叠表单——策略多选（meta 驱动，截面策略标注）、起止日、标的输入（chips + /symbols 联想 + 留空=config 默认）、配置文件下拉、标量参数覆盖（default_params 预填）、初始资金。提交 → 任务卡片内联展示（状态+日志尾部实时滚动）→ 完成后自动刷新轮次列表并选中最新 run。多策略时既有净值对比图直接生效。
2. **因子判决页**：「新建因子检验」表单——因子多选（P0/P1/P2 分组勾选，F10 置灰）、起止/split 日期、objective 切换、高级参数（层数/调仓间隔/成本率）；多因子无 split-date 时表单内联提示多重检验风险（对齐 CLI 警告）。提交 → 任务卡片 → 完成刷新 run 下拉。run 行点击展开 reasons 明细（现有 reasons-row 交互保留）。
3. **数据资产页**：覆盖度卡片保留；新增「刷新数据」表单（起止日 + "需 QMT 客户端在线"标注）→ 任务卡片。
4. **实盘页**：新增——预算卡（今日提交/上限/余额）、守护状态徽章（槽位覆盖推断）、配置只读卡、审计日志表（action 筛选）、循环行点击展开该循环执行明细、mode 筛选器（持仓/权益）、ticket 查看（折叠 JSON）。
5. **任务页（新页签）**：全部任务列表（类型/参数摘要/状态/耗时）、点击看日志（运行中 2s 轮询 tail）、取消按钮、ML 训练/评估表单（高级区）。
6. **全局**：header 任务指示灯（有 RUNNING/QUEUED 时呼吸点 + 数量）；任务运行中若研究端点 503（DuckDB 写锁），错误横幅替换为"任务运行中，数据查询暂不可用"的温和提示。

轮询节奏：任务活跃时 jobs 2s；实盘页 5s（现状）；其余按需。

## 4. 错误处理

- 子进程非零退出 → FAILED + 日志尾部直接可见（含 ImportError/QMT 离线/参数错误）。
- DuckDB 写锁冲突：研究读端点 503（现有行为），前端按任务状态柔化提示；写写冲突由单 worker 串行从根上避免（外部 CLI 手动并发跑仍可能撞锁——日志可见，不做额外协调）。
- trading.db / market.duckdb / trade_logs 缺失 → 显式空态（沿用现状约定）。
- 取消竞态：cancel 已结束任务 → 409；未知 job_id → 404。

## 5. 测试策略（pytest + AAA，目录镜像）

- `tests/infrastructure/jobs/test_job_manager.py`：用 `python -c` 微脚本测全生命周期——成功/失败码/日志捕获（环形缓冲+文件）/串行顺序/取消（排队中、运行中）/状态时间戳。
- `tests/interfaces/api/test_jobs_routes.py`：dependency_overrides 注入 echo 型 argv 的 JobManager；五种 POST 的 202 与 422 校验、列表/详情/tail/cancel/404/409；argv 构建器纯函数逐类型断言（含 config 白名单拒绝）。
- `tests/interfaces/api/test_meta_routes.py`：strategies/factors 形状与 F10 field_ready。
- `tests/interfaces/api/test_live_routes.py` 扩展：tmp sqlite 灌 audit_logs/execution_records → audit 过滤、budget 口径（含 REJECTED/FAILED 不计入）、循环钻取、mode 过滤、config/tickets 端点（tmp yaml/json）。
- CLI 增量：`--initial-capital` 覆盖逻辑单测（compare_strategies 参数解析层）。
- 前端无自动化测试（无构建链约定）；以 API 契约测试 + 手动冒烟（quant dashboard）兜底。

## 6. 非目标

- 不做用户/鉴权体系（127.0.0.1 单用户）。
- 不做任务持久化/断点续跑。
- 不做 WebSocket 推送（轮询够用；0611 WS 骨架随死代码删除，需要时可从 git 史找回）。
- 不做 multi_factor 权重的表单编辑（配置文件承载）。
- 不暴露任何交易写操作（DD-4 红线）。
- explorer 页 K 线叠加回测买卖点（trades 未入库，另立项）。

## 7. 实施记录（2026-06-12）

按 plan 14 任务全部完成并直委 main（提交范围 `13c31ff..`，每任务实现+双阶段评审+修复闭环）：

- 后端：`infrastructure/jobs/JobManager`（评审加固：取消 CAS/worker 异常护栏/PYTHONUTF8/强杀计时器）、`job_commands`（注入面收口：model_name 正则/params 字符集/symbols 逐项/日期语义）、`/api/jobs` 五任务型、`/api/meta`、live 路由 8 个只读扩展端点、compare_strategies `--initial-capital` + `--config` 失效 bug 修复、三族死代码清理（-1265 行）。
- 前端：app.js 拆 9 个 ES modules（搬运保真审查 100%）、五页签交互表单 + 通用任务卡 + 任务中心页（评审修复：钻取抗轮询/错误兜底统一/任务卡 404 终止/pre 转义）。
- 配置：`backtest.yaml` history_fetcher 切 `DuckDBHistoryDataFetcher`（本地快路径, 缺数回退 QMT）。
- 验证：E2E 经 Web API 真跑 dual_ma 回测成功入库（run_id=20260612-093431）并由 /api/research/backtests 读回；全量 pytest 绿、ruff 干净。
- 遗留债（低优先）：任务页 logTimer 切页签不清（终态自清）；live 子进程树 POSIX 强杀未做进程组（生产为 Windows TerminateProcess，已缓解）；uvicorn 单 worker 假设已注释；回测表单标的输入为逗号文本框（设计写的 chips+联想，可复用 explorer 的 /symbols datalist 补齐）；ml 策略 model_dir 参数本不该出现在表单（含 `/` 修改会被 422 护栏拦下）；503 柔化文案首屏 5s 内有竞态窗口；dual_ma registry default_params 为空 → 回测表单无均线窗口可调参（registry 数据面缺口, 非前端 bug）。

### 7.1 视觉自调试闭环（2026-06-12 追加）

- 新增 `scripts/ui_smoke.py`：Playwright（装于 Windows conda env, 渲染与用户浏览器同构）无头打开驾驶舱, 6 页签截图至 `data/ui_screenshots/` + 收集 console 错误/页面异常/失败请求, 产出机读 `smoke_report.json`；`--deep` 附加真提交小回测并等任务卡终态。WSL mirrored 网络使 Claude 可在 WSL 内直连 Windows 服务并读图自查。
- 首轮读图自查战果：① live 页无权益快照时 ECharts 渲染 ~600px 空黑框 → 改为隐藏图容器（恢复显示时 resizeCharts 防 0 尺寸）；② overview 股票池卡"无数据"歧义文案 → "—"。复跑冒烟 PASS（0 console 错误, deep 回测 succeeded, run_id=20260612-222634）, 修复均经截图二次确认。

## 8. v2 迭代：标的 chips + 时序/截面编排 + 术语 tips（2026-06-12）

用户三诉求：① 回测标的输入升级 chips+联想；② 回测结果看不到测的是什么标的，时序/截面/混合策略的编排需要在交互中讲清楚；③ 全界面专业术语零解释，无法指导学习。

- **DD-9 标的 chips**：纯前端组件（payload 仍是 `symbols: list[str]`，后端零改动）。联想复用 `/api/research/symbols?q=`（代码/名称双通道）；完整代码（点选联想/粘贴/回车）即时成 chip；粘贴逗号串自动拆分；Backspace 空输入退删末 chip；正则 `\d{6}\.(SH|SZ|BJ)` 客户端校验，非法 token 留在输入框并报错提示。
- **DD-10 时序/截面编排**（与 `compare_strategies` 真实语义对齐：`backtest_symbols = stock_universe if stock_universe else symbols`，含任一截面策略时用户标的不参与回测）：勾选含截面策略 → 标的 chips 整体禁用 + placeholder 说明"回测对象=全市场抽样池"；结果区 run meta 显示每策略 [时序]/[截面] 类型徽章 + 时序 run 的标的只读 chips（>8 只折叠 +N, title 全量）/ 截面 run 的"全市场抽样"说明。任务卡/任务列表 paramsSummary 同步加 symbols 摘要。
- **DD-11 术语 tips**：单一来源 `js/glossary.js`（GLOSSARY 字典 + `applyGlossary(root)` 装饰器）；HTML/模板只标 `data-gloss="key"`，装饰器注入 `data-tip` 文案 + CSS-only 悬停气泡（`[data-tip]:hover::after`, 无 JS 定位库）；动态渲染容器各自 applyGlossary。文案教学口径：一句定义 + 一句好坏方向/落地提醒。每页签顶部加一行 `.page-guide` 用途导览。verdicts 表头 objective 切换只换 textContent，data-tip 落在 th 上不受影响（文案覆盖双口径）。

### 8.1 实施记录（2026-06-12 夜）

- 实现即闭环验证：每步改动经 `scripts/ui_interact_shot.py`（新增的交互截图 DSL 小工具: tab/fill/type/press/hover/shot）真浏览器截图读图确认；全页冒烟 + deep（chips 路径真提交回测 succeeded）PASS。
- **对抗评审战果（3 视角 Workflow: 量化内容/JS 边界/视觉, 14 条发现全数修复）**：
  - 量化内容 6 条：`ir` 两口径混淆（多空 ICIR 闸 0.3 vs 长多年化超额 IR 闸 0.5, 量纲不同）、`monotonicity` 漏说已定向（完全递减≠1.0）、`layers` 第几层最优写反（Top=因子值最高的最后一层）、`cost_rate` 单边 vs 往返写错（引擎按换手×往返合计扣, 教成单边会让成本少算一半直接影响 PASS/FAIL）、`ic` 补带符号闸门口径、`ls_is` 基准是覆盖池等权非全市场。**全部对照 layer_backtest.py/verdict.py 实测口径改正。**
  - JS 3 条 important：Enter 取过期联想候选（加 `list.dataset.q` 配对校验）、分支 A/B 不清防抖 timer + 在途 fetch 回填已清空的 datalist（clearTimeout + 响应时比对 input 当前值丢弃过期）、≥2 非法 token 时逐键重拆光标跳尾（拆分收窄为 粘贴/尾分隔符 触发）；3 条 minor：`p.source` 漏 esc、策略复选框变更重置已改参数（暂存回填）、内联报错就近显示（#bt-symbols-err）。
  - 视觉 3 条：th 下划线被表格 border 规则吃掉（text-decoration 实现低对比下划线）、禁用 chips 不可辨识（压暗+虚线边+not-allowed）、错误横幅离表单太远（内联 sym-err）。
- **顺手修复数据层真缺口**：标的名称联想此前不可用——instruments.name 历史只存代码。`search_instruments` 改为 LEFT JOIN fundamental_snapshots `arg_max(name, date)` 回填中文名（5207 只全覆盖, TDD 3 用例），个股页与回测 chips 的"输名称→回车/点选"全链路打通（实测 平安→000001.SZ 平安银行）。
- 验证：全量 pytest 0 失败、ruff 干净、冒烟 PASS、修复均经截图二次确认。遗留观察：拖拽文本入框（insertFromDrop）不触发即时拆分, 回车/提交时兜底拆分, 不影响正确性。

### 8.2 Tippy 气泡 + 终端美学层（2026-06-12 深夜, frontend-design skill）

用户反馈：悬停不出气泡（根因=浏览器强缓存旧 JS/CSS）+ 排版丑 + 要求用专业前端 skill。

- **缓存根治**：app.py 中间件给 `/ui` 静态资源加 `Cache-Control: no-cache`（本机 ETag 协商 304 零成本, 无构建链改盘即生效）。
- **气泡专业化**：vendor Popper 2.11.8 + Tippy 6.3.7（与 echarts 同方式落盘），`applyGlossary` 改挂 Tippy——自动定位/翻转、appendTo body 免裁切、术语标题+正文双段排版（ghq 暗色主题）、onShow 动态取最新表头文案；删除整套 CSS-only `::after` 气泡。
- **终端美学层（安装并应用官方 frontend-design skill, 定位 industrial terminal）**：vendor Rajdhani（HUD 显示字: 品牌/气泡标题）+ JetBrains Mono（全部数字/代码/表格/页脚, 等宽对齐成列）共 5 个 woff2 ~90KB 本地加载；body 顶部冷光晕氛围；卡片渐变深度+发丝高光+悬停微抬；表格改圆角容器+内部发丝格线+大写字距表头+行悬停；section-title 延伸线、page-guide 渐变条、按钮渐变光、输入聚焦环、页签切换浮现动效。纯覆盖式追加层（style.css v3 段），可整段回滚。
- 验证：冒烟 PASS（0 console 错误）、六页签+气泡+局部裁切读图逐一确认。skill 已装入 `~/.claude/skills/frontend-design` 供后续会话复用。
