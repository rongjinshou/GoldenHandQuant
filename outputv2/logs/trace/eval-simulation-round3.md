# 评测模拟复盘 — 第三轮无人值守全流程运行（OpenCode + MiMo 弱档）

第三轮模拟的目的：① 验证第二轮后互换的 B16/B17 批次表；② 把模型从 mimo-v2.5-pro 降到
**mimo-v2.5（弱档）**，逼出仅靠强模型发挥才能掩盖的协议缺陷；③ 在真实 `/app` 路径、root 只读
judge-assets、全新 OpenCode 安装的条件下复刻评测机时序。本轮暴露的每一处缺陷都已在交付物中
修复（见文末对照表），修复后的交付物有待第四轮回归验证。

## 模拟环境

- 源码入口：`/app/code/judge-assets/02_04_design_implementation_consistency/`（root 属主、只读，
  从 pristine 基线释出；基线 18/24 与前两轮一致）
- agent 运行时：OpenCode 1.17.17（当轮全新安装），headless `opencode run --auto`
- 模型：`mimo/mimo-v2.5`（**非 pro**）；kickoff 仅一句"读 INSTRUCTION.md 并从头到尾执行"
- 工具链：Temurin 17.0.19 + Maven 3.9.16（预置 `$HOME/tools`，模拟"已具备则跳过"路径）

## 结果总览

| 维度 | 第二轮（pro） | 第三轮（弱档） |
|---|---|---|
| 运行时长 | 105 分钟 | 112 分钟 |
| 批次执行 | 19/19 | 19/19 + 自创 B20 补救批 |
| 公开用例 | 18 → 24（32 分钟锁定） | 18 → 23（B05 漏修 pub101）→ 收尾补救 → **24/24** |
| verify 总数 | 24 | 25（5 ADVANCED / 5 回滚 / 其余 OK） |
| subagent | 21 次 | 20 次（全部 @general，见发现 1） |
| 棘轮出手 | 3 次 | 5 次（B14×2、B16×1、B17×2）全部兜住 |
| 主上下文 | — | 输入 24.8 万 token（分批派遣的瘦身设计成立） |
| 隐藏面完整度 | review 批缺失 | **B16 空心 + B07/B15 局部空心 + B17 缺失**（见发现 4） |

两轮公开分相同（24/24）、隐藏面缺失分布不同——这正是真实评测多次提交时 58/72 波动的机制。

## 关键发现（按发生顺序）

### 1. bug-fixer 注册对当前会话必然无效（结构性，另有隔离实验实锤）

INSTRUCTION 让运行中的 agent 执行 `install-agent.sh`，但 OpenCode 仅在启动时加载 agent 清单——
本轮 20 次派遣全部落在内建 `@general` subagent 上（session 库、task 参数、流日志三方证据一致）。
主 agent 的自救是读 SKILL.md 后手写派遣 prompt，转述有损：B01 的 prompt 漏了"不要自己跑
verify"，该 subagent 当即违规。隔离实验进一步证实：全新机器上同会话派 bug-fixer 必得
`Unknown agent type`（第二轮 21 次派遣成功吃的是作者机全局目录残留注册的红利，不可外推）。

### 2. B13 断点：编译自检立功，自愈依赖模型发挥

静态分析预测的断点如期触发——EVT-A3 删除影子事件类后，B06 新建的
`PaymentSucceededNotificationListener` import 悬空。subagent 按 SKILL 跑强制编译自检当场撞见
`cannot find symbol`，读文件、改 import 到 `common.event`、复编通过，并在回报中如实说明。
结论：自检设计正确；但"自愈"是模型即兴行为，弱档这次走对了不代表每次都走对。

### 3. B14/B16 连环暴露两个协议级缺陷（本轮最重要的机制性发现）

- **自检与门禁不同构**：SKILL 自检命令是 `mvn compile`——不编译测试源码；棘轮门是
  `install -DskipTests`——含 test-compile。B14/B16 两批的 subagent 都改了生产类构造器、漏改
  模块单测（卡片明确列了要同步的 `*Test.java`），自检全绿、门禁整批回滚。同类失败三次。
- **回滚语义不被弱模型理解**：B14 第一次回滚后，重试 subagent 只补了报错的测试文件——
  它以为自己之前的生产代码改动还在，实际 ROLLED_BACK 已整批清零，于是第二次以
  `package does not exist` 再败。（B14 的 subagent 随后违规自跑 verify、第三次整批重做成功，
  等于用 3 次全量构建自费买通了一批——棘轮保证了安全，时间预算失控。）

