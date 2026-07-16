# INSTRUCTION — ShopHub 设计实现一致性修复（赛题 02_04）

> 读者是执行本作品的 **AI agent**。我们已完成「检查」——`work/bugs/` 里给出了 ShopHub 与冻结设计
> （`design-docs/` + `README.md`）之间已定位 BUG 的**详细修复卡片**（按执行批次组织，每张卡含
> 文件 / 现状 / 期望 / 改法 / 验收 / 勿犯 六段）。你要做「修复」：**按批次照卡片修改源码**，且
> **每修完一批必须过一次棘轮护栏**（`ratchet.sh verify`：通过则固化，失败自动回滚）。护栏保证
> 你交付的工程在任何时刻都不会比上一个已验证状态更差。

## 0. 心法（先读，贯穿全程）

1. **宁可少修，绝不红交。** 交付一个编译失败 / Spring 上下文起不来的工程 = 0 分，比十张卡片
   不修更糟。棘轮护栏（verify 失败自动回滚到 golden）已在结构上保证这一点——**绝不绕过它**，
   **绝不在 verify 未通过的状态下结束工作**。
2. **只照卡片修。** 卡片之外的任何"改进冲动"一律禁止——`work/bugs/README.md` 末尾有「绝不做」
   清单，那些是我们尽调后确认**必然炸掉整个上下文**的操作。
3. **每批修完立即 verify，绝不攒批。** 攒批 = 失败时无法定位是哪批引入的 + 回滚损失翻倍。
4. **19 批必须全部执行完——"当前用例全绿"不是完成条件，本任务也不存在"时间限制"。**
   本环境的用例总数以 `ratchet.sh snapshot`/`verify` 输出的 `total=` 为准——评测机上的
   `test-cases` 可能是**全量用例集**（远多于公开 24 例），也可能只是公开子集；无论哪种，
   批次表覆盖的修复面都大于任何单次可见的用例集，**全绿后弃跑剩余批次 = 主动放弃分数**。
   绝不允许以"时间受限 / 剩余批次太多 / 上下文太长 / 已经全绿 /
   剩余批次只服务隐藏用例"等任何理由跳过未执行的批次提前收尾。合法的批次缺席仅两种：
   ① 该批 verify 失败、重试一次仍失败，按协议跳过；② 严格按 `work/bugs/README.md` 依赖说明
   的连带跳过（仅限 B13→B16→B17 链及 B14/B15 中明确标注的卡片，不得自行扩大范围）。（护栏
   保证任何时刻被外部强制中断都不丢已固化成果——这是对抗**意外中断**的保险，不是你提前
   收工的许可。）

## 1. 环境准备

- 评测机已预装**完整 JDK 21（含 javac）与 Maven**——工程按 `release 17` 交叉编译，
  `java -version` 显示 **17~21 任一版本**即满足，`mvn -version` 能打印即满足，**确认后直接
  开始，绝不要再安装/下载任何 JDK 或 Maven**。无需 Docker / 数据库 / 常驻服务（黑盒测试
  自带内存 H2；仅 Maven 下载依赖需要网络）。`work/` 本身纯文本 + bash，无三方依赖。
- 若确认缺失（评测机不应出现）：把 `java -version`/`mvn -version` 的原始输出如实记入
  `result/output.md` 并停止——**不要尝试自行下载安装、不要去寻找不存在的安装目录**，
  环境缺陷不是你能修复的问题，如实记录就是正确处置。
- 修复 subagent 的命令行**不得**出现 `$HOME`、`~` 等工程外路径（headless 下子会话的外部
  目录权限询问无人应答，会让整个运行永久挂死，见 SKILL「边界」首条）；subagent 跑 Maven
  一律经 `bash work/harness/mvnw.sh <参数>`。

- **注册 bug-fixer subagent（必须执行，幂等，一条命令）**——把修复技能同时装进 OpenCode 的
  项目级（`./.opencode/`）与全局（`~/.config/opencode/`）注册目录（双保险），供第 ③ 步
  按批派遣：

