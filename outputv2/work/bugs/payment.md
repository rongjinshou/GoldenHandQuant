# B06+B07 · payment — 支付核心与发票结算

本文件覆盖 `findings.md`「payment 模块（§6.3）」全部 14 项中的 12 项（#9 事件载荷字段、#14 状态枚举命名
对齐附录C 两项不在本文件——理由见文末「跳过条目」）、「第二轮深审（§7）」7 项（#3/#5/#6/#7/#9/#10/#13）、
「第三轮深审·模块内」3 项（#8/#9/#10）、「第三轮深审·跨领域」2 项（#7/#8），并入本模块的
`app §6.12 #3`（支付回调签名校验），以及第四轮设计-实现对比新发现 1 项（PAY-B3，发票抬头长度
上限）。按执行批次拆成两节：

- **§A pay-core（批次 B06）**：支付发起 / 支付回调 / 退款申请-审核-仓库验收-完成。
- **§B pay-ext（批次 B07）**：发票开具 / 结算批次 / 支付侧通知渠道收尾。

**不做**（连带排查后明确排除，不在本文件任何卡片里）：

- 退款审核 / 仓库验收 / 发票开具 / 结算批次生成的**审计日志接入**——纯 `AuditLogService` 基础设施接入项，
  归 `S3-audit.md`（B18）的 AUD-5/AUD-6/AUD-7 三张卡。本文件 PAY-A5/PAY-B1/PAY-B2（以及与 PAY-B1
  同在 `generateInvoice` 里追加校验的 PAY-B3）会分别修改这三个方法，
  但**只改业务逻辑，不新增 `AuditLogService` 依赖**——B18 晚于本文件两批执行，届时会在本文件已改完的基础上
  再插入审计调用。**PAY-B1 有一处需要特别注意的构造函数参数顺序冲突，见该卡的「勿犯」第 1 条与本文件末尾
  「存疑点」。**
- 支付回调限流（`@RateLimit`）——归 `S4-config.md`（B19）。
- `PaymentSucceededEvent`/`RefundCompletedEvent` 事件类的权威定义迁移（到 `ecommerce-common`）、影子类删除、
  以及基于这两个事件新增的跨模块监听器（`PaymentSucceededInventoryListener` 等）——归 `S2-events.md`
  §A/§B（B13/B16）。本文件所有卡片凡是涉及这两个事件对象本身构造调用的地方，都明确标注"不改动该行"。
- `ORDER_STATUS_CONFLICT` 里 `PaymentValidator.validate()` 对订单状态的校验（第二轮深审 #4）——已属
  `order.md` 范围，本文件 PAY-A3 只在其**之后**插入金额校验，不碰状态校验那几行。

**依赖顺序**：§A 六张卡（PAY-A1..PAY-A6）之间除 PAY-A1 与 PAY-A2/PAY-A5 有共享文件外无强制顺序，建议按
编号顺序执行，每 2~3 卡编译自检一次。§B 三张卡（PAY-B1/PAY-B2/PAY-B3）中 PAY-B1 与 PAY-B2 互相独立，
PAY-B3 依赖 PAY-B1 先落地（其改法锚点在 PAY-B1 建立的参数校验区内），按编号顺序执行即可。§A 必须整体
先于 §B（批次号 B06 < B07），但这只是执行顺序约定，两节内容互不依赖。

---

## §A pay-core（批次 B06）— 支付 / 回调 / 退款

### PAY-A1 | PaymentStatus 两处枚举值命名不符附录C（PENDING→CREATED、REFUNDED→CLOSED）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/entity/PaymentStatus.java`
  （另有两处使用点分别在 PAY-A2、PAY-A5 涉及的文件里，见改法第 2/3 条）
- **现状**: 基线 `PaymentStatus` 枚举（6行）为：
  ```java
  public enum PaymentStatus {
      PENDING,
      SUCCESS,
      FAILED,
      REFUNDED
  }
  ```
  `PaymentService.pay()` 第 90 行新建支付单时 `payment.setStatus(PaymentStatus.PENDING)`（PUB-009 断言
  创建支付单后状态应为 `CREATED`）；`RefundService.processRefund()` 第 177 行退款完成后
  `payment.setStatus(PaymentStatus.REFUNDED)`。
- **期望**: `design-docs/附录C-数据模型.md` `payments.status` 取值为 `CREATED/SUCCESS/FAILED/CLOSED`
  （无 `PENDING`/`REFUNDED`）。依据: 附录C；PUB-009。
- **改法**:
  1. `PaymentStatus.java`：
     ```java
     public enum PaymentStatus {
         CREATED,
         SUCCESS,
         FAILED,
         CLOSED
     }
     ```
  2. `PaymentService.java` 第 90 行：`payment.setStatus(PaymentStatus.PENDING);` →
     `payment.setStatus(PaymentStatus.CREATED);`（该文件其余改动见 PAY-A2，两卡改的是同一文件不同片段，
     不冲突）。
  3. `RefundService.java` 第 177 行：`payment.setStatus(PaymentStatus.REFUNDED);` →
     `payment.setStatus(PaymentStatus.CLOSED);`（该文件其余改动见 PAY-A5）。
  4. 全仓搜索并同步改写：`grep -rn "PaymentStatus.PENDING\|PaymentStatus.REFUNDED" code/`。基线命中
     （生产代码只有上面两处，其余全在单测）：
     - `PaymentControllerTest.java`（约第 57 行，构造 `PaymentRecord` 用的 mock 数据）
     - `PaymentCallbackServiceTest.java`（约第 71、106 行）
     - `PaymentServiceTest.java`（约第 107、117、142、174 行，多处）
     - `SettlementBatchServiceTest.java`（约第 79、125 行）
     全部 `PENDING`→`CREATED`；`REFUNDED` 目前只有生产代码那一处引用，若上述测试文件里也有请一并处理。
- **验收**: `grep -rn "PaymentStatus.PENDING\|PaymentStatus.REFUNDED" code/` 零命中；
  `POST /api/v1/payment/pay` 响应体 `status` 字段为 `"CREATED"`；退款走完仓库验收流程后
  `GET /api/v1/payment/{paymentNo}` 的 `status` 为 `"CLOSED"`；
  `mvn -s maven-settings.xml -f code/pom.xml install -DskipTests` 编译通过。

---

