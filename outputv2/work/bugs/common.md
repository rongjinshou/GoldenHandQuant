# B11 · common — 通知组件与全局异常处理 / 测试支撑面收口 / 测试时钟全面对齐

本批覆盖 `ecommerce-common` 模块的遗留缺陷与测试支撑面契约收口：本地通知组件（`LocalNotificationServiceImpl`）故障注入检查位置错误、导致失败会穿透给调用方，且失败通知不落可查询记录（COMMON-1/2）；全局异常处理器（`GlobalExceptionHandler`）缺少对三类 Spring 框架级参数错误的处理，被误判为 500（COMMON-3）；测试支撑面四点收口（COMMON-4）——附录B §2 配置默认值全表进 `RuntimeConfigRegistry`、未知路径 404 走 `RESOURCE_NOT_FOUND` 契约体、支撑端点错误路径改抛标准异常、附录B §1 `logistics:` 配置段补齐。注意 COMMON-4 的**施工范围只含 common 模块文件与两份 yml**——`ecommerce-app` 下的支撑控制器与过滤链级单测已移交 B12（`SystemAdminController` 并入 APP-1 整文件替换目标、其余为 B12 新卡 APP-4），本批不碰 app 模块 `.java` 文件（见卡内「勿犯」第 5 条）。COMMON-5 是测试时钟全面对齐整卡：JPA 审计时间接入 `SystemClockService`（`DateTimeProvider`），并把 12 处 REST 可见时间戳与限流滑动窗的裸系统时钟全部换到测试时钟——**跨模块整卡**（common 之外还改 logistics/promotion/review 三个模块的 4 个文件，单批原子落地，先例 B14/LOGI-11、B15/LOY-12）。共五张卡：COMMON-1..4 为单点行为修正，COMMON-5 为不拨钟恒等的系统性对齐，风险均 low。

---

