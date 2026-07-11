# B18 · S3-audit — 审计基础设施与 7 类操作接入

设计依据统一是 `design-docs/03-通用规范与非功能设计.md` §6："以下操作必须记录审计日志：
①用户冻结和解冻 ②商品上下架 ③库存人工调整 ④订单取消审核 ⑤退款审核和仓库验收 ⑥发票开具
⑦结算批次生成。审计日志至少包含操作者、操作类型、业务 ID、操作前状态、操作后状态、操作时间和备注。"

本批把审计基础设施（common 新增一张共享审计表 + 一个 `AuditLogService`）和 6 类操作的接入点放在
同一批（**AUD-1 是基础设施，AUD-2..AUD-7 是接入点，互相之间也没有依赖顺序，可以任意顺序改**），
不依赖 B01-B17 任何一批就能独立生效（AUD-2/AUD-3/AUD-4/AUD-7 的 controller 侧改动只新增方法参数
/一行取值代码，不改既有安全配置，也不读其他卡片新建的类）。

**范围说明（7 类 vs 6 类）**：标题写"7 类操作接入"是对齐 design-docs 03§6 的原文分类，但本批实际只
接入其中 6 类。第 4 类"订单取消审核"（`POST /api/v1/admin/orders/{orderId}/cancel-review` →
`OrderCancelService.reviewCancel(...)`）**不在本批范围内**——该方法已经在调用 order 模块自己的
`orderService.recordEvent(...)`（一套独立于本批共享审计表的订单事件历史机制），不属于本批要接入
的 `com.ecommerce.common.audit.AuditLogService`。不要因为标题里的"7 类"就顺手在
`OrderCancelService` 里也加一份 `auditLogService.record(...)`——这不是本批卡片，真要做请单开一张
新卡，不要在这几张卡里夹带。

**每张卡都会改一个 Service 的构造函数（新增 `AuditLogService` 依赖）或方法签名（新增
`operatorId`/`Authentication` 参数）。这类改动最容易在"看起来改完了"之后被现有单元测试的编译错误
绊倒**——`mvn install -DskipTests` 只跳过测试**执行**，测试**编译**（`test-compile`）仍然会跑，
任何一个测试文件因为调用了旧签名而编译不过，整个模块乃至整个 reactor 都装不进本地仓库，后面的
黑盒测试会因为找不到构建产物而全灭。每张卡的"改法"最后都单列了"同步改测试"，**必须一起做**，不是
可选项。改完每张卡建议本地跑一次对应模块的 `test-compile` 确认（见各卡"验收"）。

修完本批立即 `bash work/harness/ratchet.sh verify`。

---

### AUD-1 | 审计基础设施完全缺失——AuditLogService 及其依赖类在基线中不存在

- 风险: high · 置信度: definite
- **文件**（均为【新增】）:
  1. `code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogEntry.java`
  2. `code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogRepository.java`
  3. `code/ecommerce-common/src/main/java/com/ecommerce/common/audit/AuditLogService.java`