```bash
bash "$R/work/harness/install-agent.sh" "$R"
```

  第一个参数必须显式传 `$R`：省略时脚本按当前工作目录安装项目级注册目录，而平台的当前
  工作目录是**多个作品共用的全局根**——会在红线目录里生成 `.opencode/`（还会触发运行时在
  该处初始化 node_modules），既违反第 ⓪ 步红线，又与并发执行的其他作品互相覆盖。

  注意：OpenCode 仅在启动时加载 agent 清单——本注册只对**之后新启动**的会话生效；你当前
  会话内直接按第 ③ 步 a 的递降链派遣即可，派不出 bug-fixer 不是安装失败。提交包内已预置
  `.opencode/` 注册目录——**仅当**你的运行时恰好启动于作品目录 R 时它才会被自动发现；平台
  实际以全局根目录启动运行时，此时 `.opencode/` 不生效、递降链走 general 即为预期路径，
  不是故障。install-agent.sh 仍需执行（幂等，向用户级目录注册，兼顾重启后的新会话）。

## 2. 执行方式

### 第 ⓪ 步 — 锚定到作品自己的目录（多任务共存的平台布局如此，不是可选检查）

评测平台把每个作品解压到**各自独立**的路径（形如 `/app/tasks/<任务id>/<作品名>/`，该目录
**可写**），但启动你的 shell/会话时**当前目录很可能是多个评测任务共享的全局根目录**——
在那里展开任何文件都会与其他任务/其他评测 agent 互相覆盖。所以开始任何操作前：

1. **定位 R**：R = 你正在阅读的这份 `INSTRUCTION.md` 所在目录的**绝对路径**（kickoff 提示词
   给了作品路径就用它；没给就找到你读的这份文件，`R=$(cd "$(dirname <该文件路径>)" && pwd)`）。
   确认 `ls "$R"` 能看到 `INSTRUCTION.md、work/、result/、logs/`。
2. **cd "$R"** 并确认可写：`touch "$R/.write-test" && rm "$R/.write-test"`。此后一切操作
   （源码复制、构建、`.ratchet/`、`maven-repo/`、记录写入）都发生在 `$R` 之内。
3. **红线**：绝不在 shell 初始所在目录（全局根目录）展开/写入任何文件；除 `$R` 与系统
   临时目录外不写任何路径。后续所有相对路径均以 `$R` 为基准（每开一个新命令/新会话，先
   `cd "$R"`）。
4. 兜底（一般用不到）：若 `$R` 确实不可写，`W=$(mktemp -d /tmp/shophub-fix-XXXXXX)`，
   `cp -a "$R/." "$W/"`，此后以 `$W` 为 R 继续，并在最终 `result/output.md` 里如实记录
   "作品目录不可写，实际工作目录为 $W"。
   完成标志：`pwd` 输出 R，且 R 下同时有 `INSTRUCTION.md、work/、result/、logs/、.opencode/`
   且可写。

### 第 ① 步 — 把待修复源码复制到 R（作品目录）

```bash
cd "$R" && cp -a /app/code/judge-assets/02_04_design_implementation_consistency/. .
```

这是平台提供的、**未修复**的 ShopHub 材料（含 `code/`、`design-docs/`、`README.md`、`test-cases/`）。
它是只读的——**复制到 R 后改副本，不要动原路径**。复制完成后 `$R` 下应出现
`code/`、`design-docs/`、`README.md`、`test-cases/`。

> 若上述路径在你的环境不存在，自行定位含 `code/pom.xml` 的 ShopHub 工程根（`pom.xml` 带
> `shophub`/`com.ecommerce` 指纹）后 `cp -a <该目录>/. .`。

复制完成后，**无条件**执行一次换行符归一（不要先检测再决定）：

