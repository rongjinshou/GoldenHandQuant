# B03+B04 · order — 订单核心与计价

本文件覆盖 findings.md order 模块（§6.2）12 项里的 11 项（#12「舍入模式 HALF_DOWN」根因在
`ecommerce-common/MonetaryUtil.roundToCent`，与 common 批次 `S1-quick-wins.md` 的 S1-1 卡片完全
同源同修，order 侧无任何代码要改，不出卡）、跨模块集成缺陷 BUG-INT-7、加固项「orderNo 同毫秒碰撞」、
第二轮深审 7 项（#4/#14/#15/#16/#17/#19/#27）、第三轮深审·模块内 中的 4 项（#3/#4/#5/#6）、
第四轮契约复核（wave-1B）3 张（ORD-A18/A19/A20，覆盖 5 处独立修复，全部已通过公开 24 例逐项门禁），
再加 round-15 的 ORD-A23（时钟成套 + orderNo 日期段 + 兑换率接配置 + ORDER_CREATED receiver，
附 payable 钳位决策留档，已实施并逐项门禁 24/0/0），
合计 **31 张卡片**（含后补的取消释放接线卡 ORD-A17/ORD-A21——两张的「执行时机」都随 B05 落地、
经 promotion.md PROMO-16 指针触达——和指向 loyalty.md LOY-12 的积分退还指针卡 ORD-A22，其实体
随 B15 落地），分两个执行批次：

- **§A order-core（批次 B03）**：状态机、错误码、下单前置校验、幂等、请求/响应契约形态对齐
  （ORD-A18~A20）——先做，因为 §B 的积分抵扣（ORD-B8）在订单持久化之后追加逻辑，依赖 §A 里创建
  订单的整体流程已经是对的。
- **§B order-pricing（批次 B04）**：金额公式、运行时配置接入、积分抵扣落地、批量下单——建议排在
  §A 之后。

**全批红线（B03/B04 通用勿犯）**：`ecommerce-order` 下存在一批**零注入零调用的死服务 bean**
（`OrderLifecycleService`、`OrderPaymentEventHandler`、`AdminOrderService`、`CustomerOrderService`、
`OrderSearchService`、`OrderMetricsService`、`OrderExportService`、`OrderReconciliationService`、
`OrderWebhookService`、`OrderAuditService`、`OrderSnapshotService`、`OrderPricingService` 等）。任何卡
都**不得**给它们接线（注入/调用/注册监听）：其中 `OrderLifecycleService` 与
`OrderPaymentEventHandler.handlePaymentSuccess` 各持一套"第二发布点"逻辑，接线会造成 `OrderPaidEvent`
双发（积分双发/物流双建单），直接破坏支付后置链。它们编译期为适配公共事件签名可能被动改动（合法），
但运行期必须保持不可达。

**前置依赖（已由更早批次满足，无需在本文件内处理）**：ORD-A7、ORD-A8 用到
`ConflictException(String code, String message)` 两参构造函数；基线代码里 `ConflictException`
只有单参构造函数，两参构造函数是 `S1-quick-wins.md`（批次 B01，卡片 S1-2）新增的。按
`work/bugs/README.md` 里 B01 在 B03/B04 之前执行的顺序，本文件落地时该构造函数应已存在；如果
执行环境不遵循这个顺序、S1-2 尚未应用，ORD-A7/ORD-A8 会编译失败，需要先补上那个两参构造函数。

**共享文件提醒**（本文件之外的其它批次也会改到下面这些文件，互不冲突但注意别越界）：

- `OrderService.java`：秒杀接入下单流程（`seckillService`/`promotionEligibleItems`/
  `SeckillPurchase`）、优惠券核销 `couponService.markUsed(...)` 调用点属于 `promotion.md`
  （批次 B05）的范围。本文件卡片改到这个文件时，如果看到这些秒杀/优惠券相关代码已经存在，不要因为
  卡片里没提到就删除或改动；如果还不存在也不用等，本文件卡片的插入点都是按注释锚点/方法边界描述的，
  和这些代码不会插在同一行。
- `OrderService.java` / `OrderCancelService.java` / `OrderTimeoutService.java`：订单取消（含超时）
  后的**积分退还**接线、以及 `redeemPoints(...)` 调用追加第 4 个实参 `orderId`，属于 `loyalty.md`
  LOY-12（批次 B15，经本文件 ORD-A22 指针防漏）的范围。B03/B04/B05 改到这三个文件时若看到
  `loyaltyCommandService.refundPointsForOrder(...)` / `refundLoyaltyPoints(...)` 相关代码已存在，
  不要因为卡片里没提到就删除；不存在也不用补——那是 B15 的事。
- `OrderQueryServiceImpl.java`：真正往 logistics/loyalty 广播"订单已支付"这件事，需要在 `markAsPaid`
  里发布迁移到 `ecommerce-common` 后的 `OrderPaidEvent`——这是事件权威定义迁移专项（`S2-events.md`
  §A，批次 B13）的范围，不在本文件内处理（ORD-A11 只管状态机校验部分，见该卡片说明）。
- `PaymentValidator.java`（`ecommerce-payment` 模块）：本文件的 ORD-A8 只改"订单状态不可支付"这一处
  校验块；同一方法里"支付金额是否等于应付金额"的校验（`PAYMENT_AMOUNT_MISMATCH`）属于 `payment.md`
  （批次 B06，尚未生成）的范围，两处代码不重叠。

---

## §A order-core（批次 B03）— 状态机 / 错误码 / 校验 / 幂等

### ORD-A1 | 创建订单成功返回 200，应为 201

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/controller/OrderController.java`
- **现状**: `createOrder(...)`（约第57-63行）调用 `orderService.createOrder(...)` 后用
  `return ResponseEntity.ok(response);`（HTTP 200）返回。
- **期望**: 创建订单成功必须返回 **201 Created**。依据: README.md §6（`POST /api/v1/orders/create |
  USER | 201`）、design-docs/附录A §6、design-docs/08 §9、README.md §8 PUB-102。
- **改法**: 
  1. 加 import：`org.springframework.http.HttpStatus`。
  2. 把 `createOrder(...)` 方法末尾的 `return ResponseEntity.ok(response);` 改成
     `return ResponseEntity.status(HttpStatus.CREATED).body(response);`。
  3. 只改这一个方法的 return 语句；本文件里 `getOrderDetail`/`listOrders`/`cancelOrder`/
     `createBatch`/`verifyPurchase` 其余 5 处 `ResponseEntity.ok(response)` **不要动**（都应保持
     200）。
- **验收**: `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub102_createOrderShouldReturn201 test`
  → 绿（HTTP 201）。

---

### ORD-A2 | 下单前从不校验用户是否被冻结

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPreconditionChecker.java`
- **现状**: `check(Long userId, int itemCount)`（约第31-40行）只调用
  `userQueryService.getUserById(userId)` 判断用户是否存在，随后直接判 `itemCount <= 0`；全程未调用
  `userQueryService.isFrozen(userId)`。被冻结的用户可以正常下单。
- **期望**: 用户被冻结时下单必须被拒绝，返回 403、`code=USER_FROZEN`。依据: design-docs/04 §2
  （FROZEN 用户"不可登录、不可下单"）、README.md §7.2（`USER_FROZEN`/403）、README.md §8
  PUB-103。
- **改法**: 在 `getUserById` 结果判空的 `if (user == null) { ... }` 块**之后**、
  `if (itemCount <= 0) { ... }` 块**之前**插入：
  ```java
  if (userQueryService.isFrozen(userId)) {
      throw new AuthorizationException("USER_FROZEN", "User is frozen: " + userId);
  }
  ```
  加 import `com.ecommerce.common.exception.AuthorizationException`（其两参构造函数
  `AuthorizationException(String code, String message)` 已存在于基线 common 模块，不用改）。
  `UserQueryService.isFrozen(Long)` 接口方法已存在，不需要新增任何跨模块方法。
- **验收**: `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub103_frozenUserCannotCreateOrder test`
  → 绿（HTTP 403，`code=USER_FROZEN`）。

---

### ORD-A3 | 风控检查从未被调用，ORDER_RISK_REJECTED 是死代码

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: 构造函数已注入 `OrderRiskChecker riskChecker`（字段约第89行），但 `createOrder(...)`
  方法体内 `// ===== Step 4: Risk check =====` 注释（约第167行）下面**是空的**——没有任何调用
  `riskChecker.check(...)` 的代码，直接跳到 Step 5 计算运费。`riskChecker` 字段在整个类里零使用。
- **期望**: 每次创建订单都必须实际执行风控检查，未通过时以冻结错误码 `ORDER_RISK_REJECTED`（400）
  拒绝。依据: design-docs/08 §3（"执行风控校验，高风险订单拒绝"）、README.md §7.2
  （`ORDER_RISK_REJECTED`/400）、README.md §8 PUB-106。
- **改法**: 在 `// ===== Step 4: Risk check =====` 注释下方（Step 3 的
  `orderValidator.validateAmount(itemTotal);` 之后、Step 5 计算运费之前）插入：
  ```java
  List<Long> skuIds = orderItems.stream()
          .map(OrderItem::getSkuId).collect(Collectors.toList());
  RiskCheckResult riskResult = riskChecker.check(userId, itemTotal, skuIds);
  if (!riskResult.isPassed()) {
      throw new BusinessException("ORDER_RISK_REJECTED",
              "Order rejected by risk check: " + riskResult.getReason());
  }
  ```
  `RiskCheckResult`、`BusinessException`、`Collectors`、`OrderItem` 均已在文件顶部 import 过，
  `orderItems` 变量在 Step 2 的循环里已经收集好，直接引用即可。**不要**修改
  `OrderRiskChecker.java`（其 `check()` 逻辑本身正确，只是没被调用）。
- **验收**: `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub106_highRiskOrderShouldBeRejected test`
  → 绿（HTTP 400，`code=ORDER_RISK_REJECTED`）；被拒订单不应落库（`orderRepository.save` 不被调用）。

---