- **现状**: `com.ecommerce.common.audit` 包在基线中完全不存在（`grep -rn "package com.ecommerce.common.audit" code/` 零命中）。design-docs/03 §6 列出的 7 类必须审计操作，没有一类真正落库——不是"审计逻辑写错了"，是审计这件事从未被实现，其余业务模块也就无从注入。
- **期望**: common 模块提供一个所有业务模块可复用的共享审计服务：一张审计表 + 一个 `record(...)` 写入方法。依据 design-docs/03 §6（审计记录字段：操作者、操作类型、业务 ID、操作前状态、操作后状态、操作时间、备注）。design-docs/附录C 未定义 `audit_log` 物理表结构，字段设计以 03 §6 的文字要求为准。
- **改法**: 新增 3 个文件，包路径 `com.ecommerce.common.audit`（**类名、字段名、方法签名必须与下方完全一致**——AUD-2..AUD-7 全部按这个签名调用）。

  **1) `AuditLogEntry.java`**（JPA 实体，继承 `com.ecommerce.common.model.BaseEntity`——继承后自动获得 `id`/`createdAt`/`updatedAt`，`createdAt` 即"操作时间"，不用单独加时间字段）：

  ```java
  package com.ecommerce.common.audit;

  import com.ecommerce.common.model.BaseEntity;
  import jakarta.persistence.Column;
  import jakarta.persistence.Entity;
  import jakarta.persistence.Table;

  @Entity
  @Table(name = "audit_log_entries")
  public class AuditLogEntry extends BaseEntity {

      @Column(name = "operator_id", nullable = false)
      private String operatorId;

      @Column(name = "action_type", nullable = false)
      private String actionType;

      @Column(name = "business_id", nullable = false)
      private String businessId;

      @Column(name = "before_state")
      private String beforeState;

      @Column(name = "after_state")
      private String afterState;

      @Column(name = "remark", length = 1000)
      private String remark;

      public AuditLogEntry() {
      }

      public AuditLogEntry(String operatorId, String actionType, String businessId,
                            String beforeState, String afterState, String remark) {
          this.operatorId = operatorId;
          this.actionType = actionType;
          this.businessId = businessId;
          this.beforeState = beforeState;
          this.afterState = afterState;
          this.remark = remark;
      }

      public String getOperatorId() { return operatorId; }
      public String getActionType() { return actionType; }
      public String getBusinessId() { return businessId; }
      public String getBeforeState() { return beforeState; }
      public String getAfterState() { return afterState; }
      public String getRemark() { return remark; }
  }
  ```

  注意：`beforeState`/`afterState` **不带** `nullable = false`（有的操作没有"操作前状态"，例如发票开具是从无到有，见 AUD-6）；`operatorId`/`actionType`/`businessId` 三个必须非空。字段全部只读（无 setter），只能通过构造函数一次性赋值。

  **2) `AuditLogRepository.java`**：

  ```java
  package com.ecommerce.common.audit;

  import org.springframework.data.jpa.repository.JpaRepository;
  import org.springframework.stereotype.Repository;

  @Repository
  public interface AuditLogRepository extends JpaRepository<AuditLogEntry, Long> {
  }
  ```

  不需要任何自定义查询方法——当前没有黑盒可观测的查询端点消费它，不要因为"看起来应该有个查询接口"就顺手加 REST 端点或自定义 finder，那是本批范围之外的臆造。

  **3) `AuditLogService.java`**：

  ```java
  package com.ecommerce.common.audit;

  import org.springframework.stereotype.Service;

  @Service
  public class AuditLogService {

      private final AuditLogRepository auditLogRepository;

      public AuditLogService(AuditLogRepository auditLogRepository) {
          this.auditLogRepository = auditLogRepository;
      }

      public void record(String operatorId, String actionType, String businessId,
                          String beforeState, String afterState, String remark) {
          auditLogRepository.save(new AuditLogEntry(operatorId, actionType, businessId,
                  beforeState, afterState, remark));
      }
  }
  ```

  `@Service`/`@Repository` 让 Spring 自动注册 bean 并完成依赖注入——**不要**额外写 `@Configuration`/`@EnableJpaRepositories`/`@ComponentScan`。`ecommerce-app` 的 `ShopHubApplication` 已经是
  `@ComponentScan(basePackages = "com.ecommerce")` + `@EnableJpaRepositories(basePackages = "com.ecommerce")` + `@EntityScan(basePackages = "com.ecommerce")`（对全部 `com.ecommerce.*` 生效），
  common 模块自己的 `CommonAutoConfiguration` 也已经是 `@ComponentScan(basePackages = "com.ecommerce.common")`——新包 `com.ecommerce.common.audit` 自动被两层扫描覆盖，无需改动任何启动类/扫描配置。表结构由 `spring.jpa.hibernate.ddl-auto: update`（`code/ecommerce-app/src/main/resources/application.yml`）在启动时自动建表，不需要手写 DDL/migration 脚本。

  各业务模块（user/product/inventory/payment）的 `pom.xml` 已经依赖 `ecommerce-common`（`grep ecommerce-common code/ecommerce-*/pom.xml` 四个模块均命中一次），**不需要新增任何 Maven 依赖**。

- **验收**:
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am install -DskipTests` 编译通过。
  - 可选新增单测（不计分，仿造）：`new AuditLogService(mockRepo).record("admin-1","SKU_ON_SHELF","sku-42","OFF_SHELF","ON_SHELF","manual review")` 后，`verify(mockRepo).save(...)` 捕获到的 `AuditLogEntry` 六个字段与入参一一对应。
  - 全量黑盒起服务不因新增实体报错（Hibernate 能正常为 `audit_log_entries` 建表）。
- **勿犯**:
  - 不要给 `AuditLogEntry` 加业务模块特定字段（比如 `skuId`/`orderId`）——它是跨模块共享表，业务标识统一走通用的 `businessId: String`（各接入点自己把业务主键 `String.valueOf(...)` 转进去），不要为了"类型安全"拆分成多个字段或多张表。
  - 不要给 `record(...)` 签名加操作时间参数——`createdAt` 由 `BaseEntity` 的 `@CreatedDate` 自动写入。
  - 不要给 `AuditLogService`/`AuditLogRepository` 加 `@Transactional`/独立事务注解——它就是一次普通的 `save` 调用，事务边界由调用方（AUD-2..AUD-7 各业务 Service 自己的 `@Transactional` 方法）决定，本类不新开、不改变任何事务。

---

### AUD-2 | 用户冻结/解冻无审计日志，且拿不到操作者身份

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserAuthService.java`
  2. `code/ecommerce-user/src/main/java/com/ecommerce/user/controller/AdminUserController.java`
  3. （同步改测试）`code/ecommerce-user/src/test/java/com/ecommerce/user/service/UserAuthServiceTest.java`
  4. （同步改测试）`code/ecommerce-user/src/test/java/com/ecommerce/user/controller/AdminUserControllerTest.java`