```bash
sed -i -e 's/\r$//' work/harness/*.sh    # 防御性归一：万一打包环节引入 CRLF，先归一为 LF（LF 时零副作用）
```

> **重启/续跑场景**（上一次运行被外部中断——评测平台拥挤超时后的重新调度、断网、进程被杀
> ——后再次从头执行本文件。**被平台重新调度属预期场景，不是异常**；无论本次 kickoff 怎么写，
> 只要检测到下述状态就走续跑流程）：
> 若 `$R` 下已存在 `.ratchet/golden-code`（`bash work/harness/ratchet.sh status` 能打印
> golden 与 best），说明这是续跑而非首跑——**跳过本步的源码复制**（重新复制会把工作树打回
> 未修复状态；棘轮虽能在下次 verify 自动回滚恢复 golden，但白白多付一轮构建与重试）。改为：
> ① 直接跑一次 `bash work/harness/ratchet.sh verify` 让工作树对齐 golden；② **重建进度真相**：
> 不要只信 `result/output.md` 的记录（上一轮可能在"verify 完成、记录未写"间隙被杀）——
> 逐批跑一遍产物核验拿到机械事实：
> `for b in B01 B02 B03 B04 B05 B06 B07 B08 B09 B10 B11 B12 B13 B14 B15 B16 B17 B18 B19; do bash work/harness/check-batch.sh $b | tail -1; done`
> ③ 以「记录 + 核验」的**并集缺口**为准：核验 MISSING 的批一律视为未完成（无论记录写了什么），
> 从批次号最小的缺口开始按第③步 a→b→c→d 补齐；核验 OK 但记录缺行的批补一行
> `ALREADY_APPLIED（续跑核验确认）` 后跳过。

### 第 ② 步 — 建立基线快照（修改任何代码之前，必须先做）

```bash
bash work/harness/ratchet.sh snapshot
```

它会：编译原始工程 → 跑公开黑盒得到**基线通过数** → 把 `code/` 快照为 golden（最后已验证良好
状态）。之后每次 `verify` 都以此为兜底——修坏了自动回滚到这里。

> **耗时与超时**：跑 snapshot/verify 时**显式给 bash 工具传 `timeout` 参数 = 1800000
> （30 分钟）**；OpenCode 对该参数没有上限，若你的运行时有上限则取其上限。若命令仍被工具
> 超时终止（输出含 terminated/exceeding timeout 字样），进程已被运行时杀死，**直接以更大的
> timeout 重跑同一条命令即可——这不算"重复启动第二个构建"**（禁止的只是命令仍在运行时并发
> 再起一个；首次构建要下载全部 Maven 依赖，最长可能 20 分钟以上，Maven 会续用已下载依赖，
> 重跑无副作用）。备选后台法：用
> `nohup bash work/harness/ratchet.sh verify >"$PWD/.ratchet/last-verify.out" 2>&1 &` 启动后，
> 用多次独立的短命令 `tail -c 2000 "$PWD/.ratchet/last-verify.out"` 轮询到出现
> `RATCHET_RESULT:` 行——不要写阻塞式 while 循环（它自己会被默认超时杀掉）。

### 第 ③ 步 — 按批次照卡片修复（核心循环）

打开 **`work/bugs/README.md`**：它给出**批次执行顺序表**（B01→B19，公开用例受影响的模块在前、
结构性高危改动殿后）与每张卡片的字段说明。**这是本步你唯一需要亲自读的文件。**

