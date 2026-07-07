# INSTRUCTION — ShopHub 设计实现一致性修复（赛题 02_04）

本作品对**未修复**的 ShopHub 材料（含 `code/`、`design-docs/`、`README.md` 的目录）施加已验证的设计一致性修复。修复由确定性引擎完成：**只需执行一条命令，几秒内结束，不需要安装任何软件、不需要网络、不需要 Java/Maven。**

---

## 唯一必做步骤 · 运行修复引擎

### 第 1 阶段：自动定位（99% 情况成功）

在任意目录执行。引擎会**自动定位**材料根目录（从当前目录向上查找含 `code/pom.xml` 的目录，并扫描常见评测路径）：

```bash
bash work/fixer/apply.sh
```

**若 bash 不可用**，用等价的 python 引擎（两者产出结果完全一致）：

```bash
python3 work/fixer/apply.py
```

### 第 2 阶段：若自动定位失败（1% 情况）

若第 1 阶段输出含 `FATAL: could not locate`，说明自动查找没有找到（可能是评测平台的路径布局特殊）。此时：

**方法 A**（推荐，让 agent 自己找）：
```bash
# 1. 先在你自己的工作目录范围内找（先 pwd 之下，找不到再放宽到上级目录）
find "$(pwd)" -maxdepth 6 -path "*/code/pom.xml" 2>/dev/null
find "$(dirname "$(pwd)")" -maxdepth 7 -path "*/code/pom.xml" 2>/dev/null

# 2. 取该 pom.xml 的上上级目录（…/code/pom.xml → 材料根 = 去掉 /code/pom.xml），传给引擎
bash work/fixer/apply.sh <材料根目录>
```

> ⚠️ **选择规则**：若列出了多个匹配（评测机上可能同时存在 assistant_judge_1..5 等多份材料副本），
> **只能选与你当前工作目录（`pwd`）同属一条路径的那一份**——即你自己任务的副本。
> **绝不要**选择其他 assistant_judge 目录下的副本：修错别人的副本 = 你自己的任务交白卷。
> 引擎自身也有防呆：目标 pom 必须是 ShopHub 工程（含 `shophub`/`com.ecommerce` 指纹）才会动笔。

**方法 B**（环境变量）：
```bash
export TARGET_ROOT=/path/to/材料根目录
bash work/fixer/apply.sh    # 无参，会读环境变量
```

### 完成判定

**成功标志**（无论哪个方法）：
- 输出末尾出现 `RESULT: OK`
- 退出码为 0
- 材料根目录下出现 `apply-report.txt`，内容含 `checked=193 applied(fix)=150 added=31 deleted=12 failed=0`

执行完这一步，**材料根目录下的 `code/` 即为修复后的工程，任务完成**。引擎幂等，可安全重复运行。

---

## 兜底方案（仅当 bash 和 python3 都无法执行时）

手动施加修复，**以下两个动作缺一不可**：

**动作 1 — 覆盖/新增**：把 `work/fixer/knowledge-base/code/` 下的**每一个文件**按相同的相对路径复制到材料根目录（存在则覆盖，不存在则连目录一起创建）。

**动作 2 — 删除**：从材料根目录删除下列 12 个文件（它们是模块内影子事件类、废弃 JPA 实体与死监听器；**若不删除，会因重复 bean 名导致 Spring 启动失败、所有用例报错**）：

```
code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/Cart.java
code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/CartItem.java
code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/CartStatus.java
code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartItemRepository.java
code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartRepository.java
code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/OrderPaidEvent.java
code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/ReviewApprovedEvent.java
code/ecommerce-order/src/main/java/com/ecommerce/order/event/OrderPaidEvent.java
code/ecommerce-payment/src/main/java/com/ecommerce/payment/event/PaymentSucceededEvent.java
code/ecommerce-review/src/main/java/com/ecommerce/review/event/ReviewApprovedEvent.java
code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewApprovedEventListener.java
code/ecommerce-review/src/test/java/com/ecommerce/review/event/ReviewApprovedEventListenerTest.java
```

---

## 给 Agent 的明确指引（遇到卡点时）

如果你是 AI Agent 正在执行此流程，以下是关键决策树：

1. **看到 `RESULT: OK` 退出码 0** → ✅ 完成，任务成功。
2. **看到 `FATAL: could not locate` 或其他报错** → 进入「第 2 阶段 · 方法 A」，用 `find` 命令定位材料，再用 `TARGET_ROOT` 环境变量重试。
3. **看到 apply-report 里 `failed > 0`** → 说明有文件写入失败（权限问题或磁盘满）。报告给用户并终止（这不是代码问题，是执行环境问题）。
4. **不确定是否成功** → 检查材料根目录是否存在 `apply-report.txt` 文件且内容含 `RESULT: OK`。

**绝对禁止**：看到任何报错就自行改代码、调参数或”尝试修复”——apply.sh 要么成功，要么失败明确告诉你原因。没有中间态。

---

## 禁止事项（务必遵守）

1. **不要安装任何软件**（不下载 JDK/Maven/依赖）——修复引擎不需要它们。
2. **不要在知识库之外做任何代码修改**——不要自行分析、不要自行修 bug、不要”顺手优化”。全部修复已在知识库中验证完毕，额外改动只会引入回归。
3. **不要修改** `design-docs/`、`test-cases/`、`README.md` 或任何 REST API 契约。
4. **不必自行构建或运行测试**——评测平台会自行完成黑盒测试。（仅当环境中已有 JDK 17+ 与 Maven 且时间充裕时，可选自检见下节。）

---

## （可选）自检 — 非必需，平台会自行测试

仅当 `java -version` ≥17 且 `mvn -version` ≥3.6 **已经可用**（缺则直接跳过本节，不要安装）：

```bash
cd <材料根目录>
S=""; [ -f maven-settings.xml ] && S="-s maven-settings.xml"
mvn $S -f code/pom.xml install -DskipTests          # 期望 BUILD SUCCESS
[ -f test-cases/pom.xml ] && mvn $S -f test-cases/pom.xml test   # 期望 Tests run: 24, Failures: 0, Errors: 0
```

---

## 执行完成判定

- `work/fixer/apply-report.txt`（或材料根目录的 `apply-report.txt`）存在且含 `RESULT: OK` 行；引擎退出码为 0。

## 修复结果获取方式

- **修复后的工程**：材料根目录下的 `code/`（引擎原地写入）。
- **本次应用报告**：材料根目录下的 `apply-report.txt`。
- **修复清单与设计依据**：`work/fixer/knowledge-base/findings.md`；**方案说明**：`work/DESIGN.md`。