- **现状**: `UserAuthService.freezeUser(Long userId)`/`unfreezeUser(Long userId)` 只有一个 `userId` 参数——不接收、不记录操作者是谁；方法体只做状态迁移 + save，没有任何审计调用。`AdminUserController.freezeUser`/`unfreezeUser` 对应也只有 `@PathVariable Long userId` 一个参数，拿不到当前登录的管理员身份。
- **期望**: 用户冻结/解冻是 design-docs/03 §6 第 1 类必须审计操作。操作者为当前登录管理员，审计记录需体现操作前后的 `UserStatus`。
- **改法**:
  1. `UserAuthService` 构造函数新增 `AuditLogService auditLogService` 依赖（跟其余 `final` 字段一样声明 + 赋值；`import com.ecommerce.common.audit.AuditLogService;`）。
  2. `freezeUser`/`unfreezeUser` 各加一个 `String operatorId` 参数（**签名变为 `freezeUser(Long userId, String operatorId)` / `unfreezeUser(Long userId, String operatorId)`**，`operatorId` 在 `userId` 之后）。方法体在 `user.setStatus(...)` 之前用局部变量捕获前置状态（`UserStatus before = user.getStatus();`），在 `userRepository.save(user)` 之后调用：
     ```java
     auditLogService.record(operatorId, "USER_FREEZE", String.valueOf(userId),
             before.name(), UserStatus.FROZEN.name(), null);
     ```
     （`unfreezeUser` 同理：`actionType` 用 `"USER_UNFREEZE"`，`afterState` 用 `UserStatus.ACTIVE.name()`。）
  3. `AdminUserController` 两个端点方法各加一个 `Authentication authentication` 方法参数（`import org.springframework.security.core.Authentication;`），调用服务时把 `authentication.getName()` 作为第二个实参传入：
     ```java
     @PostMapping("/api/v1/admin/users/{userId}/freeze")
     public ResponseEntity<Void> freezeUser(@PathVariable Long userId, Authentication authentication) {
         userAuthService.freezeUser(userId, authentication.getName());
         return ResponseEntity.ok().build();
     }
     ```
     （`unfreezeUser` 同理）。Spring MVC 会自动把当前安全上下文的 `Authentication` 绑定到该方法参数，不需要手动读 `SecurityContextHolder`。
  4. **同步改 `UserAuthServiceTest`**（该类用 `@InjectMocks`，构造函数新增的依赖只需要加一个匹配类型的 `@Mock` 字段，不用改任何显式 `new UserAuthService(...)` 调用——本文件里没有这种调用）：
     - 加字段 `@Mock private AuditLogService auditLogService;`（`import com.ecommerce.common.audit.AuditLogService;`）。
     - 把文件里所有 `userAuthService.freezeUser(<id>)` 改成 `userAuthService.freezeUser(<id>, "admin-1")`，所有 `userAuthService.unfreezeUser(<id>)` 改成 `userAuthService.unfreezeUser(<id>, "admin-1")`（含 `assertThatThrownBy(() -> ...)` 里的调用；"admin-1" 只是占位符，字符串内容不影响编译）。
  5. **同步改 `AdminUserControllerTest`**（`@WebMvcTest` + 真实 JWT 安全过滤链，`Authentication` 由请求头里的 Bearer token 解析得到，principal 是发 token 时传入的管理员 `userId`（本文件里是 `1L`），`Authentication.getName()` 对非 `UserDetails` 主体会退化为该对象的 `toString()`，也就是字符串 `"1"`）：
     - `verify(userAuthService).freezeUser(5L);` 改成 `verify(userAuthService).freezeUser(5L, "1");`。
     - `verify(userAuthService).unfreezeUser(5L);` 改成 `verify(userAuthService).unfreezeUser(5L, "1");`。
     - **不要改** `@Import({JwtTokenProvider.class, SecurityConfig.class})` 那一行——不管它此刻写的是 `SecurityConfig` 还是别的类名，都是别的卡片（安全配置去重）的范围，本卡不碰。
- **验收**:
  - `POST /api/v1/admin/users/{userId}/freeze`（ADMIN 登录态）返回 200 后，新增一条审计记录：`actionType=USER_FREEZE`，`businessId=<userId>`，`beforeState`/`afterState` 为冻结前后的 `UserStatus`，`operatorId=<当前管理员>`。`unfreeze` 同理。
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-user -am test-compile` 编译通过。
- **勿犯**:
  - `login()`/`activate()` **不属于**本卡范围——不要顺手给它们加审计调用，03 §6 的 7 类操作里没有"登录"或"激活"。
  - 不要把 `auditLogService.record(...)` 包 try-catch 或另开 `REQUIRES_NEW` 事务——参考实现是在业务方法自身的 `@Transactional` 内直接同步调用，不做失败隔离（03 §6 没有像 §7 通知、§8 事件监听器那样要求"失败不阻断主流程"，不要自行加戏）。
  - `freezeUser`/`unfreezeUser` 参数顺序是 `(Long userId, String operatorId)`，`operatorId` 在后——四处调用点（Service 方法体、Controller 两个端点、两个测试类）参数顺序必须一致，写反了编译不报错但语义错，`AuditLogEntry.operatorId` 会存成用户 ID。
  - 别漏改 `UserAuthServiceTest`/`AdminUserControllerTest` 的既有调用点——漏一个就是 `ecommerce-user` 模块 `test-compile` 失败，`mvn install -DskipTests` 整体失败，后面所有黑盒用例因为业务模块没装进本地仓库而全灭。

---

### AUD-3 | 商品上下架无审计日志

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-product/src/main/java/com/ecommerce/product/service/SkuService.java`
  2. `code/ecommerce-product/src/main/java/com/ecommerce/product/controller/AdminProductController.java`
  3. （同步改测试）`code/ecommerce-product/src/test/java/com/ecommerce/product/service/SkuServiceTest.java`
  4. （同步改测试）`code/ecommerce-product/src/test/java/com/ecommerce/product/controller/AdminProductControllerTest.java`
