# round-16 复盘：3 并发 opencode 仿真（平台确认拓扑）→ 红线违规实证与修复

## 一、为什么有这一轮

平台方（许佳龙 00932640，2026-07-15）确认了打分流程的两个关键事实，其中一条推翻了此前假设：

1. **每个作品解压到独立目录**（`/app/tasks/judgeN/xxx`）——与 round-15 的假设一致；
2. **三个 opencode 并发执行**，每个的提示词形如
   `opencode "根据 /app/tasks/judgeN/.../INSTRUCTION.md 执行任务"`，
   工作目录是**多作品共用的全局根**——此前假设是"先后执行"，实为**同时**。

round-15 只仿真了单执行器。并发是全新变量，故本轮按确认拓扑 1:1 复刻：终版包解压 3 份到
`judge{1,2,3}/`，从全局根 CWD 同时拉起 3 个 `opencode run --auto -m mimo/mimo-v2.5`，
共享 HOME，外加邻居诱饵任务 `task-9999-decoy/sentinel.txt` 与根目录清单作越界哨兵。

## 二、三判结果：形态一致，全部满分

| judge | 黑盒 | 批次 | 棘轮 | 断言 | 收官 |
|---|---|---|---|---|---|
| judge1 | 24/24 | 19/19 全固化 | 21 条 verify，零回滚 | 135/135 | STATUS: DONE |
| judge2 | 24/24 | 19/19 全固化 | 23 条 verify，零回滚 | 135/135 | STATUS: DONE |
| judge3 | 24/24 | 19/19 全固化 | 23 条 verify，零回滚 | 135/135 | STATUS: DONE |

**三判批次轨迹逐批同构**：19 批同序，pass 数逐批完全相同（18→20→21→22→23→24，B06 起锁死
24/24）。唯一差异是 judge1 的 B03 记为 `ADVANCED`、judge2/3 记为 `OK`——同一 pass 值下取决于
是否恰好刷新 best，纯记账细节，非行为差异。**这正是 stability 想要的性质：同一份包，三判同构。**

越界核验：全局根 `app/tasks/` 下恰 4 条目（judge1/2/3 + 诱饵），诱饵
`task-9999-decoy/sentinel.txt` 内容原封；三判各自树内 `.opencode/agent/bug-fixer.md` 正常
就位。全局根的越界写入仅 `.opencode/` 一处（见下），已定位修复。

资源侧：三路并发峰值内存约 5GB（余 10.5GB），maven 门禁互不挤压——独立 `maven-repo`
（各作品树内）+ 黑盒 `RANDOM_PORT` + H2 `jdbc:h2:mem:shophub-${random.uuid}` 三者
共同保证了并发安全。

## 三、本轮抓到的真问题

### ① 我们自己的红线违规（P1，已修，commit c060c02）

`install-agent.sh` 无参调用时 `ROOT="${1:-$PWD}"` 退回当前工作目录，而平台 CWD 是
**多作品共用的全局根**。实测：三个 judge 均在全局根拉出 `.opencode/`（agent/ + agents/ +
skills/），并诱导 opencode 运行时在该处初始化 `node_modules`（29 个 npm 包）。

后果两条：(a) 违反 INSTRUCTION 第⓪步自立的红线"绝不在共享全局根展开任何文件"；
(b) 并发的其他作品若同样注册同名 agent，会互相覆盖。

**根因不是笔误，是设计缺陷**：⓪步已经精确算出 R，却把红线交给 CWD 运气。修复两层：
- INSTRUCTION 第①步改为 `bash "$R/work/harness/install-agent.sh" "$R"`，显式传锚点；
- 脚本无参时从**自身路径上溯两级**反推 R（脚本恒在 `<R>/work/harness/` 下），不再信 `$PWD`。

验证：从 `/tmp`（模拟全局根）无参调用 → `.opencode/` 落在 R，CWD 零污染。

教训：**R 锚定协议必须贯穿到每一个被调用的脚本，而不止于 INSTRUCTION 正文**。凡是能从
`$PWD` 推断路径的地方，都是红线的漏洞。

### ② `check-batch.sh --all` 是假绿灯（待评估硬化）

脚本把 `--all` 当字面批次名去 artifacts.tsv 里查，查不到则输出
"该批未登记确定性产物，按通过处理 / BATCH_ARTIFACTS: OK batch=--ALL checked=0"。
**看似通过，实则零检查。** 本轮我自己先踩了一次，逐批扫才是真验证。
评测机 AI 同样可能误用。硬化方向（未实施）：无法匹配的批次名应报错退出而非"按通过处理"。

### ③ 平台级情报：并发启动撞 SQLite 锁（非我方可修，建议反馈）

三个 opencode **严格同时**启动时，judge2 在 60 秒内崩溃退出，stderr 仅两行：
`Error: Unexpected error` / `database is locked`。

机制：opencode 把会话状态存在**整个用户共享**的 SQLite 库
`~/.local/share/opencode/opencode.db`（本机已 458MB，WAL 模式）。进程初始化需对该库写入
（建会话、迁移检查），SQLite 同一时刻只允许一个写事务，撞锁者被判致命错误、进程直接退出。
错峰重启即无事——初始化写入是毫秒到秒级爆发期，错开即可。库越大锁窗口越宽。

**影响**：崩溃发生在读 INSTRUCTION **之前**，一行任务都不会执行，包内代码无可防御点。
若平台三个并发 opencode 共享同一 HOME，**这本身就能随机吃掉 1/3 的 judge**，与作品质量无关。

**建议向平台确认**：三个并发执行器是否共享 HOME？是否观察过 opencode 启动即报
`database is locked`？能否错峰数秒启动？

## 四、结论

- 终版包在**确认拓扑**（3 并发 + 独立目录 + 共享全局根 CWD）下**三判同构、全部 24/24、
  零回滚、135 断言全绿**——round-15 的 R 锚定重构在并发场景下得到实证。
- 诱饵哨兵 `task-9999-decoy/sentinel.txt` 原封未动；越界写入仅 `.opencode/` 一处，
  已定位、已修复、已验证。
- stability 掉分现有两个已证实机制：旧⓪步的 CWD 互踩（round-15 已修）、
  本轮的全局根 `.opencode/` 污染（已修）；外加一个平台侧嫌疑：并发启动撞 SQLite 锁。