### ORD-A4 | 订单金额校验抛 IllegalArgumentException，应抛 OrderValidationException

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderValidator.java`
- **现状**: `validateAmount(BigDecimal amount)`（约第18-23行）金额非法时
  `throw new IllegalArgumentException("Order amount must be positive, got: " + amount);`——这是
  Java 标准异常，不会被 `GlobalExceptionHandler` 按业务异常格式化输出 `{code,message,traceId,
  details}`，会变成未处理异常、500。
- **期望**: 必须抛 `OrderValidationException`（400，冻结错误码 `ORDER_INVALID_AMOUNT`）。依据:
  design-docs/03 §2（"订单金额校验失败必须抛出 OrderValidationException，不得抛出 Java 标准
  IllegalArgumentException"）、README.md §7.2。
- **改法**: 加 import `com.ecommerce.common.exception.OrderValidationException`；把
  `throw new IllegalArgumentException("Order amount must be positive, got: " + amount);`
  改成
  `throw new OrderValidationException("Order amount must be positive, got: " + amount);`
  `OrderValidationException(String message)` 单参构造函数（`CODE="ORDER_INVALID_AMOUNT"`）已存在于
  基线 `ecommerce-common`，不需要改 common 模块。本文件另外两个方法 `validateQuantity`/
  `validateItemsCount` 抛的是 `BusinessException`，与本条无关，不要动。
- **验收**: 商品总额或最终应付金额非正数时，`POST /api/v1/orders/create` 返回 400、
  `code=ORDER_INVALID_AMOUNT`（不是 500）。

---

### ORD-A5 | 已支付订单取消直接跳 CANCELLED，跳过商家审核

- 风险: high · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
- **现状**: `cancel(...)` 方法的 switch 语句里 `case PAID:`（约第83-84行）直接
  `return cancelPaidOrderDirectly(order, reason);`；私有方法 `cancelPaidOrderDirectly`（约第
  166-194行）把订单直接置为 `CANCELLED`（`order.setStatus(OrderStatus.CANCELLED)`）、`paidAmount`
  清零，跳过了商家审核环节。
- **期望**: 已支付（PAID）订单发起取消，必须先进入 `CANCEL_REVIEWING`（取消审核中）状态，等商家审核
  通过（走 `reviewCancel(orderId, true, ...)`）才真正变为 `CANCELLED` 并进入退款流程；订单模块本身
  不计算、不触碰任何退款金额字段（退款金额由 payment 模块的退款流程负责）。依据: design-docs/08 §6
  （"已支付订单不得直接跳转到 CANCELLED，必须先进入 CANCEL_REVIEWING"）。
- **改法**: 
  1. 把 `case PAID:` 分支改成调用一个新方法（下称 `requestPaidOrderCancelReview`）：
     ```java
     case PAID:
         return requestPaidOrderCancelReview(order, reason);
     ```
  2. 把私有方法 `cancelPaidOrderDirectly(Order order, String reason)` 整体替换成：
     ```java
     private CancelOrderResponse requestPaidOrderCancelReview(Order order, String reason) {
         OrderStatus fromStatus = order.getStatus();

         stateMachine.validateTransition(fromStatus, OrderStatus.CANCEL_REVIEWING);

         order.setStatus(OrderStatus.CANCEL_REVIEWING);
         order.setCancelReason(reason);
         orderRepository.save(order);

         orderService.recordEvent(order.getId(), fromStatus, OrderStatus.CANCEL_REVIEWING,
                 "CANCEL_REQUESTED", order.getUserId().toString(),
                 "User requested cancellation of paid order, pending merchant review: " + reason);

         return new CancelOrderResponse(order.getId(), OrderStatus.CANCEL_REVIEWING.name(),
                 "Cancellation request submitted for merchant review");
     }
     ```
     即：不再计算 `refundAmount`、不再清零 `paidAmount`、不再释放库存（库存留到 `reviewCancel`
     审核通过时再释放，那部分代码已经存在、不用动）、不再发布 `OrderCancelledEvent`（订单还没真正
     取消，只是进入审核）。
  3. 方法体不再使用 `BigDecimal`；若本文件没有其它地方用到它，可顺手删掉现在已不需要的
     `import java.math.BigDecimal;`（不删也不影响编译，只是多一个未用 import）。
  4. `reviewCancel(...)` 方法本身**不用改**（它已经正确处理 `CANCEL_REVIEWING → CANCELLED`
     审核通过、`CANCEL_REVIEWING → PAID` 审核驳回两条路径，且已在审核通过分支调用
     `inventoryReservationService.release(orderId)`）。
- **验收**: 对 PAID 订单调用 `POST /api/v1/orders/{orderId}/cancel`，响应 `status=CANCEL_REVIEWING`
  （不是 `CANCELLED`），订单在数据库里的状态是 `CANCEL_REVIEWING`；随后管理员走
  `POST /api/v1/admin/orders/{orderId}/cancel-review` 批准后才变为 `CANCELLED`。
- **勿犯**: 不要在这一步计算或触碰任何退款金额字段（`paidAmount` 等）——退款是 payment 模块拿到
  审核通过信号后才做的事，订单模块这里只负责状态流转；也不要把库存释放逻辑从 `reviewCancel` 挪到
  这里（`CANCEL_REVIEWING` 阶段库存仍应保持预占/已扣减状态，只有审核通过才释放）。

---

### ORD-A6 | 状态机把 PAID→CANCELLED 列为合法迁移

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderStateMachine.java`
- **现状**: `initTransitions()` 里（约第36-37行）：
  ```java
  allowedTransitions.put(OrderStatus.PAID,
          EnumSet.of(OrderStatus.PICKING, OrderStatus.CANCEL_REVIEWING,
                  OrderStatus.CANCELLED));
  ```
  `CANCELLED` 被列为 PAID 状态的合法直接迁移目标，是 ORD-A5 那个 bug 的根因之一——即便 ORD-A5
  已经不再调用它，只要这个集合里还留着 `CANCELLED`，状态机本身对"PAID 能否直接到 CANCELLED"这一
  问题的回答依然是错的。
- **期望**: PAID 只能迁移到 `PICKING` 或 `CANCEL_REVIEWING`，不能直接到 `CANCELLED`。依据:
  design-docs/08 §6。
- **改法**: 把
  ```java
  allowedTransitions.put(OrderStatus.PAID,
          EnumSet.of(OrderStatus.PICKING, OrderStatus.CANCEL_REVIEWING,
                  OrderStatus.CANCELLED));
  ```
  改成
  ```java
  allowedTransitions.put(OrderStatus.PAID,
          EnumSet.of(OrderStatus.PICKING, OrderStatus.CANCEL_REVIEWING));
  ```
  只改 PAID 那一处，其余状态（CREATED/PAYING/PICKING/…）的迁移集合不要动。
- **验收**: `stateMachine.canTransition(OrderStatus.PAID, OrderStatus.CANCELLED)` 返回 `false`；
  `canTransition(OrderStatus.PAID, OrderStatus.PICKING)` 和
  `canTransition(OrderStatus.PAID, OrderStatus.CANCEL_REVIEWING)` 仍返回 `true`。

---

### ORD-A7 | 订单取消 5 处状态冲突抛 400，应 409 ConflictException

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
- **现状**: `cancel(...)` 方法 switch 语句里有 4 处、`reviewCancel(...)` 方法里有 1 处，共 5 处把
  "订单当前状态不允许该操作"当成普通 `BusinessException`（400）抛出：
  1. 约第86-90行，`case SHIPPED: case DELIVERED:` →
     `throw new BusinessException("ORDER_CANNOT_CANCEL", "Order in status " + currentStatus +
     " cannot be cancelled. Please use the after-sale/return process.");`
  2. 约第92-95行，`case CANCELLED: case CLOSED:` →
     `throw new BusinessException("ORDER_ALREADY_CANCELLED", "Order is already in status " +
     currentStatus);`
  3. 约第97-99行，`case CANCEL_REVIEWING:` →
     `throw new BusinessException("ORDER_CANCEL_REVIEWING", "Order cancellation is already under
     review");`
  4. 约第101-103行，`default:` →
     `throw new BusinessException("ORDER_CANNOT_CANCEL", "Order in status " + currentStatus +
     " cannot be cancelled");`
  5. 约第206-208行，`reviewCancel(...)` 方法开头
     `if (order.getStatus() != OrderStatus.CANCEL_REVIEWING)` →
     `throw new BusinessException("ORDER_NOT_IN_REVIEW", "Order " + orderId + " is not in
     CANCEL_REVIEWING status");`
- **期望**: 这 5 处都是"订单状态不允许当前操作"的状态冲突场景，必须是 409、冻结错误码
  `ORDER_STATUS_CONFLICT`。依据: README.md §7.2（`ORDER_STATUS_CONFLICT`/409）、design-docs/03 §2
  （`ConflictException`=409 用于"状态冲突、重复提交"）。
- **改法**: 加 import `com.ecommerce.common.exception.ConflictException`；把上述 5 处的
  `new BusinessException("<原 code>", "<原 message>")` 原样替换成
  `new ConflictException("ORDER_STATUS_CONFLICT", "<原 message，文案不变>")`——只换异常类型和错误码。
  例如第 1 处变成：
  ```java
  throw new ConflictException("ORDER_STATUS_CONFLICT",
          "Order in status " + currentStatus + " cannot be cancelled. "
                  + "Please use the after-sale/return process.");
  ```
  其余 4 处同理替换。**注意**：`cancel(...)` 方法里"非本人订单"那处
  `throw new BusinessException("ORDER_NOT_OWNED", ...)`（约第70行）**不属于**这 5 处，那是权限
  问题不是状态冲突，保持 `BusinessException` 不变。`case PAID:` 分支属于 ORD-A5 的范围（改成走
  审核流程），本卡不改 PAID 分支，两卡在这个文件里改动的代码位置不重叠。
- **验收**: 对 SHIPPED/DELIVERED/CANCELLED/CLOSED/CANCEL_REVIEWING 状态的订单调用取消接口，返回
  409、`code=ORDER_STATUS_CONFLICT`；对非 `CANCEL_REVIEWING` 状态订单调用 `cancel-review` 审核接口
  同样返回 409。`ConflictException extends BusinessException`，已有单测里
  `isInstanceOf(BusinessException.class)` 的断言不受影响。

---

### ORD-A8 | 订单不可支付状态冲突用 400+非冻结码，应 409+ORDER_STATUS_CONFLICT（order + payment 两处）

- 风险: low · 置信度: definite
- **文件**: 
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentValidator.java`
- **现状**: 
  1. `OrderQueryServiceImpl.getPayableOrder(Long orderId)`（约第62-70行）对非 CREATED/PAYING 状态
     的订单：
     ```java
     throw new BusinessException("ORDER_NOT_PAYABLE",
             "Order " + orderId + " is in status " + order.getStatus()
                     + " and cannot be paid");
     ```
     ——400，且 `ORDER_NOT_PAYABLE` 不是冻结错误码。
  2. `PaymentValidator.validate(PayRequest request, OrderDto order)`（约第44-46行）对同样场景：
     ```java
     throw new BusinessException("ORDER_STATUS_INVALID",
             "Order " + request.getOrderId() + " is not in a payable status: " + status);
     ```
     ——同样 400，`ORDER_STATUS_INVALID` 也不是冻结码。这两处是"订单状态不可支付"在两个模块里各自
     独立的校验点（`getPayableOrder` 在发起支付前先查一次；`PaymentValidator` 在真正扣款前再查
     一次），必须一起改，否则黑盒测试从任一入口触发可能得到不一致的错误码。
- **期望**: 两处都必须是 409、冻结错误码 `ORDER_STATUS_CONFLICT`。依据: README.md §7.2
  （`ORDER_STATUS_CONFLICT`/409）、design-docs/03 §2。
- **改法**: 
  1. `OrderQueryServiceImpl.java`：加 import `com.ecommerce.common.exception.ConflictException`；把
     ```java
     throw new BusinessException("ORDER_NOT_PAYABLE",
             "Order " + orderId + " is in status " + order.getStatus()
                     + " and cannot be paid");
     ```
     改成
     ```java
     throw new ConflictException("ORDER_STATUS_CONFLICT",
             "Order " + orderId + " is in status " + order.getStatus()
                     + " and cannot be paid");
     ```
  2. `PaymentValidator.java`：加 import `com.ecommerce.common.exception.ConflictException`；把
     ```java
     throw new BusinessException("ORDER_STATUS_INVALID",
             "Order " + request.getOrderId() + " is not in a payable status: " + status);
     ```
     改成
     ```java
     throw new ConflictException("ORDER_STATUS_CONFLICT",
             "Order " + request.getOrderId() + " is not in a payable status: " + status);
     ```
     `PaymentValidator.java` 里其余校验（金额是否为正、支付方式是否合法、是否重复成功支付
     `PAYMENT_DUPLICATE`）**不属于**本条，不要动——尤其不要顺手加"支付金额是否等于应付金额"的
     校验，那是 `payment.md` 的范围。
- **验收**: 对已是 PAID/CANCELLED 等非可支付状态的订单调用 `POST /api/v1/payment/pay`，返回 409、
  `code=ORDER_STATUS_CONFLICT`（不是 400）。

---

### ORD-A9 | 创建订单无 externalOrderNo 幂等去重

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: `createOrder(Long userId, CreateOrderRequest request)` 方法从头到尾没有查过
  `externalOrderNo` 是否已经用过——同一个 `externalOrderNo` 重复提交会创建两条订单。
  `OrderRepository` 里已经有一个现成但从未被调用的方法
  `findByExternalOrderNoAndUserId(String externalOrderNo, Long userId)`（`OrderRepository.java`
  约第39行）。
- **期望**: 同一用户用同一个 `externalOrderNo` 重复创建订单，必须返回第一次创建的那个订单，不得
  重复创建、不得重复扣库存。依据: design-docs/03 §3（幂等规范表："创建订单 | externalOrderNo"）。
- **改法**: 在 `createOrder(...)` 方法体最开头（比 `preconditionChecker.check(userId,
  request.getItems().size());` 还早，即整个方法的第一段逻辑）插入：
  ```java
  if (request.getExternalOrderNo() != null && !request.getExternalOrderNo().isBlank()) {
      Optional<Order> existingOrder = orderRepository.findByExternalOrderNoAndUserId(
              request.getExternalOrderNo(), userId);
      if (existingOrder.isPresent()) {
          log.info("Duplicate externalOrderNo={} for userId={} — returning existing order {}",
                  request.getExternalOrderNo(), userId, existingOrder.get().getId());
          return buildCreateResponse(existingOrder.get());
      }
  }
  ```
  `java.util.Optional` 已在文件顶部 import 过；私有方法 `buildCreateResponse(Order)` 已存在（文件
  末尾），直接复用即可。不需要改 `OrderRepository.java`（方法已存在），也不需要改 common 模块。
- **验收**: 用相同 `externalOrderNo` 连续两次调用 `POST /api/v1/orders/create`（同一用户），第二次
  返回和第一次相同的 `orderId`/`orderNo`，数据库里只有一条订单记录、库存只被预占一次；
  `externalOrderNo` 为空/未传时行为不变。

---

### ORD-A10 | 超时取消订单不释放预占库存

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTimeoutService.java`
- **现状**: `cancelExpiredOrder(Order order)`（约第69行开始）把订单状态置为 `CANCELLED`、保存、记录
  事件、发布 `OrderCancelledEvent`，但从头到尾没有调用任何库存释放接口——超时未支付订单永久占着
  预占库存。