- **现状**: `SkuService.onShelf(Long skuId)`/`offShelf(Long skuId)` 单参数，不接收操作者，方法体只做状态迁移 + save，无审计调用。`AdminProductController.onShelf`/`offShelf` 只有 `@PathVariable Long skuId`。
- **期望**: 商品上下架是 design-docs/03 §6 第 2 类必须审计操作，操作者为当前登录管理员，前后状态为 `SkuStatus`。
- **改法**（与 AUD-2 同一模式，字段名不同）:
  1. `SkuService` 构造函数新增 `AuditLogService auditLogService` 依赖（`import com.ecommerce.common.audit.AuditLogService;`；**只加这一个新依赖，不要顺手加缓存管理器之类别的依赖，那是另一张卡的范围**）。
  2. `onShelf`/`offShelf` 各加 `String operatorId` 参数（**`onShelf(Long skuId, String operatorId)` / `offShelf(Long skuId, String operatorId)`**）。方法体在 `sku.setStatus(...)` 之前捕获 `SkuStatus beforeStatus = sku.getStatus();`，在 `skuRepository.save(sku);` 之后调用（如果这一行之后此刻已经有其他卡片新增的代码，比如缓存失效调用，插在那些代码之后即可，先后顺序不影响审计本身）：
     ```java
     auditLogService.record(operatorId, "SKU_ON_SHELF", String.valueOf(skuId),
             beforeStatus.name(), SkuStatus.ON_SHELF.name(), null);
     ```
     （`offShelf` 同理：`actionType` 用 `"SKU_OFF_SHELF"`，`afterState` 用 `SkuStatus.OFF_SHELF.name()`。）
  3. `AdminProductController` 的 `onShelf`/`offShelf` 各加 `Authentication authentication` 参数（`import org.springframework.security.core.Authentication;`），调用处传 `authentication.getName()`（写法与 AUD-2 的 `AdminUserController` 一致）。
  4. **同步改 `SkuServiceTest`**（`@InjectMocks`，不涉及显式构造调用）：
     - 加字段 `@Mock private AuditLogService auditLogService;`。
     - 文件里所有 `skuService.onShelf(<id>)` 改 `skuService.onShelf(<id>, "admin-1")`，所有 `skuService.offShelf(<id>)` 改 `skuService.offShelf(<id>, "admin-1")`（含 `assertThatThrownBy` 里对 DELETED SKU 的调用）。
  5. **同步改 `AdminProductControllerTest`**（这个测试类用的是 `MockMvcBuilders.standaloneSetup(controller).build()`，**不是** `@WebMvcTest`，没有真实 Spring Security 过滤链——用 MockMvc 请求构造器自带的 `.principal(...)` 方法直接给这次请求设置一个 `Principal`，Spring MVC 的 `Authentication` 参数解析器会直接拿到它，不需要引入任何 Spring Security 测试基础设施）：
     - 加 `import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;`。
     - `doNothing().when(skuService).onShelf(1L);` 改成 `doNothing().when(skuService).onShelf(eq(1L), any());`（`eq`/`any` 静态导入本文件已有）。
     - 给 on-shelf 测试的 `mockMvc.perform(post(...))` 链上加 `.principal(new UsernamePasswordAuthenticationToken("admin-1", null))`：
       ```java
       mockMvc.perform(post("/api/v1/admin/products/sku/1/on-shelf")
                       .principal(new UsernamePasswordAuthenticationToken("admin-1", null)))
               .andExpect(status().isOk());

       verify(skuService).onShelf(1L, "admin-1");
       ```
     - off-shelf 测试同理（`doNothing().when(skuService).offShelf(2L)` → `offShelf(eq(2L), any())`；`.principal(new UsernamePasswordAuthenticationToken("admin-2", null))`；`verify(skuService).offShelf(2L, "admin-2")`——用例里 on/off 两个测试用的占位用户名不同，照抄即可，不影响正确性，只要 `.principal(...)` 里的名字和 `verify(...)` 里的期望值一致）。
- **验收**:
  - `POST /api/v1/admin/products/sku/{skuId}/on-shelf`（ADMIN）返回 200 后新增审计记录：`actionType=SKU_ON_SHELF`，`businessId=<skuId>`，`beforeState`/`afterState` 为迁移前后的 `SkuStatus`，`operatorId=<管理员>`。`off-shelf` 同理。
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-product -am test-compile` 编译通过。
- **勿犯**:
  - `createSku(...)` 不在本卡范围——03 §6 只列"上下架"，不含"创建"，不要加审计。
  - 基线里 `onShelf`/`offShelf` 对 `DELETED` 状态 SKU 抛的是 `ValidationException`（400）——**改成 409/`ConflictException` 是另一张卡的范围**，本卡不碰这个异常分支，也不用管它此刻到底抛哪种异常：审计调用只加在成功迁移的路径上，异常分支走 `throw` 直接返回，不会执行到审计那一行，两张卡互不干扰。
  - 不要给审计调用加 try-catch/独立事务（理由同 AUD-2）。
  - `AdminProductControllerTest` 的 `.principal(...)` 写法是 MockMvc 原生能力（`MockHttpServletRequestBuilder`），不需要也不要为了这一个测试去引入 `spring-security-test` 的 `@WithMockUser` 或改造 `standaloneSetup(...)` 成 `@WebMvcTest`——那是不必要的大改，`.principal(...)` 已经够用。

---

### AUD-4 | 库存人工调整无审计日志（调整记录本身也缺操作者字段）

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/entity/StockAdjustment.java`
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/StockAdjustmentService.java`
  3. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/controller/AdminInventoryController.java`
  4. （同步改测试）`code/ecommerce-inventory/src/test/java/com/ecommerce/inventory/service/StockAdjustmentServiceTest.java`
  5. （同步改测试）`code/ecommerce-inventory/src/test/java/com/ecommerce/inventory/controller/AdminInventoryControllerTest.java`
