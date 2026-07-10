# 前端易用性 6σ DMAIC 迭代日志

方法：每轮 Define（CTQ+缺陷定义）→ Measure（旅程步数/回忆点基线）→ Analyze（Pareto 主摩擦）→ Improve（并行修复）→ Control（verify_all --frontend + vitest 契约 + 冒烟读图，防回退）。

**CTQ（关键质量特性）**：日常研究循环的任务完成摩擦。
**缺陷定义**：核心旅程中任何一步需要（a）回忆而非识别（b）重复输入（c）跨工具切换（d）无反馈等待（e）不可发现的能力。

**核心旅程**：J1 因子检验→读判决 · J2 提交回测→对比 · J3 查行情特征 · J4 盯任务→看结果 · J5 看实盘。

---

## R1（已完成 2026-07-10）— 认知负荷专项

Measure 基线→Improve 后：
| 缺陷 | 前 | 后 |
|---|---|---|
| "最新结果如何"导航成本 | 切页+翻列表(≥3击) | 总览发射台 1 击深链 |
| 行情标的重复输入 | 每次重敲代码 | 最近 chips 1 击 |
| 策略名回忆负担 | 裸代码名 | 中文名识别 |
| 记分牌选项可读性 | 截断 | 全文 |
| 删除误击风险(Fitts) | 紧贴过滤chips | 末位隔离+降权重 |
| 特征选择扫描负担 | 15 项平铺 | 4 组分块(Miller) |
| 净值图缩放可发现性 | inside 隐形 | slider 可见 |

Control：482 vitest 绿 · 冒烟 PASS · 提交 d14d337。

---

## R2（本轮）— 跨工具切换与联动专项

### Measure（代码走查基线）
| # | 旅程缺陷 | 当前成本 | 目标 |
|---|---|---|---|
| 1 | J2 改策略参数需离开 UI 编辑 resources yaml（跨工具+参数名回忆；参数只在悬停 title 可见） | 跨工具 ≥3 步 | 页内直改，2 击 |
| 2 | J3 K线与特征图缩放不联动、特征图无 slider（对齐"那段行情的特征"要目测） | 不可完成 | 1 拖联动 |
| 3 | J1 判决表单起止留空语义不透明（=全历史，但界面不说） | 回忆/查文档 | 就地提示 0 回忆 |
| 4 | J4 任务完成后找结果要切页翻 | 2 击+心智切换 | 行内"查看结果" 1 击 |
| 5 | 全局切页仅鼠标 | 移动+瞄准 | 数字键 1-6 直达 |

### Analyze（Pareto）
#1 是唯一的跨工具缺陷（最重）；后端 `BacktestJobRequest.params: dict[str,dict]` 已支持按策略覆盖（`src/interfaces/api/job_commands.py:48`），`/api/meta/strategies` 已返回 `default_params` —— 纯前端可修。#2-#5 均为单页小改。

### Improve
四路并行（文件所有权互斥）：A 回测参数面板 · B 行情双图联动 · C 判决日期提示+任务查看结果 · D 全局快捷键。

### Improve 结果（后测 2026-07-10）
| # | 前 | 后 | 证据 |
|---|---|---|---|
| 1 | 改参数跨工具 ≥3 步 | 勾选即现参数面板，页内直改（只发≠默认的覆盖，还原默认一键）；`dual_ma` 默认参数为空故无面板属正确行为 | param-overrides 18 例单测；`/api/meta/strategies` 实测 |
| 2 | 双图不联动、特征图无 slider | 特征图 slider 落地（读图证实）+ 页级 connect（日期域一致性有后端证据），四分支 `[inside,slider]` 统一保证联动路由 | 9 例契约测试 |
| 3 | 留空语义不透明 | 就地提示 +「留空省键」载荷修正——**顺带抓出真缺陷：原实现空串提交必 422**（撞后端日期 pattern），修正后语义才真实成立 | FactorTestForm 3 新例 |
| 4 | 完成找结果 2 击+切换 | 任务行「查看结果」1 击深链 | result-route 全矩阵单测 |
| 5 | 切页仅鼠标 | 数字键 1-6（输入框/修饰键/输入法三守卫），nav title 提示 | usePageHotkeys 16 例 |

