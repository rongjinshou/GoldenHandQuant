# Harness — 棘轮护栏与效果自检

纯 AI 修复版的 Harness 由三个脚本组成：**`ratchet.sh`（棘轮护栏，主角）** 负责把修复过程锁进
「只进不退」的轨道；**`check-all.sh`（只读诊断）** 用于排查；**`check-batch.sh`（批次产物
核验）** 在每批固化后机械核对该批卡片产物是否真实落地（防"空心批次"）。都不依赖任何"参考答案"。

## `ratchet.sh` — 快照 / 验证-固化 / 自动回滚（每批修复的强制门禁）

```bash
bash work/harness/ratchet.sh snapshot [TARGET_ROOT]   # 修改前执行一次：基线检验 + golden 快照
bash work/harness/ratchet.sh verify   [TARGET_ROOT]   # 每修完一批执行：通过则固化，失败自动回滚
bash work/harness/ratchet.sh status   [TARGET_ROOT]   # 查看 golden / 最佳通过数 / 历史
```

设计前提：**AI 修复一定会犯错，护栏保证错误不出门。**

- `snapshot`：编译原始工程 + 跑公开黑盒得到**基线通过数**，把 `code/` 快照为 golden
  （状态存于 `<target>/.ratchet/`）。
- `verify` 两道门：① 编译门（`mvn install -DskipTests`）——失败**立即自动回滚**到 golden；
  ② 回归门（全量黑盒用例，总数以本环境实际运行为准）——通过数 **≥ 当前最佳**则把工作树**固化**为新 golden，
  **< 最佳**（引入回归）则**自动回滚**。上下文起不来（bean 冲突等）= 通过数 0 = 回滚。
- 结论行机器可读：`RATCHET_RESULT: ADVANCED|OK|OK_NO_CHANGES|ROLLED_BACK|BUSY …`（含 pass/best/reason）。
  `OK_NO_CHANGES` = 工作树与 golden 无任何差异（防"回滚后未实际重修就 verify"的空重试误判；
  出现在收尾终验时属正常收官）。
- `BUSY`（exit 3）= **另一个 harness 构建正在运行**：`snapshot`/`verify` 与 `check-all.sh` 共用
  `<target>/.ratchet/lock` 非阻塞单实例锁，抢不到锁立即返回、不排队。应对：**轮询等待**——过几十秒
  重跑同一条命令，直到拿到非 BUSY 的 `RATCHET_RESULT`；**绝不并行启动第二个构建**（并行会互踩
  本地 Maven 仓库与 surefire 报告）。`status` 是纯读操作，无锁、随时可查。

数学性质：任何时刻工作树要么等于 golden、要么正在被验证；**最坏交付 = max(基线, 已固化最佳)**，
「交付 0 分工程」在结构上不可能。作者侧已实测四条路径：基线快照（24/24）、注入编译错误→自动
回滚且文件恢复、注入行为回归（编译通过但 24 例只剩 22）→检出并回滚、无改动→固化。

## `check-all.sh` — 只读诊断（不动工作树）

```bash
bash work/harness/check-all.sh [TARGET_ROOT]
```

同样两道门（编译 + 全量用例），但**只报告不回滚**，供修复过程中排查失败细节。通过数统计与
失败摘要都取自 surefire 报告（与 `ratchet.sh` 同法，skipped 不算通过）。与 `ratchet.sh` 共用同
一把单实例锁：构建被占用时提示后 exit 3，稍后再自检。批次门禁请一律用 `ratchet.sh verify`——
它才有固化/回滚语义。

## `check-batch.sh` — 批次产物确定性核验（防"空心批次"，每批固化后必跑）

```bash
bash work/harness/check-batch.sh <批次号如B16> [TARGET_ROOT]
```