### PAY-A2 | PaymentService 越权直查订单表 / 金额未 roundToCent / confirmPayment 同步执行后置动作

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentService.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentSucceededNotificationListener.java`
     【新增】
- **现状**（对应 findings §6.3 #8、第二轮深审 #3、#6）：
  1. `pay()` 第 78 行经私有方法 `queryOrderDirectly()`（第 139-170 行）用注入的 `JdbcTemplate` 手写
     SQL `SELECT id AS order_id, ... FROM orders WHERE id = ?` 直接查询 orders 表——绕过已注入却从未
     调用的 `OrderQueryService orderQueryService` 字段，违反跨模块边界规则（02§3、09§1）。
  2. `pay()` 第 88 行 `payment.setPaidAmount(request.getAmount())` 直接落库客户端传入的原始精度金额，
     未经 `MonetaryUtil.roundToCent`。
  3. `confirmPayment()`（第 110-134 行）在 `@Transactional` 方法内同步调用三个私有方法：
     `createLogistics()`（174-179 行，只打日志，无真实动作）、`earnPoints()`（181-186 行，同样只打日志）、
     `sendNotifications()`（188-202 行，**真实**调用 `notificationService.send(...)`）。三者与事件发布
     共享同一个 `@Transactional` 方法——`sendNotifications` 任何异常都会导致 `confirmPayment` 整体抛出，
     回滚支付确认事务，违反 PUB-108 与 09§3"任一后置动作失败不得导致支付确认失败"的要求。
- **期望**:
  1. design-docs/09§1："支付服务通过 OrderQueryService 查询订单信息...不得直接查询或更新订单数据库表"。
  2. design-docs/03§1：入库金额统一 `MonetaryUtil.roundToCent`（HALF_UP，2 位小数）。
  3. design-docs/09§3："物流创建、积分发放和通知发送必须通过本地事件监听器异步触发。任一后置动作失败
     不得导致支付确认失败"；03§8。
- **改法**:
  1. 删除私有方法 `queryOrderDirectly()`（第 136-170 行整段，含其上的 javadoc）、字段
     `private final JdbcTemplate jdbcTemplate;`（第 52 行）及其构造参数（第 60 行），删除
     `import org.springframework.jdbc.core.JdbcTemplate;`。`pay()` 第 78 行：
     ```java
     OrderDto order = queryOrderDirectly(request.getOrderId());
     ```
     改为
     ```java
     OrderDto order = queryPayableOrder(request.getOrderId());
     ```
     并在原 `queryOrderDirectly` 的位置放一个新的私有方法（保留故障注入钩子，否则黑盒
     `order-query-service-unavailable` 故障注入用例会失效）：
     ```java
     private OrderDto queryPayableOrder(Long orderId) {
         if (com.ecommerce.common.test.FaultInjectionRegistry.isActive("order-query-service-unavailable")) {
             throw new RuntimeException("Fault injected: order-query-service-unavailable");
         }
         return orderQueryService.getPayableOrder(orderId);
     }
     ```
     `orderQueryService` 字段基线已注入（构造函数已有该参数，只是从未被调用）。`OrderQueryService.getPayableOrder`
     在 order 模块基线已存在且已实现"非可支付状态/不存在时抛异常"，直接复用，不需要 order 模块任何改动。
     `com.ecommerce.common.exception.BusinessException` 的 import 若 `getPayment()` 等其余方法不再使用则删除
     （`ResourceNotFoundException` 仍在用，保留）。
  2. `pay()` 第 88 行：
     ```java
     payment.setPaidAmount(request.getAmount());
     ```
     改为
     ```java
     payment.setPaidAmount(MonetaryUtil.roundToCent(request.getAmount()));
     ```
     补 `import com.ecommerce.common.money.MonetaryUtil;`。
  3. 删除 `createLogistics()`、`earnPoints()`、`sendNotifications()` 三个私有方法（第 172-202 行含
     `// ---- Synchronous post-payment actions ----` 分隔注释一并删除），删除字段
     `private final LocalNotificationService notificationService;`（第 47 行）及其构造参数（第 57 行），
     删除不再使用的 `NotificationChannel`/`NotificationRequest`/`java.util.Map` import。`confirmPayment()`
     方法体只保留发布事件这一行及日志：
     ```java
     @Transactional
     public void confirmPayment(PaymentRecord payment) {
         log.info("Confirming payment: paymentNo={}, orderId={}",
                 payment.getPaymentNo(), payment.getOrderId());

         PaymentSucceededEvent event = new PaymentSucceededEvent( /* 保持当前实参与 import 不变，见下方说明 */ );
         eventPublisher.publish(event);

         log.info("Payment confirmed successfully: paymentNo={}", payment.getPaymentNo());
     }
     ```
     **`PaymentSucceededEvent` 那一行（import 路径 + 构造实参）本卡完全不改动**——它的权威定义迁移是
     `S2-events.md` §A（B13，与本批的先后顺序无关紧要，本卡措辞两态兼容）的职责；本卡只删除它前面的三行同步调用
     （`createLogistics(payment); earnPoints(payment); sendNotifications(payment);`），事件本身的构造
     代码维持文件里当前实际写的样子（无论此刻它 import 的是 `com.ecommerce.payment.event.PaymentSucceededEvent`
     还是已经迁移后的 `com.ecommerce.common.event.PaymentSucceededEvent`）。
  4. 新增文件 `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentSucceededNotificationListener.java`：
     ```java
     package com.ecommerce.payment.service;

     import com.ecommerce.common.notification.LocalNotificationService;
     import com.ecommerce.common.notification.NotificationChannel;
     import com.ecommerce.common.notification.NotificationRequest;
     import org.slf4j.Logger;
     import org.slf4j.LoggerFactory;
     import org.springframework.stereotype.Component;
     import org.springframework.transaction.event.TransactionPhase;
     import org.springframework.transaction.event.TransactionalEventListener;

     import java.util.Map;

     /**
      * Sends the payment-success notification in reaction to PaymentSucceededEvent.
      * Runs strictly AFTER_COMMIT so a notification failure can never roll back
      * payment confirmation (design-docs/09 §3; PUB-108).
      */
     @Component
     public class PaymentSucceededNotificationListener {

         private static final Logger log = LoggerFactory.getLogger(PaymentSucceededNotificationListener.class);

         private final LocalNotificationService notificationService;

         public PaymentSucceededNotificationListener(LocalNotificationService notificationService) {
             this.notificationService = notificationService;
         }

         @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
         public void onPaymentSucceeded(/* 事件类型与 import 与 confirmPayment() 里发布的那个保持一致 */ Object event) {
             // 用事件对象的 getPaymentNo()/getPaidAmount() 取值——具体类型见 confirmPayment() 当前 import
         }
     }
     ```
     **具体写法**：把参数类型从占位的 `Object event` 改成 `confirmPayment()` 里实际 import 的那个
     `PaymentSucceededEvent` 类型（`com.ecommerce.payment.event.PaymentSucceededEvent` 或
     `com.ecommerce.common.event.PaymentSucceededEvent`，两者都有 `getPaymentNo()`/`getPaidAmount()`
     两个 getter，方法体写法一致），方法体：
     ```java
         @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
         public void onPaymentSucceeded(PaymentSucceededEvent event) {
             log.info("Sending payment-success notification: paymentNo={}", event.getPaymentNo());
             NotificationRequest request = new NotificationRequest();
             request.setBizType("PAYMENT_SUCCESS");
             request.setBizId(event.getPaymentNo());
             request.setChannel(NotificationChannel.SMS); // 15§2：支付成功→SMS（第二轮深审 #13）
             request.setTemplateCode("payment_success");
             request.setVariables(Map.of(
                     "paymentNo", event.getPaymentNo(),
                     "amount", event.getPaidAmount().toString()));
             request.setIdempotencyKey("pay_notify_" + event.getPaymentNo());
             notificationService.send(request);
         }
     ```
     只能经 `LocalNotificationService.send(NotificationRequest)` 发送，绝不能直接调用 `MockMailSender`/
     `MockSmsSender`（03§7）。
- **验收**: `pay()` 编译后不再有 `JdbcTemplate` 字段（`grep -n "JdbcTemplate" PaymentService.java` 零命中）；
  用小数位 > 2 的金额（如 99.005）发起支付，落库 `paidAmount` 为两位小数（99.01，HALF_UP）；对
  `notification-send-failure` 类故障注入走完整支付回调流程，支付仍以 `SUCCESS` 收尾（
  `GET /api/v1/payment/{paymentNo}` 不受影响）；`PaymentSucceededNotificationListener` 在事务提交后
  才发送 SMS 通知（`GET /api/v1/admin/notifications` 可查到 `channel=SMS` 的记录）。