- **现状**: `StockAdjustment` 实体没有 `operatorId` 字段；`StockAdjustmentService.create(Long warehouseId, Long skuId, int afterQty, String reason)` 四参数，不接收操作者，也没有调用共享审计服务；`AdminInventoryController.createAdjustment(...)` 直接 `return stockAdjustmentService.create(warehouseId, skuId, afterQty, reason);`，完全不碰 `SecurityContextHolder`。
- **期望**: 库存人工调整是 design-docs/03 §6 第 3 类必须审计操作，"审计日志至少包含操作者"——本模块自己的 `StockAdjustment` 记录也应该带操作者字段（不只是共享审计表要有），因为它本身就是该功能的业务记录。
- **改法**:
  1. `StockAdjustment.java` 在 `reason` 字段后面加：
     ```java
     @Column(name = "operator_id", nullable = false)
     private String operatorId;
     ```
     配套 `getOperatorId()`/`setOperatorId(String operatorId)`。
  2. `StockAdjustmentService` 构造函数新增 `AuditLogService auditLogService` 依赖。`create(...)` 方法签名加第五个参数 `String operatorId`（**`create(Long warehouseId, Long skuId, int afterQty, String reason, String operatorId)`**，`operatorId` 在最后一位）。方法体里，在 `adjustment.setReason(reason);` 后面加 `adjustment.setOperatorId(operatorId);`；在 `StockAdjustment saved = stockAdjustmentRepository.save(adjustment);` 之后调用：
     ```java
     auditLogService.record(operatorId, "INVENTORY_ADJUSTMENT", String.valueOf(skuId),
             String.valueOf(beforeQty), String.valueOf(afterQty), reason);
     ```
     `businessId` 用的是 `skuId`（不是 `adjustment` 自增 id，也不是 `warehouseId`），`beforeState`/`afterState` 是数量的字符串形式，`remark` 直接用 `reason`。
  3. `AdminInventoryController.createAdjustment(...)` 方法体第一行加：
     ```java
     String operatorId = SecurityContextHolder.getContext().getAuthentication().getName();
     ```
     （`import org.springframework.security.core.context.SecurityContextHolder;`），并把 `operatorId` 作为第五个实参传给 `stockAdjustmentService.create(warehouseId, skuId, afterQty, reason, operatorId)`。这里用行内 `SecurityContextHolder` 写法（不是 AUD-2/AUD-3 的 `Authentication` 方法参数写法）——两种写法在本仓库都存在，照本文件现状风格写，不要跨文件"统一"成同一种。
  4. **同步改 `StockAdjustmentServiceTest`**（`@InjectMocks`）：
     - 加字段 `@Mock private AuditLogService auditLogService;`。
     - 文件里所有 `adjustmentService.create(<wid>, <skuId>, <qty>, "<reason>")` 改成 5 参数，加操作者占位符，如 `adjustmentService.create(1L, 100L, 80, "Physical inventory count", "admin-1")`（含"库存不存在抛异常"用例里的调用）。
  5. **同步改 `AdminInventoryControllerTest`**（`@WebMvcTest` + `@AutoConfigureMockMvc(addFilters = false)`——**安全过滤链被整体禁用**，`SecurityContextHolder` 不会被任何 servlet filter 自动填充，如果不手动设置，`AdminInventoryController.createAdjustment` 里的 `getAuthentication()` 会拿到 `null`，调 `.getName()` 直接 NPE 500，测试会失败在跟审计毫不相关的地方）：
     - 加 `import org.springframework.security.authentication.TestingAuthenticationToken;` 和 `import org.springframework.security.core.context.SecurityContextHolder;`。
     - 加一个 `@AfterEach void clearSecurityContext() { SecurityContextHolder.clearContext(); }`（避免这个手动设置的认证信息泄漏到同一 JVM 里其他测试方法——`SecurityContextHolder` 默认按 ThreadLocal 存储，JUnit 5 默认同线程顺序跑同一个类的多个 `@Test`，不清理会互相污染）。
     - `testCreateAdjustment_returnsCreated()` 里，把
       ```java
       when(stockAdjustmentService.create(eq(1L), eq(100L), eq(80), eq("Physical count")))
               .thenReturn(adjustment);
       ```
       改成
       ```java
       when(stockAdjustmentService.create(eq(1L), eq(100L), eq(80), eq("Physical count"), anyString()))
               .thenReturn(adjustment);
       ```
       （`anyString` 静态导入本文件已有），并在 `mockMvc.perform(post(...))` **之前**插入：
       ```java
       SecurityContextHolder.getContext().setAuthentication(
               new TestingAuthenticationToken("admin-1", null));
       ```
- **验收**:
  - `POST /api/v1/admin/inventory/adjustments`（ADMIN）返回 201 后：(a) 返回体 `StockAdjustment.operatorId` 等于当前管理员用户名；(b) 新增一条共享审计记录 `actionType=INVENTORY_ADJUSTMENT`，`businessId=<skuId>`，`beforeState`/`afterState` 为调整前后数量。
  - `StockAdjustmentServiceTest`：`create(...)` 返回的 `getOperatorId()` 等于传入值；库存不存在分支 `verify(auditLogService, never()).record(any(), any(), any(), any(), any(), any())`（该分支在 `orElseThrow` 处就已抛出，天然不会走到审计调用，不需要额外 if 保护）。
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-inventory -am test-compile` 编译通过；`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-inventory -am test -Dtest=AdminInventoryControllerTest` 通过（重点验证不会 NPE）。
- **勿犯**:
  - `operatorId` 参数加在**最后一位**（`create(warehouseId, skuId, afterQty, reason, operatorId)`），不要插到中间，四处调用点（Service、Controller、两个测试文件）位置必须一致。
  - 改 `create(...)` 签名时，方法上已有的注解必须**原样保留**——若 B09/INV-4 已执行，该方法 `@Transactional` 之上会有 `@CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true, cacheManager = "inventoryCacheManager")`，整方法替换时最容易连它一起丢：丢了不报编译错，但库存人工调整后摘要缓存 30 秒内不失效，属于隐藏面回归；若 B09 被跳过、方法上没有该注解，也不要在本卡补加（那是 INV-4 的职责）。
  - `StockAdjustment.operatorId` 用 `nullable = false`，跟 `warehouseId`/`skuId` 同级都是必填。
  - **`AdminInventoryControllerTest` 漏加 `SecurityContextHolder.getContext().setAuthentication(...)` 是本卡最容易犯的错**——`@AutoConfigureMockMvc(addFilters = false)` 意味着没有任何 filter 会替你填充认证信息，这不是"可选的测试改进"，是不加就必定 NPE 500 的硬需求。
  - 不要给审计调用加 try-catch/独立事务（理由同 AUD-2）。

---

### AUD-5 | 退款审核和仓库验收无审计日志

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/RefundService.java`
  2. （同步改测试）`code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/RefundServiceTest.java`