> 🚫 **绝对禁令：你（主 agent）永远不要用 read 工具打开 `work/bugs/` 下的任何卡片文件**
> （`order.md`/`cart.md`/`S2-events.md` 等）。卡片只由 subagent 读——你派遣时给出文件名与
> 小节即可，subagent 会自己打开。
>
> 这不是风格建议，是**整个运行能否跑完的前提**。卡片单个 50–120 KB；你每批读一个，19 批就是
> 约 460K token 涌进你的上下文——**实测会在第 10~12 批把上下文顶爆，运行时直接掐断会话，
> 后半程批次全部丢失**（曾实测主上下文 7K → 446K 线性爆炸）。而且你读完也没用：真正动手的是
> subagent，它必须自己读一遍卡片。你读那一遍是纯浪费，且是致命的浪费。
>
> 你在本步的上下文预算是每批 ~3K token：派遣一次、看 verify 最后一行、看 check-batch 最后
> 一行、往记录追加一行。**若你发现自己正准备 read 一个卡片文件——停下，改为派遣。**

对每一批，严格执行 a→b→c→d：

```text
a. 从批次表查出该批对应的卡片文件名与小节（多数批次 = 一个文件；order/payment/S2-events
   一个文件含两个批次，各批只做批次表指到的那个 §A/§B 小节）——**查表即可，不要打开该文件**
   （见上方禁令）。把"修复该文件的该小节"作为任务**派 subagent 执行本批**，由它打开卡片、
   逐卡修改 code/ 下的源文件。派遣方式按下面的三级递降链逐级尝试（不允许跳级）。
   **无论最终派的是哪种 agent 类型，派遣 prompt 第一行都必须是（把 <R> 替换为第⓪步锚定
   的绝对路径，其余一字不差）：
   「工程根目录是 <R>，先 cd <R>，再完整阅读 <R>/work/skills/bug-fixer/SKILL.md 并遵守其
   全部规范，然后执行：修复 work/bugs/<文件> 的 <小节>，业务代码在 <R>/code/ 下」**
   （bug-fixer 已内置该规范，重复要求无害；general 则完全依赖这一行——漏写的后果是
   subagent 不知道 mvnw.sh / test-compile / 外部路径禁令等全部纪律）。**必须写绝对路径**：
   子会话的初始目录是运行时进程的启动目录（多任务共享的全局根目录），不是 R——相对路径
   在子会话里必然落空。每次派遣前自查 prompt 是否以该行开头且 <R> 已替换为绝对路径。
   1) 用 task 工具、subagent_type="bug-fixer" 派遣；
   2) 若 1) 返回 `Unknown agent type`（会话中途注册时必然如此，不是安装失败），改用
      subagent_type="general"（OpenCode 内建，无需注册）派遣；
   3) 仅当 task 工具本身不存在时，才由主 agent 自己按 SKILL.md 逐卡修——这不构成少跑
      批次的理由。
   派 subagent 不是可选优化：它把整批长卡片隔离在子上下文里，主上下文每批只留一行结果，
   这是 19 批全部跑完的前提。**注意这份隔离只在"你自己不读卡片"时才成立**——你若先 read 一遍
   卡片再派遣，隔离形同虚设、上下文照爆，且那一遍读毫无用处（动手的是 subagent，它会自己读）。
   **一次只允许存在一个在途 subagent。**绝不并行派遣多个批次、
   绝不在上一批 verify 出结果前派下一批——棘轮以批为单位，工作树同一时刻只能承载一批
   改动（即使你的运行时工具描述鼓励并行派遣，也不适用于本任务）。
b. 本批全部卡片改完后，立即执行：
       bash work/harness/ratchet.sh verify
c. 看输出最后一行 RATCHET_RESULT，按协议走：
   - ADVANCED / OK      → 本批已固化，进入下一批
   - OK_NO_CHANGES      → 工作树与 golden 没有任何差异 = 你实际上什么都没改。
       最常见于 ROLLED_BACK 之后"以为重修了其实没写进去"——回到 a 步真正修改代码后再
       verify；本批默认【不算】已执行（第 ④ 步收尾终验时出现它则是正常收官结果）。
       例外：若 subagent 逐卡核对后如实回报『本批各卡的「现状」在代码中已不存在』（常见于
       先行批次共用同一文件时已顺带修复，或 subagent 已自行跑过 verify 并固化——后者违反
       其规范但结果有效），则在记录中写 `B0x <文件> → ALREADY_APPLIED（经逐卡核对）`，
       本批视为已执行，进入下一批。同一批 OK_NO_CHANGES 至多出现两次：第二次后必须在
       ALREADY_APPLIED 与真正重修之间二选一，绝不第三次空跑 verify。
   - ROLLED_BACK reason=… → 工作树已被自动恢复到 golden（良好状态）。
       本批允许【重试一次】：对照 verify 打印的失败摘要修正理解后**实际重修本批**
       （重试 = 重新改代码，不是重新跑一遍 verify）。**注意：回滚已清除本批全部改动
       （包括已经改对的部分）——重试必须整批从头重做全部卡片**，派遣时把失败摘要转告
       subagent 并明示"这是 ROLLED_BACK 重试，从第一张卡整批重做"；绝不只修摘要里
       报错的那几个文件；
       重试仍 ROLLED_BACK → 【跳过本批】，继续下一批
       （个别批次有前置依赖——如 B14/B15/B16 依赖 B13、B17 依赖 B16——被依赖批跳过时按
       批次表下方说明处理）。
       绝不对同一批重试第二次，绝不手工"抢救"半失败状态。（「绝不对同一批重试第二次」
       约束的是本轮之内；第 ④ 步补救循环的重开是新的一轮，重开后重新获得一次重试额度。）
   - BUSY → 已有一个构建实例在跑（多为你此前后台启动未等完的 verify）。绝不再启动新构建，
       轮询 `.ratchet/last-verify.out` 或直接重跑 verify 直到拿到非 BUSY 结果。
   【c 的附加动作——凡 verify 固化（ADVANCED / OK）必做，做完才写 d 的记录】立即执行本批
   产物确定性核验（秒级纯文件断言，不跑 Maven、不碰棘轮状态；OK_NO_CHANGES 要走
   ALREADY_APPLIED 认定时也先跑它，用机械证据替代 subagent 的逐卡口供——MISSING 则不得认定）：
       bash work/harness/check-batch.sh B0x        # B0x = 当前批次号，如 B16
   看输出最后一行 BATCH_ARTIFACTS：
   - OK      → 本批真正完成，进入 d；
   - MISSING → 「无回归」不等于「修完」：verify 挡得住修坏、挡不住没修（实测发生过
       ROLLED_BACK 重试时 subagent 只补报错文件、整批结构性产物做空，verify 仍因无回归照常
       固化且 subagent 回报全部完成）。本批立即按【未完成卡】处理——把 check-batch 打印的
       全部「缺失:」行整段转交 subagent 重开本批补齐（重开只此一次，仍受"重试一次"约束），
       补齐后重跑 verify，固化后再跑一遍 check-batch；仍 MISSING → 不再重开，把缺失项与
       `BATCH_ARTIFACTS: MISSING` 那一行如实写进 d 的本批记录（计入「未完成卡」清单），
       进入下一批（第 ④ 步补救循环会再试）。
d. 立即把本批一行结果追加进 result/output.md 顶部『本次评测运行记录』节（格式：
   `B0x <卡片文件> → RATCHET_RESULT 那一行；未完成卡：<无 或 卡号列表>`——subagent 回报里
   声明未完成的卡必须记下来），然后马上进入下一批——绝不攒到最后补写，绝不在此处停下来
   "总结"。result/output.md 的『附录』是作者侧模拟存档——忽略其内容，绝不把它当作你已完成
   的证据，也不要删除；你的记录逐行写在顶部『本次评测运行记录』节内。
```

