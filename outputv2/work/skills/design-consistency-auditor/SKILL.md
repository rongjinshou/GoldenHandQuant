---
name: design-consistency-auditor
description: ShopHub「设计-实现一致性」修复流水线的离线审查技能（Stage 1，可复跑）。逐模块把 code/ 与 design-docs/（04-15 + 附录 A/C/D）和 README 冻结契约对齐，把每处不一致记录为一条 finding（症状 → 设计依据 → 修复），在本地实修并验证，最终产出确定性引擎 work/fixer/apply.sh 直接消费的 knowledge-base/（完整修复文件 + baseline-hashes.txt + deletions.txt + findings.md）。换一份新材料重跑本技能即可从零重建知识库——这是本作品「泛化能力」的可复跑证据链。
---

# design-consistency-auditor（Stage 1：离线审查）

本技能是三段式流水线的第一段，也是整套方案「不是硬编码答案、而是可复跑 AI 审查管线」的证据。它做一件事：**系统性地把每个模块的实现与其设计契约逐条比对，产出 `apply.sh` 的全部输入**。它可以在任意一份 ShopHub 材料上重跑；产物就是 `work/fixer/knowledge-base/`。

## 产物（即 Stage 2 的输入，务必逐项产全）

```
work/fixer/knowledge-base/
├── code/...                 每个被改文件的【完整最终内容】，按原始相对路径镜像 code/
├── baseline-hashes.txt      每个被改文件在【基线（未修复）材料】下的 SHA-256，格式：<sha256><空格><空格><相对路径>
├── deletions.txt            每个【应删除】文件的基线 SHA-256 + 相对路径（同上格式）
└── findings.md              人可读索引：症状 / 设计依据(章节) / 修复方式 / 对应改动文件
```

`apply.sh` 的语义依赖这三个清单：`code/` 提供覆盖内容、`baseline-hashes.txt` 用于 hash 门控（命中基线才是「确系待修复态」）、`deletions.txt` 用于删除影子类/JPA 实体等（留着会重新引入缺陷，例如两个同简单名的 `ReviewApprovedEventListener` 会在启动时触发 `ConflictingBeanDefinitionException`）。

## 模块 → 设计文档映射（审查时逐模块对照）

| 模块 | 主设计文档 | 相关附录 |
|---|---|---|
| ecommerce-user | `design-docs/04-用户服务设计.md` | A/C/D |
| ecommerce-product | `design-docs/05-商品服务设计.md` | A/C |
| ecommerce-inventory | `design-docs/06-库存服务设计.md` | A/C/D |
| ecommerce-cart | `design-docs/07-购物车服务设计.md` | A/B/C |
| ecommerce-order | `design-docs/08-订单服务设计.md` | A/C/D |
| ecommerce-payment | `design-docs/09-支付服务设计.md` + `14-发票与结算设计.md` | A/C/D |
| ecommerce-promotion | `design-docs/10-促销服务设计.md` | A/C |
| ecommerce-logistics | `design-docs/11-物流服务设计.md` | A/C/D |
| ecommerce-loyalty | `design-docs/12-积分与会员服务设计.md` | A/C/D |
| ecommerce-review | `design-docs/13-评价服务设计.md` | A/C/D |
| ecommerce-common | `design-docs/03-通用规范与非功能设计.md` + `15-本地通知组件设计.md` | C/D |
| ecommerce-app | `design-docs/02-系统架构.md` + `03` §5 | A |

外加全模块共同基准：`design-docs/03-通用规范与非功能设计.md`（金额/异常/幂等/响应格式/限流/审计）、`README.md` 第 6 节（冻结 REST 契约）、第 7 节（错误码）、附录 A（接口请求/响应体）、附录 C（数据模型/枚举）、附录 D（本地事件载荷）。

---

## 审查流程

### 步骤 0 — 记录基线并准备环境

```bash
git -C <repo> rev-parse HEAD          # 记下基线 commit（本作品为 1b1e88f），后续算 baseline-hashes 用它
# 构建命令规范：maven-settings.xml 存在才用 -s；所有 mvn 显式带 -Dmaven.repo.local 避免污染用户 .m2；
# test-cases（独立 reactor）跑 test 时须带同一个 -Dmaven.repo.local 才能找到刚 install 的业务模块。
S=""; [ -f maven-settings.xml ] && S="-s maven-settings.xml"; R="-Dmaven.repo.local=$PWD/maven-repo"
mvn $S $R -f code/pom.xml install -DskipTests   # 确认基线能构建
```

### 步骤 1 — 先做跨模块系统性修复（优先于单点）

若干缺陷是同一根因在多个模块重复表现，应作为**一次架构级修复**，避免各模块各改一次相互冲突：