- **现状**: `reviewRefund(Long refundId, Long reviewerId, RefundReviewRequest request)` 和 `warehouseAccept(Long refundId, Long acceptorId)` 都已经带着操作者 ID 参数（`reviewerId`/`acceptorId`，由 `AdminRefundController` 从 `SecurityContextHolder` 解析后传入——**该 controller 及其测试 `AdminRefundControllerTest` 不需要改动，两个方法对外签名本卡不变**），但方法体完全没有调用任何审计服务。
- **期望**: 退款审核和仓库验收是 design-docs/03 §6 第 5 类必须审计操作（同一类里的两个动作都要记）。
- **改法**:
  1. 构造函数新增 `AuditLogService auditLogService` 依赖（`import com.ecommerce.common.audit.AuditLogService;`）。
  2. `reviewRefund(...)`：在现有的状态校验（不管此刻是一个 `if` 还是多个 `if`）全部通过之后、进入 `if (request.isApproved())` 分支**之前**，插入 `RefundStatus beforeStatus = refund.getStatus();` 捕获前置状态；在 if/else 分支结束之后、`return toRefundResponse(refund);` **之前**调用：
     ```java
     auditLogService.record(String.valueOf(reviewerId), "REFUND_REVIEW",
             refund.getRefundNo(), beforeStatus.name(), refund.getStatus().name(),
             request.isApproved() ? "approved" : "rejected: " + request.getNote());
     ```
     这里分支执行完之后再读的 `refund.getStatus()` 会自动反映批准/驳回后的最新状态——不用关心 `approveRefund(...)` 内部具体把状态置成什么（不同实现可能落到 `APPROVED`，也可能落到 `WAITING_WAREHOUSE_ACCEPT`，取决于是否还有另一张状态机卡片改过它，本卡不关心）：`approveRefund` 内部按同一个 `refundId` 重新 `findById` 拿到的是同一事务里同一个 JPA 托管实例，跟 `reviewRefund` 里的 `refund` 变量是同一个对象，写操作互相可见。**不要**自己重新查一次库，也不要硬编码目标状态字符串。
  3. `warehouseAccept(...)`：在 `refund = refundRecordRepository.save(refund);` 之后、`processRefund(refund);` **之前**插入：
     ```java
     auditLogService.record(String.valueOf(acceptorId), "REFUND_WAREHOUSE_ACCEPT",
             refund.getRefundNo(), RefundStatus.WAITING_WAREHOUSE_ACCEPT.name(),
             RefundStatus.WAREHOUSE_ACCEPTED.name(), null);
     ```
     这里前后状态可以直接写常量，因为方法开头的守卫已经保证进入这里时状态就是 `WAITING_WAREHOUSE_ACCEPT`，这两行执行完就是 `WAREHOUSE_ACCEPTED`。**审计调用必须在 `processRefund(refund)` 之前**——`processRefund` 会把状态继续推进到 `COMPLETED`，顺序放反不会报错，但审计记录的 `afterState` 会变成错误的中间态描述。
  4. **同步改 `RefundServiceTest`**（该类是显式 `new RefundService(...)` 构造，不是 `@InjectMocks`，**必须**同步改构造调用，否则编译不过）：
     - 加字段 `@Mock private AuditLogService auditLogService;`。
     - `refundService = new RefundService(refundRecordRepository, paymentRecordRepository, refundCalculator, eventPublisher, notificationService);` 在最后追加一个实参，变成 `new RefundService(refundRecordRepository, paymentRecordRepository, refundCalculator, eventPublisher, notificationService, auditLogService);`。
     - `reviewRefund(...)`/`warehouseAccept(...)` 的调用点/方法签名本身不变，不需要改动测试里已有的调用参数个数。