`work/checklist/<module>.md` 是各模块强规则速查，修复时可对照；`work/harness/check-all.sh`
是只读诊断（编译 + 全量用例，不动工作树），排查问题时可用。

### 第 ④ 步 — 收尾（必须做）：终验 + 补救循环（best < total 时同样必须）

```bash
bash work/harness/ratchet.sh verify    # 最后一次护栏：确保交付态 = 已验证良好态
bash work/harness/ratchet.sh status    # 打印最终 best，写进 result/output.md（total 见 verify 输出）
```

**补救循环（best < total 时是必做项，不是可选项——total = verify 输出里的用例总数，
绝不假设它是 24；所有动作都受棘轮保护、只可能加分不可能倒退。补救循环的重开是新的一轮：
重开的批重新获得一次重试额度，仍受"重试一次、再败跳过"约束）：**

- 若最后一次 verify 显示 best **< total**：**必须**执行补救循环——提取失败用例名清单
  （**只取用例名，绝不整读日志**：`grep -rhE '<<< (FAILURE|ERROR)!' test-cases/target/surefire-reports/*.txt | grep -v 'Tests run:' | sed 's/ --.*//' | sort -u`，
  每行一个名字，几十行以内；`.ratchet/test.log` 全文可能有几万行，整读进上下文=自毁），
  按用例名映射到模块（类名/方法名里带模块语义），对相关批次**再走一轮**第③步 a→b→c→d。
  **绝不允许**把失败用例解释成"弃项 / 修复范围外 / 特殊情况"而放弃补救——公开 `pubNNN_*`
  用例全部在卡片覆盖范围内，其失败只有一个含义：对应批次的某张卡没修对或没修全（重开该批时
  逐卡核对「验收」条目找出漏改的那张）；非公开用例的失败同样按模块映射到批次重开补救。