- **期望**: 订单超时自动取消时必须释放预占库存，效果应和用户主动取消 CREATED 订单
  （`OrderCancelService.cancelCreatedOrder` 已经在调用 `inventoryReservationService.release
  (orderId)`）一致。依据: design-docs/08 §5（"系统自动取消订单并释放预占库存"）。
- **改法**: 
  1. 构造函数加一个参数并保存成字段（`OrderTimeoutServiceTest.java` 用的是 `@InjectMocks`，不是
     显式 `new OrderTimeoutService(...)`，加参数不影响该测试文件编译）：
     ```java
     private final InventoryReservationService inventoryReservationService;

     public OrderTimeoutService(OrderRepository orderRepository,
                                 DomainEventPublisher eventPublisher,
                                 OrderService orderService,
                                 InventoryReservationService inventoryReservationService) {
         this.orderRepository = orderRepository;
         this.eventPublisher = eventPublisher;
         this.orderService = orderService;
         this.inventoryReservationService = inventoryReservationService;
     }
     ```
     加 import `com.ecommerce.inventory.query.InventoryReservationService`（`ecommerce-order` 的
     pom 已依赖 `ecommerce-inventory`，`OrderCancelService`/`OrderService` 都已在用这个接口，不需要
     加模块依赖）。
  2. 在 `cancelExpiredOrder(Order order)` 方法里，`orderRepository.save(order);` 之后、
     `orderService.recordEvent(...)` 之前，加一行：
     ```java
     inventoryReservationService.release(order.getId());
     ```
  （知识库版本顺手把 `cancelExpiredOrder` 的可见性从 `private` 改成包内可见，方便单测直接调用——
  这不是本条修复必须的，纯粹方便测试，做不做都行。）
- **验收**: 触发超时扫描后（可用 `POST /api/v1/admin/orders/timeout-cancel`，见 README.md §6 管理
  支撑接口），被取消订单占用的预占库存应被释放，和用户主动取消 CREATED 订单效果一致。

---

### ORD-A11 | markAsPaid 绕过状态机，允许 CREATED 直接标记为 PAID

- 风险: high · 置信度: suspicious
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`
- **现状**: `markAsPaid(Long orderId, String paymentNo)`（约第113-135行，`OrderPaymentStatusUpdater`
  接口实现，payment 模块通过这个跨模块接口把订单标记为已支付）用的是手写 if：
  ```java
  if (order.getStatus() != OrderStatus.PAYING && order.getStatus() != OrderStatus.CREATED) {
      throw new BusinessException("ORDER_INVALID_STATUS",
              "Cannot mark order " + orderId + " as paid when status is "
                      + order.getStatus());
  }
  ```
  这段判断完全绕开了 `OrderStateMachine`，是和 `OrderStateMachine` 定义的迁移规则并存的第二套独立
  判断逻辑——`OrderStateMachine` 里 CREATED 并不能一步到 PAID（只能 CREATED→PAYING→PAID 两跳），
  这里的手写 if 却允许 CREATED 直接被标记为 PAID。
- **期望**: 所有订单状态迁移都应该经过唯一权威的 `OrderStateMachine` 校验，不能有第二套判断逻辑。
  目前系统里没有任何代码会先把订单从 CREATED 推进到 PAYING 再调 `markAsPaid`（支付网关是同步
  mock），所以 CREATED 的情况要按"链式"经过 CREATED→PAYING、PAYING→PAID 两次校验（而不是绕开
  状态机直接放行）。依据: design-docs/08 §2（订单状态表）。
- **改法**: 
  1. 构造函数加一个参数并保存成字段（`OrderQueryServiceImplTest.java` 基线用的是 `@InjectMocks`，
     不是显式 `new OrderQueryServiceImpl(...)`，加参数不影响该测试文件编译）：
     ```java
     private final OrderStateMachine stateMachine;

     public OrderQueryServiceImpl(OrderRepository orderRepository,
                                   OrderItemRepository orderItemRepository,
                                   ProductQueryService productQueryService,
                                   OrderStateMachine stateMachine) {
         this.orderRepository = orderRepository;
         this.orderItemRepository = orderItemRepository;
         this.productQueryService = productQueryService;
         this.stateMachine = stateMachine;
     }
     ```
     `OrderStateMachine` 和 `OrderQueryServiceImpl` 在同一个包
     （`com.ecommerce.order.service`），不需要加 import。
  2. 把 `markAsPaid` 方法体里的手写 if 判断整段删掉，替换成：
     ```java
     OrderStatus fromStatus = order.getStatus();

     if (fromStatus == OrderStatus.CREATED) {
         stateMachine.validateTransition(OrderStatus.CREATED, OrderStatus.PAYING);
         stateMachine.validateTransition(OrderStatus.PAYING, OrderStatus.PAID);
     } else {
         stateMachine.validateTransition(fromStatus, OrderStatus.PAID);
     }
     ```
     放在方法开头 `findById`/`orElseThrow` 之后；原来在 if 判断之后才声明的
     `OrderStatus fromStatus = order.getStatus();` 现在提到判断之前，后续
     `order.setStatus(OrderStatus.PAID); ...` 等逻辑不变。
- **验收**: 对 SHIPPED 等真正不可标记为已支付的状态调用 `markAsPaid`，抛出的异常消息变成来自
  `OrderStateMachine.validateTransition` 的 `"Cannot transition order from ... to ..."`（而不是
  原来的 `"Cannot mark order ... as paid when status is ..."`），仍是 `BusinessException`
  （`ORDER_INVALID_TRANSITION`，400）——这是预期内的消息变化。CREATED/PAYING 状态订单仍能正常
  标记为 PAID（`POST /api/v1/payment/pay` 走到底应仍能让订单变 PAID）。（注：ORD-A20-2 会在本卡
  之后在方法开头再加一道显式 409 守卫，把"不可支付状态"的对外表现从这里的 400
  `ORDER_INVALID_TRANSITION` 进一步收敛为冻结码 409 `ORDER_STATUS_CONFLICT`——两卡按序落地后以
  ORD-A20-2 的验收为准，见该卡。）
- **勿犯**: 
  1. `markAsPaid(Long orderId, String paymentNo)` 是 `OrderPaymentStatusUpdater` 接口方法，payment
     模块通过这个接口调用——方法名、参数、返回类型（`void`）一个字都不能改，只能改方法体内部实现。
  2. 本卡**只管状态机校验**，不要在这里顺手加"发布 `OrderPaidEvent` 通知 logistics/loyalty"的
     逻辑。目前生产环境唯一会执行到 `markAsPaid` 的路径（payment 模块支付成功后调用）完全不发布
     任何事件，导致物流建单、积分入账对"支付成功"这件事没有反应；这件事由 `S2-events.md` §A 的
     **EVT-A7** 卡片专门负责（批次 B13，按批次表在本批之后执行），不在本卡任务范围内，也不要
     自己在 common 模块新建事件类。EVT-A7 届时会在 `markAsPaid` 方法末尾（状态更新保存与
     `log.info(...)` 之后）追加发布调用，和本卡改动的方法开头状态校验部分不重叠。

---

### ORD-A12 | verifyPurchase（controller 路径）按不存在的 deliveredAt 排序，REST 端点 500

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: `verifyPurchase(VerifyPurchaseRequest request)`（`OrderController.verifyPurchase` 走的
  就是这个方法，约第326行）：
  ```java
  Page<Order> orders = orderRepository.findByUserId(request.getUserId(),
          PageRequest.of(0, 100, Sort.by(Sort.Direction.DESC, "deliveredAt")));
  ```
  `Order` 实体没有 `deliveredAt` 这个字段/列，Spring Data JPA 解析排序属性时会抛
  `PropertyReferenceException`，`GET /api/v1/orders/verify-purchase` 直接 500。
- **期望**: 排序应该用实际存在的字段；订单是否"已签收"由 `status` 是否为 `DELIVERED`/`COMPLETED`
  判断（后面几行代码已经在做这件事），不依赖某个时间戳字段。依据: design-docs/附录C（orders 表
  没有 deliveredAt 列）、README.md §6（该端点应正常返回，不是 500）。
- **改法**: 把
  ```java
  PageRequest.of(0, 100, Sort.by(Sort.Direction.DESC, "deliveredAt"))
  ```
  改成
  ```java
  PageRequest.of(0, 100, Sort.by(Sort.Direction.DESC, "createdAt"))
  ```
  只改排序字段名这一处。（ORD-A20-1 随后会把这一行的分页 size 从 100 统一为 200，并把循环内的
  SPU 匹配条件扩展成 SPU-or-SKU——两卡按序各改各的、互不冲突，见该卡。）**注意**：`ecommerce-order` 模块里还有另一个同名方法
  `OrderQueryServiceImpl.verifyPurchase(Long userId, Long productId)`（跨模块 `OrderQueryService`
  接口实现，供 review 模块调用）——那个方法基线代码里排序字段本来就已经是 `"createdAt"`，是对的，
  **不要**去改它，也不用管它。
- **验收**: `GET /api/v1/orders/verify-purchase?userId=..&productId=..` 正常返回 200（不是 500），
  已购买并签收的商品返回 `purchased=true`。

---

### ORD-A13 | orderNo 生成器同一毫秒内碰撞

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: `generateOrderNo()`（约第368-372行）：
  ```java
  private String generateOrderNo() {
      String datePart = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
      // Use a simple timestamp-based suffix for uniqueness
      String seqPart = String.format("%04d", System.currentTimeMillis() % 10000);
      return "SO" + datePart + seqPart;
  }
  ```
  用 `System.currentTimeMillis() % 10000` 做序列号后缀——同一毫秒内创建的多笔订单（例如批量下单
  `POST /api/v1/orders/batch` 循环调用同一个 `OrderService.createOrder`）会生成完全相同的
  `orderNo`，违反其唯一约束，批量下单里第二笔起会因唯一约束冲突而失败。
- **期望**: `orderNo` 在同毫秒/并发场景下也必须保证唯一。依据: design-docs/附录C
  （`orders.order_no` "订单号，唯一"）。
- **改法**: 
  1. 在类的字段区加一个单调递增计数器：
     ```java
     private final java.util.concurrent.atomic.AtomicLong orderSequence =
             new java.util.concurrent.atomic.AtomicLong();
     ```
  2. 把 `generateOrderNo()` 里的
     ```java
     String seqPart = String.format("%04d", System.currentTimeMillis() % 10000);
     ```
     改成
     ```java
     String seqPart = String.format("%04d", orderSequence.incrementAndGet() % 10000);
     ```
  `OrderService` 是单例 Spring bean，单笔下单（`OrderController.createOrder`）和批量下单
  （`BatchOrderService.createBatch` 循环调用的也是同一个 `OrderService` bean 的 `createOrder`）
  共享同一个计数器实例，天然不会碰撞。
- **验收**: 同一毫秒内连续调用 `generateOrderNo()`（或直接批量下单多笔）生成的 `orderNo` 互不
  相同；批量下单多笔全部成功入库，不再因唯一约束冲突失败。

---

### ORD-A14 | 创建订单请求体 addressId 被忽略，恒用默认地址（跨模块：user）

- 风险: high · 置信度: definite
- **文件**: 
  1. `code/ecommerce-user/src/main/java/com/ecommerce/user/query/UserQueryService.java`
     （接口，新增方法）
  2. `code/ecommerce-user/src/main/java/com/ecommerce/user/service/UserQueryServiceImpl.java`
     （实现）
  3. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（调用方）
- **现状**: `CreateOrderRequest` 请求体里的 `addressId` 字段（README.md §6/design-docs/附录A §6
  冻结请求示例里明确有这个字段）从头到尾没被读取过。`OrderService.createOrder(...)` 里（约
  第217-222行）：
  ```java
  if (request.getAddressId() != null) {
      AddressDto address = userQueryService.getDefaultAddress(userId);
      if (address != null) {
          order.setAddressSnapshot(toAddressSnapshot(address));
      }
  }
  ```
  只是拿 `addressId != null` 当"用户填过地址"的信号，实际查的却永远是
  `getDefaultAddress(userId)`（默认地址），完全忽略了请求里具体传的是哪个 `addressId`——用户选一个
  非默认地址下单，订单快照里存的还是默认地址。`UserQueryService` 接口目前也没有"按 ID 查地址"的
  方法，只有 `getDefaultAddress`。
- **期望**: 创建订单应按请求里传入的 `addressId` 查询该地址（并校验属于当前用户），而不是无脑查
  默认地址。依据: README.md §6/design-docs/附录A §6（`addressId` 是冻结请求字段）、README.md §8
  PUB-102（用例创建的地址并非默认地址，通过 `addressId` 传入）。
- **改法**: 
  1. `UserQueryService.java` 接口新增一个方法（**只新增，不删不改现有的 `getDefaultAddress`/
     `getUserById`/`isActive`/`isFrozen` 这 4 个方法**）：
     ```java
     /**
      * Retrieves a specific address by ID, verifying it belongs to the given user.
      *
      * @param userId    the user ID
      * @param addressId the address ID
      * @return the address DTO (throws ResourceNotFoundException if it doesn't
      *         exist or doesn't belong to this user)
      */
     AddressDto getAddressById(Long userId, Long addressId);
     ```
  2. `UserQueryServiceImpl.java` 补实现（该类是目前唯一实现 `UserQueryService` 接口的类，不用担心
     其它实现类跟着要补）：
     ```java
     @Override
     public AddressDto getAddressById(Long userId, Long addressId) {
         UserAddress address = userAddressRepository.findById(addressId)
                 .filter(a -> a.getUserId().equals(userId))
                 .orElseThrow(() -> new ResourceNotFoundException("Address", addressId));
         return toDto(address);
     }
     ```
     复用已有的私有 `toDto(UserAddress)` 方法和 `userAddressRepository` 字段；
     `ResourceNotFoundException(String resourceName, Object identifier)` 双参构造函数、
     `ResourceNotFoundException` 的 import 在本文件里已经存在（`getUserById` 也在用）。
  3. `OrderService.java` 里把
     ```java
     if (request.getAddressId() != null) {
         AddressDto address = userQueryService.getDefaultAddress(userId);
         if (address != null) {
             order.setAddressSnapshot(toAddressSnapshot(address));
         }
     }
     ```
     改成
     ```java
     if (request.getAddressId() != null) {
         AddressDto address = userQueryService.getAddressById(userId, request.getAddressId());
         order.setAddressSnapshot(toAddressSnapshot(address));
     }
     ```
     （`getAddressById` 找不到/不属于该用户时会抛 `ResourceNotFoundException`，不再需要
     `address != null` 判空。）
- **验收**: 用户新建一个非默认地址、下单时传该地址的 `addressId`，订单详情里的 `addressSnapshot`
  应该是那个新地址的内容而不是默认地址；传一个不属于自己的 `addressId` 应该 404。
  `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub102_createOrderShouldReturn201 test`
  应仍为绿（该用例本身用非默认地址下单）。
- **勿犯**: 
  1. `UserQueryService` 是横跨 order/payment/review 等多个模块依赖的跨模块接口——**只能新增方法，
     绝对不能修改或删除 `getDefaultAddress`/`getUserById`/`isActive`/`isFrozen` 这 4 个已有方法的
     签名**；`ecommerce-order/OrderSnapshotService.java`（虽是死代码——全仓库没有任何地方注入/调用
     它，但仍会被编译）等其它地方还在用 `getDefaultAddress`，改了签名会导致编译错误。
  2. 不要把 `getDefaultAddress` 删掉或改成内部调用 `getAddressById` 再包一层——两者语义不同
     （一个是"查默认地址"，一个是"按 ID 查并校验归属"），保持独立、都保留。

---

### ORD-A15 | calculateDiscounts 吞掉真实促销业务异常

- 风险: high · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: 私有方法 `calculateDiscounts(...)`（约第378行开始）末尾：
  ```java
  return calcResponse.getTotalDiscount();
  } catch (Exception e) {
      log.warn("Failed to calculate promotions, using zero discount: {}", e.getMessage());
      return BigDecimal.ZERO;
  }
  ```
  用一个 `catch (Exception e)` 把 `promotionCalculationService.calculate(...)` 抛出的**所有**
  异常都吞掉、降级成"零折扣，订单照常创建成功"。这包括 promotion 模块为 `COUPON_EXPIRED`/
  `COUPON_THRESHOLD_NOT_MET`/`COUPON_NOT_APPLICABLE`/`COUPON_ALREADY_USED` 等 README 冻结错误码
  抛出的真实业务校验失败（`BusinessException` 及其子类）——用户传了个过期优惠券，系统不告诉他
  优惠券过期，反而悄悄按无折扣把订单创建成功了。
- **期望**: 真正的业务规则拒绝（`BusinessException` 及其子类，对应 README 冻结错误码）必须原样
  抛出、阻止订单创建；只有 promotion 模块自身的基础设施性异常（非业务拒绝）才应该降级为零折扣。
  依据: README.md §7.2（`COUPON_EXPIRED` 等错误码必须可达）。
- **改法**: 把单个 `catch (Exception e)` 拆成两层，**更具体的异常类型必须写在前面**：
  ```java
  return calcResponse.getTotalDiscount();
  } catch (BusinessException e) {
      // A real coupon/promotion validation failure (COUPON_EXPIRED,
      // COUPON_THRESHOLD_NOT_MET, COUPON_NOT_APPLICABLE, COUPON_ALREADY_USED, ...)
      // must reject order creation with its frozen error code.
      throw e;
  } catch (Exception e) {
      // Genuine infrastructure failure in the promotion module itself degrades
      // to zero discount rather than blocking order creation entirely.
      log.warn("Failed to calculate promotions, using zero discount: {}", e.getMessage());
      return BigDecimal.ZERO;
  }
  ```
  `com.ecommerce.common.exception.BusinessException` 已经在文件顶部 import 过。**只改这个私有
  方法内部的 catch 块**——方法签名、方法体前半段构造 `calcRequest` 的逻辑、以及调用方
  `calculateDiscounts(userId, request, ..., itemTotal)` 传入的第三个参数具体是什么列表，都不要动
  （那个参数是否叫 `orderItems` 还是别的子集名字，属于 `promotion.md` 秒杀接入卡片的范围，与本卡
  无关，不要因为这条卡片去改调用点）。
- **验收**: 下单时传入一个已过期的优惠券 `couponIds`，`POST /api/v1/orders/create` 返回 400、
  `code=COUPON_EXPIRED`（而不是返回 201、订单被创建、折扣为 0）；不传优惠券或 promotion 模块本身
  故障（非业务拒绝）时，订单仍能正常创建、折扣按 0 处理。
- **勿犯**: Java 里 `catch` 子句按声明顺序匹配，`BusinessException` 是 `Exception` 的子类，
  **`catch (BusinessException e)` 必须写在 `catch (Exception e)` 前面**，顺序反了编译都过不了
  （"exception has already been caught"）。不要为了图省事把两层 catch 合并回一层再用
  `instanceof` 判断——保持两层 catch 结构，和本模块其它地方（如 `PaymentValidator`）的异常分层
  风格一致。

---

### ORD-A16 | OrderCreatedEvent 监听器只打日志，从不真正发通知

- 风险: low · 置信度: likely
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/OrderEventListener.java`
- **现状**: `onOrderCreated(OrderCreatedEvent event)`（约第47行开始，
  `@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)`）只有两行
  `log.info(...)`/`log.debug(...)` 和一段注释：
  ```java
  // In production, this would:
  // - Send to analytics pipeline
  // - Update real-time dashboards
  // - Trigger notification workflows
  ```
  从未真正调用过 `LocalNotificationService`——订单创建后用户收不到任何通知。