- **勿犯**:
  1. **`PaymentService` 构造函数从 7 参数减到 5 参数（去掉 `notificationService`、`jdbcTemplate`）后，
     `PaymentServiceTest.java` 必须同步改，否则 `mvn -f code/pom.xml install -DskipTests` 在
     test-compile 阶段直接失败，黑盒测试完全跑不起来**——这是本卡最容易造成的事故：
     - 第 72 行起 `new PaymentService(paymentRecordRepository, paymentValidator, eventPublisher,
       notificationService, orderPaymentStatusUpdater, orderQueryService, jdbcTemplate)` 改成 5 参数
       （去掉 `notificationService`、`jdbcTemplate` 两个实参，其余顺序不变）。
     - 三个整块断言"旧同步 bug 是预期行为"的测试方法——`testConfirmPayment_synchronousPostActions`
       （约 135 行起）、`testConfirmPayment_postActionFailure_rollsBackPayment`（约 167 行起）、
       `testConfirmPayment_usesJdbcTemplate`（约 192 行起）——必须删除或整体改写（它们断言的正是本卡
       要修的 bug 本身，例如 `verify(notificationService).send(...)`、
       `assertThrows(RuntimeException.class, () -> paymentService.confirmPayment(payment))`）。
     - `testPay_validRequest_createsPaymentRecord` 里 `when(jdbcTemplate.queryForObject(...))` 与
       `verify(jdbcTemplate)...`/`verify(orderQueryService, never())...` 需要反过来：改成
       `when(orderQueryService.getPayableOrder(1L)).thenReturn(orderDto)` +
       `verify(orderQueryService).getPayableOrder(1L)`；`assertEquals(PaymentStatus.PENDING, ...)`
       同步改 `PaymentStatus.CREATED`（见 PAY-A1）。
  2. **不要把删掉的库存扣减动作"顺手"加回 `confirmPayment()`。** inventory 侧的
     `PaymentSucceededInventoryListener` 是另一批次（`S2-events.md` §B / B16）新增的独立监听器，本卡
     不涉及库存扣减的接线，`confirmPayment()` 改完后应该只剩发布事件 + 两行日志。
  3. **不要改动 `PaymentSucceededEvent` 的 import 路径或构造参数本身**（事件类迁移是 B13 的职责）——
     本卡只删除 `confirmPayment()` 里事件发布之前的三行同步调用，那一行本身照抄当前文件已有的样子。
  4. **新增的 `PaymentSucceededNotificationListener` 不需要接 `FailedEventRecord`/`DomainEventPublisher.
     recordListenerFailure` 之类的失败落库逻辑**——`findings.md` 第三轮深审·事件失败落库 已经明确把这个类
     排除在"6 个需要落库监听失败"的名单外（`LocalNotificationServiceImpl.send()` 内部自己 catch 并经
     `NotificationRecordService` 记录失败，不需要外层再包一层）。

---

### PAY-A3 | PaymentValidator 支付发起金额校验完全缺失

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentValidator.java`
- **现状**（findings §6.3 #2）: `validate()`（第 34-86 行）依次校验订单存在、订单状态、金额 > 0、
  支付方式合法、无重复成功支付——全程未比较 `request.getAmount()` 与 `order.getPayableAmount()`。付
  任意正数金额（哪怕 1 分钱）都能让订单被标记已支付。
- **期望**: design-docs/09§2："本系统仅支持全额支付。支付金额必须等于订单应付金额...支付金额小于或
  大于订单应付金额均应拒绝"。依据: 09§2；README §7 `PAYMENT_AMOUNT_MISMATCH`/400。
- **改法**: 在金额 > 0 校验（原第 52-56 行）之后、"Validate payment method"注释块（原第 54 行附近，
  即第二个校验块）之前插入：
  ```java
  // Validate payment amount equals the order's payable amount (design-docs/09 §2)
  if (request.getAmount().compareTo(order.getPayableAmount()) != 0) {
      throw new BusinessException("PAYMENT_AMOUNT_MISMATCH",
              "Payment amount " + request.getAmount()
                      + " does not match order payable amount " + order.getPayableAmount());
  }
  ```
  `BusinessException` 本文件已 import，无需新增依赖。**不要**碰其上的订单状态校验分支——按批次
  顺序 B03（`order.md` ORD-A8）先于本批执行，打开文件时该分支应已是
  `ConflictException("ORDER_STATUS_CONFLICT", ...)`（B03 已执行时）；若 B03 被跳过，则仍是基线的
  `BusinessException("ORDER_STATUS_INVALID", ...)`/`status != OrderStatus.CREATED && status !=
  OrderStatus.PAYING` 那几行。**无论哪种形态，一律不碰、也不要按本卡描述去"恢复"成其中任何一种**
  ——那是 `order.md` 的范围（第二轮深审 #4），本卡只在其后插入新分支。
- **验收**: 对一笔应付 100.00 的订单发起 `POST /api/v1/payment/pay`，`amount=99.99` 或 `100.01` 均
  返回 400 `PAYMENT_AMOUNT_MISMATCH`；`amount=100.00` 正常创建支付单（PUB-009 等既有用例不回归）。

---

### PAY-A4 | 支付回调：签名从不校验 / 金额从不校验 / FAILED 回调状态冲突与幂等处理不完整

- 风险: high · 置信度: definite（其中"重复 FAILED 幂等"子项 findings.md 原标 `suspicious`，已经
 参考实现验证按下述方式实现）
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentCallbackService.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/controller/PaymentController.java`
- **现状**:
  1. （对应 `app §6.12 #3`，并入本模块）`PaymentController.callback()`（第 52-58 行）只有
     `@RequestBody PaymentCallbackRequest request` 一个参数，从不读取 `X-Payment-Signature` 请求头；
     `PaymentCallbackService.processCallback()`（第 41-43 行）只把 `request.getSignature()`（请求体
     字段，从未真正用于校验）打进日志，两者都不做任何签名比对——伪造回调畅通无阻。design-docs/02§8
     第 4 条："支付回调接口使用本地模拟签名头 `X-Payment-Signature`"；README §6 第 7 节
     `/api/v1/payment/callback` 认证方式标注"签名"；黑盒 harness 固定用
     `test-cases/.../fixture/PaymentFixture.java` 的常量 `VALID_SIGNATURE = "valid-signature"`，
     经 `X-Payment-Signature` 头发起回调。
  2. （对应第三轮深审·跨领域 #7）`processSuccessCallback()`（第 67-92 行）第 79 行
     `payment.setPaidAmount(request.getAmount())`——直接采信回调体里的金额并置 `SUCCESS`，从不与订单
     应付金额比对。一次正常 `pay()` 后，用抬高的金额重放回调即可让 `paidAmount`（后续退款/开票的计算
     基础）被放大。
  3. （对应第二轮深审 #5、findings §6.3 #12）`processFailedCallback()`（第 94-114 行）：已 `SUCCESS`
     再收到 `FAILED` 回调，第 101 行抛 `BusinessException("PAYMENT_STATUS_CONFLICT", ...)`→400，应为
     状态冲突 409；且已是 `FAILED` 状态再收到一次 `FAILED` 回调（比如网关重推）没有任何幂等短路，会
     重复执行"置 FAILED + 回写订单支付失败"的副作用。
- **期望**:
  1. design-docs/02§8.4、09§3（回调鉴权）；README §6 payment/callback 认证方式"签名"。
  2. design-docs/09§2（金额必须等于订单应付金额）；README §7 `PAYMENT_AMOUNT_MISMATCH`/400。
  3. design-docs/03§2（`ConflictException`=409）；03§3（`paymentNo`+`callbackSequence` 幂等，
     "重复请求应返回第一次处理结果，不得重复扣款"）。