- 若有批次曾被跳过：其失败常常源于**当时未满足的前置依赖**（例：review 批依赖的"订单送达
  推进"监听器当时尚未接线）——收尾时依赖批多半已固化，把被跳过的批次**重开一轮**
  a→b→c→d。涉及依赖链时按批次号升序重开：先 B13，后 B16，再 B17。棘轮保证重开失败也只是
  回滚，绝不倒退。
- 若记录中存在"未完成卡"不为"无"的批次：按 a→b→c→d 重开一轮**只补这些卡**。
- 若记录中存在 `BATCH_ARTIFACTS: MISSING` 的批次：该批被固化的只是"无回归"，卡片产物并未
  落齐（空心批次）——按 a→b→c→d 重开一轮，把该批记录里的「缺失:」清单原样转交 subagent
  补齐，直到 verify 与 `check-batch` 双双 OK；重开额度用尽仍 MISSING 则如实保留记录。
- 若 best = total：对照 `work/checklist/<module>.md` 逐模块扫读一遍是可选加分动作——它是本任务
  中**唯一**的可选动作，其余一切步骤均为必做。发现某条强规则仍不满足（说明有卡漏改/改偏）→
  回到对应批次按 a→b→c 补修一轮。评分用例只考设计契约，这一步是当前可见用例覆盖不到的提分空间。

**收尾自检清单（写 STATUS: DONE 之前逐项机械核对，全部 ✓ 才算完成）：**

1. `ls code/pom.xml` 存在，且最后一次 verify 的 RATCHET_RESULT 是 ADVANCED / OK / OK_NO_CHANGES；
2. `result/output.md` 顶部『本次评测运行记录』节内 B01–B19 每批一行（含未完成卡字段）；
3. `bash work/harness/ratchet.sh status` 的 best 与 total 数值已写入记录节。

最后补全 `result/output.md` 顶部『本次评测运行记录』节：基线通过数、最终通过数与 total、
跳过批次汇总及原因（每批的 RATCHET_RESULT 行应已在第 ③ 步 d 逐批追加过），末尾一行 `STATUS: DONE`。

## 3. 构建规范

`ratchet.sh` / `check-all.sh` 内部已按本节规范执行——正常流程你不需要手动构建；仅当你需要
手动运行 Maven 排查问题时，必须照此。规则：`maven-settings.xml` 存在才用 `-s`（否则走默认
Maven Central）；**所有** Maven 命令显式指定
`-Dmaven.repo.local`，避免依赖/污染用户目录 `.m2`；`test-cases` 是独立 reactor，从该本地仓库
消费刚 `install` 的业务模块，故它的 `mvn test` 必须带**同一个** `-Dmaven.repo.local`：

