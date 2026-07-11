# B11 · common — 通知组件与全局异常处理

本批覆盖 `ecommerce-common` 模块两处遗留缺陷：本地通知组件（`LocalNotificationServiceImpl`）故障注入检查位置错误、导致失败会穿透给调用方，且失败通知不落可查询记录；全局异常处理器（`GlobalExceptionHandler`）缺少对三类 Spring 框架级参数错误的处理，被误判为 500。三张卡全部单点行为修正，风险 low。

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