- **影子事件类**：模块各自 `new` 了本地同名事件类，Spring `@EventListener` 按运行时类型分发，同名异包互不触发 → 把 `OrderCreatedEvent / OrderPaidEvent / PaymentSucceededEvent / ReviewApprovedEvent / ShipmentDeliveredEvent / RefundCompletedEvent` 的**唯一权威定义迁到 `ecommerce-common`**（所有模块都依赖 common，无循环依赖），发布方/监听方都引用 common 的类，删除各模块重复定义（进 `deletions.txt`）。
- **舍入模式**：`ecommerce-common/MonetaryUtil.roundToCent` 用 `HALF_DOWN`，应为 `HALF_UP`，一处改，全模块金额随之修正。
- **`@RateLimit` 未接入**：基础设施完整但零处使用 → 在 design-docs/03 §4 要求限流的 4 类接口加注解：登录(user)、支付回调(payment)、商品搜索(product)、创建订单(order)。
- **审计日志缺失**：design-docs/03 §6 列的 7 类操作未审计 → 在 `ecommerce-common` 建共享 `AuditLogEntry`+`AuditLogService`，7 个操作点接入。
- **错误码抄错**：`SKU_NOT_AVAILABLE` 应为 `PRODUCT_NOT_FOR_SALE`（product 与 cart 两处）。

### 步骤 2 — 逐模块审查（对每个模块重复）

对每个模块，打开其主设计文档与相关附录，逐类比对代码，把**每一处**不一致记成一条 finding：

1. **症状**：代码现在是什么、与哪条契约冲突（给出文件:行）。
2. **设计依据**：`design-docs/NN §X`（或附录 A/C/D 的具体表/字段）。
3. **修复**：改成什么（确切值/枚举/公式/状态迁移）。
4. **置信度**：definite（文档白纸黑字）/ suspicious（文档未写死、需 A/B 提交或进一步确认）。

**审查维度 checklist**（每个模块都过一遍，逐条落到具体代码）：

- **金额与舍入**：只用 `BigDecimal`；`HALF_UP`；入库保留 2 位小数；公式方向（折扣/满减/退款/运费/应付=商品+运费-优惠）与设计一致。
- **异常与错误码**：用 `com.ecommerce.common.exception` 体系（BusinessException 400 / ResourceNotFoundException 404 / AuthorizationException 401·403 / ValidationException 400 / ConflictException 409 / RateLimitException 429）；订单金额校验必须 `OrderValidationException` 而非 `IllegalArgumentException`；错误码字符串与 README 第 7 节一致。
- **幂等键**：创建订单 `externalOrderNo`、支付回调 `paymentNo+callbackSequence`、退款 `refundRequestNo`、物流回调 `trackingNo+eventTime+status`、发票 `invoiceRequestNo` —— 有字段且真的查重。
- **状态机**：合法迁移集合与设计一致（如 order 的 PAID 不得直接 →CANCELLED；logistics 严格 CREATED→PICKING→LABEL_PRINTED→OUTBOUND）。
- **事件契约（附录 D）**：发布/监听方、失败策略（失败记入事件失败表而非抛异常）、载荷字段齐全且类型正确；跨模块事件用 common 权威类。
- **响应格式**：错误响应 `{code, message, traceId, details}`；分页 `{page, size, total, items}` 且 total 正确。
- **限流 / 审计 / 缓存**：见步骤 1；另核对设计要求的缓存（购物车 Caffeine 7 天且不落库、商品详情 10 分钟、库存摘要 30 秒、运费模板 30 分钟）。
- **跨模块边界（design-docs/02 §3）**：只访问自己的表/Repository；跨模块查询走 `*QueryService`、写走领域服务或 `ApplicationEvent`；跨边界传 DTO 而非 JPA 实体；事务不依赖非关键监听器成功；通知只经 `LocalNotificationService`。

> 完整的逐模块发现母版见 `work/fixer/knowledge-base/findings.md`（本作品第一轮模块级 97 项：definite 80 / suspicious 17；该文件 §7 另记录了第二轮针对隐藏用例深层契约的 28 项追加发现，含尽调后明确放弃/暂缓项及理由）。重跑本技能时以「重新审出的 findings」为准，不要照抄旧结论。

### 步骤 3 — 本地实修 + 验证（每条 finding 都要）