### COMMON-1 | 通知故障注入检查写在 try/catch 外，`send()` 会把异常真的抛给调用方

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-common/src/main/java/com/ecommerce/common/notification/LocalNotificationServiceImpl.java`
- **现状**: `send()` 方法（第43-109行，文件共140行）里，`"notification-send-failure"` 故障注入检查位于第49-52行——在 null 校验之后、idempotency 校验（第54行开始）之前，**在 `try` 块（第69行 `try {` 开始，第105-108行 `catch`）之外**：

  ```java
      @Override
      public void send(NotificationRequest request) {
          if (request == null) {
              log.warn("Received null NotificationRequest, ignoring");
              return;
          }

          // Fault injection: simulate notification send failure
          if (FaultInjectionRegistry.isActive("notification-send-failure")) {
              throw new RuntimeException("Fault injected: notification-send-failure");
          }

          String idempotencyKey = request.getIdempotencyKey();
          ...
  ```

  一旦该故障被启用，这里 `throw` 出的 `RuntimeException` **不会被本方法自己的 catch 捕获**，而是直接冒泡给 `send()` 的调用方——无论调用方是同步业务代码还是 `@TransactionalEventListener`，都会收到一个未预期的运行时异常。`design-docs/15-本地通知组件设计.md` §4 第5条明确"失败时记录失败原因，**不影响主业务流程**"，即 `send()` 本身必须对所有发送失败（含故障注入模拟的失败）都是"言而无害"的黑洞，不能把异常泄漏出去。
- **期望**: `send()` 对任何发送失败都必须在方法内部吞掉、不得抛给调用方；调用方（无论是否处于事务中）感知不到通知子系统的失败。依据: `design-docs/15-本地通知组件设计.md` §4 第5条、`design-docs/03-通用规范与非功能设计.md` §8（"事件监听器失败时…不回滚主业务事务，除非该监听器是明确声明的强一致监听器…支付成功后的物流、积分、**通知**监听器均为非强一致监听器"）、README.md §8 黑盒用例目录 PUB-108（`pub108_paymentSuccessShouldNotBeBlockedByPostActions`——验证后置动作故障不阻塞支付成功响应；该用例注入的是 `logistics-create-shipment-failure` 而非 `notification-send-failure`，但验证的是同一条"后置失败不得传染主流程"的设计原则）。
- **改法**: 把第49-52行的故障注入 if 块从 idempotency 校验之前删除，原样搬到 `try {` 内部第一条语句（`renderTemplate` 调用之前）。

  **删除**（原第49-53行，含尾随空行，位于 null 校验和 idempotency 校验之间）:
  ```java
          // Fault injection: simulate notification send failure
          if (FaultInjectionRegistry.isActive("notification-send-failure")) {
              throw new RuntimeException("Fault injected: notification-send-failure");
          }

  ```

  **在 try 块开头插入**（原第69行 `try {` 之后，`String renderedContent = ...` 之前）:
  ```java
          try {
              // Fault injection: simulate notification send failure
              if (FaultInjectionRegistry.isActive("notification-send-failure")) {
                  throw new RuntimeException("Fault injected: notification-send-failure");
              }

              String renderedContent = renderTemplate(request.getTemplateCode(), request.getVariablesOrDefault());
  ```

  其余代码（idempotency 逻辑、`sentRecords.add(...)`、switch 分支、成功路径的 `NotificationRecordService.record(...)`）都不动。本卡与 COMMON-2 同文件同方法但改动区域不重叠（本卡只动 try 开头前后，COMMON-2 只动 catch 块），两卡建议一次性改完再编译自检，谁先谁后不影响结果。
- **验收**: 单测——`FaultInjectionRegistry.add("notification-send-failure")` 后调用 `service.send(request)`，`assertDoesNotThrow(() -> service.send(request))` 通过（不再抛出到调用方）；`mockMailSender`/`mockSmsSender` 均无交互（`verifyNoInteractions`）。批次验收：`bash work/harness/ratchet.sh verify` 24 例仍全绿。

---

### COMMON-2 | 通知发送失败只写日志、不落可查询记录，`GET /api/v1/admin/notifications` 看不到失败通知

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-common/src/main/java/com/ecommerce/common/notification/LocalNotificationServiceImpl.java`
  2. `code/ecommerce-common/src/main/java/com/ecommerce/common/notification/NotificationRecordService.java`
- **现状**:
  1. `LocalNotificationServiceImpl.send()` 的 catch 块（第105-108行）只做日志，没有任何持久化/可查询的记录动作：
     ```java
             } catch (Exception e) {
                 log.error("Failed to send notification: bizType={}, bizId={}, channel={}, error={}",
                         request.getBizType(), request.getBizId(), request.getChannel(), e.getMessage(), e);
             }
         }
     ```
  2. `NotificationRecordService`（共40行）只有一个 `record(...)`（成功路径专用，6 个参数，第12-15行）+ `getAll()`/`getByBizId()`/`clear()`；内部类 `NotificationRecordItem`（第23-39行）构造函数只接收 6 个字段，**没有 `failureReason` 字段/getter，也没有任何 `recordFailure` 方法**——类型层面就不存在"记一条失败通知"这回事。
  3. `code/ecommerce-app/src/main/java/com/ecommerce/app/controller/NotificationAdminController.java`（**不在本卡改动范围**）已经正确地把 `NotificationRecordService.getAll()` / `getByBizId(bizId)` 的结果直接序列化为 `GET /api/v1/admin/notifications` 的响应体——只要 `NotificationRecordService` 里真实存在失败记录，这个控制器不用改就能读到并透传给客户端（该文件未出现在参考实现改动集里，说明它本身没问题，不用碰）。
- **期望**: 通知发送失败必须落一条可通过 `GET /api/v1/admin/notifications` 查询到的记录，且能区分"成功"与"失败"（至少带失败原因）。依据: `design-docs/03-通用规范与非功能设计.md` §7 通知规范第4条（"失败记录"）、`design-docs/15-本地通知组件设计.md` §4 第5条（"失败时记录失败原因"）、README.md §6.8（`GET /api/v1/admin/notifications` 查询通知记录）。
- **改法**:
  1. **`NotificationRecordService.java`**——给 `NotificationRecordItem` 加 `failureReason` 字段，构造函数追加末位参数，加 getter；新增 `recordFailure(...)` 静态方法，成功路径的 `record(...)` 同步补上 `null` 参数：

     `record(...)` 方法体（原第14行）:
     ```java
             records.add(new NotificationRecordItem(bizType, bizId, receiver, channel, templateCode, idempotencyKey, LocalDateTime.now()));
     ```
     改为并在其后新增 `recordFailure`:
     ```java
             records.add(new NotificationRecordItem(bizType, bizId, receiver, channel, templateCode, idempotencyKey, LocalDateTime.now(), null));
         }

         public static void recordFailure(String bizType, String bizId, String receiver,
                                           NotificationChannel channel, String templateCode, String failureReason) {
             records.add(new NotificationRecordItem(bizType, bizId, receiver, channel, templateCode, null, LocalDateTime.now(), failureReason));
     ```
     （注意失败记录的 `idempotencyKey` 位置传 `null`——失败不做幂等去重，语义上不适用。）

     `NotificationRecordItem` 内部类（原第23-39行）整体替换为:
     ```java
         public static class NotificationRecordItem {
             private final String bizType, bizId, receiver;
             private final NotificationChannel channel;
             private final String templateCode, idempotencyKey;
             private final LocalDateTime sentAt;
             private final String failureReason;
             public NotificationRecordItem(String bt, String bi, String r, NotificationChannel c, String tc, String ik, LocalDateTime sa, String failureReason) {
                 this.bizType = bt; this.bizId = bi; this.receiver = r; this.channel = c;
                 this.templateCode = tc; this.idempotencyKey = ik; this.sentAt = sa;
                 this.failureReason = failureReason;
             }
             public String getBizType() { return bizType; }
             public String getBizId() { return bizId; }
             public String getReceiver() { return receiver; }
             public NotificationChannel getChannel() { return channel; }
             public String getTemplateCode() { return templateCode; }
             public String getIdempotencyKey() { return idempotencyKey; }
             public LocalDateTime getSentAt() { return sentAt; }
             public String getFailureReason() { return failureReason; }
         }
     ```
  2. **`LocalNotificationServiceImpl.java`**——catch 块（第105-108行）在 `log.error(...)` 之后追加一行调用:
     ```java
             } catch (Exception e) {
                 log.error("Failed to send notification: bizType={}, bizId={}, channel={}, error={}",
                         request.getBizType(), request.getBizId(), request.getChannel(), e.getMessage(), e);
                 NotificationRecordService.recordFailure(
                         request.getBizType(),
                         request.getBizId(),
                         request.getReceiver(),
                         request.getChannel(),
                         request.getTemplateCode(),
                         e.getMessage());
             }
         }
     ```
  与 COMMON-1 同文件同方法，两卡改动区域不重叠（COMMON-1 改 try 开头前后，本卡改 catch 块内部），建议一次性改完再编译自检。
- **验收**: 单测——`FaultInjectionRegistry.add("notification-send-failure")` → `service.send(request)`（`bizId` 用唯一值如 `"FAULT-001"`）→ `NotificationRecordService.getByBizId("FAULT-001")` 返回长度为 1 的列表，且 `.get(0).getFailureReason()` 非空；成功路径记录的 `getFailureReason()` 仍为 `null`（不破坏既有成功记录断言）。端到端：管理员登录后在 `notification-send-failure` 故障注入开启下触发一次会发通知的业务动作，再 `GET /api/v1/admin/notifications`，响应 `records` 数组里能看到该条、带非空 `failureReason` 字段。

---

### COMMON-3 | `GlobalExceptionHandler` 缺请求体解析失败/参数类型不符/缺参的 `VALIDATION_FAILED` 处理，被兜底为 500

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-common/src/main/java/com/ecommerce/common/exception/GlobalExceptionHandler.java`
- **现状**: 该类（共107行）对业务异常各有专门的 `@ExceptionHandler`（`ResourceNotFoundException`/`AuthorizationException`/`RateLimitException`/`ConflictException`/`OrderValidationException`/`ValidationException`/`BusinessException`/`MethodArgumentNotValidException`），外加第96-101行的兜底 `handleGeneric(Exception ex)`（500 `INTERNAL_ERROR`）。三类框架级"请求参数问题"完全没有专门处理，全部落进兜底 500：
  - `HttpMessageNotReadableException`（请求体不是合法 JSON / JSON 反序列化到 DTO 失败）
  - `MethodArgumentTypeMismatchException`（路径变量/查询参数类型不符——例如 `OrderController.getOrderDetail` 的 `@PathVariable Long orderId`，请求 `GET /api/v1/orders/abc` 时 `"abc"` 转 `Long` 失败会直接抛这个异常）
  - `MissingServletRequestParameterException`（必填查询参数缺失——例如 `AdminInventoryController.outbound` 的 `@RequestParam Long warehouseId` 无默认值，请求 `POST /api/v1/admin/inventory/outbound` 时不带 `warehouseId` 会抛这个异常）

  这三类异常在 Spring MVC 里发生于 Controller 方法体执行之前（HTTP 消息转换/参数绑定阶段），冒泡后只命中 `@ExceptionHandler(Exception.class)`，返回 `{code:"INTERNAL_ERROR", ...}` + 500，而不是参数问题该有的 400。
- **期望**: 这三类客户端参数问题应统一返回 400 + `code=VALIDATION_FAILED`，不是 500。依据: `README.md` §7.1 通用错误码表（`VALIDATION_FAILED | 400 | 请求参数校验失败`）。
- **改法**: 在文件顶部 import 区插入三个新 import（按字母序插入到对应位置，不打乱其余 import）。
  原有 import 区（原第3-14行）：
  ```java
  import com.ecommerce.common.dto.ApiError;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.http.HttpStatus;
  import org.springframework.http.ResponseEntity;
  import org.springframework.web.bind.MethodArgumentNotValidException;
  import org.springframework.web.bind.annotation.ExceptionHandler;
  import org.springframework.web.bind.annotation.RestControllerAdvice;

  import java.util.HashMap;
  import java.util.Map;
  import java.util.UUID;
  ```
  改为：
  ```java
  import com.ecommerce.common.dto.ApiError;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.http.HttpStatus;
  import org.springframework.http.ResponseEntity;
  import org.springframework.http.converter.HttpMessageNotReadableException;
  import org.springframework.web.bind.MethodArgumentNotValidException;
  import org.springframework.web.bind.MissingServletRequestParameterException;
  import org.springframework.web.bind.annotation.ExceptionHandler;
  import org.springframework.web.bind.annotation.RestControllerAdvice;
  import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

  import java.util.HashMap;
  import java.util.Map;
  import java.util.UUID;
  ```

  然后在 `handleMethodArgumentNotValid(...)` 方法的闭合 `}`（原第94行）之后、`@ExceptionHandler(Exception.class)`／`handleGeneric(...)`（原第96行）之前，插入一个新方法：

  ```java
      /**
       * Framework-level bad-request cases: an unreadable / mistyped JSON body, a
       * path or query parameter whose type does not match, or a missing required
       * query parameter. README §7.1 classifies these as client parameter problems
       * (VALIDATION_FAILED, 400) — not INTERNAL_ERROR (500), which the generic
       * handler below would otherwise return.
       */
      @ExceptionHandler({HttpMessageNotReadableException.class,
              MethodArgumentTypeMismatchException.class,
              MissingServletRequestParameterException.class})
      public ResponseEntity<ApiError> handleBadRequestParameter(Exception ex) {
          String traceId = generateTraceId();
          log.warn("Bad request parameter [{}]: {}", traceId, ex.getMessage());
          ApiError error = new ApiError("VALIDATION_FAILED", "Request validation failed",
                  traceId, new HashMap<>());
          return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(error);
      }
  ```

  方法内部逻辑与已有 `handleValidation`/`handleMethodArgumentNotValid` 风格一致（生成 traceId、warn 日志、空 `details` 的 `ApiError`）。不要改动任何已有 handler 方法体，也不要动 `handleGeneric`。只改这一个文件。
- **验收**（均需带合法 token，避免被安全过滤链先一步拦成 401 而非走到参数绑定阶段）:
  1. `GET /api/v1/orders/abc`（`orderId` 传非数字，带合法 USER token）——改前返回 500 `INTERNAL_ERROR`，改后返回 400，响应体 `code` 为 `VALIDATION_FAILED`。
  2. `POST /api/v1/admin/inventory/outbound`（带合法 ADMIN token，只传 `skuId`+`quantity`，不传 `warehouseId`）——改前 500，改后 400 `VALIDATION_FAILED`。
  3. 任意 `@RequestBody` 端点（如 `POST /api/v1/admin/warehouses`，带合法 ADMIN token）请求体传一段非法 JSON（如 `{`）——改前 500，改后 400 `VALIDATION_FAILED`。
  4. 单测（可仿照同目录 `GlobalExceptionHandlerTest.java` 现有写法追加用例，不改其余既有测试）：`new GlobalExceptionHandler().handleBadRequestParameter(new MissingServletRequestParameterException("warehouseId", "Long"))` 返回状态 400、`getBody().getCode()` 等于 `"VALIDATION_FAILED"`。
  5. `grep -n "HttpMessageNotReadableException\|MethodArgumentTypeMismatchException\|MissingServletRequestParameterException" code/ecommerce-common/src/main/java/com/ecommerce/common/exception/GlobalExceptionHandler.java` 命中新增的 3 处 import + 1 处 `@ExceptionHandler` 注解行。

---

### COMMON-4 | 测试支撑面契约收口：附录B §2 默认值表不全、未知路径 404 被兜底成 500、支撑端点错误路径不走契约错误体、附录B §1 logistics 配置段缺失

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-common/src/main/java/com/ecommerce/common/test/RuntimeConfigRegistry.java`
  2. `code/ecommerce-common/src/main/java/com/ecommerce/common/exception/GlobalExceptionHandler.java`
  3. （同步单测）`code/ecommerce-common/src/test/java/com/ecommerce/common/exception/GlobalExceptionHandlerTest.java`
  4. `code/ecommerce-app/src/main/resources/application.yml`
  5. `code/ecommerce-app/src/test/resources/application-test.yml`

  （关联但**本卡不施工**的 app 侧文件：`SystemAdminController.java` 的错误路径修订已并入 B12/APP-1 的整文件
  替换目标；`FaultInjectionAdminController.java` 与 `SecurityConfigTest.java` 由 B12/APP-4 承载——见「勿犯」
  第 5 条。）
- **现状**: 四处相互独立的小缺陷合并成一张卡（同属"黑盒支撑面与配置契约"，design-docs/01 明确这些支撑接口**纳入 API 契约**）：

  **a.** `RuntimeConfigRegistry` 的 `defaults` map 只有 4 个键（`payment.retry-times`=5、`invoice.tax-rate`="0.06"、`loyalty.activity-multiplier`="1.0"、`member.discount-rate`="0.95"）。附录B §2「配置默认值」表共 8 行，缺了 6 行：`order.expire-minutes`(60)、`order.max-items`(30)、`payment.refund-fee-rate`(0.02)、`cart.ttl-days`(7)、`loyalty.max-redeem-points-per-order`(10000)、`loyalty.max-redeem-ratio`(0.5)。后果：无运行期覆盖时 `GET /api/v1/admin/system/configs/{key}` 对这 6 个**文档明确给了默认值**的键返回 404。（业务读取点各带自身 fallback 且常量与表值一致——`OrderPreconditionChecker.DEFAULT_MAX_ITEMS=30`、`OrderService.DEFAULT_EXPIRE_MINUTES=60`、`RefundCalculator`→yml 0.02、`LoyaltyPointService.DEFAULT_MAX_REDEEM_POINTS=10000`/`DEFAULT_MAX_REDEEM_RATIO=0.5`——所以补表**不改变任何业务读数**，只修支撑接口的可观察行为。）

  **b.** Spring Boot 3.2 对"没有任何 handler 匹配的请求"从静态资源兜底抛 `org.springframework.web.servlet.resource.NoResourceFoundException`；`GlobalExceptionHandler` 没有对应处理器，带合法 token 访问未知 `/api/v1/**` 路径落进兜底 `handleGeneric` → **500 `INTERNAL_ERROR`**。README §7.1 规定 404 = `RESOURCE_NOT_FOUND`（资源不存在）。（无 token 时安全链先拦成 401，问题只在认证通过后暴露。）

  **c.** `SystemAdminController`（configs/clock）与 `FaultInjectionAdminController` 的错误路径手搓非契约响应：缺 `value` → 400 `{"error":"value is required"}`；未知配置键 → `ResponseEntity.notFound().build()` 404 **空体**；非法 `timestamp` → 400 `{"error":"Invalid timestamp format, ..."}`；`offsetMinutes`/`timestamp` 均缺 → 400 `{"error":...}`；缺 `fault` 名 → 400 `{"error":"fault name is required"}`。另有一个 500 隐患：`PUT /clock` 的 `((Number) body.get("offsetMinutes")).longValue()` 盲目强转，body 传数字字符串（如 `{"offsetMinutes":"30"}`）直接 `ClassCastException` → 500。design-docs/03 固定错误响应为 `{code, message, traceId, details}`。

  **d.** `application.yml` 与 `application-test.yml` 均缺附录B §1 示例配置里的 `logistics:` 段（`default-carrier: LOCAL_EXPRESS`、`free-shipping-threshold: 199.00`）。纯配置文件对齐项：代码读取仍走 `RuntimeConfigRegistry`/常量（LOGI-9 的 controller 读 `logistics.default-carrier` 运行期键、ORD-B5 的免运费阈值读 `order.free-shipping-threshold`），无任何 `@Value`/`@ConfigurationProperties` 绑定这两个键，补上后行为零变化——只消除"文档示例配置有、工程配置文件无"的静态不一致。
- **期望**: a. 附录B §2 表内 8 键在无覆盖时全部能从 `GET /api/v1/admin/system/configs/{key}` 读到文档默认值；b. 未匹配路径返回 404 + `{code:"RESOURCE_NOT_FOUND",...}` 契约体；c. 支撑端点错误路径全部走标准异常（`ValidationException`→400 `VALIDATION_FAILED`、`ResourceNotFoundException`→404 `RESOURCE_NOT_FOUND` 契约体），`offsetMinutes` 接受 Number 或数字字符串、其余非法值 400 而非 500；d. 两份 yml 含附录B §1 的 `logistics:` 段。依据: 附录B §1 示例配置 + §2 表、README §7.1 通用错误码表、design-docs/03（错误响应格式）、design-docs/01（"黑盒测试需要的可观察支撑能力……纳入 API 契约"）。**成功路径的响应形状与内容逐字节不变。**
- **改法**:
  1. `RuntimeConfigRegistry.defaults` 换成 `Map.ofEntries`，第一段逐行镜像附录B §2 表（新增 6 键值一律写字符串；`payment.retry-times` 保持既有 Integer `5` 不动），第二段保留 2 个表外既有键：
  ```java
      private static final Map<String, Object> defaults = Map.ofEntries(
              // 附录B §2 配置默认值 (one entry per table row)
              Map.entry("order.expire-minutes", "60"),
              Map.entry("order.max-items", "30"),
              Map.entry("payment.retry-times", 5),
              Map.entry("payment.refund-fee-rate", "0.02"),
              Map.entry("invoice.tax-rate", "0.06"),
              Map.entry("cart.ttl-days", "7"),
              Map.entry("loyalty.max-redeem-points-per-order", "10000"),
              Map.entry("loyalty.max-redeem-ratio", "0.5"),
              // pre-existing tunables outside the 附录B §2 table
              Map.entry("loyalty.activity-multiplier", "1.0"),
              Map.entry("member.discount-rate", "0.95")
      );
  ```
  2. `GlobalExceptionHandler` 新增 import `org.springframework.web.servlet.resource.NoResourceFoundException;`（插在 `MethodArgumentTypeMismatchException` import 之后），并在 `handleGeneric` 之前插入：
  ```java
      @ExceptionHandler(NoResourceFoundException.class)
      public ResponseEntity<ApiError> handleNoResourceFound(NoResourceFoundException ex) {
          String traceId = generateTraceId();
          log.warn("No resource for request [{}]: {}", traceId, ex.getMessage());
          ApiError error = new ApiError("RESOURCE_NOT_FOUND", "Resource not found",
                  traceId, new HashMap<>());
          return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
      }
  ```
  3. `GlobalExceptionHandlerTest` 追加用例（import `HttpMethod` 与 `NoResourceFoundException`）：`handler.handleNoResourceFound(new NoResourceFoundException(HttpMethod.GET, "api/v1/no-such-path"))` → 404、code=`RESOURCE_NOT_FOUND`、message=`Resource not found`、traceId 非空、details 空。
  4. **app 侧三个 `.java` 文件本卡不施工**（施工细节见 B12）：`SystemAdminController` 的错误路径修订（标准
     异常 + `parseOffsetMinutes` 防御解析 + `timestamp` 取值 `String.valueOf`）已并入 B12/APP-1 的整文件
     替换目标；`FaultInjectionAdminController` 与 `SecurityConfigTest` 的修订由 B12/APP-4 承载。本卡执行者
     对 `ecommerce-app` 下的 `.java` 文件一律不动。
  5. 两个 yml 文件末尾（`loyalty:` 段之后）各追加同一段：
  ```yaml

  logistics:
    default-carrier: LOCAL_EXPRESS
    free-shipping-threshold: 199.00
  ```
- **验收**:
  1. `grep -qF "order.expire-minutes" code/ecommerce-common/src/main/java/com/ecommerce/common/test/RuntimeConfigRegistry.java` 命中（artifacts.tsv B11 断言）；8 个表键全部出现在该文件。
  2. `grep -qF "NoResourceFoundException" code/ecommerce-common/src/main/java/com/ecommerce/common/exception/GlobalExceptionHandler.java` 命中（artifacts.tsv B11 断言）。
  3. 单测：`mvn -f code/pom.xml test -pl ecommerce-common -Dtest=GlobalExceptionHandlerTest`（11 例）全绿
     （`SecurityConfigTest` 的过滤链级用例属 B12/APP-4 验收范围）。
  4. 行为核对（带 ADMIN token）：`GET /api/v1/admin/system/configs/order.expire-minutes` → 200 `{"key":"order.expire-minutes","value":"60"}`；`GET /api/v1/admin/system/configs/no.such.key` → 404 `{code:"RESOURCE_NOT_FOUND",...}`（此两项 getConfig 的 404 契约体在 B12/APP-1 落地后完整成立）。带 USER token `GET /api/v1/no-such-path` → 404 `{code:"RESOURCE_NOT_FOUND",...}`（改前 500 `INTERNAL_ERROR`，本卡 handler 落地即生效）。clock/fault-injections 的错误路径行为核对属 B12（APP-1/APP-4）验收范围。
  5. `grep -n "default-carrier" code/ecommerce-app/src/main/resources/application.yml code/ecommerce-app/src/test/resources/application-test.yml` 各命中一次。
  6. 黑盒回归 24/24（PUB-101 会打 `PUT configs/member.discount-rate`、PUB-108 会打 fault-injections 的成功路径）。
- **勿犯**:
  1. 附录B §2 的默认值以**表原文**为准逐行抄：`order.max-items` 是 **30** 不是 100、`payment.retry-times` 是 **5** 不是 3——不要凭记忆写"常见值"。
  2. `payment.retry-times` 保持既有 Integer `5`，不要顺手统一成字符串——`GET configs/payment.retry-times` 的 `value` 会从 JSON number 变成 string，无故改变已验证的可观察响应。
  3. 不要删掉 `loyalty.activity-multiplier`/`member.discount-rate` 两个表外既有键（业务在读，PUB-101 还会用 `PUT configs/member.discount-rate` 覆盖它）。
  4. 六个成功路径响应（PUT config 200 `{key,value}`、GET config 200 `{key,value}`、PUT clock 200 `{offsetMinutes}`/`{timestamp}`、DELETE clock 200 `{reset:true}`、POST fault 200 `{activeFaults}`、DELETE fault 204 空体）一律不得变化。
  5. **分工，不要越界**：`ecommerce-app` 下的 `.java` 文件本卡一律不改——`SystemAdminController` 的错误路径
     修订已包含在 app.md APP-1（B12）的整文件替换目标文本中（该目标已同步为含标准错误体的新版，B11/B12 任意
     先后均收敛到同一文本），`FaultInjectionAdminController`/`SecurityConfigTest` 由 B12/APP-4 施工。本卡
     越界去改会与 B12 的整文件替换互相覆盖、白费工。文件 1/2/3（common 侧）与两份 yml 正常随 B11 应用。
  6. 不要把 405（`HttpRequestMethodNotSupportedException`）/415 也"顺手"收口——契约未对其定义错误码，保持框架默认行为。

---

### COMMON-5 | 测试时钟全面对齐：JPA 审计时间戳走真实时钟、12 处 REST 可见时间戳/限流窗裸用系统时钟——拨钟用例全部失真

- 风险: low · 置信度: definite
- **文件**（**跨模块整卡**：common 之外还改 logistics/promotion/review 的 4 个既有文件里的孤立时间戳行，不碰任何结构。跨模块单批原子落地先例：B14/LOGI-11（order+app 3 个新文件）、B15/LOY-12（loyalty+order 跨模块整卡）——本卡与之相同，必须一次性整卡应用，不得按模块拆半）:
  1. `code/ecommerce-common/src/main/java/com/ecommerce/common/config/CommonAutoConfiguration.java`
  2. `code/ecommerce-common/src/main/java/com/ecommerce/common/notification/NotificationRecordService.java`
  3. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/DomainEventPublisher.java`
  4. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/AbstractDomainEvent.java`
  5. `code/ecommerce-common/src/main/java/com/ecommerce/common/ratelimit/RateLimitAspect.java`
  6. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
  7. `code/ecommerce-promotion/src/main/java/com/ecommerce/promotion/service/CouponService.java`
  8. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
  9. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewModerationService.java`
  10. （同步单测）`code/ecommerce-common/src/test/java/com/ecommerce/common/ratelimit/RateLimitAspectTest.java`、`code/ecommerce-common/src/test/java/com/ecommerce/common/notification/LocalNotificationServiceImplTest.java`
- **现状**（行号均为本卡动工前基线）:

  **a. JPA 审计时钟（系统性）**：`CommonAutoConfiguration.java:13` 只写了裸 `@EnableJpaAuditing`，未配 `DateTimeProvider` → 全仓所有继承 `BaseEntity` 的实体（`BaseEntity.java:27-33` 的 `@CreatedDate createdAt` / `@LastModifiedDate updatedAt`）审计时间一律走**真实时钟**，`PUT /api/v1/admin/system/clock` 拨钟对其完全无效。直接受害者：`SalesStatisticsService.java:91/:108` 按 `order.getCreatedAt().toLocalDate()` 把订单落进日桶——拨钟到目标日期后下的订单，`createdAt` 仍是真实日期，按拨后日期查销售统计恒为 0，拨钟类统计用例必挂。

  **b. REST 可见时间戳裸用 `LocalDateTime.now()`（12 处，逐行清单）**：
  | 文件 | 行 | 字段 | REST 可见处 |
  |---|---|---|---|
  | `ShipmentService.java` | 207 | `label.setPrintedAt(...)` | 面单打印时间（发货单详情） |
  | `ShipmentService.java` | 323 | `tracking.setEventTime(...)`（`recordTracking`） | 物流轨迹 `eventTime`（轨迹查询） |
  | `CouponService.java` | 71 | `userCoupon.setClaimedAt(...)` | 用户券 `claimedAt`（我的优惠券） |
  | `ReviewService.java` | 104 | `review.setReviewedAt(...)`（敏感词自动驳回路径） | 评价 `reviewedAt` |
  | `ReviewService.java` | 151 | `append.setAppendCreatedAt(...)` | 追评时间 |
  | `ReviewModerationService.java` | 55 | `review.setReviewedAt(...)`（人工通过） | 评价 `reviewedAt` |
  | `ReviewModerationService.java` | 90 | `review.setReviewedAt(...)`（人工驳回） | 评价 `reviewedAt` |
  | `NotificationRecordService.java` | 14 | 成功记录 `sentAt` | `GET /api/v1/admin/notifications` |
  | `NotificationRecordService.java` | 19 | 失败记录 `sentAt` | 同上 |
  | `DomainEventPublisher.java` | 83 | `record.setOccurredAt(...)`（`recordListenerFailure`） | `GET /api/v1/admin/events/failures` |
  | `DomainEventPublisher.java` | 99 | `record.setOccurredAt(...)`（`persistFailure`） | 同上 |
  | `AbstractDomainEvent.java` | 26 | 事件基类 `occurredAt` | 事件失败记录载荷 |

  **c. 限流滑动窗**：`RateLimitAspect.java:101` `long now = System.currentTimeMillis();`——1 分钟滑动窗（`WINDOW_MS=60_000`）用真实毫秒钟计时，拨钟对"限流窗口过期解除"完全不可观测（触发 429 后拨快 2 分钟仍然 429，只能真等 60 秒）。
- **期望**: 测试时钟是 API 契约的一部分：design-docs/01-项目概述.md §8「运行模式」末段——"黑盒测试需要的可观察支撑能力通过 `/api/v1/admin/` 下的 REST 管理接口提供，包括配置覆盖、故障注入、**测试时钟**……这些接口均……**纳入 API 契约**"；design-docs/03-通用规范与非功能设计.md §5「黑盒测试隔离」——"用例需要创建前置条件时，必须通过正式 REST API 或**已纳入契约的 ADMIN 测试支撑接口**完成"（拨钟正是此类前置条件手段，拨了必须对业务可观察面生效）。因此凡 REST 可见的业务时间戳（实体审计 `createdAt`/`updatedAt`、单据/轨迹/评审/通知/事件失败记录时间）与时间窗判定（限流滑动窗）都必须读 `SystemClockService`。不拨钟时 `SystemClockService.now()` ≡ `LocalDateTime.now()`，**全部替换点恒等无扰、零行为变化**。
- **改法**（逐文件逐行）:
  1. `CommonAutoConfiguration.java`：`@EnableJpaAuditing` → `@EnableJpaAuditing(dateTimeProviderRef = "systemClockDateTimeProvider")`，类体内新增

     ```java
         @Bean
         public DateTimeProvider systemClockDateTimeProvider() {
             return () -> Optional.of(SystemClockService.now());
         }
     ```

     补 import：`com.ecommerce.common.test.SystemClockService`、`org.springframework.context.annotation.Bean`、`org.springframework.data.auditing.DateTimeProvider`、`java.util.Optional`。
  2. 现状表 b 的 12 行逐行把 `LocalDateTime.now()` 换成 `SystemClockService.now()`。无 import 的文件补 `import com.ecommerce.common.test.SystemClockService;`（`ShipmentService`/`CouponService` 基线已有）；替换后 `java.time.LocalDateTime` import 不再被引用的文件（`ShipmentService`、`CouponService`、`ReviewService`、`ReviewModerationService`、`DomainEventPublisher`）删除该 import（`NotificationRecordService`/`AbstractDomainEvent` 仍以 `LocalDateTime` 作字段类型，保留）。
  3. `NotificationRecordService.recordFailure(...)` 签名在 `templateCode` 之后、`failureReason` 之前**插入 `String idempotencyKey` 参数**，记录项不再硬编码 `null`（COMMON-2 落地时"失败不做幂等去重"的取舍修订：失败记录同样要携带请求的幂等键，便于按键核对重复失败）；唯一调用方 `LocalNotificationServiceImpl.send()` catch 块（第108-114行）在 `getTemplateCode()` 之后补传 `request.getIdempotencyKey()`。
  4. `RateLimitAspect.java`：`isAllowed` 第101行 `System.currentTimeMillis()` 改为调用新增私有方法：

     ```java
         private long nowMillis() {
             return SystemClockService.now().atZone(ZoneId.systemDefault()).toInstant().toEpochMilli();
         }
     ```

     补 import：`com.ecommerce.common.test.SystemClockService`、`java.time.ZoneId`。
  5. 同步单测：`RateLimitAspectTest` 新增拨钟用例（limit=1 触发 429 后 `SystemClockService.setOffset(2)` → 同 key 再次放行，`finally` 里 `SystemClockService.reset()`）；`LocalNotificationServiceImplTest` 故障注入用例请求补 `idempotencyKey` 并断言失败记录的 `getIdempotencyKey()` 等于该键。
- **验收**:
  1. `grep -qF "dateTimeProviderRef" code/ecommerce-common/src/main/java/com/ecommerce/common/config/CommonAutoConfiguration.java` 命中（artifacts.tsv B11 断言）。
  2. `grep -qF "SystemClockService" code/ecommerce-common/src/main/java/com/ecommerce/common/ratelimit/RateLimitAspect.java` 命中（artifacts.tsv B11 断言）。
  3. `grep -qF "String idempotencyKey, String failureReason" code/ecommerce-common/src/main/java/com/ecommerce/common/notification/NotificationRecordService.java` 命中（artifacts.tsv B11 断言；注意裸词 `idempotencyKey` 在基线就存在于 `record(...)`/内部类，不能做锚）。
  4. `grep -qF "tracking.setEventTime(SystemClockService.now());" code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java` 命中（artifacts.tsv B14 断言；裸词 `SystemClockService` 在该文件基线已有——pickupTime/deliveredAt，不能做锚）。
  5. 反向 grep：`grep -rn "LocalDateTime.now()" code/ecommerce-common/src/main/java/ --include="*.java"` 仅剩 `SystemClockService.java`（时钟源自身）与 `CommonAutoConfiguration.java` 的 javadoc 注释行，无任何业务代码行。
  6. 模块单测：`mvn -f code/pom.xml test` 全绿（`RateLimitAspectTest` 拨钟用例、`LocalNotificationServiceImplTest` 幂等键断言在内）。
  7. 黑盒回归 24/24（全部替换点不拨钟恒等，不应有任何用例受扰）。
- **勿犯**:
  1. **已在时钟上的点不要重复动/误伤**：`ShipmentService.java:278 pickupTime`、`:280 deliveredAt`、`CouponService.java:143 usedAt` 基线已是 `SystemClockService.now()`，原样保留；`SystemClockService.java:14` 自身的 `LocalDateTime.now()` 是时钟源实现，**绝对不能改**（改了就是自引用死循环）。
  2. **不碰 Caffeine 缓存内部 ticker**：cart 7 天 TTL、商品缓存等过期机制是基础设施内部行为，未纳入 REST 可见契约；给 Caffeine 换 ticker 属高危改动且无用例背书，一律不做。`GlobalExceptionHandler.java:144` traceId 里的 `System.currentTimeMillis()`（不透明唯一串成分）与 `LocalNotificationServiceImpl.java:64` `sentRecords` 的 `Instant.now()`（无读者的死累积表，见 findings.md）同理不动。
  3. **跨模块文件清单以上 9 个 `.java` 为全集，防漏也防越界**：不要顺手去动 order/payment/user/inventory/cart 模块里的裸 `now()`（属各自模块批次的治理范围，且部分是刻意保留的内部时间）；也不要漏掉 review 两个文件——它们不在 common 模块，最容易被"按模块施工"的执行者漏掉，故本卡强调**单批原子跨模块**一次做完。
- **验证记录**: 四点分四步落地，每步后独立门禁（`code install -DskipTests` + `test-cases` 黑盒）均 24/0/0；最终整卡门禁 24/0/0 + 全仓单测 BUILD SUCCESS。