- **改法**:
  1. `PaymentController.java`：`callback()` 签名改为：
     ```java
     @PostMapping("/callback")
     public ResponseEntity<String> callback(
             @RequestBody PaymentCallbackRequest request,
             @RequestHeader(value = "X-Payment-Signature", required = false) String signature) {
         log.info("Payment callback received: paymentNo={}, status={}",
                 request.getPaymentNo(), request.getStatus());
         paymentCallbackService.processCallback(request, signature);
         return ResponseEntity.ok("OK");
     }
     ```
     补 `import org.springframework.web.bind.annotation.RequestHeader;`。注意签名来自**请求头**，不是
     `request.getSignature()`（请求体字段本身不用删，只是不再作为鉴权依据）。**不要**在这里顺手加
     `@RateLimit`——回调限流是 `S4-config.md`（B19）的职责，本卡不涉及。
  2. `PaymentCallbackService.java`：`processCallback` 签名改为
     `processCallback(PaymentCallbackRequest request, String signature)`，方法体最前面（幂等检查之前）
     插入签名校验：
     ```java
     private static final String VALID_SIGNATURE = "valid-signature";
     ...
     @Transactional
     public void processCallback(PaymentCallbackRequest request, String signature) {
         log.info("Processing payment callback: paymentNo={}, status={}",
                 request.getPaymentNo(), request.getStatus());

         if (!VALID_SIGNATURE.equals(signature)) {
             throw AuthorizationException.unauthorized("Invalid payment callback signature");
         }
         // 原有幂等检查与状态分支保持不变
     ```
     `AuthorizationException.unauthorized(String)` 是 `common/exception/AuthorizationException.java`
     基线已有的静态工厂方法，直接 import 使用（`com.ecommerce.common.exception.AuthorizationException`），
     无需新增依赖。字面量 `"valid-signature"` 与黑盒 harness 的 `PaymentFixture.VALID_SIGNATURE` 一致。
  3. `processSuccessCallback()` 第 79 行前插入金额比对，基准是 `payment.getOrderAmount()`（`pay()` 时
     已锁定在 `PaymentRecord` 上的订单应付金额，不用重新查订单）：
     ```java
     BigDecimal callbackAmount = MonetaryUtil.roundToCent(request.getAmount());
     if (payment.getOrderAmount() == null || callbackAmount.compareTo(payment.getOrderAmount()) != 0) {
         throw new BusinessException("PAYMENT_AMOUNT_MISMATCH",
                 "Callback amount " + callbackAmount
                         + " does not match order payable amount " + payment.getOrderAmount());
     }
     payment.setPaidAmount(callbackAmount); // 原第79行，改用校验并四舍五入到分之后的金额
     ```
     补 `import com.ecommerce.common.money.MonetaryUtil;`（`java.math.BigDecimal` 已 import）。
  4. `processFailedCallback()` 方法体最前面加已 `FAILED` 幂等短路，`SUCCESS` 冲突分支改 409：
     ```java
     private void processFailedCallback(PaymentCallbackRequest request) {
         PaymentRecord payment = paymentRecordRepository.findByPaymentNo(request.getPaymentNo())
                 .orElseThrow(() -> new ResourceNotFoundException("PaymentRecord", request.getPaymentNo()));

         if (payment.getStatus() == PaymentStatus.FAILED) {
             log.info("Payment already FAILED, ignoring duplicate callback: paymentNo={}",
                     request.getPaymentNo());
             return;
         }
         if (payment.getStatus() == PaymentStatus.SUCCESS) {
             throw new ConflictException("PAYMENT_STATUS_CONFLICT",
                     "Cannot mark as FAILED when already SUCCESS");
         }
         // 其余（setStatus(FAILED)/setCallbackSequence/setCallbackData/save/markPaymentFailed）不变
     }
     ```
     补 `import com.ecommerce.common.exception.ConflictException;`（`ConflictException(code,message)`
     双参构造函数由 `S1-quick-wins.md` 的 S1-2 卡（B01，先于本批 B06 执行）已加好，直接可用；
     若编译报 `ConflictException` 无双参构造（说明 B01 被跳过），先照 `S1-quick-wins.md` S1-2
     补上该构造函数再继续本卡）。
- **验收**: 不带 `X-Payment-Signature` 头或带错误值发起回调 → 401 `UNAUTHORIZED`；带
  `valid-signature` 且金额与下单应付金额不一致 → 400 `PAYMENT_AMOUNT_MISMATCH`；金额一致 → 正常
  `SUCCESS` 流程不受影响（PUB-009/PUB-108 等既有用例不回归）；对同一已 `SUCCESS` 的支付单重放一次
  `FAILED` 回调 → 409 `PAYMENT_STATUS_CONFLICT`；对同一已 `FAILED` 的支付单重放 `FAILED` 回调（不同
  `callbackSequence`）→ 直接返回 200，不重复调用 `orderPaymentStatusUpdater.markPaymentFailed`。
- **勿犯**:
  1. **`processCallback` 从 1 参数改 2 参数是破坏性签名变更**——`PaymentCallbackServiceTest.java` 里
     直接调用 `callbackService.processCallback(request)`（约第 80/114/149 行，纯 Java 调用，非
     MockMvc）必须同步改成两参数调用（第二个实参传 `"valid-signature"` 或按各用例场景传对应值），
     否则 test-compile 失败；该文件类头注释（约第 29 行）"processCallback() does NOT verify
     signature"与 `@DisplayName("callback is processed WITHOUT signature verification")` 用例
     （断言的就是本卡要修的 bug）需要一并删除或反向改写。`PaymentControllerTest` 走 `MockMvc`（HTTP
     层），Java 签名变化不影响其编译，但"回调返回 200"的用例若不带签名头会从 200 变 401，需要给该
     用例补上 `X-Payment-Signature: valid-signature` 头，否则会留红。
  2. **金额比对基准是 `payment.getOrderAmount()`**（`PaymentRecord` 已有此字段，`pay()` 时已赋值），
     不是重新查订单——不要在回调路径里引入新的跨模块查询。
  3. 不要把 PAY-A1 负责的枚举重命名（`PaymentStatus.PENDING`/`REFUNDED`）顺手在本卡里改掉，本卡对
     `PaymentStatus` 只读不写。

---