- **期望**: 订单创建后应该通过 `LocalNotificationService` 发一条 `IN_APP` 通知（订单状态类通知走
  IN_APP 渠道）。依据: design-docs/15 §2（"IN_APP | 订单状态、退款状态"）、design-docs/03 §7
  （"所有通知必须通过 LocalNotificationService 发送"）。
- **改法**: 
  1. 构造函数加一个参数并保存成字段（本文件基线没有对应单测文件，加参数无编译风险）：
     ```java
     private final LocalNotificationService notificationService;

     public OrderEventListener(OrderRepository orderRepository,
                                LocalNotificationService notificationService) {
         this.orderRepository = orderRepository;
         this.notificationService = notificationService;
     }
     ```
     加 import：`com.ecommerce.common.notification.LocalNotificationService`、
     `com.ecommerce.common.notification.NotificationChannel`、
     `com.ecommerce.common.notification.NotificationRequest`、`java.util.Map`。
  2. 在 `onOrderCreated` 方法里，`log.info(...)` 那行之后、`log.debug(...)` 那行之前，插入：
     ```java
     NotificationRequest request = new NotificationRequest();
     request.setBizType("ORDER_CREATED");
     request.setBizId(String.valueOf(event.getOrderId()));
     request.setChannel(NotificationChannel.IN_APP);
     request.setTemplateCode("order_created");
     request.setVariables(Map.of(
             "orderId", String.valueOf(event.getOrderId()),
             "amount", event.getPayableAmount().toString()
     ));
     request.setIdempotencyKey("order_notify_" + event.getOrderId());
     notificationService.send(request);
     ```
     那段 "In production, this would..." 注释可以删掉。**不要**改 `onOrderPaid`/
     `onOrderCancelled`/三个 `*Fallback` 方法，也不要改 `OrderCreatedEvent` 类本身（字段够用：
     `getOrderId()`/`getPayableAmount()` 已存在）。
- **验收**: 创建订单成功后，调用 `GET /api/v1/admin/notifications`（README.md §6 管理支撑接口）
  能查到一条 `bizType=ORDER_CREATED`、`channel=IN_APP` 的通知记录。

---

### ORD-A17 | 订单取消成功路径只释放库存，从不归还优惠券/秒杀名额（接线卡）

- 风险: low · 置信度: definite
- **执行时机（先读这条再动手）**: 本卡调用的 `couponService.releaseForOrder(...)` /
  `seckillService.releaseForOrder(...)` 是 `promotion.md` PROMO-14/PROMO-15（批次 B05）新增的方法。
  按批次表顺序（B03 早于 B05）执行到本文件时**这两个方法还不存在，先跳过本卡**，等执行 B05 批次时
  把本卡与 PROMO-14/15 **同批一起落地、一起 verify**（若 B03 阶段就单独应用本卡，
  `ecommerce-order` 编译不过、`mvn install -DskipTests` 失败，黑盒 0/24）。本卡编号留在 §A 只因
  它改的是 order 模块文件；其产物断言在 `artifacts.tsv` 里也登记为 B05。
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
  2. （同步测试）`code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderCancelServiceTest.java`
- **现状**: 基线 `OrderCancelService` 的取消成功路径——`cancelCreatedOrder(...)`（基线第 110 行起，
  内有 `inventoryReservationService.release(order.getId())`）、`cancelPayingOrder(...)`（基线第
  143 行起）、`reviewCancel(...)` 审核通过分支（基线第 201 行起，内有
  `inventoryReservationService.release(orderId)`）——只释放**库存**，从不通知 promotion 模块归还
  券/秒杀名额；构造函数注入的 5 个协作者里没有任何 promotion 服务。ORD-A5/ORD-A7 落地后该文件的
  PAID 分支改走 `requestPaidOrderCancelReview`（只进 `CANCEL_REVIEWING`，不释放任何资源——那是
  对的，本卡不碰它）、5 处状态冲突换成了 `ConflictException`，但三条成功路径依旧没有券/名额释放。
  于是（配合 PROMO-4/8/13 的消费侧）出现单向棘轮：下单即消费券和秒杀名额，取消却永不归还。
- **期望**: 每条**真正到达 `CANCELLED`** 的路径（CREATED 直接取消、PAYING 取消、CANCEL_REVIEWING
  审核通过）都调用 PROMO-14/15 的 `releaseForOrder(orderId)` 归还券与秒杀名额；释放是 best-effort
  ——失败只记日志，绝不阻断取消本身（与同方法里既有的库存释放 try/catch 模式一致；精神同
  design-docs/03 §8"监听器失败……不得回滚主事务"）。依据: design-docs/08 §6（取消规则表：取消
  须释放订单占用的资源）+ PROMO-14/15 卡「期望」引用的 10 §2/§4 条款。来源：`findings.md`
  「已识别但因时间/风险预算未实施」条目"优惠券/秒杀名额在订单取消后从未释放"的 order 侧接线。