1. 在 `code/` 里实际改代码修复该 finding。
2. 跑 `mvn $S $R -f code/pom.xml test`（`$S`/`$R` 见步骤0：settings 防御 + 显式本地仓库 `-Dmaven.repo.local`；含针对**无黑盒覆盖**模块新增的单元测试，用于锁定修复），再 `install -DskipTests` 后跑 `mvn $S $R -f test-cases/pom.xml test`（24 个公开黑盒用例应逐步转绿）。
3. 确认不引入新的编译/测试失败。suspicious 项逐条判断是否修，并在 `findings.md` 说明理由（例如枚举大范围改名前，先确认没有黑盒用例断言具体字符串）。

### 步骤 4 — 生成 knowledge-base（apply.sh 的输入）

全部修复合入后，从基线 commit 取「确切改动清单」并物化：

```bash
BASELINE=<基线commit>     # 本作品：1b1e88f
KB=work/fixer/knowledge-base

# 存在性判断务必用 git cat-file -e（退出码），不要用 `git show ... | sha256sum`
# 是否非空来判断——对基线不存在的路径，git show 退出码非0但 stdout 仍是空字节流，
# sha256sum 照样会读空输入算出一个"看似合法"的哈希（空字符串的 SHA-256，一个固定
# 值），导致新增文件被误记一条基线哈希，apply.sh 就会把它误判成"目标未命中基线"
# 而非"该走 ADD"。

# (1) 改动(含新增/重命名)文件 → 复制完整最终内容到 KB，改动的记录其在基线的 SHA-256
git -C <repo> diff --name-only --diff-filter=ACMR "$BASELINE"..HEAD -- code/ | while read -r rel; do
  mkdir -p "$KB/$(dirname "$rel")"
  cp "<repo>/$rel" "$KB/$rel"
  if git -C <repo> cat-file -e "$BASELINE:$rel" 2>/dev/null; then
    base=$(git -C <repo> show "$BASELINE:$rel" | sha256sum | awk '{print $1}')
    printf '%s  %s\n' "$base" "$rel" >> "$KB/baseline-hashes.txt"
  fi   # 基线不存在（新增文件）则不写 base 行，apply.sh 会走 [ADD]
done

# (2) 删除文件 → 记录其在基线的 SHA-256 到 deletions.txt（同样先判存在性）
git -C <repo> diff --name-only --diff-filter=D "$BASELINE"..HEAD -- code/ | while read -r rel; do
  if git -C <repo> cat-file -e "$BASELINE:$rel" 2>/dev/null; then
    base=$(git -C <repo> show "$BASELINE:$rel" | sha256sum | awk '{print $1}')
    printf '%s  %s\n' "$base" "$rel" >> "$KB/deletions.txt"
  fi
done

# (3) 重命名(R)的旧路径也要记入 deletions.txt —— --diff-filter=D 不包含重命名
# （git 把它归类为 R，不是 D），(1) 里的 ACMR 只处理了新路径，旧路径若不删除，
# apply.sh 不会知道要清理它。
git -C <repo> diff --name-status --diff-filter=R "$BASELINE"..HEAD -- code/ \
    | while IFS=$'\t' read -r status old new; do
  if git -C <repo> cat-file -e "$BASELINE:$old" 2>/dev/null; then
    base=$(git -C <repo> show "$BASELINE:$old" | sha256sum | awk '{print $1}')
    printf '%s  %s\n' "$base" "$old" >> "$KB/deletions.txt"
  fi
done
```

`baseline-hashes.txt` / `deletions.txt` 的行格式必须是 `<sha256>` + 两个空格 + `<相对路径>`（`apply.sh` 用 `awk '$2==p'` 精确匹配第二字段）。**`$rel` 已经包含 `code/` 前缀** —— 拼接目标路径时是 `$KB/$rel`，不是 `$KB/code/$rel`（否则会在知识库内部产生 `code/code/...` 的双重嵌套，apply.sh 会把每个文件都误判成目标不存在而全部走 ADD）。最后手写 `findings.md`：把每条 finding 整理成「症状 / 设计依据 / 修复 / 改动文件」表格，供评审抽查。

### 步骤 5 — 端到端自检（含 hash 门控与幂等）

把基线 commit 的 `code/`（未修复版）还原到临时目录模拟 judge-assets 布局，跑一遍完整链路验证：

1. `bash work/fixer/apply.sh <临时根>` → 检查 apply-report：每个文件 hash 命中基线、全部应用、`failed=0`。
2. 加载 `design-consistency-fixer/SKILL.md` 复核 + 跑验证套件 → 从「脏」状态自动收敛到全绿（24/24）。
3. 再跑一次 `apply.sh` 验证**幂等**：第二次全部 `[OK] already fixed`、`failed=0`、不破坏任何文件。
4. 可选：用一个全新、不带审查上下文的 agent，仅凭 `SKILL.md`+checklist+一份未修复材料，检验能否复现同样修复（「即使很蠢的模型也能做对」的独立性检验）。
