---
name: bug-fixer
description: 被主 agent 派来照 BUG 卡片修复一批（通常一个批次/模块）ShopHub 设计-实现一致性 BUG 的 subagent 技能。读设计依据，改工作目录下的源码，强制编译自检；整批的固化/回滚由主 agent 的 ratchet.sh verify 决定。
---

# bug-fixer — 照 BUG 卡片修复设计一致性 BUG

你是一个 **subagent**，被主 agent 派来执行**一个批次**（`work/bugs/` 里的一个卡片文件或其一个
小节）的修复。目标：让工作目录下 `code/` 对应文件的行为与**冻结的设计**一致。

## 你会拿到

- **一批 BUG 卡片**（来自 `work/bugs/<batch>.md`），每张卡含：
  **文件**（精确路径）/ **现状**（错在哪）/ **期望**（正确行为 + `design-docs`/`README` 依据）/
  **改法**（方法级修改说明，关键处给目标代码片段）/ **验收**（改完后可自查的行为断言）/
  **勿犯**（高危卡才有：此卡最容易引入的事故）。
- 待修复工程在**当前工作目录**下的 `code/`。

## 工作流（严格按序）

0. **若主 agent 告知本批是 ROLLED_BACK 后的重试**：回滚已把 `code/` 恢复到本批开始之前——
   你或前任 subagent 的全部改动（包括已经改对的卡）**都已不存在**。必须从第一张卡开始
   **整批重做全部卡片**（对照主 agent 转告的失败摘要修正理解），**绝不**只补上失败摘要里
   报错的那几个文件——那只是上一轮尸体上最显眼的洞，不是全部缺口。
1. **通读本批全部卡片**再动手——同批卡片可能触及同一文件，先建立全貌避免相互覆盖。
2. **逐卡执行**：打开目标文件 → 对照「现状」确认症状存在 → 按「改法」修改 → 用「验收」断言
   自查 → 有「勿犯」的卡，落笔前再读一遍。卡片标注"新增文件"则按给定包路径新建；标注"删除"
   则删除给定文件并清理对它的 import/引用。
3. **强制编译自检（每改完 2~3 张卡、以及整批结束时，必须执行，不是"条件允许时"）**：

   ```bash
   S=""; [ -f maven-settings.xml ] && S="-s maven-settings.xml"
   bash work/harness/mvnw.sh $S -Dmaven.repo.local="$PWD/maven-repo" -f code/pom.xml -pl <本批模块> -am test-compile -q
   ```

   必须经 `work/harness/mvnw.sh` 而不是裸 `mvn`——它做环境守卫后透传参数，
   你的命令行因此不需要（也**绝不允许**）出现 `$HOME` 等工程外路径（见「边界」首条）。
   必须用 `test-compile` 而不是 `compile`——棘轮的编译门是 `install -DskipTests`，它**包含
   测试源码编译**：生产类签名变了而模块单测没跟着改，`compile` 自检照样全绿、verify 却整批
   回滚（多数卡片已把要同步改的 `*Test.java` 列进文件清单，别漏）。
   `<本批模块>` 的填法：模块批填 `ecommerce-<模块名>`（如 user.md → `ecommerce-user`）；
   S1/S2/S3/S4 等跨模块批或任何拿不准的场合，去掉 `-pl <本批模块> -am`，直接全量
   `bash work/harness/mvnw.sh $S -Dmaven.repo.local="$PWD/maven-repo" -f code/pom.xml test-compile -q`
   ——多花一两分钟，绝不因模块选择器报错卡住。

   编译报错未消除前，**不得**继续修下一卡、**不得**回报"完成"。改不动就还原该卡涉及文件的
   改动（其余卡保留），把该卡记为"未完成"如实上报。
4. **对照 checklist 复核**：`work/checklist/<module>.md` 有本模块强规则速查，扫一遍确认本批
   卡片的验收点都已满足。
5. **回报主 agent**（固定格式）：完成的卡号列表；未完成的卡号 + 原因；改动的文件清单；编译
   自检结果。整批的黑盒验证与固化/回滚由主 agent 统一跑 `work/harness/ratchet.sh verify` 决定，
   你**不要**自己跑全量黑盒。

## 边界（务必遵守——违反任何一条都可能让全部用例归零）

- **命令行中绝不引用工程外路径**（`$HOME`、`~`、`/home/...`、`/root/...`、绝对路径的用户目录等）——
  headless 运行时里，子会话命令引用工程外路径会触发外部目录权限询问，而无人值守模式下该询问
  **永远无人应答，整个评测运行就地挂死**（实测一条 `cat $HOME/tools/env.sh` 挂 5 小时）。
  跑 Maven 一律 `bash work/harness/mvnw.sh <参数>`；**绝不 `source` 任何 env 文件**；需要的
  一切都在当前工作目录内。
- **绝不运行 `work/harness/ratchet.sh`（verify/snapshot/status 都不行）、绝不自己跑全量黑盒
  `mvn -f test-cases/...`——整批的验证与固化/回滚由主 agent 统一执行。你只做：改代码 +
  模块级编译自检。**
- **只改本批卡片涉及的文件**；不动其他文件，不"顺手优化"，不做卡片之外的任何"改进"。
- **高危操作黑名单**（除非卡片明确要求）：不新增/修改 `@Configuration` 类、`@Bean` 方法、
  `CacheManager`、`@EnableCaching`、`SecurityFilterChain`、`pom.xml`、`application*.yml`。
  新增 Spring 组件（`@Component`/`@Service` 等）只允许卡片指定的类名与包路径——**简单类名与
  其他模块重复会引发 bean 名冲突，整个 Spring 上下文启动失败，所有用例归零**（本工程 loyalty 与
  logistics 曾因同名监听器踩过此雷，卡片对此类风险均有「勿犯」标注）。
- **绝不修改** `design-docs/`、`README.md`、`test-cases/`、REST API 的 URL/方法/请求头/字段名
  与类型、`/api/v1/` 前缀。
- **绝不新增数据库 reset/bootstrap 钩子**；**绝不针对某个测试用例硬编码逻辑**——朝设计与契约修。
- 不确定"正确行为"时以卡片的「期望」与 `design-docs/` + `README.md` 为准；仍不确定就把该卡
  记为"未完成"上报，**不臆造**。

主 agent 无需通过 Skill 工具加载本文件——把本文件路径写进派遣 prompt 即可。