- **改法**:
  1. 加 import（order 模块 pom 已依赖 ecommerce-promotion，`OrderService` 里早有同款注入，
     不需要动任何 pom）：
     ```java
     import com.ecommerce.promotion.service.CouponService;
     import com.ecommerce.promotion.service.SeckillService;
     ```
  2. 构造注入两个 promotion 领域服务（字段区加两个 `private final`，构造函数参数列表末尾追加
     `CouponService couponService, SeckillService seckillService` 并赋值——增量追加，别整段替换
     覆盖既有参数）。
  3. 类末尾（`reviewCancel` 之后）新增私有帮助方法，两段**独立** try/catch：
     ```java
     /**
      * Give back the coupons and the seckill allocation consumed by an order
      * once its cancellation has succeeded (mirrors the consumption side,
      * {@code OrderService} Step 10b). Both calls are best-effort: a release
      * failure is logged and swallowed — it must never block the cancellation
      * itself (design-docs/03: post-actions must not fail the main flow),
      * exactly like the inventory release above. Only invoked on paths that
      * actually reach CANCELLED — a PAID order entering CANCEL_REVIEWING keeps
      * its coupons/allocation until the review is approved.
      */
     private void releasePromotions(Long orderId) {
         try {
             couponService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release coupons for cancelled order {}: {}", orderId, e.getMessage());
         }
         try {
             seckillService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release seckill allocation for cancelled order {}: {}",
                     orderId, e.getMessage());
         }
     }
     ```
  4. 三个调用点（都在订单已持久化为目标状态之后）：
     - `cancelCreatedOrder(...)`：库存释放 try/catch 之后、`orderService.recordEvent(...)` 之前，加
       ```java
       // Give back coupons and seckill allocation consumed by this order
       releasePromotions(order.getId());
       ```
     - `cancelPayingOrder(...)`：`orderRepository.save(order)` 之后、`recordEvent` 之前，加同样两行；
     - `reviewCancel(...)` 的 `approved` 分支：库存释放 try/catch 之后、`recordEvent` 之前，加
       `releasePromotions(orderId);`（形参本来就叫 `orderId`）。
     `requestPaidOrderCancelReview` 与 `reviewCancel` 的驳回分支**不加**。
  5. **`OrderCancelServiceTest.java`** 同步：
     - 加 import `com.ecommerce.promotion.service.CouponService`/`SeckillService` 与
       `static org.mockito.Mockito.doThrow`；`@Mock` 字段区加
       `@Mock private CouponService couponService;`、`@Mock private SeckillService seckillService;`
       （`@InjectMocks` 构造注入自动接上，缺了这两个 mock 会注入 null）；
     - 既有 `testCancel_paidOrder_movesToCancelReviewing` 末尾加
       `verify(couponService, never()).releaseForOrder(anyLong());` 与 seckill 同款断言
       （审核前不许释放）；既有 `testReviewCancel_approve` 末尾加
       `verify(couponService).releaseForOrder(10L);`、`verify(seckillService).releaseForOrder(10L);`；
     - 新增三个用例：CREATED 取消 → 两个 `releaseForOrder(1L)` 各被调用一次；PAYING 取消（内联
       fixture，`status=PAYING`）→ 响应 `CANCELLED` 且两个 `releaseForOrder(5L)` 被调用；
       `doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L)` 时
       取消 CREATED 单**仍然成功**（响应 `CANCELLED`），且 `verify(seckillService).releaseForOrder(1L)`
       （前一段失败不影响后一段）。
- **验收**:
  - 单测：`OrderCancelServiceTest` 全绿，覆盖"三条成功路径都释放、CANCEL_REVIEWING 阶段不释放、
    释放失败不阻断取消"。
  - 端到端：见 PROMO-14/15 的端到端验收（券回 `AVAILABLE`、`soldQuantity` 回落）；对 PAID 单仅发起
    取消申请（进入 `CANCEL_REVIEWING`）后查券，状态仍是 `USED`；管理员审核**驳回**后券仍是 `USED`
    （订单回到 PAID，资源保留）。
  - 公开 24 例回归全绿。
- **勿犯**: 不要在 `requestPaidOrderCancelReview`（PAID→CANCEL_REVIEWING）里释放——券/名额和库存
  一样要等审核通过才归还，驳回时订单回到 PAID、资源必须原样保留（ORD-A5「勿犯」的镜像）。不要把
  `releasePromotions` 的 try/catch 去掉或把异常往外抛——释放失败只 `log.warn`，绝不能让取消接口
  500。不要把两段 try/catch 合并成一段——券释放失败不应连累秒杀释放。超时自动取消路径**不在本卡范围**（本卡只覆盖
  `OrderCancelService` 的三条路径）——`OrderTimeoutService` 的同款释放由后补的 **ORD-A21** 单独
  落卡（与本卡同批 B05 执行，见该卡），不要在本卡里顺手改它；`OrderLifecycleService` 依旧是
  头部红线里的死服务，任何卡都不得接线。

---

### ORD-A18 | cancel-review 请求体双形态：冻结 fixture 发 {"approved": boolean}，被 decision 的 @NotBlank 直接 400

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/dto/AdminCancelReviewRequest.java`
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/controller/AdminOrderController.java`
  3. （同步测试）`code/ecommerce-order/src/test/java/com/ecommerce/order/controller/AdminOrderControllerTest.java`
- **现状**: 基线 `AdminCancelReviewRequest` 只有 `decision`/`comment` 两个字段，且 `decision` 上有
  `@NotBlank(message = "Review decision is required (APPROVE or REJECT)")`；
  `AdminOrderController.reviewCancel(...)`（约第52-64行）以 `@Valid @RequestBody` 接收后
  `boolean approved = "APPROVE".equalsIgnoreCase(request.getDecision());`。而**冻结**黑盒 fixture
  `test-cases/src/test/java/com/ecommerce/blackbox/common/fixture/OrderFixture.java` 第143-148行的
  `cancelReview(...)` 发送的请求体是 `{"approved": boolean}`——根本没有 decision 字段。于是所有经
  fixture 走 `POST /api/v1/admin/orders/{orderId}/cancel-review` 的用例都在 bean-validation 阶段被
  400（`VALIDATION_FAILED`）拒掉，永远到不了业务逻辑。
- **期望**: 端点必须同时接受两种客户端形态：`{"approved": true/false}`（冻结 fixture 形态，
  test-cases 不可修改，是该请求体形态的铁证）与 `{"decision": "APPROVE"/"REJECT"}`（基线管理台
  形态，继续兼容）。依据: test-cases/.../fixture/OrderFixture.java:143-148（冻结请求体）、
  README.md §6（`POST /api/v1/admin/orders/{orderId}/cancel-review | ADMIN | 200` 冻结端点）、
  design-docs/08 §6/§9（取消审核流程）。
- **改法**:
  1. DTO：去掉 `decision` 上的 `@NotBlank`（连同已无人使用的
     `import jakarta.validation.constraints.NotBlank;`），新增 `private Boolean approved;` 字段与
     getter/setter。**必须用包装类型 `Boolean`**——null 表示"客户端没传这个字段"，原生 boolean 会把
     "没传"和"传了 false"混为一谈。
  2. Controller 把 `boolean approved = "APPROVE".equalsIgnoreCase(request.getDecision());` 改成：
     ```java
     boolean approved = request.getApproved() != null
             ? request.getApproved()
             : "APPROVE".equalsIgnoreCase(request.getDecision());
     ```
     显式 `approved` 优先；回落 decision 字符串时**常量写在前面**（`"APPROVE".equalsIgnoreCase(...)`），
     decision 为 null 时天然不 NPE、按驳回处理。`orderCancelService.reviewCancel(orderId, approved,
     comment, adminId)` 调用及其下游一概不动。
  3. 同步测试 `AdminOrderControllerTest`：保留既有 3 个 decision 形态用例；新增 3 个用例——
     `{"approved": true}`→批准、`{"approved": false}`→驳回、两字段同发时 approved 优先。注意新增
     用例的 stub 里 comment 参数用 `any()` 而不是 `anyString()`（approved 形态下 comment 是 null，
     `anyString()` 匹配不到 null，stub 不生效会 NPE）。
- **验收**: 单测 `AdminOrderControllerTest` 全绿（8 例）。对 CANCEL_REVIEWING 状态订单：请求体
  `{"approved": true}` → 200、订单转 CANCELLED；`{"approved": false}` → 200、订单回 PAID；
  `{"decision": "APPROVE"}` 行为与基线一致。公开 24 例回归全绿。
- **勿犯**: 不要动 fixture/test-cases（冻结）；不要给 `approved` 加任何 bean-validation 必填约束——
  两种形态各只传自己的字段，任何一边必填都会 400 掉另一边；不要删 `decision` 字段或改其语义
  （基线形态仍要兼容）；空体 `{}` 按驳回处理即可，不要为它发明新错误码。

---

### ORD-A19 | 批量下单每行结果缺 README §8 冻结的 status 字段（SUCCESS/FAILED）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/dto/BatchCreateOrderResponse.java`
  2. （同步测试）`code/ecommerce-order/src/test/java/com/ecommerce/order/service/BatchOrderServiceTest.java`
- **现状**: 内部类 `BatchOrderResult`（约第53行起）只有
  `externalOrderNo/orderId/orderNo/success(boolean)/error` 五个字段；`success(...)`/`failure(...)`
  两个工厂方法只设置 `success` 布尔。每行结果的 JSON 里没有任何 `status` 字符串字段。
- **期望**: README.md §8 PUB-016 验收明文"**每条结果 status=SUCCESS**，成功数量=2"——每行结果必须有
  `status` 字段：成功行 `"SUCCESS"`、失败行 `"FAILED"`；`success` 布尔保留（既有对外字段，冻结契约
  禁止删改字段名/类型，本卡只**新增**）。依据: README.md §8 PUB-016、design-docs/08 §7（"最终返回
  每条的创建结果明细"）。
- **改法**:
  1. `BatchOrderResult` 增加 `private String status;` 与 getter/setter；
  2. `success(...)` 工厂体内加 `r.status = "SUCCESS";`，`failure(...)` 工厂体内加 `r.status = "FAILED";`；
  3. 同步测试 `BatchOrderServiceTest`：在既有 `isSuccess()` 断言旁补 `getStatus()` 等于
     `"SUCCESS"`/`"FAILED"` 的断言（两处：单笔失败用例、全成功用例）。
  `BatchOrderService` 本身零改动——两个静态工厂是 `BatchOrderResult` 唯一的构造入口，改工厂即覆盖
  所有路径。
- **验收**: `POST /api/v1/orders/batch` 两笔合法订单 → 每条结果 `status="SUCCESS"`、`successCount=2`
  （PUB-016 主张）；一笔失败时该行 `status="FAILED"` 且 `error` 带失败原因。公开 24 例回归全绿。
- **勿犯**: 不要删除/重命名 `success` 布尔或把它改成字符串——只新增 `status` 字段；不要在
  `BatchOrderService` 里散落地 `setStatus(...)`，赋值只放在两个工厂方法里，保证 success 布尔与
  status 字符串永远同步。

---

### ORD-A20 | 行为对齐三件套：verifyPurchase 双 ID 匹配、markAsPaid 409 冲突码、销售统计未授权 90 天上限

一张卡三处独立小修（20-1/20-2/20-3），都在 order 模块、代码位置互不重叠，可一次落地一次回归。

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`（20-1、20-2）
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`（20-1）
  3. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/SalesStatisticsService.java`（20-3）
  4. （同步测试）`OrderQueryServiceImplTest.java`、`SalesStatisticsServiceTest.java`

**20-1 verifyPurchase 双路径按 SPU-or-SKU 匹配 + 分页 size 统一 200**

- **现状**: 两条 verifyPurchase 路径——跨模块 `OrderQueryServiceImpl.verifyPurchase(userId, productId)`
  （review 模块经 `OrderQueryService` 接口调用）与 REST 路径
  `OrderService.verifyPurchase(VerifyPurchaseRequest)`（`GET /api/v1/orders/verify-purchase`）——匹配
  条件都只按 SPU：`sku.getSpuId().equals(productId)`。而冻结 fixture `OrderFixture#verifyPurchase`
  的 javadoc 明文 `@param productId product (SPU/SKU) id`——productId 可能传的就是 SKU id，按现状
  一律误判为未购买。另外两路径分页 size 不一致（跨模块 200 / REST 100）。
- **期望**: 匹配条件为"SPU 命中**或** SKU 命中"（当前绿路径的严格超集，只增不减）；两路径分页 size
  统一为 200。依据: test-cases/.../fixture/OrderFixture.java（`productId product (SPU/SKU) id`）、
  design-docs/08 §8（`verifyPurchase(userId, productId)`）、design-docs/13 §2（评价前购买校验）。
- **改法**: 两处把匹配条件改为
  ```java
  if (sku != null && (sku.getSpuId().equals(productId)
          || item.getSkuId().equals(productId))) {
  ```
  （REST 路径里 productId 写作 `request.getProductId()`）；REST 路径的
  `PageRequest.of(0, 100, ...)` 改为 `PageRequest.of(0, 200, ...)`。**两处必须同改**，否则 REST 与
  跨模块两个入口对同一 productId 给出不同答案。若执行时 ORD-A12 尚未应用（排序字段还是
  `deliveredAt`），排序字段属于 ORD-A12 的范围，本卡只改 size 与匹配条件。
- **验收**: `OrderQueryServiceImplTest` 新增"productId=SKU id（SPU id 不同）时返回 purchased=true"
  用例；既有 SPU 命中 / 不命中 / 非签收跳过 3 个用例不改仍绿。

**20-2 markAsPaid 不可支付状态显式抛 409 ORDER_STATUS_CONFLICT**