### PAY-A5 | RefundService：申请退款 orderId 来源与幂等键缺失、审核直接跳过仓库验收、完成通知渠道错误

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/RefundService.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/dto/RefundApplyRequest.java`
  3. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/repository/RefundRecordRepository.java`
  4. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/entity/RefundRecord.java`
- **现状**:
  1. （对应第三轮深审·模块内 #8、findings §6.3 #10）`applyRefund()`（第 59-92 行）第 81 行
     `refund.setOrderId(request.getOrderId())`——直接采信客户端请求体里的 `orderId`（可与 `paymentNo`
     所属订单不一致地伪造），而不是从已查出、已校验过的 `PaymentRecord`（`payment.getOrderId()`）取值；
     该被污染的 `orderId` 后续会经 `RefundCompletedEvent` 驱动错误的订单被标记 `REFUNDED`。整个方法
     也没有幂等键，重复提交同一笔退款申请会创建多条重复退款单，违反 03§3。
  2. （对应 findings §6.3 #3、第二轮深审 #7）`reviewRefund()`（第 98-124 行）审核通过分支调用私有
     `approveRefund()`（第 127-141 行），其内部把状态置 `RefundStatus.APPROVED` 后立即在第 136 行
     调用 `processRefund(refund)`——退款当场完成，完全跳过仓库验收（`warehouseAccept()`，第
     143-165 行）这一步，与 09§4"商家审核通过后不得直接退款，必须等待仓库验收"矛盾。`reviewRefund`
     第 106 行对非 `PENDING_REVIEW` 状态统一抛 `BusinessException("REFUND_STATUS_INVALID")`→400，
     README 冻结码 `REFUND_WAITING_WAREHOUSE_ACCEPT`/409 在全仓库从未被抛出过。
  3. （对应第二轮深审 #9）`processRefund()`（第 168-186 行）内 `sendRefundNotification()` 第 206 行
     `request.setChannel(NotificationChannel.EMAIL)`——退款完成通知应走 `IN_APP`。
- **期望**:
  1. design-docs/09§4："财务退款"以支付单为准，非客户端自报；03§3 幂等规范：退款申请幂等键
     `refundRequestNo`。
  2. design-docs/09§4："商家审核通过后不得直接退款，必须等待仓库验收"；README §7
     `REFUND_WAITING_WAREHOUSE_ACCEPT`/409。
  3. design-docs/15§2：退款状态通知走 `IN_APP`（`EMAIL` 只用于注册激活/发票）。
- **改法**:
  1. `RefundApplyRequest.java` 新增字段（保留原有 3 参数构造函数不变）：
     ```java
     private String refundRequestNo;
     public String getRefundRequestNo() { return refundRequestNo; }
     public void setRefundRequestNo(String refundRequestNo) { this.refundRequestNo = refundRequestNo; }
     ```
  2. `RefundRecordRepository.java` 新增方法：
     ```java
     Optional<RefundRecord> findByRefundRequestNo(String refundRequestNo);
     ```
  3. `RefundRecord.java` 新增字段（放在 `refundNo` 字段之后）：
     ```java
     @Column(name = "refund_request_no", unique = true, length = 64)
     private String refundRequestNo;

     public String getRefundRequestNo() { return refundRequestNo; }
     public void setRefundRequestNo(String refundRequestNo) { this.refundRequestNo = refundRequestNo; }
     ```
     （`ddl-auto` 均为 `update`/`create-drop`，H2 自动建列，不用手写迁移脚本。）
  4. `applyRefund()` 方法体最前面（日志行之后，查支付记录之前）插入幂等短路：
     ```java
     if (request.getRefundRequestNo() != null) {
         Optional<RefundRecord> existing = refundRecordRepository
                 .findByRefundRequestNo(request.getRefundRequestNo());
         if (existing.isPresent()) {
             return toRefundResponse(existing.get());
         }
     }
     ```
     补 `import java.util.Optional;`（若未 import）。第 81 行
     `refund.setOrderId(request.getOrderId());` → `refund.setOrderId(payment.getOrderId());`（`payment`
     变量已在同方法前面通过 `paymentNo` 查出，直接复用），并在构建 `refund` 实体那几行补一行
     `refund.setRefundRequestNo(request.getRefundRequestNo());`。
  5. `reviewRefund()` 第 106 行前插入新分支，`REFUND_STATUS_INVALID` 顺带改用 `ConflictException`
     （与相邻分支保持一致的 409 语义，同时也是 `RefundStatus` 状态冲突场景，符合 03§2）：
     ```java
     if (refund.getStatus() == RefundStatus.WAITING_WAREHOUSE_ACCEPT) {
         throw new ConflictException("REFUND_WAITING_WAREHOUSE_ACCEPT",
                 "Refund " + refundId + " is already waiting on warehouse acceptance");
     }
     if (refund.getStatus() != RefundStatus.PENDING_REVIEW) {
         throw new ConflictException("REFUND_STATUS_INVALID",
                 "Refund is not in PENDING_REVIEW status: " + refund.getStatus());
     }
     ```
     补 `import com.ecommerce.common.exception.ConflictException;`（双参构造函数 S1-2 已提供；
     若编译报 `ConflictException` 无双参构造（说明 B01 被跳过），先照 `S1-quick-wins.md` S1-2
     补上该构造函数再继续本卡）。
  6. `approveRefund()` 第 131 行 `refund.setStatus(RefundStatus.APPROVED);` →
     `refund.setStatus(RefundStatus.WAITING_WAREHOUSE_ACCEPT);`，**删除**第 136 行
     `processRefund(refund);` 这一调用——`approveRefund` 到此为止，不再触发退款完成。`warehouseAccept()`
     本身不用改：它已经在验收成功后调用 `processRefund(refund)`（第 160 行），现在变成 `processRefund`
     唯一的调用入口。
  7. `sendRefundNotification()` 第 206 行：`request.setChannel(NotificationChannel.EMAIL);` →
     `request.setChannel(NotificationChannel.IN_APP);`。
  8. `processRefund()` 第 177 行 `payment.setStatus(PaymentStatus.REFUNDED)` 的重命名由 PAY-A1 负责，
     本卡不重复处理，但改完后该行应读作 `payment.setStatus(PaymentStatus.CLOSED)`。
- **验收**:
  - 两次带相同 `refundRequestNo` 的 `POST /api/v1/refunds/apply` 只创建一条退款记录，第二次返回与
    第一次相同的 `refundId`。
  - 退款单 `orderId` 恒等于 `paymentNo` 对应支付记录的 `orderId`，即使请求体里塞了别的 `orderId`。
  - 审核通过（`approved=true`）后 `GET /api/v1/refunds/{refundId}` 状态为 `WAITING_WAREHOUSE_ACCEPT`，
    不是 `COMPLETED`；对处于该状态的退款单再次调用 `/review` → 409 `REFUND_WAITING_WAREHOUSE_ACCEPT`。
  - 只有调用 `POST /api/v1/admin/refunds/{refundId}/warehouse-accept` 之后状态才变为 `COMPLETED`，
    且此时才发出 `IN_APP` 渠道的 `REFUND_COMPLETED` 通知。
- **勿犯**:
  1. **不要漏删 `approveRefund()` 里 `processRefund(refund);` 那一行**——只改状态值不删这行调用，
     退款依旧会在审核通过时立刻完成，是本卡最容易犯的"改了一半"错误。
  2. `RefundCompletedEvent` 的构造调用（在 `processRefund()` 内）不要改动其 import/参数——事件类
     迁移是 B13 职责，本卡只改状态值和它上面的 `orderId` 来源。
  3. **不要在本卡里给 `reviewRefund`/`warehouseAccept` 加 `auditLogService.record(...)`。**
     退款审核/仓库验收的审计日志是 `S3-audit.md`（B18）的 AUD-5 卡的职责，AUD-5 明确假设本卡改完后
     `RefundService` 构造函数仍是 5 参数
     `(refundRecordRepository, paymentRecordRepository, refundCalculator, eventPublisher,
     notificationService)`——本卡不新增任何构造参数，与 AUD-5 的假设一致，不需要额外处理。
  4. `RefundServiceTest.java` 里若有断言"审核通过即完成退款/状态变 COMPLETED"或断言 `orderId` 取自
     request 的用例，会随本卡改变而失败（非编译错误，构造函数参数个数不变），属预期回归，可同步改写
     断言或删除；`applyRefund` 若有测试用 mock 校验 `refund.getOrderId()` 等于 `request.getOrderId()`
     的断言，需要反过来断言等于 `payment.getOrderId()`。

---

### PAY-A6 | RefundCalculator：退款公式多扣固定 1.00 + 手续费率硬编码不读运行时配置

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/RefundCalculator.java`
- **现状**（findings §6.3 #4、第三轮深审·模块内 #9）: `calculate()`（第 29-45 行）第 34 行手续费率
  直接取 `paymentConfig.getRefundFeeRate()`（静态配置，不支持运行时覆盖）；第 38 行在算出
  `baseRefund = paidAmount × (1-feeRate)` 之后又用 `MonetaryUtil.subtract(baseRefund, BigDecimal.ONE)`
  多减了固定 1 元，design-docs 明确不允许任何固定费用。
- **期望**: design-docs/09§5："退款金额 = 实付金额 × (1 - 手续费率)...不得额外扣除固定费用"，默认
  手续费率 2%；design-docs/附录B `payment.refund-fee-rate` 支持运行时覆盖（同 `invoice.tax-rate` 的
  `RuntimeConfigRegistry` 用法）。
- **改法**: `calculate()` 方法体改为：
  ```java
  public BigDecimal calculate(BigDecimal paidAmount) {
      if (paidAmount == null || paidAmount.compareTo(BigDecimal.ZERO) <= 0) {
          return BigDecimal.ZERO;
      }

      BigDecimal feeRate = RuntimeConfigRegistry.getBigDecimal(
              "payment.refund-fee-rate", paymentConfig.getRefundFeeRate());
      BigDecimal refundFactor = BigDecimal.ONE.subtract(feeRate);

      BigDecimal refund = MonetaryUtil.multiply(paidAmount, refundFactor);

      log.debug("Refund calculated: paid={}, factor={}, refund={}", paidAmount, refundFactor, refund);
      return refund;
  }
  ```
  即：第 34 行手续费率改用 `RuntimeConfigRegistry.getBigDecimal("payment.refund-fee-rate",
  paymentConfig.getRefundFeeRate())`（`paymentConfig` 仍作为兜底默认值注入，构造函数不变）；删除原来
  的中间变量 `baseRefund` 与第 38 行再减 1.00 那一步，直接用 `MonetaryUtil.multiply` 一步算出最终
  `refund`。补 `import com.ecommerce.common.test.RuntimeConfigRegistry;`；`java.math.RoundingMode`
  的 import 若不再直接使用可删（`MonetaryUtil.multiply` 内部已处理 HALF_UP 舍入）。
- **验收**: `paidAmount=100.00`、默认费率 2% → `refund=98.00`（不再是 97.00）；通过运行时配置接口把
  `payment.refund-fee-rate` 覆盖成 `0.05` 后再算，`refund=95.00`，不需要重启或改配置文件即生效。

