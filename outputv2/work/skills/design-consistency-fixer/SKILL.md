---
name: design-consistency-fixer
description: ShopHub「设计-实现一致性」修复流水线的在线复核技能（Stage 3）。在确定性修复引擎 work/fixer/apply.sh 跑完之后由评测机的 agent 加载执行。核心是「验证优先」：先构建目标工程并跑黑盒套件，全绿即收工；仅对失败/跳过的用例，按对应模块的 checklist 深核，用「备份→编译门控→回滚」护栏做一处朝设计契约的修复。绝不针对具体测试用例硬编码，一律朝 design-docs/ 冻结契约修复。
---

# design-consistency-fixer（Stage 3：在线复核）

本技能是三段式流水线的最后一段。前两段已经完成：

- **Stage 1（离线审查，提交前已跑）** 逐模块比对 `design-docs/` 与 `code/`，把每处不一致沉淀成 `work/fixer/knowledge-base/`（已验证的完整修复文件 + `baseline-hashes.txt` + `deletions.txt` + `findings.md`）。
- **Stage 2（确定性应用）** 由 `INSTRUCTION.md` 直接调用 `work/fixer/apply.sh <target-root>`，逐文件读目标→比对基线 SHA-256→把已验证修复整文件写入目标，并打印 apply-report（checked / applied / added / deleted / **skipped(failed)**）。

**本技能不重复调用 `apply.sh`**（那是 `INSTRUCTION.md` 的职责）。本技能只做两件事：**验证** Stage 2 的结果，以及**仅在必要时**做带护栏的深核修复。

## 不可逾越的红线

- **绝不针对测试用例硬编码。** 不得识别 testRunId / 特定输入并返回写死的响应，不得为「让某个 PUB-xxx 变绿」写针对该用例的分支。修复方向永远是「让代码符合 `design-docs/` 与 README 第 6/7 节冻结契约」——隐藏用例只会以文档为准出题。
- **禁改「已绿且 hash 匹配」的文件。** Stage 2 已确定性修好的东西不要再动，弱模型二次修改只会好心办坏事。
- **绝不改动冻结文件：** `design-docs/`、`README.md`、`test-cases/`、REST API 的 URL/方法/请求头/字段名与类型、`/api/v1/` 前缀。
- **绝不新增任何数据库 reset/bootstrap 钩子**（黑盒隔离由测试 harness 负责，业务代码不得自带 reset）。
- **不允许静默吞掉失败**：回滚了就如实写进 `result/output.md`。

## 前置：确定目标根目录

`<target-root>` 是包含 ShopHub `code/`、`test-cases/`、`maven-settings.xml`、`design-docs/` 的项目根——即按 `INSTRUCTION.md` 第 ① 步把源码复制进来的**当前工作目录**（不写死任何平台绝对路径）：

```bash
TARGET="$(pwd)"   # 已按 INSTRUCTION 第①步定位并 cp 源码进来的当前工作目录
cd "$TARGET"      # 后续命令中 maven-settings.xml / test-cases 均相对此根
```

假设 `mvn`（3.6+）与 `java`（17+）已可用——环境准备由 `INSTRUCTION.md` 负责，本技能不做安装。`maven-settings.xml` 已是空 `<settings/>`，走 Maven Central。

**构建命令规范（下文所有 `mvn` 均按此，示例为简洁未每条重复）**：`maven-settings.xml` 存在才用 `-s`；**所有** Maven 命令显式带 `-Dmaven.repo.local="$TARGET/maven-repo"`，避免依赖/污染用户目录 `.m2`；`test-cases` 是独立 reactor，从该本地仓库消费刚 `install` 的业务模块，故它的 `mvn test` 必须带**同一个** `-Dmaven.repo.local`。即在下文命令前先设置：

```bash
SETTINGS_OPT=""; [ -f "$TARGET/maven-settings.xml" ] && SETTINGS_OPT="-s $TARGET/maven-settings.xml"
REPO_OPT="-Dmaven.repo.local=$TARGET/maven-repo"
```

---

## 步骤 1 — 先跑验证套件（永远第一步）

业务模块与黑盒测试是两个独立 reactor，`test-cases/` 从本地 `.m2` 消费业务模块，所以**必须先 `install` 再跑黑盒**：

```bash
# 1a. 构建业务模块并装入本地仓库（跳过业务模块自测，加速）
mvn $SETTINGS_OPT $REPO_OPT -f code/pom.xml install -DskipTests

# 1b. 跑 24 个公开黑盒用例（同一个 REPO_OPT，才能找到刚装入的业务模块）
mvn $SETTINGS_OPT $REPO_OPT -f test-cases/pom.xml test
```

把两条命令的结果（BUILD SUCCESS/FAILURE、Tests run/Failures/Errors、失败的具体 `pubNNN_*` 方法名）记录到 `result/output.md`，并回读 Stage 2 打印的 apply-report 中 `skipped/failed` 的数量。

## 步骤 2 — 分支判断