- **现状**: `markAsPaid`（ORD-A11 落地后）把不可支付状态交给状态机深处抛
  `ORDER_INVALID_TRANSITION`（400）；基线（ORD-A11 之前）则是手写 if 抛 `ORDER_INVALID_STATUS`
  （400）。两个都不是冻结码，而"订单状态不允许操作"按 README §7.2 是 409。
- **期望**: 订单状态不在可支付集合（CREATED/PAYING）时，`markAsPaid`（支付回调链路
  `PaymentCallbackService.processSuccessCallback` → `markAsPaid`，链上无 catch，异常直达 REST 层）
  必须对外表现为 409、`code=ORDER_STATUS_CONFLICT`，与 `getPayableOrder`（ORD-A8）一致。依据:
  README.md §7.2（`ORDER_STATUS_CONFLICT | 409 | 订单状态不允许操作`）、design-docs/03 §2
  （`ConflictException`=409 用于状态冲突）。
- **改法**: 在 `markAsPaid` 取得 `OrderStatus fromStatus = order.getStatus();` 之后、状态机校验
  之前插入：
  ```java
  if (fromStatus != OrderStatus.CREATED && fromStatus != OrderStatus.PAYING) {
      throw new ConflictException("ORDER_STATUS_CONFLICT",
              "Order " + orderId + " in status " + fromStatus
                      + " cannot be marked paid");
  }
  ```
  `ConflictException` 的 import 已由 ORD-A8 加过。**绝不动 `OrderStateMachine`**——守卫之后的链式
  状态机校验原样保留（通过守卫的 CREATED/PAYING 仍走状态机权威校验）。本卡**收敛 ORD-A11 的验收**：
  不可支付状态的对外表现由"400 `ORDER_INVALID_TRANSITION`"升级为"409 `ORDER_STATUS_CONFLICT`"。
- **验收**: 单测：SHIPPED/CANCELLED 订单 `markAsPaid` → `ConflictException`、消息含
  "cannot be marked paid"、不 save 不发事件；CREATED/PAYING 正常转 PAID 并发布 `OrderPaidEvent`
  的既有用例不改仍绿。

**20-3 销售统计删除未授权且恒假的 90 天上限**

- **现状**: `SalesStatisticsService.getSalesStatistics` 在 startDate>endDate 校验之后有：
  ```java
  // Limit range to 90 days for performance
  if (startDate.until(endDate).getDays() > 90) {
      throw new BusinessException("DATE_RANGE_TOO_LARGE",
              "Date range cannot exceed 90 days for performance reasons");
  }
  ```
  `Period.getDays()` 只返回"日"分量（0-31），157 天跨度返回 6——该检查恒假、从未生效；且任何设计
  文档（08 / 附录A / 附录B）都没有授权过统计窗口上限，`DATE_RANGE_TOO_LARGE` 也不是 README §7
  冻结错误码。
- **期望**: 大跨度日期范围正常出统计（不设上限）。**删除该检查而不是"修好"它**——把恒假检查修
  "对"会让文档从未授权的 400 变成真实可达，反而制造新的不一致。保留 null 校验与 startDate>endDate
  的 400（`INVALID_DATE_RANGE`）。依据: design-docs/08 §9（该端点无任何范围限制条款）。
- **改法**: 整段删除上面的 if 块（含注释共 5-6 行）。`BusinessException` import 保留——前面两个
  校验还在用。
- **验收**: 单测：157 天跨度（2026-01-01 → 2026-06-07）正常返回不抛异常；startDate>endDate 仍 400。
  端到端 `GET /api/v1/admin/orders/statistics/sales?startDate=2026-01-01&endDate=2026-06-07` → 200。

- **公共验收**: 公开 24 例回归全绿（16+8）。
- **勿犯**: 20-1 不要去掉 `sku != null` 判空、不要动方法签名（`OrderQueryService.verifyPurchase` 是
  跨模块冻结接口）；20-2 不要把 409 守卫写进 `OrderStateMachine`（它是全部状态迁移的公共权威，409
  冲突语义只属于"把订单标记为已支付"这一操作视角）；20-3 不要顺手把 `Period.getDays()` 换成
  `ChronoUnit.DAYS.between(...)` 来"修复"上限——上限本身未获授权，要删不要修。

---

### ORD-A21 | 超时取消只释放库存，从不归还优惠券/秒杀名额（接线卡）

- 风险: low · 置信度: definite
- **执行时机（先读这条再动手）**: 同 ORD-A17——本卡调用的 `couponService.releaseForOrder(...)` /
  `seckillService.releaseForOrder(...)` 是 `promotion.md` PROMO-14/PROMO-15（批次 B05）新增的方法。
  按批次表顺序（B03 早于 B05）执行到本文件时**这两个方法还不存在，先跳过本卡**，等执行 B05 批次时
  经 PROMO-16 指针把本卡与 ORD-A17、PROMO-14/15 **同批一起落地、一起 verify**（若 B03 阶段就单独
  应用本卡，`ecommerce-order` 编译不过、黑盒 0/24）。本卡编号留在 §A 只因它改的是 order 模块文件；
  其产物断言在 `artifacts.tsv` 里也登记为 B05。
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTimeoutService.java`
  2. （同步测试）`code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderTimeoutServiceTest.java`
- **现状**: ORD-A10 落地后 `OrderTimeoutService.cancelExpiredOrder(...)` 已经会
  `inventoryReservationService.release(order.getId())` 释放预占库存，但与 ORD-A17 修复前的
  `OrderCancelService` 一样从不通知 promotion 模块。超时取消是**第四条真正到达 CANCELLED 的路径**
  （前三条见 ORD-A17），漏掉它就是资源单向棘轮的最后一个缺口：用户下单占住券/秒杀名额后弃单不付，
  60 分钟后系统自动取消，库存回来了，券和名额永远回不来。
- **期望**: 超时取消与用户取消同样归还订单占用的资源。依据: design-docs/08 §5（超时"系统自动取消
  订单并释放预占库存"）+ 08 §6 取消释放资源原则 + PROMO-14/15「期望」引用的 10 §2/§4 条款（与
  ORD-A17 完全同源）。释放 best-effort：失败只记日志，绝不阻断取消本身。
- **改法**:
  1. 加 import（order 模块 pom 已依赖 ecommerce-promotion，不用动 pom）：
     ```java
     import com.ecommerce.promotion.service.CouponService;
     import com.ecommerce.promotion.service.SeckillService;
     ```
  2. 字段区加两个 `private final`（`CouponService couponService;`、`SeckillService seckillService;`），
     构造函数参数列表末尾**增量追加**同名参数并赋值——别整段替换覆盖既有参数。
  3. `cancelExpiredOrder(...)` 里，`inventoryReservationService.release(order.getId());` 之后、
     `orderService.recordEvent(...)` 之前，插入：
     ```java
     // Give back coupons and seckill allocation consumed by this order —
     // a timeout cancellation returns the order's resources exactly like a
     // user-requested cancellation (OrderCancelService) does.
     releasePromotions(order.getId());
     ```
  4. 类末尾新增私有帮助方法（与 ORD-A17 的同名方法仅 javadoc/日志文案不同，两段**独立** try/catch）：
     ```java
     /**
      * Give back the coupons and the seckill allocation consumed by an expired
      * order once its timeout cancellation has succeeded (mirrors the
      * consumption side, {@code OrderService} Step 10b, and the same helper in
      * {@code OrderCancelService}). Both calls are best-effort: a release
      * failure is logged and swallowed — it must never block the cancellation
      * itself (design-docs/03: post-actions must not fail the main flow).
      */
     private void releasePromotions(Long orderId) {
         try {
             couponService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release coupons for expired order {}: {}", orderId, e.getMessage());
         }
         try {
             seckillService.releaseForOrder(orderId);
         } catch (Exception e) {
             log.warn("Failed to release seckill allocation for expired order {}: {}",
                     orderId, e.getMessage());
         }
     }
     ```
  5. **`OrderTimeoutServiceTest.java`** 同步：
     - 加 import `com.ecommerce.promotion.service.CouponService`/`SeckillService` 与
       `static org.mockito.Mockito.doThrow`；`@Mock` 字段区加
       `@Mock private CouponService couponService;`、`@Mock private SeckillService seckillService;`
       （`@InjectMocks` 构造注入自动接上；缺了这两个 mock 会注入 `null`，helper 里的 NPE 会被
       try/catch 吞掉，测试静默变弱）。
     - 新增两个用例（B15 的 LOY-12 之后会把它们扩成含积分退还断言的终态，见该卡；本批先按下面写）：
       ```java
       @Test
       @DisplayName("timeout gives back coupons and seckill allocation")
       void testCancelExpiredOrder_releasesPromotionsAndRefundsPoints() {
           orderTimeoutService.cancelExpiredOrder(expiredOrder);

           verify(couponService).releaseForOrder(1L);
           verify(seckillService).releaseForOrder(1L);
       }

       @Test
       @DisplayName("timeout release failures are swallowed and never block the cancellation")
       void testCancelExpiredOrder_releaseFailureDoesNotBlockCancel() {
           doThrow(new RuntimeException("release boom")).when(couponService).releaseForOrder(1L);

           orderTimeoutService.cancelExpiredOrder(expiredOrder);

           assertThat(expiredOrder.getStatus()).isEqualTo(OrderStatus.CANCELLED);
           verify(seckillService).releaseForOrder(1L);
           verify(orderService).recordEvent(eq(1L), eq(OrderStatus.CREATED), eq(OrderStatus.CANCELLED),
                   eq("TIMEOUT_CANCEL"), eq("SYSTEM"), anyString());
           verify(eventPublisher).publish(any(com.ecommerce.order.event.OrderCancelledEvent.class));
       }
       ```
- **验收**:
  - 单测：`OrderTimeoutServiceTest` 全绿——超时取消调用两个 `releaseForOrder(1L)`；券释放抛异常时
    取消仍完成（状态 CANCELLED、事件照记照发、秒杀释放照跑）。
  - `grep -n "releasePromotions" OrderTimeoutService.java` 命中 ≥2 处（1 定义 + 1 调用）。
  - 端到端：用券+秒杀下单后不支付，`POST /api/v1/admin/orders/timeout-cancel`（时钟拨过期后）触发
    超时取消 → 券回 `AVAILABLE`、`soldQuantity` 回落（同 PROMO-14/15 的端到端验收）。
  - 公开 24 例回归全绿。
- **勿犯**: 不要把 try/catch 去掉或把异常往外抛——`cancelExpiredOrders` 的循环虽有外层 catch，但
  释放失败若中断本方法，事件记录/发布会被跳过。不要把两段 try/catch 合并成一段——券释放失败不应
  连累秒杀释放。**只做券/秒杀释放**：积分退还的两行是 B15 `loyalty.md` LOY-12 的事（本批 loyalty
  侧 `refundPointsForOrder` 还不存在，现在接线必编译失败）。照旧不得接线 `OrderLifecycleService`
  等头部红线死服务。

---

### ORD-A22 | 【指针卡】取消/超时路径的积分退还 —— 实体在 loyalty.md 的 LOY-12，随 B15 执行

- 风险: low · 置信度: definite
- **本卡不含改法**：订单取消（用户取消 CREATED/PAYING、商家审核通过、超时自动取消）后退还下单时
  已抵扣的积分，需要 loyalty 侧先新增 `LoyaltyCommandService.refundPointsForOrder(...)`（批次 B15
  才落地）。order 侧接线代码若在本批（B03）就应用，`ecommerce-order` 引用不存在的方法，编译不过、
  黑盒 0/24——这与 ORD-A17/PROMO-16 的时序问题同型但方向相反（那次是 order 等 promotion 的 B05，
  这次是 order 等 loyalty 的 B15）。因此**全部改动（loyalty 新方法 + REFUND 流水 + order 侧
  `OrderService`/`OrderCancelService`/`OrderTimeoutService` 接线 + 三个测试文件同步）都写在
  `work/bugs/loyalty.md` 的 `### LOY-12`**，随 B15 批次整体执行。
- **执行时机**: B03/B04 执行本文件时**跳过本卡，什么都不改**；执行 B15 批次时打开
  `work/bugs/loyalty.md`，定位 `### LOY-12`，逐字照做（含测试同步）。其产物断言在 `artifacts.tsv`
  里登记为 B15。
- **验收**: B15 之后 `grep -n "refundLoyaltyPoints"` 在 `OrderCancelService.java` 命中 ≥4 处
  （1 处 helper 定义 + 3 处调用）、`OrderTimeoutService.java` 命中 ≥2 处（1 定义 + 1 调用）；
  `grep -n "refundPointsForOrder"` 两文件各 ≥1 处（helper 体内的跨模块调用，artifacts.tsv B15
  断言即它）；`OrderService.java` 的 `redeemPoints(...)` 调用带 4 个实参。