---

## §B pay-ext（批次 B07）— 发票 / 结算 / 通知渠道

### PAY-B1 | InvoiceService.generateInvoice 多处缺陷：金额无视请求参数、超额校验从未生效、税额两步舍入、缺幂等键、开票成功不通知

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/InvoiceService.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/dto/InvoiceRequest.java`
  3. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/repository/InvoiceRecordRepository.java`
  4. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/entity/InvoiceRecord.java`
- **现状**（`generateInvoice()`，第 51-104 行）:
  1. （findings §6.3 #5、第二轮深审 #10）第 63 行
     `BigDecimal invoiceAmount = successfulPayment.getPaidAmount();`——完全忽略
     `request.getInvoiceAmount()`，无论请求要开多少钱，永远按订单全部实付金额开票，不支持部分开票；
     该值也从未经 `MonetaryUtil.roundToCent`。
  2. （findings §6.3 #6）第 66-74 行剩余可开票金额校验写反了：只在"已开票金额 ≥ 实付金额"（即已经
     开满）时才抛 `BusinessException("INVOICE_LIMIT_EXCEEDED", ...)`（非冻结错误码），从未校验"本次
     请求金额是否超过剩余可开票金额"——README 冻结码 `INVOICE_AMOUNT_EXCEEDED` 在全仓库从未被抛出。
  3. （第三轮深审·模块内 #10）第 76-77 行税额两步舍入：
     `invoiceAmount.multiply(taxRate).setScale(4, RoundingMode.HALF_UP)` 后再
     `MonetaryUtil.roundToCent(...)`，与本模块 `RefundCalculator` 等处统一使用的单步
     `MonetaryUtil.multiply` 不一致，边界值上两种算法可能相差 1 分钱。
  4. （findings §6.3 #11）整个方法没有幂等键，重复提交同一开票申请会产生多条发票记录（且因 2 的判断
     逻辑，还会侵蚀剩余可开票额度）。
  5. （第三轮深审·跨领域 #8）开票成功后（第 97 行 `invoiceRecordRepository.save(invoice)` 之后）没有
     任何通知逻辑。
- **期望**:
  1. design-docs/14§3："一个订单可以申请多张发票。单张发票金额不得超过订单剩余可开票金额"；09§6
     同；03§1（入库 2 位小数）。
  2. README §7 `INVOICE_AMOUNT_EXCEEDED`/400；design-docs/14§3 公式：剩余可开票金额 = 订单实付金额 −
     已开票成功金额，本次金额不得超过该剩余值。
  3. design-docs/14§4："税额 = 发票金额 × 税率...按 RoundingMode.HALF_UP 保留两位小数"，与 03§1
     舍入规则统一为单步 `MonetaryUtil.multiply`。
  4. design-docs/03§3 幂等规范：发票申请幂等键 `invoiceRequestNo`。
  5. design-docs/15§2："发票通知 → EMAIL"；03§7/15§4 通知失败不影响主业务流程（best-effort）。
- **改法**:
  1. `InvoiceRequest.java` 新增字段：
     ```java
     private String invoiceRequestNo;
     public String getInvoiceRequestNo() { return invoiceRequestNo; }
     public void setInvoiceRequestNo(String invoiceRequestNo) { this.invoiceRequestNo = invoiceRequestNo; }
     ```
  2. `InvoiceRecordRepository.java` 新增方法：
     ```java
     Optional<InvoiceRecord> findByInvoiceRequestNo(String invoiceRequestNo);
     ```
  3. `InvoiceRecord.java` 新增字段（放在 `invoiceNo` 字段之后）：
     ```java
     @Column(name = "invoice_request_no", unique = true, length = 64)
     private String invoiceRequestNo;

     public String getInvoiceRequestNo() { return invoiceRequestNo; }
     public void setInvoiceRequestNo(String invoiceRequestNo) { this.invoiceRequestNo = invoiceRequestNo; }
     ```
  4. `generateInvoice()` 方法体最前面（日志行之后）加幂等短路 + 金额非空/正数校验：
     ```java
     if (request.getInvoiceRequestNo() != null) {
         Optional<InvoiceRecord> existing = invoiceRecordRepository
                 .findByInvoiceRequestNo(request.getInvoiceRequestNo());
         if (existing.isPresent()) {
             return toInvoiceResponse(existing.get());
         }
     }
     if (request.getInvoiceAmount() == null || request.getInvoiceAmount().compareTo(BigDecimal.ZERO) <= 0) {
         throw new ValidationException("invoiceAmount", "Invoice amount must be greater than 0");
     }
     ```
     补 `import java.util.Optional;`；`ValidationException` 本文件基线已 import。新增这个非空/正数
     校验是因为金额来源即将从"内部可信值"（`successfulPayment.getPaidAmount()`）改为"客户端传参"。
  5. 第 63 行起（原变量赋值 + 剩余额度校验）改为：
     ```java
     BigDecimal invoiceAmount = MonetaryUtil.roundToCent(request.getInvoiceAmount());

     BigDecimal alreadyInvoiced = invoiceRecordRepository
             .sumInvoiceAmountByOrderIdAndStatus(request.getOrderId(), InvoiceStatus.ISSUED);
     BigDecimal remaining = MonetaryUtil.subtract(successfulPayment.getPaidAmount(), alreadyInvoiced);

     if (invoiceAmount.compareTo(remaining) > 0) {
         throw new BusinessException("INVOICE_AMOUNT_EXCEEDED",
                 "Requested invoice amount " + invoiceAmount
                         + " exceeds remaining invoiceable amount " + remaining);
     }
     ```
     即删除原来"已开满才报错"的分支，改成"本次请求超过剩余可开票额度才报错"，错误码同步改为
     `INVOICE_AMOUNT_EXCEEDED`。
  6. 第 76-77 行两步舍入改单步：
     ```java
     BigDecimal taxAmount = MonetaryUtil.multiply(invoiceAmount, taxRate);
     ```
     删除 `.setScale(4, RoundingMode.HALF_UP)` 那一步；若 `java.math.RoundingMode` import 不再被
     使用则删除。
  7. 构建 `invoice` 实体那几行补一行 `invoice.setInvoiceRequestNo(request.getInvoiceRequestNo());`。
  8. 构造函数新增 `LocalNotificationService notificationService` 依赖（**不要**加 `AuditLogService`，
     理由见「勿犯」第 1 条）：
     ```java
     private final LocalNotificationService notificationService;

     public InvoiceService(InvoiceRecordRepository invoiceRecordRepository,
                           PaymentRecordRepository paymentRecordRepository,
                           LocalNotificationService notificationService) {
         this.invoiceRecordRepository = invoiceRecordRepository;
         this.paymentRecordRepository = paymentRecordRepository;
         this.notificationService = notificationService;
     }
     ```
     `invoiceRecordRepository.save(invoice)` 那一行之后、`return toInvoiceResponse(invoice)` 之前，
     新增 best-effort 通知（失败自己 catch，不向外抛，不影响开票主流程）：
     ```java
     try {
         NotificationRequest notification = new NotificationRequest();
         notification.setBizType("INVOICE_ISSUED");
         notification.setBizId(invoice.getInvoiceNo());
         notification.setReceiver(String.valueOf(userId));
         notification.setChannel(NotificationChannel.EMAIL); // 15§2：发票通知→EMAIL
         notification.setTemplateCode("invoice_issued");
         notification.setVariables(Map.of(
                 "invoiceNo", invoice.getInvoiceNo(),
                 "orderId", String.valueOf(invoice.getOrderId()),
                 "invoiceAmount", invoice.getInvoiceAmount().toString()));
         notification.setIdempotencyKey("invoice_notify_" + invoice.getInvoiceNo());
         notificationService.send(notification);
     } catch (Exception e) {
         log.warn("Failed to send invoice notification for invoiceNo={}: {}",
                 invoice.getInvoiceNo(), e.getMessage());
     }
     ```
     补 `import com.ecommerce.common.notification.LocalNotificationService;`、`NotificationChannel`、
     `NotificationRequest`、`java.util.Map`。只能经 `LocalNotificationService.send(...)` 发送，绝不能
     直接调用 `MockMailSender`。
  9. **可选顺带清理**（零风险，不改变任何可观察行为）：`TAX_RATE` 兜底常量当前是
     `new BigDecimal("0.13")`，但 `common/test/RuntimeConfigRegistry.java` 内部 `defaults` 表已经把
     `"invoice.tax-rate"` 硬编码为 `"0.06"`（`getBigDecimal` 的 `fallback` 参数只在 registry 查不到
     该 key 时才用得到，而这个 key 恒在 `defaults` 里，`TAX_RATE` 实际从未生效过）——改成
     `new BigDecimal("0.06")` 只是消除误导性死代码，对齐 design-docs/14§4/附录B 的 6% 默认税率。
- **验收**:
  - 订单实付 800 元，先开 300 元发票，能查到该发票 `invoiceAmount=300.00`（不再是 800）；再开 600
    元 → 400 `INVOICE_AMOUNT_EXCEEDED`（剩余只有 500）；再开 500 元 → 成功。
  - 带相同 `invoiceRequestNo` 重复提交只产生一条发票记录。
  - `invoiceAmount=100.005` 提交后落库为 `100.01`（HALF_UP 两位小数）；税额用单步 `MonetaryUtil.multiply`
    计算。
  - 开票成功后 `GET /api/v1/admin/notifications` 能查到一条 `bizType=INVOICE_ISSUED, channel=EMAIL`
    的通知；对通知发送故障注入不影响 `POST /api/v1/invoices` 本身返回 201。
- **勿犯**:
  1. **本卡把 `InvoiceService` 构造函数从 2 参数改成 3 参数（新增 `notificationService`，且明确
     不加 `auditLogService`）——这会与 `S3-audit.md`（B18）的 AUD-6 卡产生参数顺序上的表述冲突，
     必须知晓：** AUD-6 卡片文本里写的"现状"是
     `new InvoiceService(invoiceRecordRepository, paymentRecordRepository)`（2 参数），并按此写了
     "追加实参变成 `new InvoiceService(invoiceRecordRepository, paymentRecordRepository,
     auditLogService)`"——这段描述没有像同一文件 AUD-7 卡那样加"若已被本卡新增过参数就加在最后"的
     防御性说明。**若本卡（B07）已先于 B18 执行，届时 `InvoiceService` 的构造函数实际已是 3 参数
     `(invoiceRecordRepository, paymentRecordRepository, notificationService)`**，执行 AUD-6 时
     应以文件当前实际内容为准，把 `auditLogService` 追加在**当前最后一个参数之后**（即变成 4 参数，
     `notificationService` 在前、`auditLogService` 在后），而不是机械地照抄 AUD-6 文本里"变成 3
     参数"的字面描述、或误判卡片已过期而跳过。`InvoiceServiceTest.java` 同理：本卡先给
     `new InvoiceService(invoiceRecordRepository, paymentRecordRepository)` 追加第三个实参
     `notificationService`（mock），AUD-6 执行时再在其后追加第四个实参 `auditLogService`（mock）。
     这一冲突已在本文件末尾「存疑点」里向流程负责人报告，若 `S3-audit.md` 后续被同步修订则以修订版
     为准。
  2. **不要把"剩余可开票额度"算错方向**——`remaining` 是"实付金额 − 已开票"，`invoiceAmount` 超过
     `remaining` 才报错，不是超过 `successfulPayment.getPaidAmount()` 整体。
  3. **不要在本卡里加 `auditLogService.record(...)`**（发票开具审计是 S3/B18 AUD-6 的职责，此时
     构造函数没有该依赖，硬加会导致编译期找不到符号）。
  4. **通知发送必须包在 try/catch 里且不重新抛出**——否则一次通知失败会让整个开票请求跟着失败，
     违反 best-effort 要求。

---

### PAY-B2 | SettlementBatchService：结算批次退款汇总永远为 0

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/SettlementBatchService.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/repository/RefundRecordRepository.java`
- **现状**（findings §6.3 #7）: `generateBatch()`（第 56 行起）构造批次实体时，第 105-106 行
  `createBatchEntity(batchDate, totalPaymentAmount, BigDecimal.ZERO, totalInvoiceAmount, orderCount)`
  ——`totalRefundAmount` 参数硬编码 `BigDecimal.ZERO`；本类从未注入 `RefundRecordRepository`，退款
  数据完全没有参与结算汇总。