- **验收**:
  - 管理员审核退款（通过或驳回）后新增一条 `actionType=REFUND_REVIEW` 的审计记录，`businessId` 为退款单号，`beforeState`/`afterState` 反映审核前后状态。
  - 仓库验收后新增一条 `actionType=REFUND_WAREHOUSE_ACCEPT` 的审计记录，`beforeState=WAITING_WAREHOUSE_ACCEPT`，`afterState=WAREHOUSE_ACCEPTED`。
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-payment -am test-compile` 编译通过。
- **勿犯**:
  - `applyRefund(...)`（用户发起退款申请）**不在**本卡范围——03 §6 第 5 类写的是"审核和仓库验收"，不含"申请"。
  - 不要因为要拿 `beforeStatus` 就顺手把状态判断逻辑（`PENDING_REVIEW`/`WAITING_WAREHOUSE_ACCEPT` 冲突码那部分）也重写——那是另一张卡（状态冲突改 409）的范围，本卡只在**已有**判断通过之后插入审计调用，不改判断逻辑本身、不改抛出的异常类型。
  - `AdminRefundController`/`RefundController`/`AdminRefundControllerTest` **不需要改动**——`reviewerId`/`acceptorId` 早已从 `SecurityContextHolder` 解析好，`reviewRefund`/`warehouseAccept` 对外方法签名不变。
  - 不要给审计调用加 try-catch/独立事务（理由同 AUD-2）。
  - `RefundServiceTest` 的 `new RefundService(...)` 是显式构造调用，跟 AUD-2/AUD-3/AUD-4 的 `@InjectMocks` 反射注入不是一回事——漏加最后一个实参就是编译错误，不是运行时错误。

---

### AUD-6 | 发票开具无审计日志

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/InvoiceService.java`
  2. （同步改测试）`code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/InvoiceServiceTest.java`
- **现状**: `generateInvoice(Long userId, InvoiceRequest request)` 已经带着 `userId`（由 `InvoiceController` 从 `SecurityContextHolder` 解析后传入——**该 controller 及其测试 `InvoiceControllerTest` 不需要改动，方法对外签名本卡不变**），但方法体完全没有调用审计服务。
- **期望**: 发票开具是 design-docs/03 §6 第 6 类必须审计操作。这里没有"审核"性质的状态迁移（发票是从无到有），操作者用发起开票请求的 `userId`。
- **改法**:
  1. 构造函数新增 `AuditLogService auditLogService` 依赖（`import com.ecommerce.common.audit.AuditLogService;`）。**「现状」里的 `(invoiceRecordRepository, paymentRecordRepository)` 是基线的原始签名——若你打开文件时发现构造函数已经因为另一张卡（`payment.md` PAY-B1，可能新增了 `notificationService`）多了参数，不要因为文本对不上就跳过或改错位置：一律把 `auditLogService`追加到你看到的当前参数列表最后一位**（同 AUD-7 的处理方式）。参数顺序不影响 Spring 按类型注入，只要类型和个数对，位置在第几位都可以。
  2. 在 `invoice = invoiceRecordRepository.save(invoice);` 之后插入：
     ```java
     auditLogService.record(String.valueOf(userId), "INVOICE_ISSUE",
             invoice.getInvoiceNo(), null, InvoiceStatus.ISSUED.name(),
             "amount=" + invoiceAmount);
     ```
     `beforeState` 传 `null`（开票前没有"前置状态"这个概念）；`businessId` 用发票号 `invoice.getInvoiceNo()`（不是订单号）；`remark` 用 `"amount=" + invoiceAmount` 拼一个可读备注——`invoiceAmount` 是方法里已经算好、代表"这次实际开票金额"的那个局部变量（不管它此刻是恒等于订单实付全额，还是已经被另一张卡改成读 `request.getInvoiceAmount()`，用当次方法体里那个变量即可，不要重新引用 `request.getInvoiceAmount()` 的原始未校验值）。
  3. **同步改 `InvoiceServiceTest`**（显式 `new InvoiceService(...)` 构造，**必须**同步改）：
     - 加字段 `@Mock private AuditLogService auditLogService;`。
     - 找到文件里实际的 `new InvoiceService(...)` 调用，在**当前**实参列表最后追加 `auditLogService`（如果此刻已经因为 PAY-B1 多了 `notificationService` 实参，就加在那之后：`new InvoiceService(invoiceRecordRepository, paymentRecordRepository, notificationService, auditLogService)`；如果还是基线的 2 参数就直接追加成 3 参数——总之以你打开文件时看到的实际调用为准，不要假设「现状」里写的一定还成立）。
     - `generateInvoice(...)` 调用点本身不变，不需要改调用参数个数。
- **验收**:
  - `POST /api/v1/invoices`（USER）成功开票后新增一条 `actionType=INVOICE_ISSUE` 的审计记录，`businessId=<invoiceNo>`，`beforeState=null`，`afterState=ISSUED`，`operatorId=<发起用户 ID>`。
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-payment -am test-compile` 编译通过。
- **勿犯**:
  - 本卡**只加审计调用**——不要顺手把同方法里其它已知问题一起改掉（金额是否读请求参数、`INVOICE_AMOUNT_EXCEEDED` 错误码、税额舍入方式、开票通知渠道等都是其它卡的范围）；只在**现有**的 `invoiceRecordRepository.save(invoice)` 之后插入审计这一行，不改前面任何计算逻辑。
  - `InvoiceController`/`InvoiceControllerTest` **不需要改动**——`userId` 早已从 `SecurityContextHolder` 解析好。
  - 不要给审计调用加 try-catch/独立事务（理由同 AUD-2）。
  - 构造函数新增参数是显式 `new InvoiceService(...)` 调用，漏加会编译错误（同 AUD-5 的提醒）。

---

### AUD-7 | 结算批次生成无审计日志，且服务方法缺 operatorId 参数

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/SettlementBatchService.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/controller/AdminSettlementController.java`
  3. （同步改测试）`code/ecommerce-payment/src/test/java/com/ecommerce/payment/service/SettlementBatchServiceTest.java`
  4. （同步改测试）`code/ecommerce-payment/src/test/java/com/ecommerce/payment/controller/AdminSettlementControllerTest.java`