- **勿犯**: 绝不能因为"这卡指向另一个文件"而跳过 B15 的 LOY-12——artifacts.tsv B15 的
  `refundPointsForOrder` 三行会核验它，缺了整批按未完成处理。也绝不能在 B03/B04 提前做。

---

### ORD-A23 | round-15（已实施）：order 侧时钟成套 + orderNo 日期段 + 兑换率接配置 + ORDER_CREATED 补 receiver（附 payable 钳位决策留档）

- 风险: low（8 处小步替换/补行，无契约变化） · 置信度: definite
- **文件**:
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/OrderEventListener.java`
  3. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderCancelService.java`
  4. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **A·时钟成套（paidAt/cancelledAt）**: 原状 5 处业务时间戳读死墙钟——`OrderQueryServiceImpl.
  markAsPaid()`（原 :163）`setPaidAt(LocalDateTime.now())`、`OrderEventListener.onOrderPaid()` 兜底补
  paidAt（原 :89）、`OrderCancelService` 三个取消路径 `setCancelledAt(LocalDateTime.now())`
  （原 :128/:167/:237）。管理端拨钟（`PUT /api/v1/admin/system/clock`，design-docs/03 §5 测试支撑）后
  这些时间戳不跟走，与同模块已接时钟的 `expiresAt`（`OrderService` Step 9）不同源。改法：5 处全部换
  `SystemClockService.now()`，各文件补 `import com.ecommerce.common.test.SystemClockService;`，清理
  随之失效的 `java.time.LocalDateTime` import。
- **B·orderNo 日期段**: `OrderService.generateOrderNo()`（原 :469）日期段 `LocalDate.now()` 改
  `SystemClockService.now().toLocalDate()`（附录A 明示 orderNo 形如 `SO+yyyyMMdd+4 位序号`，日期段应
  反映系统时钟）；单调序列段不动；`java.time.LocalDate` import 随之移除。
- **C·下单路径兑换率接配置**: `OrderService` Step 7（原 :256-257）积分抵扣硬编码
  `MonetaryUtil.multiply(points, 0.01)`，运行时改写 `loyalty.redeem-rate` 对下单路径无效、与 loyalty
  侧 `LoyaltyPointService.pointsToAmount()`（读配置、`divide(rate, 2, HALF_UP)`）不同源。改法：与
  loyalty 完全同式——`int redeemRate = RuntimeConfigRegistry.getInt("loyalty.redeem-rate", 100);
  BigDecimal.valueOf(redeemedPoints).divide(BigDecimal.valueOf(redeemRate), 2, RoundingMode.HALF_UP)`
  （附录B §1 该键默认 100；补 `java.math.RoundingMode` import）。
- **D·ORDER_CREATED 通知补 receiver**: `OrderEventListener.onOrderCreated()` 构建的
  `NotificationRequest` 从不 `setReceiver`，通知记录收件人为空。改法：补
  `request.setReceiver(String.valueOf(event.getUserId()));`——与 `ShipmentService`/`InvoiceService`
  的既有 `String.valueOf(userId)` 约定一致。
- **勿犯**:
  1. `OrderService.recordEvent()` 的 `setCreatedAtLog(LocalDateTime.now())` 和 JPA 审计列
     （`createdAt`/`updatedAt`，由实体生命周期钩子填充）**不在本卡范围**，刻意未动——成套改它们
     牵扯 `@PrePersist` 体系，需单独评估。
  2. C 点必须保持与 `LoyaltyPointService.pointsToAmount` **完全同式**（同 key、同默认、同 divide
     scale/舍入），否则订单侧 `pointsDeductionAmount` 与 loyalty 侧扣减金额在非默认 rate 下出现分叉。
- **验收**: 拨钟 +N 天后支付/取消，`paidAt`/`cancelledAt` 为拨后时间，新订单 `orderNo` 日期段为拨后
  日期；`PUT /api/v1/admin/system/configs/loyalty.redeem-rate=50` 后带 `redeemPoints=100` 下单，
  `pointsDeductionAmount=2.00`（100/50）。公开 24 例回归通过（round-15 每项后门禁均 24/0/0）。
  artifacts.tsv 锚点：B03 `OrderQueryServiceImpl`↦`SystemClockService`、B04 `OrderService`↦
  `loyalty.redeem-rate`（均已双向验证：终态命中、基线 1b1e88f 不命中）。
- **决策留档（payable < 0.01 钳位到 0.01，2026-07-15 复核维持）**: `OrderTotalCalculator.calculate()`
  （:94-96）在扣完优惠/积分后若应付 `< 0.01` 则**钳位为 0.01**。design-docs/03 §1 存在双读法：
  ①"入库金额保留 2 位、正额下限 0.01"（钳位读法）；②"扣减不得使应付为负，可为 0"（0 元单读法）。
  选择维持钳位，理由：基线实现即钳位、公开 24 例与之相容；0 元应付将把"支付回调金额=0.00"的特判
  引入支付链（改动面更大、风险更高）；loyalty 侧 `estimateRedeemPoints` 的抵扣上限（max-redeem-ratio
  0.5）实际也使正常路径到不了 0 元。若隐藏用例证实 0 元单预期，改动点单一（删 :94-96 钳位分支），
  持本记录重议即可。

---

## §B order-pricing（批次 B04）— 金额 / 配置接入 / 积分抵扣 / 批量

### ORD-B1 | payableAmount 计算漏加 shippingFee

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTotalCalculator.java`
- **现状**: `calculate(BigDecimal itemTotal, BigDecimal shippingFee, BigDecimal packagingFee,
  BigDecimal discountAmount, BigDecimal pointsDeductionAmount)`（约第81行开始）：
  ```java
  BigDecimal payableAmount = MonetaryUtil.add(itemTotal, packagingFee);
  payableAmount = MonetaryUtil.subtract(payableAmount, discountAmount);
  payableAmount = MonetaryUtil.subtract(payableAmount, pointsDeductionAmount);
  ```
  第一行只把 `itemTotal` 和 `packagingFee` 相加，方法入参 `shippingFee` 全程未被使用——运费永远
  不计入应付金额。
- **期望**: `应付金额 = 商品总额 + 运费 + 包装费 − 优惠 − 积分抵扣`。依据: design-docs/08 §4
  （订单计价公式）、design-docs/附录A §6（示例：`itemTotal=398.00, shippingFee=0.00,
  packagingFee=2.00, discountAmount=30.00, pointsDeductionAmount=10.00 → payableAmount=360.00`，
  即 398+0+2−30−10=360）、README.md §8 PUB-104。
- **改法**: 把
  ```java
  BigDecimal payableAmount = MonetaryUtil.add(itemTotal, packagingFee);
  ```
  改成
  ```java
  BigDecimal payableAmount = MonetaryUtil.add(MonetaryUtil.add(itemTotal, shippingFee), packagingFee);
  ```
  下面两行 `subtract` 折扣、积分抵扣不用动。这个方法是纯计算，不涉及跨模块调用，只改这一行。
- **验收**: `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubAdditionalBehaviorTest#pub104_orderTotalShouldIncludeShipping test`
  → 绿。`calculate(100.00, 8.00, 2.00, 0, 0)` 应返回 `110.00`（不是 `102.00`）。

---