- **期望**: design-docs/14§5："结算批次按自然日生成，包含支付成功且未结算的订单、退款和发票数据"——
  退款汇总应为当日真实完成的退款总额，不是恒零。
- **改法**:
  1. `RefundRecordRepository.java` 新增方法：
     ```java
     List<RefundRecord> findByStatusAndCompletedAtBetween(
             RefundStatus status, LocalDateTime start, LocalDateTime end);
     ```
     补 `import java.time.LocalDateTime;`（若未 import）。
  2. `SettlementBatchService.java` 构造函数新增 `RefundRecordRepository refundRecordRepository` 依赖
     （**不要**加 `AuditLogService`/`operatorId` 参数，理由见「勿犯」；`generateBatch(LocalDate
     batchDate)` 方法签名本身不变）：
     ```java
     private final RefundRecordRepository refundRecordRepository;

     public SettlementBatchService(SettlementBatchRepository settlementBatchRepository,
                                   SettlementOrderItemRepository settlementOrderItemRepository,
                                   PaymentRecordRepository paymentRecordRepository,
                                   InvoiceRecordRepository invoiceRecordRepository,
                                   RefundRecordRepository refundRecordRepository) {
         this.settlementBatchRepository = settlementBatchRepository;
         this.settlementOrderItemRepository = settlementOrderItemRepository;
         this.paymentRecordRepository = paymentRecordRepository;
         this.invoiceRecordRepository = invoiceRecordRepository;
         this.refundRecordRepository = refundRecordRepository;
     }
     ```
     补 `import com.ecommerce.payment.entity.RefundRecord;`、
     `import com.ecommerce.payment.entity.RefundStatus;`、
     `import com.ecommerce.payment.repository.RefundRecordRepository;`。
  3. 在计算 `totalInvoiceAmount` 之后、构造批次实体之前，插入：
     ```java
     BigDecimal totalRefundAmount = refundRecordRepository
             .findByStatusAndCompletedAtBetween(RefundStatus.COMPLETED, startOfDay, endOfDay)
             .stream()
             .map(RefundRecord::getRefundAmount)
             .filter(a -> a != null)
             .reduce(BigDecimal.ZERO, MonetaryUtil::add);
     ```
     第 105-106 行
     `createBatchEntity(batchDate, totalPaymentAmount, BigDecimal.ZERO, totalInvoiceAmount, orderCount)`
     → `createBatchEntity(batchDate, totalPaymentAmount, totalRefundAmount, totalInvoiceAmount, orderCount)`。
  4. 同步更新 `SettlementBatchServiceTest.java`：`new SettlementBatchService(...)` 的 4 参数调用改成
     5 参数（补 `refundRecordRepository` mock，加在最后一位），否则 test-compile 失败。
- **验收**: 当日有一笔已 `COMPLETED` 的退款（金额 50.00）与若干笔支付，
  `POST /api/v1/admin/settlements/batches?batchDate=当日` 返回的 `totalRefundAmount=50.00`，不再
  恒为 `0`（或 `0.00`）。
- **勿犯**:
  1. 构造函数新增的 `refundRecordRepository` 是**第 5 个**参数，加在 `invoiceRecordRepository` 之后
     ——`S3-audit.md`（B18）的 AUD-7 卡明确写了"如果此刻已经因为另一张卡多了 `refundRecordRepository`
     参数，就加在那之后，总之加在参数列表最后一位"，即 AUD-7 已针对本卡做了防御性处理，本卡不需要
     额外协调，但**参数一定要加在最后**，不要插到中间，否则会打乱 AUD-7 对"最后一位"的假设。
  2. 空批次分支（`payments.isEmpty()` 时）不受本卡影响，继续用 `BigDecimal.ZERO` 走
     `createBatchEntity(...)`（本卡改动只发生在有支付记录的正常分支）。