- **现状**: `generateBatch(LocalDate batchDate)` 单参数，不接收操作者，方法体没有任何审计调用；`AdminSettlementController.generateBatch(...)` 也完全不碰 `SecurityContextHolder`，直接 `settlementBatchService.generateBatch(date)`。
- **期望**: 结算批次生成是 design-docs/03 §6 第 7 类必须审计操作，操作者为当前登录管理员。
- **改法**:
  1. `SettlementBatchService` 构造函数新增 `AuditLogService auditLogService` 依赖。`generateBatch(...)` 方法签名加第二个参数 `String operatorId`（**`generateBatch(LocalDate batchDate, String operatorId)`**）。方法体有两条出口路径，**两条都要加审计调用**：
     - 空批次分支（`payments.isEmpty()`）：在 `batch = settlementBatchRepository.save(batch);` 之后、`return toBatchResponse(batch);` 之前：
       ```java
       auditLogService.record(operatorId, "SETTLEMENT_BATCH_GENERATE",
               batch.getBatchNo(), null, SettlementStatus.GENERATED.name(), "orderCount=0");
       ```
     - 正常批次分支：在 for 循环写完 `settlementOrderItem` 之后、`return toBatchResponse(batch);` 之前：
       ```java
       auditLogService.record(operatorId, "SETTLEMENT_BATCH_GENERATE",
               batch.getBatchNo(), null, SettlementStatus.GENERATED.name(),
               "orderCount=" + orderCount + ", totalPayment=" + totalPaymentAmount);
       ```
     两条的 `actionType`/`beforeState`(`null`，批次是新建的，没有前置状态)/`afterState` 一致，只有 `remark` 内容不同。
  2. `AdminSettlementController.generateBatch(...)` 方法体里，把
     ```java
     SettlementBatchResponse response = settlementBatchService.generateBatch(date);
     ```
     改为
     ```java
     SettlementBatchResponse response = settlementBatchService.generateBatch(
             date, SecurityContextHolder.getContext().getAuthentication().getName());
     ```
     并加 `import org.springframework.security.core.context.SecurityContextHolder;`。这里用行内 `SecurityContextHolder` 写法（跟 AUD-4 的 `AdminInventoryController` 一致）。
  3. **同步改 `SettlementBatchServiceTest`**（显式 `new SettlementBatchService(...)` 构造，**必须**同步改）：
     - 加字段 `@Mock private AuditLogService auditLogService;`。
     - 在 `new SettlementBatchService(settlementBatchRepository, settlementOrderItemRepository, paymentRecordRepository, invoiceRecordRepository, ...)` 调用的**最后**追加 `auditLogService`（如果此刻已经因为另一张卡多了 `refundRecordRepository` 参数，就加在那之后，总之加在参数列表最后一位）。
     - 把文件里**所有** `settlementBatchService.generateBatch(<date表达式>)` 调用（`when(...)` 和 `verify(...)` 都要改，不要只改一半）加第二个参数，用 `anyString()` 匹配器：`generateBatch(any(LocalDate.class), anyString())` / `generateBatch(eq(xxx), anyString())`，具体用哪种匹配器跟随该行原有的第一个参数写法；需要 `import static org.mockito.ArgumentMatchers.anyString;`（如果本文件还没有这个静态导入）。
  4. **同步改 `AdminSettlementControllerTest`**（`@WebMvcTest` + `@AutoConfigureMockMvc(addFilters = false)`，但**方法级已经有** `@WithMockUser(username = "999", roles = {"ADMIN"})`——`@WithMockUser` 在测试方法执行前直接由 Spring Test 框架写入 `SecurityContextHolder`，不依赖 servlet filter，`addFilters = false` 不影响它，**不需要**像 AUD-4 那样额外手动 `setAuthentication(...)`）：
     - 把文件里所有 `when(settlementBatchService.generateBatch(any(LocalDate.class)))` 改成 `when(settlementBatchService.generateBatch(any(LocalDate.class), anyString()))`，所有 `verify(settlementBatchService).generateBatch(any(LocalDate.class));` 改成 `verify(settlementBatchService).generateBatch(any(LocalDate.class), anyString());`；加 `import static org.mockito.ArgumentMatchers.anyString;`。
- **验收**:
  - `POST /api/v1/admin/settlements/batches`（ADMIN）成功生成批次（无论当天有无支付记录）后新增一条 `actionType=SETTLEMENT_BATCH_GENERATE` 的审计记录，`businessId=<batchNo>`，`afterState=GENERATED`，`operatorId=<当前管理员用户名>`（本例中 `@WithMockUser(username="999")`，预期为 `"999"`）。
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-payment -am test-compile` 编译通过；`-Dtest=SettlementBatchServiceTest,AdminSettlementControllerTest test` 通过。
- **勿犯**:
  - **两个分支都要加**——不要因为空批次分支"没什么好审计的"就漏掉它；参考实现里空批次分支同样调用了 `auditLogService.record(...)`，只是 remark 固定为 `"orderCount=0"`。
  - `operatorId` 加在**第二个**参数位置（`generateBatch(LocalDate batchDate, String operatorId)`），不要加在第一位。
  - 批次已存在冲突（`ConflictException`）分支在审计调用点之前就已经抛出，不需要额外保护。
  - `SettlementBatchServiceTest` 里 `generateBatch(...)` 的调用点可能不止两处（如果其它卡片已经为退款汇总之类的场景加了新用例），**逐个 grep 确认改全**，不要只改前两个就以为完事。
  - 不要给审计调用加 try-catch/独立事务（理由同 AUD-2）。