- **1b 全绿（Tests run=N, Failures=0, Errors=0）且 apply-report 无 skipped/failed** → 进入**快路径**：只做**轻量抽查**（见步骤 3.0），确认后即收工，写 `result/output.md` 的 `STATUS: DONE`。这是省 token/时长、拿性能分的正常路径——Stage 2 通常已把已知不一致全部修好。
- **有失败用例，或 apply-report 有 skipped/failed** → 进入**深核路径**（步骤 3.1 起），且**只针对失败涉及的模块**，不要逐份核对全部 12 个 checklist（全绿时那纯烧 token）。

---

## 步骤 3 — 深核复核

### 3.0 轻量抽查（快路径也做，留真实推理痕迹）

从 2~3 份高价值 checklist（如 `order.md`、`payment.md`、`promotion.md`）各抽 1 条强规则，打开对应源文件确认其已符合期望（例如：`OrderController` 创建订单返回 201；`MonetaryUtil.roundToCent` 用 `HALF_UP`；DISCOUNT 券折扣公式方向正确）。把「抽查了哪几条、是否符合」写进 `logs/trace/`。**只读不改**。

### 3.1 定位失败 → 映射到模块 → 打开 checklist

把每个失败的 `pubNNN_*` 用例映射到它考核的模块，然后打开对应清单（相对本技能目录）：

```
../../fixer/checklist/<module>.md
```

模块清单一览：`common.md user.md product.md inventory.md cart.md order.md payment.md promotion.md logistics.md loyalty.md review.md app.md`。清单每条都写明「**看什么 → 期望什么（设计依据）**」，你只需核对与机械修正，**不需要自己从设计文档反推期望值**（发现环节已在 Stage 1 做掉）。

### 3.2 带护栏的单点修复（每处修复严格照此顺序）

对 checklist 里核出的、与设计契约不符的**某一处**：

```bash
# (1) 改动前先备份——不能依赖 git，评测机上的材料未必是 git 仓库
cp "$TARGET/code/ecommerce-<X>/.../Foo.java" "$TARGET/code/ecommerce-<X>/.../Foo.java.bak"

# (2) 按 checklist 给出的「期望」做最小改动（编辑源文件）

# (3) 编译门控：只编译+自测被改模块，快速发现编译/单测破坏
mvn -s maven-settings.xml -pl ecommerce-<X> -f code/pom.xml test

# (4) 通过后，重装该模块并重跑黑盒，确认目标失败用例转绿、且通过总数未下降
mvn -s maven-settings.xml -pl ecommerce-<X> -am -f code/pom.xml install -DskipTests
mvn -s maven-settings.xml -f test-cases/pom.xml test
```

**回滚条件（任一满足即回滚）**：(3) 编译失败或单测出现新失败；或 (4) 黑盒通过总数相比修改前**下降**。回滚：

```bash
mv "$TARGET/code/ecommerce-<X>/.../Foo.java.bak" "$TARGET/code/ecommerce-<X>/.../Foo.java"
```

并把「改了什么、为何回滚」如实写进 `result/output.md`。

### 3.3 有界重试

针对**同一个**失败用例，最多重试一次（换一条 checklist 依据或换一处改法）。仍不绿则停手，如实记录为「未能修复」，不无限重试（保护稳定性与性能分）。修复彻底完成后可删除 `.bak` 备份。

---

## 步骤 4 — 收尾

- 写 `result/output.md`：Stage 2 apply-report 摘要、单元测试通过数、黑盒通过数（`X/24`）、每处 Stage 3 深核/回滚的如实记录、以及末尾一行 `STATUS: DONE`。
- 写 `logs/trace/`：验证命令输出、抽查/深核的推理过程。
- 修复后的工程即目标处的 `<target-root>/code/`，无需另外导出。

## 命令速查

> 下表为简洁略去统一前缀；实际执行每条 `mvn` 均按上文「构建命令规范」带 `$SETTINGS_OPT $REPO_OPT`（`-s`（存在时）+ `-Dmaven.repo.local=$TARGET/maven-repo`）。`test-cases` 的 `test` 也须带同一个 `$REPO_OPT`。

| 目的 | 命令 |
|---|---|
| 构建并装入 .m2 | `mvn -s maven-settings.xml -f code/pom.xml install -DskipTests` |
| 跑黑盒（24 例） | `mvn -s maven-settings.xml -f test-cases/pom.xml test` |
| 单模块编译门控 | `mvn -s maven-settings.xml -pl ecommerce-<X> -f code/pom.xml test` |
| 单模块重装 | `mvn -s maven-settings.xml -pl ecommerce-<X> -am -f code/pom.xml install -DskipTests` |
| 跑单个黑盒用例 | `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub008_createBasicOrder test` |

黑盒用例分布：`PubBasicFlowTest`（PUB-001..016）、`PubAdditionalBehaviorTest`（PUB-101..108），编号对应 README 第 8 节。模块 artifactId 均为 `ecommerce-<module>`（如 `ecommerce-order`）。