### 4. B16 空心固化 → B17 顶罪双败（58/72 波动的机制解释，全链有据）

B16 第一败回滚后，重试只补了报错单测 → verify「无回归」照常固化 → **三个跨模块监听器
（库存扣减 / 订单送达推进 / 退款完成）与监听失败落库全部不存在**，而 subagent 的完成回报
声称 4 卡全部 ✅ 并附文件清单（讲的是回滚前的故事），主 agent 如实记账 B16 OK。
到 B17：REV-1 的"购买+签收"校验依赖 B16 的送达推进监听器把订单推到 DELIVERED——监听器
不存在，pub014 必挂，B17 两败被跳过、替 B16 顶罪。收尾即使重开 B17 也无解（病根在 B16）。
**"verify 挡得住修坏、挡不住没修"是本方案此前最大的结构性盲区**。
（勘误：初版产物核验清单曾把本轮 B07/B15 也报为局部空心——第四轮复查证实那是两条锚点
取自参考实现注释/日志行的误报，锚点已换成行为载重代码并重验（findByInvoiceRequestNo /
recordPayment / getProvinceRules()）；本轮真实的隐藏面损失即 B16 空心 + B17 缺失两处。）

### 5. 收尾补救循环：best<24 分支实战通过，重开跳过批未执行

24/24 前主 agent 严格照第④步走：check-all 定位 pub101 → 根因到
`PromotionController.extractUserId()` 硬编码 1L（=B05 漏掉的 PROMO-6）→ 修复 → ADVANCED
24/24（自创"B20"补救批编号，记录诚实；瑕疵：此步由主 agent 直接动手而非派 subagent）。
但达到 24/24 后即写 STATUS: DONE，**未按协议重开曾被跳过的 B17**——"公开全绿 → 收工"的
引力再次得到实证（旧文本把该要求嵌在补救循环段内，易被读成 best<24 范畴）。

## 本轮驱动的交付物修复（全部已提交）

| 缺陷 | 修复 | commit |
|---|---|---|
| 注册不热加载、派遣链断裂 | INSTRUCTION ③a 三级递降链（bug-fixer → general+SKILL 指针 → 自修）；§1 明示"仅对新会话生效"；**提交包预置 `.opencode/` 注册目录**（先于会话启动存在） | c871ea7 |
| 预置 result/output.md 的 STATUS: DONE 干扰 | 顶部新增『本次评测运行记录』空节，作者存档降为附录并去裸 DONE | c871ea7 |
| bash 工具 2 分钟默认超时 vs 构建 5~20 分钟 | 超时注记给出确切参数（timeout=1800000）、超时后重跑的合法性、后台+短命令轮询法 | c871ea7 |
| "预算/全绿冲刺"等提前收尾话术空隙 | 第④步改为"收尾必须做：终验+补救循环"，全文删除"预算" | c871ea7 |
| 自检与门禁不同构 | SKILL 自检改 `mvn test-compile`（模块与全量两式）并解释机理 | 78862c7 |
| 回滚语义误解 | SKILL 新增第 0 步"重试=整批从头重做"；INSTRUCTION ③c 同步明示并要求派遣时转告 | 78862c7 |
| **空心批次（verify 盲区）** | **`check-batch.sh` + `artifacts.tsv`（84 条断言）确定性产物核验**：每批固化后机械核对新增/删除/关键 grep，MISSING 按未完成卡重开；三组树验证（参考 19/19 OK、基线 19/19 MISSING、本轮空心 golden B16=MISSING 7/7 精确复现） | 40ced90 |
| 卡片时序缺陷（EVT-A3 漏列 B06 监听器、LOY-10 与 ORD-B8 重复、过期锚点等 13 处） | 双态措辞/去重占位卡/依赖声明补全 | c871ea7 |
| ratchet 自身故障模式（copy_code 非原子、无并发锁、snapshot 写序、JDK 版本盲区、CRLF） | mv 交换+自愈、flock+BUSY、写序对调、版本烟测、三层 CRLF 防御（.gitattributes / 无条件 sed / 脚本自愈序言） | c871ea7 |

## 第四轮回归验证点（建议）

1. 三级递降链：全新环境下派遣是否稳定落到 bug-fixer（预置 `.opencode/`）或 general（递降）；
2. test-compile 自检后，B14/B16 类"漏改单测"是否在批内被拦截；
3. check-batch 是否把空心批当场揪出并触发重开（B16 场景回归）；
4. 24/24 后是否仍继续重开曾跳过/MISSING 的批次（新第④步措辞）；
5. B17 在 B14/B16 真实落地后能否固化（本轮未能验证——B16 空心导致前提缺失）。