### ORD-B2 | 批量下单共用一个事务，一条失败整批回滚

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/BatchOrderService.java`
- **现状**: 类声明处（约第20-21行）：
  ```java
  @Service
  @Transactional
  public class BatchOrderService {
  ```
  class 级 `@Transactional` 把整个 `createBatch(...)` 方法（包括循环里对
  `orderService.createOrder(...)` 的多次调用）包在**同一个**数据库事务里——一旦批次里某一笔失败
  抛异常，外层事务被整体标记为 rollback-only，已经"成功"的那几笔在提交时也会被一起回滚掉。
- **期望**: 批量下单里任何一笔失败，不能影响其它笔——每一笔都应该在各自独立的事务里创建/提交。
  依据: design-docs/08 §7（"任何一条失败不得导致整批订单回滚"）。
- **改法**: 
  1. 把类声明上的 `@Transactional` 注解删掉：
     ```java
     @Service
     public class BatchOrderService {
     ```
  2. 删掉现在已经不再使用的 import：`import org.springframework.transaction.annotation.
     Transactional;`。
  `createBatch` 方法体本身不用动——`orderService` 是单独注入的 Spring bean（构造函数注入），
  `orderService.createOrder(...)` 走的是它自己的 `@Transactional` 代理，去掉
  `BatchOrderService` 类上的事务注解之后，循环里每次调用就是各自独立的事务了。
- **验收**: `BatchOrderService.class.getAnnotation(Transactional.class)` 为 `null`；批量下单一笔
  失败（如某个 SKU 库存不足）时，其它成功的几笔仍然落库、可查询到，不会被一起回滚。

---

### ORD-B3 | 批量下单 continueOnError=false 时单行失败即中止整批，应恒续跑

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/BatchOrderService.java`
- **现状**: `createBatch(...)` 循环体 `catch (Exception e)` 块末尾（约第63-67行）：
  ```java
  // If continueOnError is false, rethrow to stop processing
  if (!request.isContinueOnError()) {
      log.error("Batch aborted due to error with continueOnError=false");
      throw new com.ecommerce.common.exception.BusinessException(
              "BATCH_ORDER_FAILED",
              "Batch order processing aborted: " + e.getMessage());
  }
  ```
  当请求体 `continueOnError=false` 时，遇到第一笔失败就直接把异常再抛出去，中止整批处理——后面
  排队的订单请求根本不会被尝试，也拿不到各自的成功/失败结果。
- **期望**: 不管请求体里 `continueOnError` 是 `true` 还是 `false`，批量下单都应该逐条尝试、失败的
  记录失败原因并跳过，继续处理下一条，最终返回每条的明细结果——"任何一条失败不得导致整批订单
  回滚"没有例外。依据: design-docs/08 §7。
- **改法**: 把上面那段"如果 `continueOnError=false` 就重新抛出中止"的 `if` 块整段删掉，只保留
  失败记录逻辑：
  ```java
  } catch (Exception e) {
      log.warn("Batch order failed: externalOrderNo={}, error={}",
              orderRequest.getExternalOrderNo(), e.getMessage());
      results.add(BatchOrderResult.failure(
              orderRequest.getExternalOrderNo(), e.getMessage()));
      failureCount++;
      // design-docs/08 §7: invalid orders are recorded and SKIPPED; a single
      // failure must never abort/roll back the batch. Always continue.
  }
  ```
  即删掉 `if (!request.isContinueOnError()) { ... throw ... }` 那 5 行，`catch` 块前半段记录失败
  结果的代码（`log.warn`/`results.add`/`failureCount++`）保留不变。本卡建议和 ORD-B2 一起做（同
  文件同方法），两条改动的代码位置不重叠（B2 改类注解，B3 改循环体内部），谁先谁后不影响结果。
- **验收**: `continueOnError=false` 且批次里第 1 笔失败、第 2 笔本应成功时，响应里
  `totalCount=2, successCount=1, failureCount=1`，且第 2 笔确实被尝试并成功创建（不是被跳过）。

---

### ORD-B4 | 包装费按商品件数累加，应按订单固定一份

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTotalCalculator.java`
- **现状**: 
  ```java
  private static final BigDecimal PACKAGING_FEE_PER_ITEM = new BigDecimal("1.00");
  ...
  public BigDecimal calculatePackagingFee(int itemCount) {
      if (itemCount <= 0) {
          return BigDecimal.ZERO;
      }
      return MonetaryUtil.multiply(PACKAGING_FEE_PER_ITEM, BigDecimal.valueOf(itemCount));
  }
  ```
  包装费 = 1.00 × 商品件数，件数越多包装费越高。
- **期望**: 包装费是整单固定一份（不随商品件数变化），默认 2.00 元，且要支持运行时配置覆盖。依据:
  design-docs/附录B `order.packaging-fee`（默认 2.00）、design-docs/附录A §6 示例（单行商品订单
  `packagingFee=2.00`）、08 §4。
- **改法**: 
  1. 把常量
     ```java
     private static final BigDecimal PACKAGING_FEE_PER_ITEM = new BigDecimal("1.00");
     ```
     改名改值成
     ```java
     private static final BigDecimal DEFAULT_PACKAGING_FEE = new BigDecimal("2.00");
     ```
  2. 把方法体改成：
     ```java
     public BigDecimal calculatePackagingFee(int itemCount) {
         if (itemCount <= 0) {
             return BigDecimal.ZERO;
         }
         return MonetaryUtil.roundToCent(
                 RuntimeConfigRegistry.getBigDecimal("order.packaging-fee", DEFAULT_PACKAGING_FEE));
     }
     ```
     `itemCount` 参数保留（仍用来判断是否是空订单，空订单包装费为 0），但不再参与金额计算。加
     import `com.ecommerce.common.test.RuntimeConfigRegistry`（如果 ORD-B5 已经加过这行 import，
     这里不用重复加，两条卡片改的是同一个文件里的两个不同方法）。
- **验收**: `calculatePackagingFee(1)`、`calculatePackagingFee(3)`、`calculatePackagingFee(10)` 都
  应该返回同一个值 `2.00`（不再随件数变化）；`calculatePackagingFee(0)` 仍返回 `0`。通过
  `PUT /api/v1/admin/system/configs/order.packaging-fee` 覆盖配置后，新建订单的包装费应跟随新值。

---

### ORD-B5 | 免运费阈值硬编码 199.00，运行时配置覆盖无效

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderTotalCalculator.java`
- **现状**: `calculateShippingFee(BigDecimal itemTotal)`（约第47行开始）：
  ```java
  if (itemTotal.compareTo(FREE_SHIPPING_THRESHOLD) >= 0) {
      return BigDecimal.ZERO;
  }
  ```
  `FREE_SHIPPING_THRESHOLD` 是编译期常量 `199.00`，管理员通过
  `PUT /api/v1/admin/system/configs/order.free-shipping-threshold` 改了运行时配置也不生效。
- **期望**: 免运费阈值默认 199.00，但要能被运行时配置覆盖。依据: design-docs/附录B
  `order.free-shipping-threshold`（默认 199.00）。
- **改法**: 把
  ```java
  if (itemTotal.compareTo(FREE_SHIPPING_THRESHOLD) >= 0) {
      return BigDecimal.ZERO;
  }
  ```
  改成
  ```java
  BigDecimal threshold = RuntimeConfigRegistry.getBigDecimal(
          "order.free-shipping-threshold", FREE_SHIPPING_THRESHOLD);
  if (itemTotal.compareTo(threshold) >= 0) {
      return BigDecimal.ZERO;
  }
  ```
  `FREE_SHIPPING_THRESHOLD` 常量本身不用删，继续当默认值用。加 import
  `com.ecommerce.common.test.RuntimeConfigRegistry`（如果 ORD-B4 已经加过，不用重复加）。
- **验收**: 默认配置下 `calculateShippingFee(199.00)` 仍返回 `0`；把
  `order.free-shipping-threshold` 运行时覆盖成比如 `100.00` 后，`calculateShippingFee(150.00)`
  应该返回 `0`（原本按硬编码 199 阈值应该收运费）。

---

### ORD-B6 | order.max-items 从未被强制校验

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPreconditionChecker.java`
- **现状**: `check(Long userId, int itemCount)` 只校验了 `itemCount <= 0`（订单不能是空的），没有
  上限校验。仓库里唯一沾边的 `OrderValidationUtils`（`code/ecommerce-order/.../util/
  OrderValidationUtils.java`）里虽然有个类似上限校验，但从未被任何地方调用（死代码），且默认值
  写错（100，应为 30）——**不要**去修那个死代码类，本卡直接在 `OrderPreconditionChecker` 里接入
  真正生效的校验。
- **期望**: 单笔订单商品种类数超过上限（默认 30，可运行时配置覆盖）必须被拒绝。依据:
  design-docs/附录B `order.max-items`（默认 30）。
- **改法**: 
  1. 加一个默认值常量：
     ```java
     private static final int DEFAULT_MAX_ITEMS = 30;
     ```
  2. 在 `itemCount <= 0` 判断之后追加：
     ```java
     int maxItems = RuntimeConfigRegistry.getInt("order.max-items", DEFAULT_MAX_ITEMS);
     if (itemCount > maxItems) {
         throw new BusinessException("ORDER_ITEMS_LIMIT_EXCEEDED",
                 "Order item count " + itemCount + " exceeds the limit of " + maxItems);
     }
     ```
  加 import `com.ecommerce.common.test.RuntimeConfigRegistry`。若本文件已经因为 ORD-A2
  （`isFrozen` 校验）被改过，本卡插入位置是"`itemCount<=0` 检查"之后即可，和 `isFrozen` 检查
  （在 `getUserById` 判空之后）不冲突，两段各自独立插入、互不影响。
- **验收**: 创建订单商品种类数（`items` 数组长度）超过 30 时返回 400、
  `code=ORDER_ITEMS_LIMIT_EXCEEDED`；30 种或以下正常创建。运行时把 `order.max-items` 覆盖成更小
  的值后，上限应跟随新值。

---

### ORD-B7 | order.expire-minutes 硬编码 60 分钟，不读配置

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: `createOrder(...)` 里（约第215行）：
  ```java
  order.setExpiresAt(SystemClockService.now().plusMinutes(60));
  ```
  `60` 是硬编码字面量，管理员运行时覆盖 `order.expire-minutes` 配置对下单流程没有任何效果。
- **期望**: 订单过期时长默认 60 分钟，但要能被运行时配置覆盖。依据: design-docs/附录B
  `order.expire-minutes`（默认 60）、design-docs/08 §5。
- **改法**: 
  1. 在类字段区加默认值常量：
     ```java
     private static final int DEFAULT_EXPIRE_MINUTES = 60;
     ```
  2. 把
     ```java
     order.setExpiresAt(SystemClockService.now().plusMinutes(60));
     ```
     改成
     ```java
     int expireMinutes = RuntimeConfigRegistry.getInt("order.expire-minutes", DEFAULT_EXPIRE_MINUTES);
     order.setExpiresAt(SystemClockService.now().plusMinutes(expireMinutes));
     ```
  加 import `com.ecommerce.common.test.RuntimeConfigRegistry`（本文件里只有这一处需要它，和
  ORD-B8 新加的 `LoyaltyCommandService` 字段无关，两条卡片互不影响）。
- **验收**: 默认配置下新建订单的 `expiresAt` 仍是创建时间 +60 分钟；把 `order.expire-minutes`
  运行时覆盖成比如 `1` 分钟后，新建订单的 `expiresAt` 应该是创建时间 +1 分钟，且
  `OrderTimeoutService` 的定时扫描能在配置的时长后正确把它扫描为过期。

---

### ORD-B8 | 积分抵扣只估算，从未真正扣减

- 风险: high · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderService.java`
- **现状**: `createOrder(...)` 的 Step 7（紧跟在 Step 6 `calculateDiscounts` 之后，按注释锚点
  `// ===== Step 7:` 定位；具体行号会因 ORD-A3/ORD-A9 等卡片的插入而漂移）：
  ```java
  BigDecimal pointsDeductionAmount = BigDecimal.ZERO;
  int redeemedPoints = 0;
  if (request.getRedeemPoints() > 0) {
      // Need a preliminary payable amount for points estimation
      BigDecimal prePointsAmount = MonetaryUtil.add(itemTotal, packagingFee);
      prePointsAmount = MonetaryUtil.subtract(prePointsAmount, discountAmount);

      int redeemable = loyaltyQueryService.estimateRedeemPoints(prePointsAmount, userId);
      redeemedPoints = Math.min(request.getRedeemPoints(), redeemable);

      if (redeemedPoints > 0) {
          // 100 points = 1 yuan
          pointsDeductionAmount = MonetaryUtil.multiply(
                  BigDecimal.valueOf(redeemedPoints), new BigDecimal("0.01"));
      }
  }
  ```
  只调用了**只读**的 `loyaltyQueryService.estimateRedeemPoints(...)` 来算"这笔订单最多能抵扣多少
  积分"，`payableAmount` 也确实按这个估算值扣减了——但全程没有调用任何"真正从用户账户扣减这些积分"
  的写操作。`loyalty` 模块已有现成接口
  `LoyaltyCommandService.redeemPoints(Long userId, int points, BigDecimal orderAmount)`
  （`ecommerce-loyalty` 模块，已存在、方法签名不用改，唯一实现类 `LoyaltyPointService` 是单一
  `@Service` bean），只是从来没被 order 模块调用过。后果：同一批积分可以被用在任意多笔订单上反复
  "抵扣"，用户账户积分余额从未真正减少。
- **期望**: 订单创建成功（已经落库）之后，必须真正调用 `loyaltyCommandService.redeemPoints(...)`
  扣减用户积分账户，而不是只在计价时估算。依据: design-docs/12 §3（积分抵扣规则）、
  design-docs/附录A §6（`pointsDeductionAmount` 字段）。
- **改法**: 
  1. 构造函数新增一个参数并保存成字段（`OrderServiceTest.java` 基线用的是 `@InjectMocks`，不是
     显式 `new OrderService(...)`，加参数不影响该测试文件编译；用完整类名，和文件里
     `promotionCalculationService` 字段同样的写法，不用加 import）：
     ```java
     private final com.ecommerce.loyalty.query.LoyaltyCommandService loyaltyCommandService;
     ```
     构造函数参数列表里加一个 `com.ecommerce.loyalty.query.LoyaltyCommandService
     loyaltyCommandService` 形参、赋值给这个字段，加在参数列表末尾即可（Spring 按类型自动装配，
     不看顺序；如果同一个构造函数同时被别的卡片加了别的新参数，都加进去，互不影响）。
  2. 把 Step 7 里 `prePointsAmount` 的计算挪到 `if (request.getRedeemPoints() > 0)` 外面（变成
     无条件执行的局部变量，因为下面第 3 步的 Step 10b 也要用到它）：
     ```java
     BigDecimal pointsDeductionAmount = BigDecimal.ZERO;
     int redeemedPoints = 0;
     BigDecimal prePointsAmount = MonetaryUtil.subtract(
             MonetaryUtil.add(itemTotal, packagingFee), discountAmount);
     if (request.getRedeemPoints() > 0) {
         int redeemable = loyaltyQueryService.estimateRedeemPoints(prePointsAmount, userId);
         redeemedPoints = Math.min(request.getRedeemPoints(), redeemable);

         if (redeemedPoints > 0) {
             pointsDeductionAmount = MonetaryUtil.multiply(
                     BigDecimal.valueOf(redeemedPoints), new BigDecimal("0.01"));
         }
     }
     ```
     即：`prePointsAmount` 声明和赋值提到 `if` 之前、无条件执行；`if` 块内部只保留"算
     `redeemable`/`redeemedPoints`/`pointsDeductionAmount`"这部分，`estimateRedeemPoints` 这次
     已有的只读估算调用**保留不动**，新加的真正扣减调用是下一步、职责不同。
  3. 在订单和订单明细都已经落库（`orderRepository.save(order)`、
     `orderItemRepository.saveAll(orderItems)`）、库存也已预占
     （`inventoryReservationService.reserve(...)`，即 `// ===== Step 10: Reserve inventory =====`
     之后）、发布 `OrderCreatedEvent`（`// ===== Step 11: Publish OrderCreatedEvent =====`）
     **之前**，追加一段：
     ```java
     if (redeemedPoints > 0) {
         try {
             loyaltyCommandService.redeemPoints(userId, redeemedPoints, prePointsAmount);
         } catch (Exception e) {
             log.warn("Failed to redeem {} points for user {} on order {}: {}",
                     redeemedPoints, userId, orderId, e.getMessage());
         }
     }
     ```
     用 try/catch 包住、失败只记警告日志、不向上抛异常——此时订单已经创建成功，积分扣减是订单
     成功之后的收尾步骤，不应该让它失败去反悔一个已经成立的订单（和同一处后面秒杀/优惠券"仅在
     订单持久化成功后消费"的既有模式一致，那部分是 `promotion.md` 的范围，不要跟着改）。
- **验收**: 用户带着 `redeemPoints=1000` 下单成功后，其积分账户可用余额应减少（通过 loyalty 模块
  查询接口能看到），而不是保持不变；同一批积分不能被两笔不同订单各自"抵扣"成功而账户余额只扣
  一次或不扣。
- **勿犯**: 
  1. `redeemPoints(...)` 调用必须放在订单**持久化成功之后**，绝不能放在订单保存之前的计价阶段——
     如果提前调用，一旦后续步骤（比如库存预占）失败导致整个 `createOrder` 事务回滚，`redeemPoints`
     对 loyalty 模块表的写入（loyalty 是独立模块，走的是它自己的方法调用而不是同一个 JPA 持久化
     上下文，不一定会随 order 的事务一起回滚）可能不会被撤销，造成"订单没创建成功、积分却被真的
     扣了"的资金损失级别的不一致。
  2. `redeemPoints` 调用必须包在 try/catch 里、失败不抛出——绝不能因为积分扣减这个收尾步骤失败就
     让整个已经成功的下单请求返回错误。
  3. 不要把 `loyaltyQueryService.estimateRedeemPoints(...)` 这次已有的调用删掉或改动——它是计价
     阶段用来算 `pointsDeductionAmount` 的只读估算，和这里新加的真正扣减调用职责不同，两个都要
     保留。
