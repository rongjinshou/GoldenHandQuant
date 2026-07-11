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

## R5（已完成 2026-07-11）— 新测量仪器专项

Define：前四轮改进仅经"单测+静态暗色截图"验证；本轮用**新仪器**测此前不可见的缺陷面。
仪器（常设入库 `scripts/ui_deep_probe.py`，支持 `--only 节` 重跑）：① 真交互驱动 ② 亮色全页扫描 ③ axe-core 双主题 ④ 重负载计时。

### Measure 结果
- **功能层零缺陷**：七类真交互（快捷键/参数面板/深链前进后退/组合chips/双图slider联动/视角记忆/排序/日志过滤）全 PASS，全程 0 console error；R1-R4 改进端到端全部成立。
- **性能非问题**：7397 笔交易 run 渲染 0.04s；bundle JS 1.37MiB。
- **axe 初扫 serious 133 节点**（color-contrast 101 / nested-interactive 26 / link-in-text 6）。

### Analyze → Improve（三层递进，含两个隐藏真缺陷）
1. 常规修复 7 项+同病灶 3 处：fchip 选中态 2.96→5.90、暗色 `--accent-strong: #e08a6d`（激活页签 4.39→5.22，全站暗色链接受益）、回测左轨小字、light 三处、特征区 GlossaryTip 移出 checkbox（嵌套交互清零）、空态链接下划线、fchip aria-pressed。
2. **测量系统教训（Gage R&R）**：axe 曾把入场动画中途的 α 混合色当前景（报 #000000）——仪器补 `reduced_motion="reduce"` 仿真。
3. **真缺陷两枚（仪器扫出、人眼从未发现）**：
   - `.fchip.disabled` 只有 class 无 `disabled` 属性 → 读屏当可用按钮播报（补属性后 axe 豁免+语义正确）；
   - **`<button>` 化容器不继承 color**：FactorCard 换 button 后中性指标值以 `#000000` 画在暗底上（1.26:1 近乎隐形，像素采样实证）——补 `color: inherit`，并全仓扫出 Jobs id-btn / PipelineMap 节点同病灶一并修；
   - FactorCard/Modal 徽章 18% 混合底文字不足 → 新增 `--c-{pass,warn,fail}-strong` 令牌（各值实算 4.71-5.9）。

### Control
**axe 双主题×六页归零（serious 0）**；`verify_all --frontend` 六项全绿；探针为常设仪器可随时复扫。
教训入册：① button 化必须带 `color: inherit`（已修三处+扫描口径留档）② UI 测量必须 reduced-motion ③ "截图看着正常"不能替代计算值/像素采样。

### R5 遗留（低优先）
- light 主题若干 hover 瞬时态 accent 小字 <4.5（axe 静态扫不到）——下轮批量套 accent-strong。
- GlossaryTip 触发器 aria-label 用 term 键而非中文。

---

## R6（已完成 2026-07-11）— 瞬时态与降级态专项

Define：静态可见缺陷已归零（R5）；剩余暗区=**时间维度上的状态**。仪器扩展 E 网络降级仿真（route abort，零服务端副作用）/ F 键盘全旅程 / G hover 对比度枚举 / pytest 抖动率。

### Measure（12 findings + 1 工具链）
- **R6-01（高）断连零指示坐实**：三张截图 MD5 逐字节相同——断连 13s 页面与实时无法区分（批二 isStale 从未接线的后果）。
- 键盘旅程六页无焦点陷阱；3 处 `outline:none` 无环输入框；帮助浮层焦点困住但无可见落点。
- hover 枚举 7/7 不达标（light 悬停掉到 accent 2.44-2.96——"悬停即降级"）。
- **新真缺陷**：总览刷新留空日期 422——后端 `DataRefreshJobRequest` 两日期必填无默认，"留空=自动补缺口"只在 CLI 存在，**Web 通道从未走通**；帮助文案一直在撒谎。
- pytest 抖动率：受控 5/5 全绿，此前 1 次红为不可复现瞬态（记录监控，不追凶）。

### Improve（全部落地，680 vitest）
- **StaleIndicator**：实盘页头常驻「数据更新于 HH:mm:ss」，断连转「⚠ 连接中断，显示 X 前数据，重试中…」（warn-strong 色 + aria-live），恢复自动回正——探针 E2.1 实测指示词出现 ✓。
- 刷新表单前端必填校验（buildRefreshRequest 纯函数，载荷恰两非空键）+ 修正撒谎文案。
- 错误横幅：技术串移出正文（存 title 悬停）+ Overview/Verdicts/FactorTestForm 接 dismissible。
- 焦点环 3 处（chip-input×2 内嵌环 / log-filter 走全局环）；HotkeyHelp 开 closable 给焦点可见落点。
- hover 7 处 → accent-strong（实算 5.57/5.14/4.69/4.59）；LvBadge pass/warn/fail → strong 三件套（C 节复扫揪出的最后漏网）。

### Control
探针 **E 8/8 PASS**（断连指示/恢复自愈/前端拦截零副作用）· **G 归零** · **C axe 双主题归零**；`verify_all --frontend` 六项全绿。E4 断言随新契约更新（空日期改由前端拦截，422 路径退役）。

### R6 遗留 → R7 全部清零

---

## R7（已完成 2026-07-12）— 遗留清扫

| 项 | 落地 |
|---|---|
| 同型空日期 422 收口 | BacktestForm（form-dates.ts 必填守卫）+ ML 训练/评估（ml-forms.ts 载荷纯函数化，"通过校验的载荷永不携带空串"）；**顺带堵两处同型**：symbols 清空→省键走后端默认、n_trials 清空→省键（旧实现 `Number(null)=0` 撞 `ge=1` 必 422） |
| Jobs 横幅+陈旧指示 | dismissible+technical 透传（listError 屏蔽标志跨失败 tick 保持、成功 tick 复位）；StaleIndicator 复用到任务列表标题旁 |
| GlossaryTip 读屏名 | 删 aria-label(term 键)，可及名回落中文插槽内容（满足 Label-in-Name；词条首句方案会覆盖可见名，弃） |

Control：`verify_all --frontend` 全绿 · axe 双主题归零 · **715 vitest**。

### 受控稳态（当前）
七轮 DMAIC 完成。遗留区清零。防线：verify_all 六项门禁 + 715 契约测试 + 数据哨兵 + 常设探针（A-G 七节）。
**监控模式**：新摩擦随用随记于下方候选区，攒批或高价值即开新轮。

## R8 候选区（随用随记）
- （低）StaleIndicator 在 Jobs 页 testid 仍为 live-conn-* 前缀（可参数化）
- （低）GlossaryTip popover 正文无 aria-describedby 关联（NPopover teleport 限制）
- （低）n_trials 手输 0 依赖 naive min=1 钳制+后端兜底，前端未重复数值域校验