补的是 `ratchet.sh` 结构上挡不住的洞：verify 只证明「编译过 + 用例无回归」——挡得住
**修坏**，挡不住**没修**。实测发生过 subagent 在 ROLLED_BACK 重试时只补上次报错的文件，整批
结构性产物（B16 的三个跨模块监听器）全部缺失，verify 因"无回归"照常把空心状态固化为 golden，
subagent 还回报全部完成。本脚本读 `work/bugs/artifacts.tsv`（84 条断言，B01–B19 每批至少 1 条）
对目标批次逐条机械核验，**不依赖模型口供**：`exists` = 卡片【新增】的文件必须存在；`absent` =
卡片【删除】的文件必须不存在；`grep` = 卡片「改法」的载重锚点字符串必须能 `grep -F` 命中
（固定串，非正则）。纯文件系统 + grep：不跑 Maven、不写任何文件、无锁秒级随时可跑，清单按
脚本自身位置定位（`../bugs/artifacts.tsv`，不依赖调用方 CWD，CRLF 自愈后依然成立）。结论行
机器可读：`BATCH_ARTIFACTS: OK batch=<B> checked=<n>`（该批无条目时 `checked=0` 也算 OK）或
`BATCH_ARTIFACTS: MISSING batch=<B> missing=<k>/<n>`（缺失明细已按 `缺失: 类型 路径 参数`
逐条先行打印）。MISSING 的处置协议见 INSTRUCTION 第 ③ 步 c 的附加动作与第 ④ 步补救循环：
按未完成卡用缺失清单重开补齐。清单只收「正常按批次表顺序执行必然成立」的**无条件**产物，
有条件卡（LOY-10 去重占位、EVT-A3"若存在"分支等）不收录；且 84 条断言已逐条双向甄别——
参考实现终态 19/19 批全 OK、未修复基线 19/19 批全 MISSING——既不误报也不放过整批做空。

## `install-agent.sh` — 注册 bug-fixer subagent（环境准备时执行一次）

```bash
bash work/harness/install-agent.sh [ROOT]      # ROOT 省略 = 当前工作目录
```

把 `work/skills/bug-fixer/SKILL.md` 装成 OpenCode 的 subagent/skill 定义，项目级
（`./.opencode/`）与全局（`~/.config/opencode/`）各装一份（双保险），每处三个文件：
`agent/bug-fixer.md` 与 `agents/bug-fixer.md`（`mode: subagent`，供 task 派遣；官方文档主形态
为单数 `agent/`，两目录现行等价、都会被扫描，双装防版本口径差异）、`skills/bug-fixer/SKILL.md`
（skill 形式）。幂等，可重复执行；某处写失败只警告不中断，两处全失败才 exit 1（此时主 agent
直接照 SKILL.md 自行执行每批修复）。注册**不热加载**：只对之后新启动的会话生效，当前会话内派
不出 bug-fixer 属正常，按 INSTRUCTION 第③步 a 的递降链改派内建 general subagent 即可。

## 构建规范（两脚本内部即按此执行，手动构建也须照此）

- `maven-settings.xml` **存在才用** `-s`（否则走默认 Maven Central；内网镜像不可达时其内容可按
  README 置为空的 `<settings/>`）。
- 所有 Maven 命令**显式指定** `-Dmaven.repo.local=<target>/maven-repo`，避免依赖/污染用户目录
  `.m2` 缓存、保证各 agent 工作目录相互隔离。
- `test-cases` 是**独立 reactor**，从该本地仓库消费刚 `install` 的业务模块，因此它的 `mvn test`
  必须带**同一个** `-Dmaven.repo.local`，否则找不到业务模块。
- 脚本内部以 bash 数组传递 mvn 参数，目标路径含空格/非 ASCII 也安全。
- 四个脚本第 2 行自带 **CRLF 自愈序言**：万一交付包被错误转成 CRLF 行尾，脚本会自动生成 LF
  副本重新执行，无需人工干预（`outputv2/.gitattributes` 亦已强制 `*.sh` 以 LF 检出，双保险；
  `check-batch.sh` 读 `artifacts.tsv` 时还会逐字段剥 `\r`，清单本身被 CRLF 化也不误判）。

> 单个 subagent 改完 2~3 张卡后的**强制**局部编译自检（同样带 settings 防御与本地仓库）：
> `S=""; [ -f maven-settings.xml ] && S="-s maven-settings.xml"; mvn $S -Dmaven.repo.local="$PWD/maven-repo" -f code/pom.xml -pl <module> -am compile -q`。
> 注意这只是编译门——bean 冲突等上下文级错误要靠主 agent 的 `ratchet.sh verify` 兜住。