```bash
TARGET="$R"    # 第⓪步锚定的作品目录（第①步已把源码复制到这里）

# maven 设置：存在则用；内网镜像不可达时其内容可按 README 置为空的 <settings/>
SETTINGS_OPT=""; [ -f "$TARGET/maven-settings.xml" ] && SETTINGS_OPT="-s $TARGET/maven-settings.xml"

# 本地仓库：README 要求所有 Maven 命令显式指定 -Dmaven.repo.local，避免依赖用户目录缓存
REPO_OPT="-Dmaven.repo.local=$TARGET/maven-repo"

# 构建修复后的业务工程（始终执行，证明可编译）
mvn $SETTINGS_OPT $REPO_OPT -f "$TARGET/code/pom.xml" install -DskipTests           # 期望 BUILD SUCCESS

# 黑盒用例（同一个 REPO_OPT；总数以实际运行为准——评测机可能是全量集）
[ -f "$TARGET/test-cases/pom.xml" ] && mvn $SETTINGS_OPT $REPO_OPT -f "$TARGET/test-cases/pom.xml" test   # 期望 Failures: 0, Errors: 0
```

## 4. 执行完成判定

**全部满足**才算完成：

1. 批次表 B01→B19 每批都已执行——合法的批次终态只有三种：已固化 / `ALREADY_APPLIED`
   （经逐卡核对，见第 ③ 步 c）/ 按协议跳过（verify 重试仍失败，或按依赖说明连带跳过，
   见心法第 4 条）。**"当前用例已全绿"不构成跳过理由**，全绿后剩余批次仍必须逐批执行；
2. **最后一次 `ratchet.sh verify` 的 RATCHET_RESULT 是 `ADVANCED` / `OK` / `OK_NO_CHANGES`**
   （即交付态 = 已验证良好态；收尾终验时工作树通常与 golden 一致，`OK_NO_CHANGES` 即正常收官；
   `ROLLED_BACK` 后工作树也等于 golden，但仍须重跑一次 verify 得到上述结果才收工；`BUSY` 不是
   终态——按第 ③ 步 c 轮询到非 BUSY 结果为止）；
3. `result/output.md` 顶部『本次评测运行记录』节内含 B01–B19 共 19 行批次记录（缺行 = 判定 1
   未满足），末尾是你本次写入的 `STATUS: DONE`。

## 5. 修复结果获取方式

- **修复后的工程**：`<R>/code/`（R=第⓪步锚定的作品目录；golden 已同步，`.ratchet/` 为护栏
  状态目录，可忽略）。
- **BUG 卡片与批次表**：`work/bugs/`（`README.md` 为索引）。
- **方案说明**：`work/DESIGN.md`；**运行报告**：`result/output.md`。

## 6. 禁止事项

1. 不修改 `design-docs/`、`README.md`、`test-cases/`、REST API 的 URL/方法/请求头/字段名与类型、`/api/v1/` 前缀。
2. 不针对某个测试用例硬编码逻辑——朝**设计与契约**修，而非迎合可见用例。
3. 不新增数据库 reset/bootstrap 钩子。
4. 只改 BUG 卡片涉及的源码，不"顺手优化"无关代码。
5. **高危操作黑名单**（除非卡片明确要求）：不新增/修改 `@Configuration` 类、`@Bean` 方法、
   `CacheManager`、`@EnableCaching`、`SecurityFilterChain`、`pom.xml`、`application*.yml`；
   新增 Spring 组件必须按卡片给定的类名/包路径（bean 名冲突会让整个上下文启动失败 = 0 分）。
6. 遵守 `work/bugs/README.md` 的「绝不做」清单。