### Control 记录
`verify_all.py --frontend` **六项全绿**（ruff/pytest/frontend-fresh/data-quality/vitest 529/typecheck）；冒烟 PASS（console 0 错）；读图核验参数区条件与 slider。数据质量门禁（NULL 固化哨兵）持续绿——特征缺口修复受控。
备注：pytest 在链中出现过一次瞬时红（复跑即绿，疑与 dashboard 读锁竞争）；WSL interop binfmt 本会话丢失，验收经 `/init` 蹦床走 Windows 侧（`wsl --shutdown` 后自愈，与代码无关）。

---

## R3（已完成 2026-07-11）— 重复操作与遗留收尾专项

| 改进 | 落地 | 证据 |
|---|---|---|
| 行情组合记忆 | 「最近」chips 记整组（`000021.SZ +2` 形态），顺序不敏感去重、旧 key 事务式迁移、写失败保数据 | recent-symbols 27 例 |
| 判决因子快捷组 | P 标签真按钮整组勾/清；「上轮同款」=当前选中轮因子集（跳过下架/禁用并提示，全不可用非破坏） | factor-selection 13 + 表单 5 例 |
| 表格列排序 | DataTable `sortable` 列（降→升→无序循环、aria-sort、null 沉底、不变异 props、排序态跨轮询保持）；执行 6 列/审计 2 列启用 | DataTable +11 例（TDD 红→绿） |
| `?overlay=` 深链 | 叠加对比入 URL；"缺席=清空/非法=忽略不回写"两种 null 语义拆读写两函数 | run-selection +17 例 |
| 参数已改高亮 | 左缘 accent 竖线（占位零跳版）+「默认 x」变可点单键还原；高亮与提交 diff 共用 `isOverridden` 单一事实源 | param-overrides +7 例 |

Control：`verify_all --frontend` 六项全绿（vitest **601**/pytest/ruff/数据门禁/fresh/typecheck）· 冒烟 PASS（console 0 错）。

---

## R4（已完成 2026-07-11）— Pareto 尾部收割

| 改进 | 落地 | 证据 |
|---|---|---|
| 判决视角记忆 | filter+sort 入 sessionStorage（字段级容错、setup 即恢复零闪跳、FILTER_KEYS 单一事实源） | view-state 18+4 例 |
| 回测最优列高亮 | ≥2 策略时每列最优加 accent 底线+加粗（方向表：收益类 max/回撤换手 min/交易数不评），图例条件追加 | metric-cell +8 例 |
| 实盘徽章截断标识 | 打满 limit 显 `500+`（badgeCount 纯函数；limit 收敛单源常量）；SubNav badge 放宽 number\|string（集成时收口去 cast） | logic +3 例 |
| 任务日志过滤 | 标题行过滤框（大小写不敏感、N/M 计数、过滤态暂停滚底、未过滤零开销直通） | ui +4 例 + 接线 5 例 |
| `?` 帮助浮层 | Shift+/ 唤起快捷键清单（NAV 动态生成；守卫 options 只松 shift 一档） | hotkeys +11 例 |

集成收口：Verdicts.spec beforeEach 补 sessionStorage.clear（防跨例泄漏）；SubNav badge 类型放宽。
Control：`verify_all --frontend` 六项全绿（vitest **659**）· 冒烟 PASS。

---

## 受控状态声明（2026-07-11）

四轮 DMAIC 后，审计发现的 Pareto 高价值摩擦已收割完毕（R1 认知负荷 → R2 跨工具/联动 → R3 重复操作 → R4 尾部）。过程能力防线已建：
- **门禁**：`verify_all.py --frontend`（ruff/pytest/fresh/数据质量/vitest/typecheck）
- **契约**：659 vitest 含对比度守卫、三源同值、深链幂等、排序不变异等行为锁
- **哨兵**：数据质量门禁（NULL 固化）、check_frontend_fresh 漂移防线

**后续模式**：新摩擦随用随记入本日志 R5 候选区，攒足一批或出现高价值项再开一轮 DMAIC；不为迭代而迭代。

## R5 候选区（随用随记）
（空）