---

### PAY-B3 | 申请发票对抬头长度零校验，附录B `invoice.max-title-length: 100` 形同虚设（第四轮设计-实现对比 #2）

- 风险: low · 置信度: likely（设计依据是附录B §1/§2 的 `invoice.max-title-length: 100`——配置
  声明了上限即要求实现生效；14 文档与附录A 未另行规定超限行为，错误语义按工程通用参数校验惯例取）
- **文件**: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/InvoiceService.java`
- **现状**: 申请发票入口（`generateInvoice`，PAY-B1 同批已先行改造）对 `request.getTitle()`
  没有任何长度校验——传 300 字符的抬头照样开票入库。附录B 声明的
  `invoice.max-title-length`（默认 100）在全工程零读取。
- **期望**: 抬头长度超过运行期配置 `invoice.max-title-length`（默认 100）时拒绝开票，抛
  `ValidationException` → HTTP 400（`GlobalExceptionHandler` 已有该异常的 400 映射）；
  100 字符以内正常开票；通过 `PUT /api/v1/admin/system/configs/invoice.max-title-length`
  覆盖后新上限即时生效。
- **改法**: 在 `generateInvoice` 现有参数校验区（title/金额空值校验旁）追加：
  ```java
  int maxTitleLength = RuntimeConfigRegistry.getInt("invoice.max-title-length", 100);
  if (request.getTitle() != null && request.getTitle().length() > maxTitleLength) {
      throw new ValidationException("title",
              "Invoice title length " + request.getTitle().length()
                      + " exceeds the limit of " + maxTitleLength);
  }
  ```
  `ValidationException` 用本工程已有的 `(String field, String reason)` 双参构造（第一参是字段名，
  这是全工程惯例，如 `new ValidationException("amount", ...)`）；`RuntimeConfigRegistry` 与
  `ValidationException` 的 import 若因 PAY-B1 已存在则不重复添加，缺哪个补哪个。
- **验收**: 101 字符抬头 `POST /api/v1/invoices` → HTTP 400；100 字符 → 正常开票；
  管理接口把 `invoice.max-title-length` 覆盖为 10 后，11 字符抬头 → 400（运行期可配生效）。
- **勿犯**:
  1. 校验加在**实际开票之前**、且不影响幂等命中分支——同一 `invoiceRequestNo` 重放返回已开
     发票的路径不要经过新校验（幂等语义优先，不因新校验改变）。
  2. 只校验 title 长度——不要顺手校验 taxNo/其他字段，文档只声明了 title 上限。
  3. 不要用 `IllegalArgumentException` 或 `BusinessException` 替代 `ValidationException`。

---

## 跳过条目说明

- **findings §6.3 #9**（`PaymentSucceededEvent` 缺 `paidAt`、多了个恒 `null` 的 `userId`）：本条目
  的修复本质上是"把事件类的字段迁移正确"，而事件类本身（`PaymentSucceededEvent`）的权威定义迁移到
  `ecommerce-common` 是 `S2-events.md` §A（B13）的职责——迁移到新包时，编译期就强制要求所有发布方
  按新的字段签名（`paymentNo/orderId/paidAmount/paidAt/aggregateId/traceId`，无 `userId`）重新构造
  该事件，这是类型迁移的必然副产品，不可能脱离 B13 单独完成。本文件所有涉及 `PaymentSucceededEvent`
  构造调用的地方（PAY-A2）都明确交代"不改动该行"。跳过，未生成独立卡片。
- **findings §6.3 #14**（`RefundStatus`/`InvoiceStatus` 命名与附录C 出入较大，6 vs 5 个值，
  `CANCELLED` vs `VOIDED`）：`suspicious` 置信度；核对参考实现的改动清单发现
  `RefundStatus.java`/`InvoiceStatus.java` 均未被改动（参考实现只收录"最终确实被改过"的
  文件），说明参照解在权衡"附录C 只是文字表格、无黑盒断言依赖具体字符串"之后判定不改，风险高于收益
  （六个枚举值被引用于全模块状态机分支，贸然对齐会牵扯大量分支重写且无可验证收益）。跳过，未生成
  独立卡片，与参照解保持一致。

---

## 存疑点（供流程负责人裁决）

1. **PAY-B1 与 `S3-audit.md` AUD-6 卡的构造函数参数顺序冲突**（已在 PAY-B1「勿犯」第 1 条详细说明）：
   AUD-6 假设执行时 `InvoiceService` 构造函数仍是基线的 2 参数，直接"追加"`auditLogService`成为第 3
   参数；但按批次表执行顺序，本文件 PAY-B1（B07）先于 AUD-6 所在的 `S3-audit.md`（B18）执行，会先把
   它改成 3 参数 `(..., notificationService)`。参考实现里的最终真值是 4 参数且顺序为
   `(invoiceRecordRepository, paymentRecordRepository, auditLogService, notificationService)`——
   `auditLogService` 在前、`notificationService` 在后，与"先执行 B07 再执行 B18 各自追加"会得到的
   `(..., notificationService, auditLogService)`顺序不同。**这只影响构造函数形参声明顺序和调用点
   实参顺序，Spring 按类型注入不受影响，`InvoiceServiceTest` 的显式 `new InvoiceService(...)` 调用
   只要参数类型和个数对得上、`@Mock` 字段类型正确，参数写在第 3 位还是第 4 位在功能上等价**——真正
   的风险点在于 AUD-6 卡片文本本身没有像同文件 AUD-7 那样写"若已被其他卡改过就追加在最后"的防御性
   措辞，执行 AUD-6 的 agent 如果机械比对文本里的"现状"（2 参数）和实际文件（3 参数）不一致，可能
   误判卡片过期而跳过、或者改错位置。建议：要么由流程负责人同步给 `S3-audit.md` AUD-6 补一句与
   AUD-7 一致的防御性说明，要么在 B18 执行前人工确认。**（已处理：AUD-6 现已补上"追加到你打开
   文件时看到的当前参数列表最后一位"的防御性措辞，此存疑点已消除，无需人工干预。）**PAY-A5/PAY-B2 与 AUD-5/AUD-7 之间**没有**
   这个问题（AUD-5 假设的 5 参数 `RefundService` 构造函数与本文件 PAY-A5 的改动一致；AUD-7 已自带
   防御性说明，兼容本文件 PAY-B2 新增的第 5 个参数）。
2. **`InvoiceService.TAX_RATE` 兜底常量 0.13→0.06**（PAY-B1 改法第 9 条）：这不是 14 项/深审列表里
   明确列出的条目，是核对参考实现时顺带发现的死代码级不一致（已用 `RuntimeConfigRegistry`
   源码验证该常量在当前实现下从未真正生效，改与不改都不影响任何可观察行为）。已在卡片里标注"可选"，
   按参考实现真值写出，供裁决是否保留。
3. **`RefundService.reviewRefund` 里 `REFUND_STATUS_INVALID` 从 `BusinessException`/400 改
   `ConflictException`/409**（PAY-A5 改法第 5 条）：这一具体子项没有在 findings.md 任何一处被单独
   列为条目，是修复"跳过仓库验收"（§6.3 #3 / 第二轮深审 #7）时，为保持同一 `if/else` 链里两个相邻
   状态冲突分支语义一致而顺带对齐的（`REFUND_WAITING_WAREHOUSE_ACCEPT` 与
   `REFUND_STATUS_INVALID` 是同一段状态校验里紧邻的两个分支）。参考实现真值确认两者都是
   `ConflictException`。风险评估为低（`REFUND_STATUS_INVALID` 不是 README 冻结错误码，只是 HTTP
   状态码从 400 变 409，属于典型的"状态冲突=409"归类修正）。
