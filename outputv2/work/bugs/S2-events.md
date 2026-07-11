# B13+B16 · S2-events — 事件权威定义与监听器网络

> 本卡覆盖 ShopHub 的跨模块事件体系：影子事件类统一迁移到 `ecommerce-common`（§A，批次 B13）+
> 缺失的跨模块监听器补全（§B，批次 B16）。信息源：`outputv2/work/bugs/findings.md`
> （§6.0 影子事件类模式、common #3、Task 13 INT-1/3/5/6、第二轮深审 #18、第三轮深审·跨领域 #5、
> 第三轮深审·事件失败落库）+ 对未修复原始代码逐文件核对 + 与已验证参考实现（153 项修复、24/24
> 黑盒稳定通过、17+ 次独立复跑）逐行比对——各卡片「改法」里给出的目标代码即来自该参考实现。
>
> **执行顺序read me first**：§A 必须整批一次做完，不能只做一半（迁移到一半 = 部分模块还在 import
> 已删除的包 = 编译失败，全部 24 例 ERROR，不是某几个用例失败）。§B 依赖 §A（§B 新监听器全部
> `import com.ecommerce.common.event.*`，§A 不完成这些类不存在）；若因故跳过 §A，§B 也整体跳过。
> `common` 模块任何时候都不得反向依赖 order/payment/logistics/loyalty/review/inventory 等业务模块
> ——本卡新增的 5 个事件类只用 `java.math.BigDecimal`/`java.util.List`/`java.time.LocalDateTime`
> 等 JDK 类型，不 import 任何业务包。
>
> **跨批边界（务必读完再动手）**：本卡多处要改的文件同时也是其他模块批次的改动对象（order/payment/
> logistics/loyalty/review 各有自己的模块批次卡）。原则：本卡只做"事件类型正确 + 监听器注册正确 +
> 事务语义正确 + 失败可观测"这四件事，不做其他业务规则修复（哪怕参考实现里同一个文件、
> 同一个方法紧挨着还有别的改动）。每张卡的"改法"里会明确标出"这一步是我的、那一步不是我的"，
> 以及不是我的那部分如果还没做会不会影响本卡编译/验收。除非明确写出"必须一并处理"（本卡只有一处，
> 见 EVT-A6 第5步——因为不处理会产生比迁移前更糟的双发 bug），否则一律不越界。

---

## §A 事件权威定义迁移（批次 B13；B14 logistics / B15 loyalty / B16 §B 依赖本批建好的事件类）

> **执行时机说明**：按批次表，本批在各模块批（B02–B12）**之后**执行——届时 order/payment 等
> 模块的业务代码已被前面的批次修改过。本节各卡的「现状」描述基于**基线代码**；若打开文件时
> 看到的代码与「现状」细节不完全一致（方法体已被前面批次改动），不要因此判定卡片失效，
> 以**文件当前实际内容**为准执行「改法」的语义：迁移 import 到 `com.ecommerce.common.event`、
> 删除影子事件类、调用点构造实参保持文件里当前写的样子。改法中引用的锚点（方法名/保存调用）
> 以当前代码位置为准。

### EVT-A1 | common 没有任何事件的权威定义：6 个模块各自为政地重复定义同名事件类

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/AbstractDomainEvent.java`（修改）
  2. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/OrderPaidEvent.java`【新增】
  3. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/PaymentSucceededEvent.java`【新增】
  4. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/RefundCompletedEvent.java`【新增】
  5. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/ReviewApprovedEvent.java`【新增】
  6. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/ShipmentDeliveredEvent.java`【新增】
- **现状**：基线 `AbstractDomainEvent` 只有 `eventId`/`occurredAt` 两个通用字段（缺附录D §1 要求的
  `aggregateId`/`traceId`，`getEventType()` 也没有——common 模块发现 #3）。更根本的问题：
  `OrderPaidEvent`/`PaymentSucceededEvent`/`ReviewApprovedEvent` 在**多个模块里各自重复定义**（`order.event.OrderPaidEvent`
  与 `loyalty.event.OrderPaidEvent` 是两个完全不同的 Java 类，只是同名；`payment.event.PaymentSucceededEvent`
  同理；`loyalty.event.ReviewApprovedEvent` 与 `review.event.ReviewApprovedEvent` 也是两个不同的类）。
  Spring 的 `@EventListener`/`@TransactionalEventListener` 按**运行时 Class 对象**精确匹配分发，
  发布方发布的是 A 包的类、监听方监听的是 B 包的同名类，二者不是同一个 `Class`，监听器永远不会被调用。
  各模块的单测之所以一直是绿的，是因为测试里直接 `new` 本地影子事件、手动调用监听器方法，绕开了
  Spring 事件总线本身，掩盖了这个问题。`RefundCompletedEvent` 目前定义在 `payment.event` 包，
  `ShipmentDeliveredEvent` 全仓库不存在任何定义。
- **期望**：附录D 规定的 5 个事件（OrderPaidEvent/PaymentSucceededEvent/ShipmentDeliveredEvent/
  ReviewApprovedEvent/RefundCompletedEvent）各自**只有一个权威 Java 类**，且必须放在
  `ecommerce-common`——这是模块依赖图（02 §2）里唯一一个所有业务模块都会依赖的模块，只有放在这里，
  发布方和监听方才可能引用到同一个编译期类型，不产生新的 Maven 循环依赖（比如 loyalty 不依赖
  order/review，但要监听它们发布的事件，只能通过一个双方都依赖的公共位置）。`AbstractDomainEvent`
  补齐 `aggregateId`/`traceId`/`getEventType()`（附录D §1；common #3）。
- **改法**：

  **1) `AbstractDomainEvent.java`** — 整个文件替换为：

  ```java
  package com.ecommerce.common.event;

  import org.springframework.context.ApplicationEvent;

  import java.time.LocalDateTime;
  import java.util.UUID;

  /**
   * Base class for all domain events in the ShopHub system.
   * Extends Spring's ApplicationEvent for integration with the Spring event bus.
   */
  public abstract class AbstractDomainEvent extends ApplicationEvent {

      private final String eventId;
      private final LocalDateTime occurredAt;
      private final String aggregateId;
      private final String traceId;

      public AbstractDomainEvent(Object source) {
          this(source, null, null);
      }

      protected AbstractDomainEvent(Object source, String aggregateId, String traceId) {
          super(source);
          this.eventId = UUID.randomUUID().toString();
          this.occurredAt = LocalDateTime.now();
          this.aggregateId = aggregateId;
          this.traceId = traceId;
      }

      public String getEventId() {
          return eventId;
      }

      public LocalDateTime getOccurredAt() {
          return occurredAt;
      }

      public String getAggregateId() {
          return aggregateId;
      }

      public String getTraceId() {
          return traceId;
      }

      public String getEventType() {
          return getClass().getSimpleName();
      }
  }
  ```

  注意：单参构造函数 `AbstractDomainEvent(Object source)` **必须保留**（委托给新的 3 参构造），
  因为 `order.event.OrderCreatedEvent`、`order.event.OrderCancelledEvent`、`payment.event.PaymentFailedEvent`
  这三个**不迁移**的模块本地事件类都还在用这个单参构造——删掉或改签名会导致这三个类编译失败。

  **2) `OrderPaidEvent.java`【新增】**，包 `com.ecommerce.common.event`：

  ```java
  package com.ecommerce.common.event;

  import java.math.BigDecimal;
  import java.util.List;

  /**
   * Published by ecommerce-order when an order transitions to PAID.
   * Listened to by ecommerce-logistics, ecommerce-loyalty, and common notification
   * (design-docs/附录D section 2). Lives in common because loyalty (which only
   * depends on ecommerce-common) must be able to listen to it via
   * {@code @EventListener} without a cross-module dependency on ecommerce-order.
   */
  public class OrderPaidEvent extends AbstractDomainEvent {

      private final Long orderId;
      private final Long userId;
      private final BigDecimal paidAmount;
      private final List<OrderItemPayload> items;

      public OrderPaidEvent(Object source, Long orderId, Long userId, BigDecimal paidAmount,
                             List<OrderItemPayload> items, String aggregateId, String traceId) {
          super(source, aggregateId, traceId);
          this.orderId = orderId;
          this.userId = userId;
          this.paidAmount = paidAmount;
          this.items = items;
      }

      public Long getOrderId() { return orderId; }
      public Long getUserId() { return userId; }
      public BigDecimal getPaidAmount() { return paidAmount; }
      public List<OrderItemPayload> getItems() { return items; }

      public static class OrderItemPayload {
          private final Long skuId;
          private final Integer quantity;
          private final BigDecimal price;

          public OrderItemPayload(Long skuId, Integer quantity, BigDecimal price) {
              this.skuId = skuId;
              this.quantity = quantity;
              this.price = price;
          }

          public Long getSkuId() { return skuId; }
          public Integer getQuantity() { return quantity; }
          public BigDecimal getPrice() { return price; }
      }
  }
  ```

  注意字段：只有 `orderId`/`userId`/`paidAmount`/`items` 四个业务字段（附录D §2），**没有 `paymentNo`**
  ——基线 order 和 loyalty 各自的影子类都带了/缺了不同的字段组合，这里以附录D 为准，`paymentNo` 不在
  契约里，不要加。

  **3) `PaymentSucceededEvent.java`【新增】**，包 `com.ecommerce.common.event`：

  ```java
  package com.ecommerce.common.event;

  import java.math.BigDecimal;
  import java.time.LocalDateTime;

  /**
   * Published by payment-service when a payment succeeds.
   * Listeners (order, inventory, logistics, loyalty, notification) must not
   * roll back the payment transaction on failure.
   *
   * <p>Payload per design-docs/附录D §3: paymentNo, orderId, paidAmount, paidAt.
   * Lives in ecommerce-common so the real publisher's class is the one Spring
   * dispatches to, rather than a module-local shadow copy.
   */
  public class PaymentSucceededEvent extends AbstractDomainEvent {

      private final String paymentNo;
      private final Long orderId;
      private final BigDecimal paidAmount;
      private final LocalDateTime paidAt;

      public PaymentSucceededEvent(Object source, String paymentNo, Long orderId,
                                   BigDecimal paidAmount, LocalDateTime paidAt,
                                   String aggregateId, String traceId) {
          super(source, aggregateId, traceId);
          this.paymentNo = paymentNo;
          this.orderId = orderId;
          this.paidAmount = paidAmount;
          this.paidAt = paidAt;
      }

      public String getPaymentNo() {
          return paymentNo;
      }

      public Long getOrderId() {
          return orderId;
      }

      public BigDecimal getPaidAmount() {
          return paidAmount;
      }

      public LocalDateTime getPaidAt() {
          return paidAt;
      }
  }
  ```

  注意：基线 `payment.event.PaymentSucceededEvent` 有一个恒为 `null` 的 `userId` 字段、缺 `paidAt`
  （payment 模块发现 #9）——这里直接按附录D §3 的四个字段（paymentNo/orderId/paidAmount/paidAt）来，
  **没有 `userId`**，不是"传 null"，是这个位置根本不存在。

  **4) `RefundCompletedEvent.java`【新增】**，包 `com.ecommerce.common.event`：

  ```java
  package com.ecommerce.common.event;

  import java.math.BigDecimal;

  /**
   * Published by ecommerce-payment when a refund completes (after warehouse
   * acceptance). Listened to by ecommerce-order (design-docs/02 §5: "更新售后状态"
   * — transition the order to REFUNDED) and notification (handled synchronously
   * within {@code RefundService} itself, not via this event). Lives in common
   * because ecommerce-order cannot depend on ecommerce-payment (payment already
   * depends on order via OrderQueryService — the reverse would be circular), so
   * order could not otherwise reference the publisher's event class from an
   * {@code @EventListener}.
   */
  public class RefundCompletedEvent extends AbstractDomainEvent {

      private final String refundNo;
      private final String paymentNo;
      private final Long orderId;
      private final Long userId;
      private final BigDecimal refundAmount;

      public RefundCompletedEvent(Object source, String refundNo, String paymentNo,
                                  Long orderId, Long userId, BigDecimal refundAmount,
                                  String traceId) {
          super(source, refundNo, traceId);
          this.refundNo = refundNo;
          this.paymentNo = paymentNo;
          this.orderId = orderId;
          this.userId = userId;
          this.refundAmount = refundAmount;
      }

      public String getRefundNo() { return refundNo; }
      public String getPaymentNo() { return paymentNo; }
      public Long getOrderId() { return orderId; }
      public Long getUserId() { return userId; }
      public BigDecimal getRefundAmount() { return refundAmount; }
  }
  ```

  注意构造函数：`super(source, refundNo, traceId)`——`aggregateId` 传的是 `refundNo`，**不是** `orderId`。
  这个类本来就在 `payment.event` 包，第一轮就已经存在（不是全新概念），只是位置不对、没人监听
  （第二轮深审 #18：「该事件类仍留在 payment.event 包（未迁移到 common），导致 order 模块...根本无法引用它写监听器」）。

  **5) `ReviewApprovedEvent.java`【新增】**，包 `com.ecommerce.common.event`：

  ```java
  package com.ecommerce.common.event;

  /**
   * Published by ecommerce-review when a review passes moderation.
   * Listened to by ecommerce-loyalty (design-docs/附录D section 5). Lives in
   * common because loyalty (which only depends on ecommerce-common) must be
   * able to listen to it via {@code @EventListener} without a cross-module
   * dependency on ecommerce-review.
   */
  public class ReviewApprovedEvent extends AbstractDomainEvent {

      private final Long reviewId;
      private final Long userId;
      private final Long orderId;
      private final Long productId;

      public ReviewApprovedEvent(Object source, Long reviewId, Long userId, Long orderId,
                                  Long productId, String aggregateId, String traceId) {
          super(source, aggregateId, traceId);
          this.reviewId = reviewId;
          this.userId = userId;
          this.orderId = orderId;
          this.productId = productId;
      }

      public Long getReviewId() { return reviewId; }
      public Long getUserId() { return userId; }
      public Long getOrderId() { return orderId; }
      public Long getProductId() { return productId; }
  }
  ```

  注意：基线两个影子类（loyalty 和 review 各自的）都**只有 `reviewId`/`userId` 两个字段**——附录D §5
  要求 4 个字段（reviewId/userId/orderId/productId，review 模块发现 #3：「事件缺 orderId/productId」），
  这里必须补全，不是照抄任何一个影子类的字段。

  **6) `ShipmentDeliveredEvent.java`【新增】**，包 `com.ecommerce.common.event`：

  ```java
  package com.ecommerce.common.event;

  import java.time.LocalDateTime;

  /**
   * Published by ecommerce-logistics when a shipment is marked delivered.
   * Listened to by ecommerce-order and ecommerce-loyalty (design-docs/附录D
   * section 4). Lives in common because neither order nor loyalty depends on
   * ecommerce-logistics, so neither could otherwise reference the publisher's
   * event class from an {@code @EventListener}.
   */
  public class ShipmentDeliveredEvent extends AbstractDomainEvent {

      private final Long orderId;
      private final Long shipmentId;
      private final LocalDateTime deliveredAt;

      public ShipmentDeliveredEvent(Object source, Long orderId, Long shipmentId,
                                     LocalDateTime deliveredAt, String aggregateId, String traceId) {
          super(source, aggregateId, traceId);
          this.orderId = orderId;
          this.shipmentId = shipmentId;
          this.deliveredAt = deliveredAt;
      }

      public Long getOrderId() { return orderId; }
      public Long getShipmentId() { return shipmentId; }
      public LocalDateTime getDeliveredAt() { return deliveredAt; }
  }
  ```

  这个类在未修复代码里全仓库不存在（`grep -rn "ShipmentDeliveredEvent" code/` 零命中），是纯新增，
  没有影子类需要删除。**谁来 `publish` 这个事件不是本卡的事**——logistics 模块批次会在
  `ShipmentService.updateStatus(...)` 里发布它（签收时机由该批次的状态机改造决定），本卡只需要把类建好，
  让那边能 `import`。

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-common -am compile` 通过；
  `code/ecommerce-common/src/main/java/com/ecommerce/common/event/` 目录下能看到
  `AbstractDomainEvent.java`（已改）、`DomainEventPublisher.java`（本步骤**不改**，见下方勿犯）、
  `FailedEventRecord.java`/`FailedEventRecordRepository.java`（不改）、加上 5 个新类，共 8 个 `.java`
  主文件；`AbstractDomainEvent` 有 `getAggregateId()`/`getTraceId()`/`getEventType()` 三个新方法。
- **勿犯**：
  - 这一步**不要**碰 `DomainEventPublisher.java`——它的改动（新增 `recordListenerFailure` 方法）是
    §B EVT-B4 的职责，提前加了也不算错，但会打乱"§A 和 §B 分离"的可追溯性；本卡按 §A/§B 的划分走，
    §A 阶段 `DomainEventPublisher.java` 原样不动。
  - 新增的这 5 个类**只能 import JDK 类型**（`java.math.*`/`java.util.*`/`java.time.*`）和本包内的
    `AbstractDomainEvent`——绝不能 import 任何 `com.ecommerce.order.*`/`com.ecommerce.payment.*`/
    `com.ecommerce.logistics.*`/`com.ecommerce.loyalty.*`/`com.ecommerce.review.*`/`com.ecommerce.inventory.*`
    下的类。一旦 common 反向依赖了某个业务模块，Maven reactor 会出现循环依赖（common 是所有业务模块
    的基础依赖），整个工程编译失败，比任何单个测试失败都严重。
  - `ReviewApprovedEvent` 的字段顺序是 `(reviewId, userId, orderId, productId)`——不是
    `(reviewId, userId, productId, orderId)`，两个 `Long` 字段位置容易记反，必须和 参考实现
    完全一致，因为 EVT-A6 里 `ReviewModerationService.java` 会按这个顺序传参。
  - `RefundCompletedEvent` 的 `aggregateId` 用的是 `refundNo` 而不是 `orderId`——不要"想当然"地把
    `orderId` 当聚合根 ID 传进去。

---

### EVT-A2 | order 模块仍在发布/监听自己包内的影子 `OrderPaidEvent`

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/event/OrderPaidEvent.java`【删除】
  2. `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/OrderEventListener.java`
  3. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderLifecycleService.java`
  4. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderPaymentEventHandler.java`
- **现状**：order 模块自定义了 `com.ecommerce.order.event.OrderPaidEvent`（4 字段：orderId/userId/
  paymentNo/paidAmount，无 items/aggregateId/traceId），三处引用——**重要更正（经与 `order.md`
  交叉核实、并对全仓库含参考实现做 `grep "orderLifecycleService\."` 验证）：以下两个类
  在基线和已验证修复版里都**没有任何调用方**，都是死代码，下面不再区分"真发布点/死代码"，两个都
  只为编译安全而改**：
  - `OrderLifecycleService.transition(..., PAID, ...)` 内部的 `publishTransitionEvent` 分支——
    `OrderLifecycleService` 全仓零调用（没有任何地方 `new` 它或把它当依赖注入，`@Service` 注解
    的 bean 无人问津）；
  - `OrderPaymentEventHandler.handlePaymentSuccess(...)`——同样零调用（Task 13 INT-6 已指出）；
  - `OrderEventListener.onOrderPaid(...)`——本模块内部监听，用于给 `Order` 实体打 `paidAt` 时间戳，
    纯内部用途，和跨模块通知无关，这一处是真实生效的（`ApplicationEventPublisher`/Spring 事件总线
    按类型分发，与"谁调用了发布方法"无关）。
  - **真正的生产可达发布点是 `OrderQueryServiceImpl.markAsPaid`**（`OrderPaymentStatusUpdater`
    跨模块接口实现，payment 模块支付成功后唯一会调用的方法）——但它在基线里**完全不发布任何事件**
    （连影子类都没发布过，不是"发布了错的类"，是"压根没发布"）。这不是本卡的范围，见新增的
    **EVT-A7** 卡片（本文件 §A 末尾）。`order.md` 的 ORD-A11 卡片已经在其"勿犯"里明确把这件事
    甩给了本文件，EVT-A7 正是补上这一环。
- **期望**：三处统一改用 `com.ecommerce.common.event.OrderPaidEvent`（附录D §2），影子类删除。
- **改法**：

  **1)** 删除文件 `code/ecommerce-order/src/main/java/com/ecommerce/order/event/OrderPaidEvent.java`。

  **2) `OrderEventListener.java`**：
  - 把 `import com.ecommerce.order.event.OrderPaidEvent;` 改成
    `import com.ecommerce.common.event.OrderPaidEvent;`。
  - `onOrderPaid(OrderPaidEvent event)` 方法体里的日志行，原来是：
    ```java
    log.info("[OrderEventListener] Order paid: orderId={}, userId={}, paymentNo={}, amount={}, eventId={}",
            event.getOrderId(), event.getUserId(), event.getPaymentNo(),
            event.getPaidAmount(), event.getEventId());
    ```
    改成（common 版 `OrderPaidEvent` 没有 `getPaymentNo()`，这个占位符和实参必须删掉，否则编译失败）：
    ```java
    log.info("[OrderEventListener] Order paid: orderId={}, userId={}, amount={}, eventId={}",
            event.getOrderId(), event.getUserId(),
            event.getPaidAmount(), event.getEventId());
    ```
  - 其余方法（含 `onOrderPaidFallback(OrderPaidEvent event)` 的签名）不用改，类型跟着 import 自动切换。
  - 若 `onOrderCreated` 里已有 `LocalNotificationService` 调用（B03/ORD-A16 所加的订单创建通知，
    按批次顺序此刻应已存在），**原样保留，绝不删除**；若还没有（B03 被跳过）也不要在本卡顺手
    补——那是另一个发现（第二轮深审 #19 → ORD-A16）的修复，不属于本卡。本卡只改 import 与
    `onOrderPaid` 的日志行，不增删任何通知逻辑。

  **3) `OrderLifecycleService.java`**：
  - import 块：删除 `import com.ecommerce.order.event.OrderPaidEvent;`，新增：
    ```java
    import com.ecommerce.common.event.OrderPaidEvent;
    import com.ecommerce.order.entity.OrderItem;
    import com.ecommerce.order.repository.OrderItemRepository;
    import java.util.stream.Collectors;
    ```
    （`OrderItemRepository` 基线已存在且已有 `findByOrderId(Long orderId)` 方法，不用新建，只是这个类
    之前没有注入它。）
  - 类字段新增：`private final OrderItemRepository orderItemRepository;`
  - 构造函数新增形参 `OrderItemRepository orderItemRepository`（紧跟在 `orderRepository` 后面），
    构造体里加 `this.orderItemRepository = orderItemRepository;`——构造函数从 6 参数变 7 参数：
    ```java
    public OrderLifecycleService(OrderRepository orderRepository,
                                  OrderItemRepository orderItemRepository,
                                  OrderStateMachine stateMachine,
                                  DomainEventPublisher eventPublisher,
                                  InventoryIntegrationService inventoryIntegration,
                                  OrderEventLogService eventLogService,
                                  OrderService orderService) {
        this.orderRepository = orderRepository;
        this.orderItemRepository = orderItemRepository;
        this.stateMachine = stateMachine;
        this.eventPublisher = eventPublisher;
        this.inventoryIntegration = inventoryIntegration;
        this.eventLogService = eventLogService;
        this.orderService = orderService;
    }
    ```
  - `publishTransitionEvent(...)` 方法的 `case PAID:` 分支，原来是：
    ```java
    case PAID:
        eventPublisher.publish(new OrderPaidEvent(this, order.getId(),
                order.getUserId(), order.getPaymentNo(), order.getPayableAmount()));
        break;
    ```
    改成：
    ```java
    case PAID:
        List<OrderItem> items = orderItemRepository.findByOrderId(order.getId());
        eventPublisher.publish(new OrderPaidEvent(this, order.getId(),
                order.getUserId(), order.getPayableAmount(),
                toEventItems(items), String.valueOf(order.getId()), null));
        break;
    ```
  - 类里新增私有方法（放在 `resetToCreated(...)` 之后、类的最后一个 `}` 之前）：
    ```java
    private List<OrderPaidEvent.OrderItemPayload> toEventItems(List<OrderItem> items) {
        return items.stream()
                .map(item -> new OrderPaidEvent.OrderItemPayload(
                        item.getSkuId(), item.getQuantity(), item.getPrice()))
                .collect(Collectors.toList());
    }
    ```
  - `case CANCELLED:` 分支（发布 `OrderCancelledEvent`）完全不动——那个事件不迁移，还是
    `order.event.OrderCancelledEvent`。

  **4) `OrderPaymentEventHandler.java`**（死代码，但仍需能编译通过）：
  - import 块同样把 `import com.ecommerce.order.event.OrderPaidEvent;` 换成
    `import com.ecommerce.common.event.OrderPaidEvent;`，新增
    `import com.ecommerce.order.entity.OrderItem;`、
    `import com.ecommerce.order.repository.OrderItemRepository;`、
    `import java.util.List;`、`import java.util.stream.Collectors;`（`java.time.LocalDateTime`
    已存在不用动）。
  - 字段新增 `private final OrderItemRepository orderItemRepository;`；构造函数新增形参
    `OrderItemRepository orderItemRepository`（紧跟 `orderRepository` 之后）并赋值。
  - `handlePaymentSuccess(...)` 方法末尾，原来是：
    ```java
    // Publish event
    eventPublisher.publish(new OrderPaidEvent(this, orderId, order.getUserId(),
            paymentNo, order.getPayableAmount()));
    ```
    改成：
    ```java
    // Publish event — the shared common OrderPaidEvent, so logistics and
    // loyalty (neither of which depends on ecommerce-order) can listen.
    List<OrderItem> items = orderItemRepository.findByOrderId(orderId);
    eventPublisher.publish(new OrderPaidEvent(this, orderId, order.getUserId(),
            order.getPayableAmount(), toEventItems(items), String.valueOf(orderId), null));
    ```
  - 类里同样新增私有方法 `toEventItems`（内容同上）。
  - 这个类基线和参考实现里都**没有**对应的单元测试文件（`OrderPaymentEventHandlerTest.java`
    不存在），不用处理测试。

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml compile` 通过；
  `grep -rn "com.ecommerce.order.event.OrderPaidEvent" code/` 零命中（文件已删）；
  `grep -rn "import com.ecommerce.common.event.OrderPaidEvent" code/ecommerce-order` 命中
  `OrderEventListener.java`/`OrderLifecycleService.java`/`OrderPaymentEventHandler.java` 三处。
- **勿犯**：
  - 不要漏改 `OrderPaymentEventHandler.java`——它是死代码，很容易被误判为"没人用，不用管"，但只要它
    还 `import` 被删除的影子类，整个 `ecommerce-order` 模块就编译不过，Maven reactor 直接失败，
    24 个黑盒用例全部因为 `mvn install` 都跑不到而 ERROR（不是断言失败）。
  - 不要在这一步顺手实现 `markAsPaid` 的状态机改造（order 模块发现 #11，`OrderQueryServiceImpl`
    另一个文件的职责）——本卡只保证事件类型正确、编译通过。
  - 不要忘记删日志行里的 `event.getPaymentNo()`——common 版事件没有这个方法，这是编译期报错，
    不是运行时才发现，`mvn compile` 第一步就会挂。

---

### EVT-A3 | payment 模块仍在发布自己包内的影子 `PaymentSucceededEvent`/`RefundCompletedEvent`

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/event/PaymentSucceededEvent.java`【删除】
  2. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/event/RefundCompletedEvent.java`【删除】
  3. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentService.java`
  4. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/RefundService.java`
  5. `code/ecommerce-payment/src/main/java/com/ecommerce/payment/service/PaymentSucceededNotificationListener.java`
     （若存在——B06/PAY-A2 新建的监听器，import 着第 1 项要删除的影子事件类，见改法第 5 步）
- **现状**：两个事件类都定义在 `payment.event` 包下。附录D 要求的监听方（`PaymentSucceededEvent`：
  order/inventory/logistics/loyalty/notification；`RefundCompletedEvent`：order）都不在 payment
  模块内部，跨模块不允许反向依赖 payment，这些模块根本 import 不到这两个类——即使正确 publish，
  也不可能有任何跨模块监听器编译进去监听它们。`RefundCompletedEvent` 目前**全仓库零监听者**
  （第二轮深审 #18）。
- **期望**：两个类迁到 common（EVT-A1 已建好）。`PaymentSucceededEvent` 补齐 `paidAt` 字段、去掉恒为
  `null` 的 `userId`（附录D §3：paymentNo/orderId/paidAmount/paidAt 四字段——payment 模块发现 #9
  一并解决）；`RefundCompletedEvent` 保持 5 个业务字段 + `traceId`。
- **改法**：

  **1)** 删除 `code/ecommerce-payment/src/main/java/com/ecommerce/payment/event/PaymentSucceededEvent.java`

  **2)** 删除 `code/ecommerce-payment/src/main/java/com/ecommerce/payment/event/RefundCompletedEvent.java`

  **3) `PaymentService.java`**：
  - `import com.ecommerce.payment.event.PaymentSucceededEvent;` 改成
    `import com.ecommerce.common.event.PaymentSucceededEvent;`。
  - `confirmPayment(PaymentRecord payment)` 方法内构造事件的那几行，原来是：
    ```java
    PaymentSucceededEvent event = new PaymentSucceededEvent(
            this, payment.getPaymentNo(), payment.getOrderId(),
            null, payment.getPaidAmount());
    eventPublisher.publish(event);
    ```
    改成：
    ```java
    PaymentSucceededEvent event = new PaymentSucceededEvent(
            this, payment.getPaymentNo(), payment.getOrderId(),
            payment.getPaidAmount(), payment.getPaidAt(),
            payment.getPaymentNo(), null);
    eventPublisher.publish(event);
    ```
    `payment.getPaidAt()` 基线已经能读到有效值——`PaymentRecord` 实体本来就有 `paidAt` 字段，调用
    `confirmPayment` 之前 `PaymentCallbackService` 已经 `payment.setPaidAt(LocalDateTime.now())`，
    不需要新增任何字段。第 6 个参数 `payment.getPaymentNo()` 是 `aggregateId`，第 7 个 `null` 是
    `traceId`。
  - **不属于本卡的部分（不要动）**：参考实现里这个类的 `confirmPayment` 方法已经被 payment
    模块批次整体精简（去掉了 `createLogistics`/`earnPoints`/`sendNotifications` 三个同步私有方法，
    以及 `queryOrderDirectly` 里的 `JdbcTemplate` 直查订单表逻辑，只剩发布事件这一行）——那是
    payment 模块批次（对应 findings.md payment #8："支付确认事务同步执行物流/积分/通知"、
    第二轮深审 #3："`queryOrderDirectly` 用 `JdbcTemplate` 直接查 `orders` 表"）的职责。本卡只改上面
    这一处事件构造调用；如果 payment 模块批次还没执行，这三个同步方法和 `JdbcTemplate` 查询原样留着
    不影响本卡编译，也不影响本卡验收（等 payment 模块批次执行时会被整体替换）。

  **4) `RefundService.java`**：
  - `import com.ecommerce.payment.event.RefundCompletedEvent;` 改成
    `import com.ecommerce.common.event.RefundCompletedEvent;`。
  - `processRefund(RefundRecord refund)` 方法内构造事件的那几行，原来是：
    ```java
    RefundCompletedEvent event = new RefundCompletedEvent(
            this, refund.getRefundNo(), refund.getPaymentNo(),
            refund.getOrderId(), refund.getUserId(), refund.getRefundAmount());
    eventPublisher.publish(event);
    ```
    改成（只在末尾加一个 `null` 作为 `traceId`，其余 6 个参数顺序、取值都不变）：
    ```java
    RefundCompletedEvent event = new RefundCompletedEvent(
            this, refund.getRefundNo(), refund.getPaymentNo(),
            refund.getOrderId(), refund.getUserId(), refund.getRefundAmount(), null);
    eventPublisher.publish(event);
    ```
  - **不属于本卡的部分（不要动）**：参考实现里 `RefundService.java` 还有 `AuditLogService`、
    幂等键 `refundRequestNo`、`ConflictException`（`REFUND_WAITING_WAREHOUSE_ACCEPT`/
    `REFUND_STATUS_INVALID`）、退款 `orderId` 改取自 `PaymentRecord` 而非客户端请求体等改动——都是
    payment 模块批次（payment #3/#10、第二轮深审 #7/#8、第三轮深审·模块内 #8 等）的职责，不属于本卡。

  **5) `PaymentSucceededNotificationListener.java`（若存在——B06/PAY-A2 新建）**：
  - 该监听器由 B06/PAY-A2 新建，import 按新建当时文件里的事件类型写。若它 import 的是
    `com.ecommerce.payment.event.PaymentSucceededEvent`（本卡第 1 步删除的影子类），不切换则整个
    payment 模块编译不过：把该 import 切到 `com.ecommerce.common.event.PaymentSucceededEvent`，
    方法体不变（两版事件都有 `getPaymentNo()`/`getPaidAmount()`，`onPaymentSucceeded` 的取值代码
    原样可用）。若它已 import common 包的版本则无需改动；若该文件不存在（B06 被跳过）则无此步。

- **验收**：编译通过；`grep -rn "com.ecommerce.payment.event.PaymentSucceededEvent\|com.ecommerce.payment.event.RefundCompletedEvent" code/`
  零命中（文件已删且无处再 import 旧包路径）。
- **勿犯**：
  - 不要在这一步给 `PaymentService`/`RefundService` 做额外的业务重构——本卡唯一目标是"事件类型正确
    + 编译通过"，多改一行都可能和 payment 模块批次的改动在同一段代码上产生冲突，两批谁后执行谁的
    版本才是终态，容易在批次之间出现难以排查的中间态。
  - `PaymentSucceededEvent` 新构造函数是 **7 参**而不是原来的 5 参，`userId` 参数被彻底去掉（不是
    传 `null` 占位，是这个位置根本不存在了）——数参数位置，不要对着旧签名硬套导致参数顺序错位
    （比如把 `paidAt` 传去了 `aggregateId` 的位置，编译能通过但语义全错）。

---

### EVT-A4 | loyalty 监听的是自己包内的影子事件，Spring 从未把真实事件路由过去

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/OrderPaidEvent.java`【删除】
  2. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/ReviewApprovedEvent.java`【删除】
  3. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/OrderPaidEventListener.java`
  4. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/ReviewApprovedEventListener.java`
  5. `code/ecommerce-loyalty/src/test/java/com/ecommerce/loyalty/event/OrderPaidEventListenerTest.java`
  6. `code/ecommerce-loyalty/src/test/java/com/ecommerce/loyalty/event/ReviewApprovedEventListenerTest.java`
- **现状**：loyalty 模块自己定义了 `loyalty.event.OrderPaidEvent`（4 字段，无 items）和
  `loyalty.event.ReviewApprovedEvent`（仅 2 字段：reviewId/userId，缺 orderId/productId），两个
  监听器都用普通 `@EventListener` 监听自己包内的这两个类。order 发布的是它自己的
  `order.event.OrderPaidEvent`，review 发布的是 `review.event.ReviewApprovedEvent`——都是不同的
  Java 类型，Spring 按运行时类型精确分发，监听器永远不会被触发（loyalty 模块发现 #2/#3：
  「支付积分在真实环境从未发放」「评价奖励积分从未真正发放」）。loyalty 自己的单测直接
  `new` 本地影子事件调用监听器方法，绕过事件总线，一直是绿的。另外，这两个监听器目前是普通
  `@EventListener`，和发布方共享同一个事务：一旦积分发放抛异常（比如故障注入场景），会把发布方的
  事务（支付确认 / 评价审核）一起标记为 rollback-only 而报 500（第三轮深审·跨领域 #5）。
- **期望**：两个监听器改为监听 `com.ecommerce.common.event.OrderPaidEvent` /
  `com.ecommerce.common.event.ReviewApprovedEvent`（附录D §2/§5）；本模块两个影子类删除；监听器
  方法改 `@TransactionalEventListener(phase = AFTER_COMMIT)` + 方法级
  `@Transactional(propagation = REQUIRES_NEW)`，失败只记日志、不得影响发布方事务（02 §5、03 §8、
  09 §3）；`OrderPaidEventListener` 因为要和 logistics 模块新增的同名类共存，必须给显式 bean 名
  `@Component("loyaltyOrderPaidEventListener")`（Task 13 INT-1）。
- **改法**：

  **1)** 删除 `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/OrderPaidEvent.java`

  **2)** 删除 `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/ReviewApprovedEvent.java`

  **3) `OrderPaidEventListener.java`** 整个文件替换为（包路径不变，仍是 `com.ecommerce.loyalty.event`；
  `failureRecorder` 字段和上报调用**本步骤先不加**，留给 EVT-B4 统一补，见该卡）：

  ```java
  package com.ecommerce.loyalty.event;

  import com.ecommerce.common.event.OrderPaidEvent;
  import com.ecommerce.loyalty.service.LoyaltyPointService;
  import com.ecommerce.loyalty.service.MemberLevelService;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;
  import org.springframework.transaction.annotation.Propagation;
  import org.springframework.transaction.annotation.Transactional;
  import org.springframework.transaction.event.TransactionPhase;
  import org.springframework.transaction.event.TransactionalEventListener;

  /**
   * Listens for {@link OrderPaidEvent} and awards loyalty points for the order.
   *
   * <p>This is the {@code com.ecommerce.common.event.OrderPaidEvent} published
   * by ecommerce-order after payment confirmation (design-docs/附录D §2).
   * loyalty previously defined and listened to its own module-local shadow of
   * this event, so Spring never routed the real, order-published event here
   * and order-payment points were never actually awarded; that shadow class
   * has been removed and this listener now depends on the shared common type.
   *
   * <p>On order paid:
   * <ol>
   *   <li>Refresh the user's member level against their up-to-date annual
   *       consumption <em>before</em> scoring (design-docs/12 §6.9 item 11),
   *       so this very payment's tier-multiplier reflects any tier crossed by
   *       this same payment.</li>
   *   <li>Calculate points via {@link LoyaltyPointService#calcOrderPoints}</li>
   *   <li>Award points via {@link LoyaltyPointService#earnPoints}</li>
   * </ol>
   *
   * <p>Bean name is qualified with the module ({@code loyaltyOrderPaidEventListener})
   * because ecommerce-logistics also registers a component simple-named
   * {@code OrderPaidEventListener}; both are distinct, per-module reactions to the
   * same event and must both be registered, so an explicit name avoids the
   * {@code ConflictingBeanDefinitionException} that a shared default name would cause.
   */
  @Component("loyaltyOrderPaidEventListener")
  public class OrderPaidEventListener {

      private static final Logger log = LoggerFactory.getLogger(OrderPaidEventListener.class);

      private final LoyaltyPointService loyaltyPointService;
      private final MemberLevelService memberLevelService;

      public OrderPaidEventListener(LoyaltyPointService loyaltyPointService,
                                     MemberLevelService memberLevelService) {
          this.loyaltyPointService = loyaltyPointService;
          this.memberLevelService = memberLevelService;
      }

      // Runs AFTER_COMMIT in its own REQUIRES_NEW transaction, mirroring the
      // inventory/logistics post-payment listeners: awarding points is a
      // non-critical post-payment action (design-docs/02 §3/§5, 03 §8, 09 §3) and
      // must never roll back the payment-confirmation transaction. A plain
      // @EventListener runs inside that transaction, so a points failure (e.g.
      // fault injection) would mark it rollback-only and abort the whole payment.
      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onOrderPaid(OrderPaidEvent event) {
          log.info("Received OrderPaidEvent: orderId={}, userId={}, amount={}",
                  event.getOrderId(), event.getUserId(), event.getPaidAmount());

          try {
              // Track this payment against the user's running annual
              // consumption and re-evaluate their member level before scoring,
              // so calcOrderPoints below uses the correct, current multiplier.
              memberLevelService.recordPaymentAndEvaluate(event.getUserId(), event.getPaidAmount());

              int points = loyaltyPointService.calcOrderPoints(
                      event.getPaidAmount(), event.getUserId(), 1.0);
              if (points > 0) {
                  loyaltyPointService.earnPoints(
                          event.getUserId(), points, "ORDER",
                          event.getOrderId().toString(),
                          "Order payment reward, orderId=" + event.getOrderId());
              }
              log.info("Awarded {} points for orderId={}", points, event.getOrderId());
          } catch (Exception e) {
              log.error("Failed to award points for orderId={}: {}", event.getOrderId(), e.getMessage(), e);
          }
      }
  }
  ```

  **⚠️ 跨批依赖，务必读完再动手**：这个方法调用了 `MemberLevelService.recordPaymentAndEvaluate(Long userId, BigDecimal paidAmount)`。
  基线的 `MemberLevelService` **没有**这个方法（只有 `evaluateAndUpgrade(Long userId)`）——
  `recordPaymentAndEvaluate` 是 loyalty 模块批次为了修复 loyalty 模块发现 #11（「会员等级只在查询
  `/member-level` 时重算，支付时不刷新」）新增的方法，**不属于本卡、也不应该由本卡新增或改写
  `MemberLevelService.java`**（越界会和 loyalty 模块批次冲突）。处理方式：
  - 若执行本卡时 loyalty 模块批次已经跑过、`recordPaymentAndEvaluate` 已存在：按上面的代码原样写，
    直接编译通过。
  - 若执行本卡时该方法还不存在：把上面那一行临时替换为
    `memberLevelService.evaluateAndUpgrade(event.getUserId());`（只刷新等级、不做本次支付金额的年度
    消费累加，语义上略弱于最终态，但不会编译失败，也不会引入错误行为）；等 loyalty 模块批次落地后，
    再把这一行换回 `recordPaymentAndEvaluate(event.getUserId(), event.getPaidAmount())`。**不要**
    在这张卡里顺手往 `MemberLevelService.java` 加这个方法。

  **4) `ReviewApprovedEventListener.java`** 整个文件替换为（`failureRecorder` 同样留给 EVT-B4）：

  ```java
  package com.ecommerce.loyalty.event;

  import com.ecommerce.common.event.ReviewApprovedEvent;
  import com.ecommerce.common.test.RuntimeConfigRegistry;
  import com.ecommerce.loyalty.service.LoyaltyPointService;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;
  import org.springframework.transaction.annotation.Propagation;
  import org.springframework.transaction.annotation.Transactional;
  import org.springframework.transaction.event.TransactionPhase;
  import org.springframework.transaction.event.TransactionalEventListener;

  /**
   * Listens for {@link ReviewApprovedEvent} and awards review reward points.
   *
   * <p>This is the {@code com.ecommerce.common.event.ReviewApprovedEvent}
   * published by ecommerce-review once a review passes moderation
   * (design-docs/附录D §5). loyalty previously defined and listened to its
   * own module-local shadow of this event, so Spring never routed the real,
   * review-published event here and review reward points were never actually
   * awarded; that shadow class has been removed and this listener now depends
   * on the shared common type.
   */
  @Component
  public class ReviewApprovedEventListener {

      private static final Logger log = LoggerFactory.getLogger(ReviewApprovedEventListener.class);

      /**
       * Default review reward points per approved review, used when
       * {@code loyalty.review-reward-points} has no runtime override
       * (design-docs/附录B §1: default 20).
       */
      private static final int REVIEW_REWARD_POINTS = 20;

      private final LoyaltyPointService loyaltyPointService;

      public ReviewApprovedEventListener(LoyaltyPointService loyaltyPointService) {
          this.loyaltyPointService = loyaltyPointService;
      }

      // AFTER_COMMIT + REQUIRES_NEW: review reward points are a non-critical
      // post-approval action and must not roll back the review-approval
      // transaction if awarding fails (design-docs/02 §5, 03 §8).
      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onReviewApproved(ReviewApprovedEvent event) {
          log.info("Received ReviewApprovedEvent: reviewId={}, userId={}, orderId={}, productId={}",
                  event.getReviewId(), event.getUserId(), event.getOrderId(), event.getProductId());

          try {
              int rewardPoints = RuntimeConfigRegistry.getInt(
                      "loyalty.review-reward-points", REVIEW_REWARD_POINTS);
              loyaltyPointService.earnPoints(
                      event.getUserId(), rewardPoints, "REVIEW",
                      event.getReviewId().toString(),
                      "Review reward, reviewId=" + event.getReviewId());
              log.info("Awarded {} review reward points for reviewId={}, userId={}",
                      rewardPoints, event.getReviewId(), event.getUserId());
          } catch (Exception e) {
              log.error("Failed to award review points for reviewId={}: {}",
                      event.getReviewId(), e.getMessage(), e);
          }
      }
  }
  ```

  注意：这个类**没有**显式 bean 名（普通 `@Component`）——review 模块自己的同名监听器在 EVT-A6 里
  被整个删除了，删除之后 loyalty 这个 `ReviewApprovedEventListener` 不再有任何同名类冲突，不需要
  也不应该加限定 bean 名。`RuntimeConfigRegistry` 是 `com.ecommerce.common.test` 包下基线就有的
  测试支撑基础设施（`getInt(String key, int fallback)` 方法基线已存在），这里直接用，**不是**新的
  跨批依赖。

  **5) `OrderPaidEventListenerTest.java`** 整个文件替换为：

  ```java
  package com.ecommerce.loyalty.event;

  import com.ecommerce.common.event.OrderPaidEvent;
  import com.ecommerce.loyalty.service.LoyaltyPointService;
  import com.ecommerce.loyalty.service.MemberLevelService;
  import org.junit.jupiter.api.BeforeEach;
  import org.junit.jupiter.api.Test;
  import org.junit.jupiter.api.extension.ExtendWith;
  import org.mockito.InOrder;
  import org.mockito.Mock;
  import org.mockito.junit.jupiter.MockitoExtension;

  import java.math.BigDecimal;
  import java.util.List;

  import static org.mockito.ArgumentMatchers.any;
  import static org.mockito.ArgumentMatchers.anyInt;
  import static org.mockito.ArgumentMatchers.anyString;
  import static org.mockito.ArgumentMatchers.eq;
  import static org.mockito.Mockito.inOrder;
  import static org.mockito.Mockito.never;
  import static org.mockito.Mockito.verify;
  import static org.mockito.Mockito.when;

  /**
   * Unit tests for {@link OrderPaidEventListener}.
   *
   * <p>The listener must react to {@code com.ecommerce.common.event.OrderPaidEvent}
   * — the class actually published by ecommerce-order — rather than a
   * module-local shadow. A previous version of this test constructed a
   * loyalty-local shadow event and called the listener method directly, which
   * "passed" even though Spring would never have dispatched a real,
   * order-published event to it (design spec §6.9 items 2 and 11).
   */
  @ExtendWith(MockitoExtension.class)
  class OrderPaidEventListenerTest {

      @Mock
      private LoyaltyPointService loyaltyPointService;

      @Mock
      private MemberLevelService memberLevelService;

      private OrderPaidEventListener listener;

      @BeforeEach
      void setUp() {
          listener = new OrderPaidEventListener(loyaltyPointService, memberLevelService);
      }

      private OrderPaidEvent commonEvent(Long orderId, Long userId, BigDecimal paidAmount) {
          return new OrderPaidEvent(new Object(), orderId, userId, paidAmount,
                  List.of(new OrderPaidEvent.OrderItemPayload(10L, 2, new BigDecimal("75.00"))),
                  "order-" + orderId, "trace-" + orderId);
      }

      @Test
      void testEarnPointsOnOrderPaid() {
          Long orderId = 100L;
          Long userId = 200L;
          BigDecimal paidAmount = new BigDecimal("150.00");

          OrderPaidEvent event = commonEvent(orderId, userId, paidAmount);

          when(loyaltyPointService.calcOrderPoints(paidAmount, userId, 1.0))
                  .thenReturn(16500);

          listener.onOrderPaid(event);

          verify(loyaltyPointService).calcOrderPoints(
                  eq(paidAmount), eq(userId), eq(1.0));

          verify(loyaltyPointService).earnPoints(
                  eq(userId), eq(16500), eq("ORDER"),
                  eq(orderId.toString()),
                  eq("Order payment reward, orderId=" + orderId));
      }

      @Test
      void testZeroPoints_doesNotEarnPoints() {
          OrderPaidEvent event = commonEvent(300L, 400L, BigDecimal.ZERO);

          when(loyaltyPointService.calcOrderPoints(BigDecimal.ZERO, 400L, 1.0))
                  .thenReturn(0);

          listener.onOrderPaid(event);

          verify(loyaltyPointService, never()).earnPoints(any(), anyInt(), anyString(), anyString(), anyString());
      }

      /**
       * design spec §6.9 item 11: member level must be refreshed against the
       * user's up-to-date annual consumption BEFORE points are scored for this
       * same payment, so a tier crossed by this payment already applies to it.
       */
      @Test
      void testMemberLevelRefreshedBeforeScoring() {
          Long orderId = 500L;
          Long userId = 600L;
          BigDecimal paidAmount = new BigDecimal("6000.00");

          OrderPaidEvent event = commonEvent(orderId, userId, paidAmount);
          when(loyaltyPointService.calcOrderPoints(paidAmount, userId, 1.0)).thenReturn(100);

          listener.onOrderPaid(event);

          verify(memberLevelService).recordPaymentAndEvaluate(userId, paidAmount);

          InOrder order = inOrder(memberLevelService, loyaltyPointService);
          order.verify(memberLevelService).recordPaymentAndEvaluate(userId, paidAmount);
          order.verify(loyaltyPointService).calcOrderPoints(paidAmount, userId, 1.0);
      }

      @Test
      void testMemberLevelRefreshFailure_doesNotPropagate() {
          Long orderId = 700L;
          Long userId = 800L;
          BigDecimal paidAmount = new BigDecimal("10.00");

          OrderPaidEvent event = commonEvent(orderId, userId, paidAmount);
          org.mockito.Mockito.doThrow(new RuntimeException("boom"))
                  .when(memberLevelService).recordPaymentAndEvaluate(userId, paidAmount);

          org.junit.jupiter.api.Assertions.assertDoesNotThrow(() -> listener.onOrderPaid(event));
      }
  }
  ```

  如果第 3 步暂时用 `evaluateAndUpgrade` 兜底（`MemberLevelService.recordPaymentAndEvaluate` 还不
  存在），这个测试文件里 `testMemberLevelRefreshedBeforeScoring` 和
  `testMemberLevelRefreshFailure_doesNotPropagate` 两个方法会编译失败（找不到 mock 方法）——把这两个
  方法里的 `recordPaymentAndEvaluate(userId, paidAmount)` 同步替换成
  `evaluateAndUpgrade(userId)` 即可临时保持编译通过，等第 3 步换回正式调用时这两个测试方法也一并换回。

  **6) `ReviewApprovedEventListenerTest.java`** 整个文件替换为：

  ```java
  package com.ecommerce.loyalty.event;

  import com.ecommerce.common.event.ReviewApprovedEvent;
  import com.ecommerce.common.test.RuntimeConfigRegistry;
  import com.ecommerce.loyalty.service.LoyaltyPointService;
  import org.junit.jupiter.api.AfterEach;
  import org.junit.jupiter.api.BeforeEach;
  import org.junit.jupiter.api.Test;
  import org.junit.jupiter.api.extension.ExtendWith;
  import org.mockito.Mock;
  import org.mockito.junit.jupiter.MockitoExtension;

  import static org.junit.jupiter.api.Assertions.assertEquals;
  import static org.mockito.ArgumentMatchers.eq;
  import static org.mockito.Mockito.verify;

  /**
   * Unit tests for {@link ReviewApprovedEventListener}.
   *
   * <p>The listener must react to
   * {@code com.ecommerce.common.event.ReviewApprovedEvent} — the class
   * actually published by ecommerce-review — rather than a module-local
   * shadow (design spec §6.9 item 3).
   */
  @ExtendWith(MockitoExtension.class)
  class ReviewApprovedEventListenerTest {

      @Mock
      private LoyaltyPointService loyaltyPointService;

      private ReviewApprovedEventListener listener;

      @BeforeEach
      void setUp() {
          listener = new ReviewApprovedEventListener(loyaltyPointService);
      }

      @AfterEach
      void tearDown() {
          RuntimeConfigRegistry.clear();
      }

      private ReviewApprovedEvent commonEvent(Long reviewId, Long userId) {
          return new ReviewApprovedEvent(new Object(), reviewId, userId, 1234L, 5678L,
                  "review-" + reviewId, "trace-" + reviewId);
      }

      @Test
      void testReviewApproved_awards20Points() {
          Long reviewId = 999L;
          Long userId = 888L;

          ReviewApprovedEvent event = commonEvent(reviewId, userId);

          listener.onReviewApproved(event);

          verify(loyaltyPointService).earnPoints(
                  eq(userId),
                  eq(20),
                  eq("REVIEW"),
                  eq(reviewId.toString()),
                  eq("Review reward, reviewId=" + reviewId));
      }

      @Test
      void testReviewRewardPointsConstant_is20() throws Exception {
          java.lang.reflect.Field field = ReviewApprovedEventListener.class
                  .getDeclaredField("REVIEW_REWARD_POINTS");
          field.setAccessible(true);
          int value = field.getInt(null);
          assertEquals(20, value, "Review reward points constant should be 20");
      }

      @Test
      void testReviewRewardPoints_honorsRuntimeConfigOverride() {
          Long reviewId = 111L;
          Long userId = 222L;
          RuntimeConfigRegistry.put("loyalty.review-reward-points", 50);

          listener.onReviewApproved(commonEvent(reviewId, userId));

          verify(loyaltyPointService).earnPoints(
                  eq(userId), eq(50), eq("REVIEW"),
                  eq(reviewId.toString()),
                  eq("Review reward, reviewId=" + reviewId));
      }
  }
  ```

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-loyalty -am test` 通过；
  容器启动后 `applicationContext.getBean("loyaltyOrderPaidEventListener")` 能取到 bean；
  `grep -rn "com.ecommerce.loyalty.event.OrderPaidEvent\b\|com.ecommerce.loyalty.event.ReviewApprovedEvent\b" code/`
  （限定到影子类本身的包名，不含监听器类）零命中。
- **勿犯**：
  - `@Component("loyaltyOrderPaidEventListener")` 这个显式 bean 名**不能漏**——logistics 模块
    （EVT-A5）也会新建一个简单类名同样叫 `OrderPaidEventListener` 的 `@Component`，两个类如果都用
    默认 bean 名（Spring 默认取简单类名首字母小写，两个都会是 `orderPaidEventListener`），Spring
    容器启动时会抛 `ConflictingBeanDefinitionException`——这不是某个测试断言失败，是**整个
    Spring 上下文起不来**，24 个黑盒用例会全部 ERROR。这是本卡范围内风险最高的单点故障，EVT-A5
    那张卡也会重复这条警告。
  - `onOrderPaid`/`onReviewApproved` 方法上要**同时**叠 `@Transactional(propagation = REQUIRES_NEW)`
    和 `@TransactionalEventListener(phase = AFTER_COMMIT)` 两个注解——少一个都不对：少
    `@TransactionalEventListener` 就还是和发布方同事务（故障注入积分发放失败会连累支付确认事务
    500）；少 `@Transactional(REQUIRES_NEW)` 就是在 AFTER_COMMIT 阶段裸跑、没有存活事务托底写库。
  - 不要把 `MemberLevelService.recordPaymentAndEvaluate` 依赖问题"自己动手"解决掉（比如跑去改
    `MemberLevelService.java` 加这个方法）——按上面第 3 步给的降级方案处理，那个方法的正式实现是
    loyalty 模块批次的职责。

---

### EVT-A5 | logistics 全模块没有任何事件监听器，支付成功后发货单从不自动创建

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/event/OrderPaidEventListener.java`【新增】
  2. `code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/event/OrderPaidEventListenerTest.java`【新增】
- **现状**：logistics 模块整个仓库没有一个 `@EventListener`/`@TransactionalEventListener`
  （logistics 模块发现 #4）。`ShipmentService.createShipment(...)` 方法本身没问题，但没有任何调用方
  触发它——发货单永远不会自动创建，整条 拣货→打面单→出库→签收 链条无从谈起，进而导致
  `OrderQueryServiceImpl.verifyPurchase` 判断"已购买且已收货"时永远等不到订单进入 DELIVERED，
  评价接口被 `REVIEW_PURCHASE_REQUIRED` 一直拦着。
- **期望**：附录D §2 规定 logistics-service 是 `OrderPaidEvent` 的监听方之一；新增监听器，订单支付
  后自动创建发货单（design-docs/11 §1）。因为要在 AFTER_COMMIT 阶段执行写库操作，必须搭配
  `@Transactional(REQUIRES_NEW)`（否则重演 Task 13 INT-3：发货单"看似创建成功"实际从未 flush 到
  数据库，订单永远拿不到发货单）。因为 loyalty 模块（EVT-A4）也有一个同简单类名的
  `OrderPaidEventListener`，必须显式命名 bean（Task 13 INT-1）。
- **改法**：

  **1)** 新增文件 `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/event/OrderPaidEventListener.java`
  （`ecommerce-logistics` 模块目前没有 `event` 包，新建该目录；`failureRecorder` 字段和上报调用
  **本步骤先不加**，留给 EVT-B4 统一补）：

  ```java
  package com.ecommerce.logistics.event;

  import com.ecommerce.common.event.OrderPaidEvent;
  import com.ecommerce.logistics.repository.ShipmentRepository;
  import com.ecommerce.logistics.service.ShipmentService;
  import com.ecommerce.order.query.OrderDto;
  import com.ecommerce.order.query.OrderQueryService;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;
  import org.springframework.transaction.annotation.Propagation;
  import org.springframework.transaction.annotation.Transactional;
  import org.springframework.transaction.event.TransactionPhase;
  import org.springframework.transaction.event.TransactionalEventListener;

  /**
   * Listens for {@link OrderPaidEvent} and auto-creates a shipment for the paid order
   * (design-docs/11 section 1: "订单支付成功后，物流服务通过监听 OrderPaidEvent 创建发货单，
   * 不应由订单服务同步调用" — logistics creates the shipment by listening to the event,
   * not via a synchronous call from the order module).
   *
   * <p>Runs after the triggering transaction commits, so a failure here can never roll
   * back the payment/order-paid transaction (design-docs/02 section 5: non-critical
   * listeners must not affect the transaction that published the event) — this is
   * exercised by PUB-108 via the {@code logistics-create-shipment-failure} fault
   * injection flag, which is why any failure is caught and logged here rather than
   * left to propagate.
   *
   * <p>The freight amount and delivery address are not carried on the event payload
   * (design-docs/附录D specifies {@code {orderId, userId, paidAmount, items}} only) —
   * per design-docs/11 section 4 ("运费最终以订单创建时计算结果为准"), the freight already
   * locked in at order-creation time is reused here via {@link OrderQueryService},
   * rather than recomputed.
   *
   * <p>Bean name is qualified with the module ({@code logisticsOrderPaidEventListener})
   * because ecommerce-loyalty also registers a component simple-named
   * {@code OrderPaidEventListener}; both are distinct, per-module reactions to the
   * same event and must both be registered, so an explicit name avoids the
   * {@code ConflictingBeanDefinitionException} that a shared default name would cause.
   */
  @Component("logisticsOrderPaidEventListener")
  public class OrderPaidEventListener {

      private static final Logger log = LoggerFactory.getLogger(OrderPaidEventListener.class);

      private final ShipmentService shipmentService;
      private final OrderQueryService orderQueryService;
      private final ShipmentRepository shipmentRepository;

      public OrderPaidEventListener(ShipmentService shipmentService,
                                    OrderQueryService orderQueryService,
                                    ShipmentRepository shipmentRepository) {
          this.shipmentService = shipmentService;
          this.orderQueryService = orderQueryService;
          this.shipmentRepository = shipmentRepository;
      }

      // REQUIRES_NEW is essential: this listener fires AFTER_COMMIT of the order-paid
      // transaction, so no live transaction remains bound for writes. Without a fresh
      // transaction, ShipmentService.createShipment's save() would join the already
      // committed transaction and never flush — the shipment would appear "created"
      // (with a null id) but never actually persist, leaving the order with no shipment
      // to pick/ship/deliver. A new transaction here also keeps a shipment-creation
      // failure (e.g. the logistics-create-shipment-failure fault) from affecting the
      // payment transaction, which has already committed.
      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onOrderPaid(OrderPaidEvent event) {
          Long orderId = event.getOrderId();
          try {
              if (shipmentRepository.findByOrderId(orderId).isPresent()) {
                  log.info("Shipment already exists for orderId={}, skipping auto-create", orderId);
                  return;
              }

              OrderDto order = orderQueryService.getOrder(orderId);
              shipmentService.createShipment(orderId, event.getUserId(),
                      order.getShippingFee(), order.getAddressSnapshot());

              log.info("Auto-created shipment for orderId={} on OrderPaidEvent", orderId);
          } catch (Exception e) {
              log.error("Failed to auto-create shipment for orderId={}: {}", orderId, e.getMessage(), e);
          }
      }
  }
  ```

  `ShipmentService.createShipment(Long orderId, Long userId, BigDecimal shippingFee, String addressSnapshot)`
  这个方法签名基线已经存在（`ecommerce-logistics/.../service/ShipmentService.java` 第 68 行附近），
  不需要新建或改签名。`OrderDto.getShippingFee()`/`getAddressSnapshot()` 两个字段基线的 `OrderDto`
  也已经有，`ecommerce-logistics/pom.xml` 基线已经依赖 `ecommerce-order`（模块依赖图 02 §2 payment/
  logistics/loyalty 位于 order 下方），不需要加新的 Maven 依赖。

  **2)** 新增测试文件
  `code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/event/OrderPaidEventListenerTest.java`：

  ```java
  package com.ecommerce.logistics.event;

  import com.ecommerce.common.event.OrderPaidEvent;
  import com.ecommerce.logistics.entity.Shipment;
  import com.ecommerce.logistics.repository.ShipmentRepository;
  import com.ecommerce.logistics.service.ShipmentService;
  import com.ecommerce.order.query.OrderDto;
  import com.ecommerce.order.query.OrderQueryService;
  import org.junit.jupiter.api.Test;
  import org.junit.jupiter.api.extension.ExtendWith;
  import org.mockito.InjectMocks;
  import org.mockito.Mock;
  import org.mockito.junit.jupiter.MockitoExtension;

  import java.math.BigDecimal;
  import java.util.Collections;
  import java.util.Optional;

  import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
  import static org.mockito.ArgumentMatchers.any;
  import static org.mockito.Mockito.never;
  import static org.mockito.Mockito.verify;
  import static org.mockito.Mockito.when;

  /**
   * Unit tests for {@link OrderPaidEventListener}.
   *
   * <p>Proves that paying an order triggers real, auto-created shipment creation
   * via the event (design-docs/11 section 1), that a shipment is never duplicated
   * for the same order, and that a failure here never propagates back out (PUB-108:
   * post-payment logistics failure must not block payment success).
   */
  @ExtendWith(MockitoExtension.class)
  class OrderPaidEventListenerTest {

      @Mock
      private ShipmentService shipmentService;
      @Mock
      private OrderQueryService orderQueryService;
      @Mock
      private ShipmentRepository shipmentRepository;

      @InjectMocks
      private OrderPaidEventListener orderPaidEventListener;

      @Test
      void onOrderPaid_createsShipmentForOrder() {
          Long orderId = 100L;
          Long userId = 200L;

          OrderDto order = new OrderDto();
          order.setOrderId(orderId);
          order.setUserId(userId);
          order.setShippingFee(new BigDecimal("8.00"));
          order.setAddressSnapshot("{\"province\":\"Guangdong\"}");

          when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.empty());
          when(orderQueryService.getOrder(orderId)).thenReturn(order);

          OrderPaidEvent event = new OrderPaidEvent(this, orderId, userId, new BigDecimal("108.00"),
                  Collections.emptyList(), String.valueOf(orderId), null);

          orderPaidEventListener.onOrderPaid(event);

          verify(shipmentService).createShipment(orderId, userId, new BigDecimal("8.00"),
                  "{\"province\":\"Guangdong\"}");
      }

      @Test
      void onOrderPaid_shipmentAlreadyExists_skipsCreation() {
          Long orderId = 101L;
          when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.of(new Shipment()));

          OrderPaidEvent event = new OrderPaidEvent(this, orderId, 200L, BigDecimal.TEN,
                  Collections.emptyList(), String.valueOf(orderId), null);

          orderPaidEventListener.onOrderPaid(event);

          verify(shipmentService, never()).createShipment(any(), any(), any(), any());
          verify(orderQueryService, never()).getOrder(any());
      }

      @Test
      void onOrderPaid_shipmentCreationFails_doesNotPropagate() {
          Long orderId = 102L;
          when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.empty());
          when(orderQueryService.getOrder(orderId)).thenThrow(new RuntimeException("boom"));

          OrderPaidEvent event = new OrderPaidEvent(this, orderId, 200L, BigDecimal.TEN,
                  Collections.emptyList(), String.valueOf(orderId), null);

          // Per PUB-108, a failed post-payment action must never bubble back up
          // and threaten the transaction that published the event.
          assertDoesNotThrow(() -> orderPaidEventListener.onOrderPaid(event));
      }

      @Test
      void onOrderPaid_shipmentServiceThrows_doesNotPropagate() {
          Long orderId = 103L;
          Long userId = 200L;
          OrderDto order = new OrderDto();
          order.setOrderId(orderId);
          order.setUserId(userId);
          order.setShippingFee(BigDecimal.ZERO);
          order.setAddressSnapshot("{}");

          when(shipmentRepository.findByOrderId(orderId)).thenReturn(Optional.empty());
          when(orderQueryService.getOrder(orderId)).thenReturn(order);
          when(shipmentService.createShipment(any(), any(), any(), any()))
                  .thenThrow(new RuntimeException("Fault injected: logistics-create-shipment-failure"));

          OrderPaidEvent event = new OrderPaidEvent(this, orderId, userId, BigDecimal.TEN,
                  Collections.emptyList(), String.valueOf(orderId), null);

          assertDoesNotThrow(() -> orderPaidEventListener.onOrderPaid(event));
      }
  }
  ```

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-logistics -am test` 通过；
  容器启动后 `applicationContext.getBean("logisticsOrderPaidEventListener")` 能取到 bean；支付一笔
  订单后（黑盒场景）能查到对应 `Shipment` 记录。
- **勿犯**：
  - `@Component("logisticsOrderPaidEventListener")` 显式 bean 名不能漏——和 EVT-A4 是同一个风险点
    的两面，两边都要改到，缺一个都会撞 `ConflictingBeanDefinitionException`，24 例全灭。
  - 必须先查 `shipmentRepository.findByOrderId(orderId)` 是否已有发货单再创建——防御性幂等，避免
    重复消费同一事件时重复建单。
  - `createShipment` 的运费和地址参数要从 `orderQueryService.getOrder(orderId)` 拿，不要自己重新
    计算运费——运费在下单时已经算好定死了（下单侧运费计算是另一张卡的事）。
  - 不要监听 `PaymentSucceededEvent`——发货单创建的触发时机是"订单变为已支付"（`OrderPaidEvent`），
    不是"支付成功"（`PaymentSucceededEvent`）这两个事件语义不同、附录D 里声明的监听关系也不同
    （库存扣减才监听 `PaymentSucceededEvent`，见 EVT-B1）。

---

### EVT-A6 | review 发布的是自己包内的影子事件，还有一套从未被真正触发的冗余监听器

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-review/src/main/java/com/ecommerce/review/event/ReviewApprovedEvent.java`【删除】
  2. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewApprovedEventListener.java`【删除】
  3. `code/ecommerce-review/src/test/java/com/ecommerce/review/event/ReviewApprovedEventListenerTest.java`【删除】
  4. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewModerationService.java`
  5. `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
  6. `code/ecommerce-review/src/test/java/com/ecommerce/review/service/ReviewModerationServiceTest.java`
  7. `code/ecommerce-review/src/test/java/com/ecommerce/review/service/ReviewServiceTest.java`
  8. `code/ecommerce-app/src/test/java/testsupport/DuplicateClassNameExcludeFilter.java`（可选清理，非编译必需）
- **现状**：review 模块自己定义 `review.event.ReviewApprovedEvent`（只有 reviewId/userId 两个字段，
  缺 orderId/productId），并且自己又建了一个监听它的 `review.service.ReviewApprovedEventListener`
  （`@Component("reviewReviewApprovedEventListener")`，特意起了限定名字避免和 loyalty 的同名类冲突）
  ——但这个监听器只会打日志 + 调一个私有方法 `awardReviewPoints`，方法体注释写死
  `"In production this would call LoyaltyPointService.earnPoints()"`，从来没真正加过积分，是纯摆设
  死代码。真正应该加分的是 loyalty 模块的监听器，但 loyalty 监听的是它自己那个影子类（EVT-A4 已
  处理），两边都不是同一个类，双重失联。另外，`ReviewService.createReview(...)` 在评价刚提交
  （状态 `PENDING_REVIEW`，还没审核）时就发一次 `ReviewApprovedEvent`，`ReviewModerationService.approve(...)`
  审核通过时又发一次——同一条评价触发两次"审核通过"事件，且第一次发生在真正审核通过之前，语义上是
  错的（review 模块发现 #2/#3/#4）。
- **期望**：附录D §5：`ReviewApprovedEvent` 由 review-service 发布、loyalty-service 监听，字段
  reviewId/userId/orderId/productId 四个都要有，且只应在审核通过（`ReviewModerationService.approve`）
  时发布恰好一次。
- **改法**：

  **1)** 删除 `code/ecommerce-review/src/main/java/com/ecommerce/review/event/ReviewApprovedEvent.java`

  **2)** 删除 `code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewApprovedEventListener.java`
  （整个死代码监听器，连同它的 `@Component("reviewReviewApprovedEventListener")` 一起消失——loyalty
  才是这个事件唯一该有的监听方，review 模块自己不应该有监听器）

  **3)** 删除 `code/ecommerce-review/src/test/java/com/ecommerce/review/event/ReviewApprovedEventListenerTest.java`
  （测的就是上面被删的类）

  **4) `ReviewModerationService.java`**：
  - `import com.ecommerce.review.event.ReviewApprovedEvent;` 改成
    `import com.ecommerce.common.event.ReviewApprovedEvent;`
  - 如果文件顶部还没有，新增 `import java.util.UUID;`（用于生成 `traceId`）
  - `approve(...)` 方法末尾，原来是：
    ```java
    // Publish event for loyalty point award.
    eventPublisher.publish(new ReviewApprovedEvent(this, reviewId, review.getUserId()));
    ```
    改成：
    ```java
    // Publish the shared ReviewApprovedEvent exactly once, only on approval
    // (design-docs/附录D §5; loyalty-service listens for review reward points).
    eventPublisher.publish(new ReviewApprovedEvent(this, reviewId, review.getUserId(),
            review.getOrderId(), review.getProductId(),
            String.valueOf(reviewId), UUID.randomUUID().toString()));
    ```
    `Review` 实体基线已有 `getOrderId()`/`getProductId()`，不用新增字段——评价本来就是对某个订单
    某个商品发起的。

  **5) `ReviewService.java`**（本卡唯一一处"删除发布点"而不是"切换发布点"的例外，务必读完原因）：
  - 删除 `import com.ecommerce.review.event.ReviewApprovedEvent;` 这一行 import。
  - `createReview(...)` 方法里紧跟在 `reviewRepository.save(review)` 之后的这一整行删除：
    ```java
    eventPublisher.publish(new ReviewApprovedEvent(this, saved.getId(), userId));
    ```
  - 如果这个类的 `DomainEventPublisher eventPublisher` 字段删掉这一行发布调用后不再被任何其他地方
    使用，把这个字段、构造函数里对应的形参、以及
    `import com.ecommerce.common.event.DomainEventPublisher;` 一并删除（构造函数参数数量减 1）；
    如果同一个类里 `eventPublisher` 还被别处用到，只删发布这一行，字段保留。
  - **为什么必须删而不是只切 import**：评价刚提交时状态是 `PENDING_REVIEW`，还没被管理员审核，
    此时发"审核通过"事件语义上就是错的；而且如果这一行只是切换 import 而不删除，EVT-A4 完成
    loyalty 迁移之后，这条监听器会真的收到这个事件并加分——变成"提交评价送一次积分 + 审核通过又送
    一次"，双重发放，比迁移前（两边根本没连上、谁都没收到）更糟。这个删除是让"发布点"回归附录D
    定义的正确语义，是完成影子类清理不可分割的一部分，不是本卡在越界改 review 业务规则。

  **6) `ReviewModerationServiceTest.java`**：
  - `import com.ecommerce.review.event.ReviewApprovedEvent;` 改成
    `import com.ecommerce.common.event.ReviewApprovedEvent;`
  - 已有的"approve 发布 ReviewApprovedEvent 恰好一次"断言（类似
    `verify(eventPublisher, times(1)).publish(captor.capture());` 配合
    `ArgumentCaptor<ReviewApprovedEvent>`）类型换掉即可继续通过；如果想验证得更细，可以断言
    `captor.getValue().getOrderId()`/`getProductId()` 等于 review 实体上的对应字段。
  - "reject 从不发布"、"非 PENDING_REVIEW 状态审核抛异常且从不发布"这类
    `verify(eventPublisher, never()).publish(any(ReviewApprovedEvent.class));` 断言同理，类型换掉
    即可，语义不变。

  **7) `ReviewServiceTest.java`**：
  - 如果第 5 步把 `ReviewService` 的 `eventPublisher` 字段整个删了，这个测试类里
    `@Mock private DomainEventPublisher eventPublisher;` 字段和对应的
    `import com.ecommerce.common.event.DomainEventPublisher;` 也要删除——否则 `@InjectMocks` 找不到
    匹配新构造函数参数组合的 mock 集合，测试类初始化会失败。
  - 删除原来那个断言"创建评价会立刻发布 ReviewApprovedEvent"的测试方法（基线里方法名类似
    `testCreateReview_awardsPointsImmediately`，`@DisplayName("createReview: publishes ReviewApprovedEvent immediately after save, before approval")`）
    ——这个测试断言的正是要被修掉的错误行为，必须整个删除，不能留着断言旧行为，否则会和第 5 步的
    代码改动互相打架、测试变红。

  **8)（可选，非编译必需，仅为保持配置整洁）`DuplicateClassNameExcludeFilter.java`**：
  `EXCLUDED_FQNS` 集合里 `"com.ecommerce.review.service.ReviewApprovedEventListener"` 这一行字符串
  字面量现在指向一个已经不存在的类，留着不影响编译（纯字符串比较，扫不到对应类名就是没有任何效果），
  可以顺手删掉这一行让配置和代码保持一致；不删也不算错，不影响任何黑盒用例，不必为此单独起一次改动。

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-review -am test` 通过；
  `grep -rn "com.ecommerce.review.event.ReviewApprovedEvent\|com.ecommerce.review.service.ReviewApprovedEventListener" code/`
  除了可能残留的 `DuplicateClassNameExcludeFilter.java` 字符串（无害）之外零命中；
  `grep -n "eventPublisher.publish" code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewService.java`
  零命中；`grep -n "eventPublisher.publish" code/ecommerce-review/src/main/java/com/ecommerce/review/service/ReviewModerationService.java`
  命中恰好 1 处。
- **勿犯**：
  - 最容易漏的一步就是"只切 `ReviewService.java` 的 import，不删发布调用"——这是本卡里唯一一处
    "删除发布点"而不是"切换发布点 import"的例外，原因见第 5 步的解释，一定要完整读完再动手。
  - 不要把 review 模块自己的 `ReviewApprovedEventListener` 误认为"应该保留、只是切个 import"——它
    是彻头彻尾的死代码影子监听器，唯一正确的监听方是 loyalty，这个类和它的测试必须整个删除，不是
    修改。
  - 删除 `ReviewApprovedEventListener.java` 之后，不要忘记检查 `ReviewService.java`/
    `ReviewModerationService.java` 的 `eventPublisher` 字段构造函数参数数量是否需要同步调整（第 5
    步已说明判断依据），漏改会导致 Spring 找不到匹配构造函数或测试 `@InjectMocks` 失败。

---

### EVT-A7 | markAsPaid（真正的支付确认路径）从未发布 OrderPaidEvent——物流建单、积分入账对真实支付无反应

- 风险: high · 置信度: definite（补充定位卡片：本条不在原始 findings.md 任何一条里单独出现，是核对
  `order.md` ORD-A11 与本文件 EVT-A2 的交叉引用时发现的覆盖缺口——两张卡各自的"勿犯"都提到这件事
  "属于对方的范围"，结果谁都没做。此卡专门补上，避免两张卡互相甩锅导致空缺。）
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`
- **现状**: `markAsPaid(Long orderId, String paymentNo)` 是 `OrderPaymentStatusUpdater` 跨模块接口的
  实现——payment 模块支付成功后**唯一**会调用的方法（`OrderLifecycleService`/`OrderPaymentEventHandler`
  两个文件虽然也构造过影子 `OrderPaidEvent`，但已核实全仓零调用，是死代码，见 EVT-A2 现状说明）。
  `markAsPaid` 方法体只做状态迁移和落库，从未发布任何事件（连影子类都没发布过）。后果：真实支付
  成功后，logistics 从不会自动建发货单，loyalty 从不会给用户加积分——这不是"用错了事件类"，是
  "压根没有发布这一步"，覆盖面比其余几张 EVT 卡更严重。
- **期望**: `markAsPaid` 状态迁移成功、订单落库后，必须发布 `com.ecommerce.common.event.OrderPaidEvent`
  （附录D §2 权威字段：orderId/userId/payableAmount/items/aggregateId/traceId），供 logistics（自动
  建发货单）与 loyalty（积分入账）监听。依据: 附录D §2、02§5（OrderPaidEvent 发布方=order）、
  Task 13 INT-6（本卡与之相关但不是同一处——INT-6 是"支付后库存不扣减"，由 EVT-B1 的
  `PaymentSucceededInventoryListener` 负责监听 `PaymentSucceededEvent`，与本卡发布的
  `OrderPaidEvent` 是两个不同事件、服务不同订阅方，互不替代）。
- **改法**:
  1. import 块新增：
     ```java
     import com.ecommerce.common.event.DomainEventPublisher;
     import com.ecommerce.common.event.OrderPaidEvent;
     import java.util.stream.Collectors;
     ```
     （`com.ecommerce.order.entity.OrderItem` 和 `java.util.List` 基线已经 import，不用重复加。）
  2. 类字段新增 `private final DomainEventPublisher eventPublisher;`。
  3. 构造函数新增形参 `DomainEventPublisher eventPublisher`，**加在你打开文件时看到的当前参数列表
     最后一位**（如果 `order.md` 的 ORD-A11 已经先跑过，构造函数此刻是 4 参数
     `(orderRepository, orderItemRepository, productQueryService, stateMachine)`，本卡加完变 5
     参数；如果 ORD-A11 还没跑，此刻是 3 参数，本卡加完变 4 参数——两种情况都只管"加在最后一位、
     赋值给新字段"，不要因为参数个数和下面示例不一致就怀疑卡片过期）：
     ```java
     this.eventPublisher = eventPublisher;
     ```
  4. `markAsPaid` 方法体末尾——`orderRepository.save(order);` 和后面
     `log.info("Order {} marked as paid, ...", ...);` 这两行**保持原样、不要删除或改动**（不管
     ORD-A11 是否已经把方法开头的状态校验换成了 `stateMachine.validateTransition(...)`，这两行都
     在方法最后、不受影响），在 `log.info(...)` 那一行**之后**追加：
     ```java

     // Publish the shared OrderPaidEvent so logistics (auto-create shipment)
     // and loyalty (accrue points) — both of which only depend on
     // ecommerce-common, never on ecommerce-order — react to the payment.
     List<OrderItem> items = orderItemRepository.findByOrderId(orderId);
     eventPublisher.publish(new OrderPaidEvent(this, orderId, order.getUserId(),
             order.getPayableAmount(), toEventItems(items), String.valueOf(orderId), null));
     ```
  5. 类里新增私有方法（放在类的最后一个 `}` 之前即可，紧邻其他 private 辅助方法）：
     ```java
     private List<OrderPaidEvent.OrderItemPayload> toEventItems(List<OrderItem> items) {
         return items.stream()
                 .map(item -> new OrderPaidEvent.OrderItemPayload(
                         item.getSkuId(), item.getQuantity(), item.getPrice()))
                 .collect(Collectors.toList());
     }
     ```
     如果 EVT-A2 卡片已经在 `OrderLifecycleService.java`/`OrderPaymentEventHandler.java` 里各建过
     一份同名私有方法，那两份和这份是**三个不同类里各自独立的私有方法**，同名不冲突，不要因为
     "似乎已经写过"就跳过这一步——这个类（`OrderQueryServiceImpl`）目前还没有这个方法。
- **验收**: `mvn -s maven-settings.xml -f code/pom.xml compile` 通过；对一笔 CREATED/PAYING 状态的
  真实订单调 `markAsPaid`（或走完整的 `POST /api/v1/payment/pay` 流程），订单变 PAID 后能在
  `GET /api/v1/admin/events/failures` 或物流/积分模块各自的查询接口观察到 logistics 自动建了发货单、
  loyalty 给该用户加了积分（即 `OrderPaidEvent` 确实被消费）；
  `grep -n "eventPublisher.publish" code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderQueryServiceImpl.java`
  命中恰好 1 处。
- **勿犯**:
  1. 只在 `markAsPaid` 里加发布调用——**不要**碰 `markPaymentFailed` 或同文件其他方法。
  2. 不要把发布调用挪到方法开头或状态校验之前——必须在 `orderRepository.save(order)` **之后**
     （订单已真正落库、状态迁移已确定成功）才发布，否则校验失败的半成品状态也会误发事件。
  3. 不要给这个发布调用包 try/catch——`eventPublisher.publish(...)` 是同步的 Spring
     `ApplicationEventPublisher.publishEvent(...)` 调用，本身不抛业务异常；真正的"监听器失败不
     影响主流程"由各监听器自己的 `AFTER_COMMIT + REQUIRES_NEW`（EVT-A4/EVT-A5/EVT-B1/EVT-B2/EVT-B3）
     保证，发布方这一层不需要额外防御。
  4. 不要因为 `OrderQueryServiceImplTest.java` 用的是 `@InjectMocks` 就以为不用管测试文件——加了新
     字段后 Mockito 会自动找同类型 mock 注入，但如果测试类里已经有断言"markAsPaid 不发布任何事件"
     之类的旧行为断言，需要删除或改写，否则会和本卡改动的行为互相矛盾变红（先跑一次测试确认）。

---

## §B 监听器网络补全（批次 B16，依赖 §A，若 §A 被跳过本批连带跳过；B17 review 反过来依赖本批的"订单送达推进"监听器）

> §B 四张卡新增的 6 个监听器（inventory 1、logistics 1〔EVT-A5,已建〕、loyalty 2〔EVT-A4,已建〕、
> order 2）里，EVT-B1/B2/B3 新建剩余 3 个；EVT-B4 是横切整个 6 个监听器的失败落库补丁，必须在
> EVT-A4/EVT-A5/EVT-B1/EVT-B2/EVT-B3 都完成之后执行。

### EVT-B1 | 支付成功后库存从不真正扣减

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/event/PaymentSucceededInventoryListener.java`【新增】
- **现状**：附录D §3 规定 inventory-service 是 `PaymentSucceededEvent` 的监听方之一，但基线里没有
  任何监听者。真正会扣库存的代码是 `OrderPaymentEventHandler.handlePaymentSuccess`（调用
  `InventoryReservationService.deductAfterPayment`），但这个方法是死代码，0 次执行（Task 13
  INT-6）；真实的支付确认路径（`OrderQueryServiceImpl.markAsPaid`）只置订单状态为 PAID、不碰库存。
  `InventoryReservationService.deductAfterPayment(Long orderId)` 这个方法在基线的接口
  （`ecommerce-inventory/.../query/InventoryReservationService.java`）和实现
  （`InventoryReservationServiceImpl`）里都已经存在，只是没有任何调用方触发它。
- **期望**：新增一个监听器，`PaymentSucceededEvent` 一旦发布，就调用已存在的
  `InventoryReservationService.deductAfterPayment(orderId)`——预占转已扣减（onHandStock+reservedStock
  双减）、生成出库单。这个方法本身是幂等的（只处理仍是 `RESERVED` 状态的预占记录），监听器不需要
  自己再做一层幂等判断。
- **改法**：新增文件
  `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/event/PaymentSucceededInventoryListener.java`
  （inventory 模块目前没有 `event` 包，新建该目录；`failureRecorder` 字段和上报调用**本步骤先不加**，
  留给 EVT-B4）：

  ```java
  package com.ecommerce.inventory.event;

  import com.ecommerce.common.event.PaymentSucceededEvent;
  import com.ecommerce.inventory.query.InventoryReservationService;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;
  import org.springframework.transaction.annotation.Propagation;
  import org.springframework.transaction.annotation.Transactional;
  import org.springframework.transaction.event.TransactionPhase;
  import org.springframework.transaction.event.TransactionalEventListener;

  /**
   * Deducts reserved stock once payment succeeds.
   *
   * <p>Order creation only <em>reserves</em> stock; the actual on-hand deduction
   * happens after payment (design-docs/01 §3 "创建订单时只预占库存，不扣减库存。支付成功后扣减库存"、
   * design-docs/06 §3 支付成功后扣减库存). design-docs/附录D §3 lists inventory-service as a
   * {@link PaymentSucceededEvent} listener; previously nothing consumed that event, so
   * paid orders never converted their reservation into a real deduction + outbound order.
   *
   * <p>{@code deductAfterPayment} is idempotent — it only processes still-RESERVED
   * reservations and marks them DEDUCTED — so a retried/duplicated payment callback
   * cannot double-deduct.
   *
   * <p>Runs AFTER_COMMIT in its own (REQUIRES_NEW) transaction: a deduction failure
   * must not roll back the payment (design-docs/02 §5), and the write needs a live
   * transaction to persist.
   */
  @Component
  public class PaymentSucceededInventoryListener {

      private static final Logger log = LoggerFactory.getLogger(PaymentSucceededInventoryListener.class);

      private final InventoryReservationService inventoryReservationService;

      public PaymentSucceededInventoryListener(InventoryReservationService inventoryReservationService) {
          this.inventoryReservationService = inventoryReservationService;
      }

      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onPaymentSucceeded(PaymentSucceededEvent event) {
          Long orderId = event.getOrderId();
          try {
              inventoryReservationService.deductAfterPayment(orderId);
              log.info("Deducted reserved stock for orderId={} on PaymentSucceededEvent", orderId);
          } catch (Exception e) {
              log.error("Failed to deduct stock for orderId={}: {}", orderId, e.getMessage(), e);
          }
      }
  }
  ```

  没有显式 bean 名——目前没有任何其他模块会建一个简单类名同样叫 `PaymentSucceededInventoryListener`
  的类，普通 `@Component` 即可。

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-inventory -am test` 通过；
  一笔订单支付成功后（黑盒场景）能观察到对应 SKU 的 `onHandStock`/`reservedStock` 相应减少。
- **勿犯**：
  - `@Transactional(propagation = REQUIRES_NEW)` 和 `@TransactionalEventListener(phase = AFTER_COMMIT)`
    两个注解必须同时叠加，缺一不可——原因和 EVT-A4/EVT-A5 完全一样。
  - 不要自己重新实现"预占转扣减"的逻辑——`InventoryReservationService.deductAfterPayment(Long orderId)`
    基线已经存在且能用（它本身还有一个独立的、不属于本卡的 bug：扣减后没生成出库单，即 inventory
    模块发现 #3，那是 inventory 模块批次的职责，和监听器是否存在无关，不影响本卡验收）。本卡只负责
    "让这个已有方法被正确触发"，不负责这个方法内部对不对。
  - 不要监听 `OrderPaidEvent`——库存扣减的时机是"支付成功"而不是"订单变为已支付"，这两个事件虽然
    常常前后脚发生，但附录D 里声明的监听关系是不同的事件（发货单创建才监听 `OrderPaidEvent`，见
    EVT-A5）。

---

### EVT-B2 | 发货签收后订单永远停在 PAID，评价被"必须收货"拦死

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/ShipmentDeliveredEventListener.java`【新增】
- **现状**：logistics 签收后会发布 `ShipmentDeliveredEvent`（附录D §4；由 logistics 模块批次在
  `ShipmentService.updateStatus` 里发布，不属于本卡，类本身已经在 EVT-A1 建好），但基线全仓库没有
  任何监听者。`OrderQueryServiceImpl.verifyPurchase` 判断"已购买且已收货"时只认 `DELIVERED`/
  `COMPLETED` 两个状态，订单永远到不了这两个状态，导致评价接口一直报 `REVIEW_PURCHASE_REQUIRED`
  （Task 13 INT-5）。另外，`OrderLogisticsStatusUpdater` 这个端口在系统里是 no-op 实现（黑盒测试
  harness 注册的是一个无限定符的 no-op bean，生产环境不能注册真实实现，否则会撞 Task 13 INT-1
  同款 bean 冲突，详见 findings.md 第二轮"尽调后明确放弃"一节），所以 PICKING/SHIPPED 这两个中间
  状态永远不会被真实写到订单上——收到 `ShipmentDeliveredEvent` 时订单状态实际上通常还是 `PAID`。
- **期望**：新增监听器，收到 `ShipmentDeliveredEvent` 后把订单从当前状态推进到 `DELIVERED`。因为
  中间状态不会被真实写入，需要顺着状态机链式校验 `PAID→PICKING→SHIPPED→DELIVERED`（只校验合法性，
  不落库中间状态，只落库最终的 `DELIVERED`）。已经是 `DELIVERED`/`COMPLETED` 的直接跳过（幂等）。
- **改法**：新增文件
  `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/ShipmentDeliveredEventListener.java`
  （`failureRecorder` 字段和上报调用**本步骤先不加**，留给 EVT-B4）：

  ```java
  package com.ecommerce.order.listener;

  import com.ecommerce.common.event.ShipmentDeliveredEvent;
  import com.ecommerce.order.entity.Order;
  import com.ecommerce.order.entity.OrderStatus;
  import com.ecommerce.order.repository.OrderRepository;
  import com.ecommerce.order.service.OrderService;
  import com.ecommerce.order.service.OrderStateMachine;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;
  import org.springframework.transaction.annotation.Propagation;
  import org.springframework.transaction.annotation.Transactional;
  import org.springframework.transaction.event.TransactionPhase;
  import org.springframework.transaction.event.TransactionalEventListener;

  /**
   * Advances the order to DELIVERED when logistics publishes the shared
   * {@link ShipmentDeliveredEvent} (design-docs/附录D §4: order-service listens to
   * ShipmentDeliveredEvent). This is the authoritative signal that the parcel was
   * received, which {@code OrderQueryService.verifyPurchase} then relies on to allow
   * a product review (design-docs/08 §2 order lifecycle: ... SHIPPED → DELIVERED).
   *
   * <p>The logistics {@code OrderLogisticsStatusUpdater} port is a no-op in the
   * running system, so the intermediate PICKING/SHIPPED statuses are never applied
   * to the order — it is still PAID when the parcel arrives. Like
   * {@code OrderQueryServiceImpl.markAsPaid} chains CREATED→PAYING→PAID, this
   * validates the designed hops up to DELIVERED rather than bypassing the state
   * machine with an ad-hoc jump.
   *
   * <p>Runs AFTER_COMMIT in its own (REQUIRES_NEW) transaction: a failure here must
   * never roll back the logistics delivery (design-docs/02 §5 — non-critical
   * listeners must not affect the publishing transaction), and the status write
   * needs a live transaction to actually persist.
   */
  @Component
  public class ShipmentDeliveredEventListener {

      private static final Logger log = LoggerFactory.getLogger(ShipmentDeliveredEventListener.class);

      private final OrderRepository orderRepository;
      private final OrderStateMachine stateMachine;
      private final OrderService orderService;

      public ShipmentDeliveredEventListener(OrderRepository orderRepository,
                                            OrderStateMachine stateMachine,
                                            OrderService orderService) {
          this.orderRepository = orderRepository;
          this.stateMachine = stateMachine;
          this.orderService = orderService;
      }

      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onShipmentDelivered(ShipmentDeliveredEvent event) {
          Long orderId = event.getOrderId();
          try {
              Order order = orderRepository.findById(orderId).orElse(null);
              if (order == null) {
                  log.warn("ShipmentDeliveredEvent for unknown orderId={}, ignoring", orderId);
                  return;
              }

              OrderStatus from = order.getStatus();
              if (from == OrderStatus.DELIVERED || from == OrderStatus.COMPLETED) {
                  return; // idempotent — delivery already recorded
              }

              // Validate the designed path to DELIVERED. Because the logistics status
              // port is a no-op, the order is normally still PAID here, so chain the
              // hops (PAID→PICKING→SHIPPED→DELIVERED) the state machine defines.
              if (from == OrderStatus.PAID) {
                  stateMachine.validateTransition(OrderStatus.PAID, OrderStatus.PICKING);
                  stateMachine.validateTransition(OrderStatus.PICKING, OrderStatus.SHIPPED);
                  stateMachine.validateTransition(OrderStatus.SHIPPED, OrderStatus.DELIVERED);
              } else {
                  stateMachine.validateTransition(from, OrderStatus.DELIVERED);
              }

              order.setStatus(OrderStatus.DELIVERED);
              orderRepository.save(order);

              orderService.recordEvent(orderId, from, OrderStatus.DELIVERED,
                      "DELIVERED", "LOGISTICS_SYSTEM",
                      "Shipment delivered, shipmentId=" + event.getShipmentId());

              log.info("Order {} marked DELIVERED on ShipmentDeliveredEvent (from {})", orderId, from);
          } catch (Exception e) {
              log.error("Failed to mark order {} delivered: {}", orderId, e.getMessage(), e);
          }
      }
  }
  ```

  `OrderService.recordEvent(Long orderId, OrderStatus from, OrderStatus to, String eventType, String operatorId, String note)`
  这个 6 参方法基线已经存在（`OrderPaymentEventHandler.handlePaymentSuccess` 就在用它），不需要
  新建或改签名。`OrderStateMachine.validateTransition(...)` 同理基线已存在。

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-order -am test` 通过；黑盒场景
  下走完 支付→(物流签收模拟)→ 后，`GET` 订单详情能看到状态变为 `DELIVERED`，评价接口不再报
  `REVIEW_PURCHASE_REQUIRED`。
- **勿犯**：
  - 不要写成"直接从任意状态跳到 DELIVERED"——必须走 `stateMachine.validateTransition(...)` 逐段
    校验。`OrderStateMachine` 里 PAID 的合法后继只有 `PICKING`/`CANCEL_REVIEWING`/`CANCELLED`，
    不包含 `DELIVERED`；如果绕过状态机直接 `order.setStatus(DELIVERED)`，虽然能让评价流程"看起来"
    通过，但破坏了"状态机是唯一权威的状态迁移入口"这个设计前提。
  - 幂等分支（`from == DELIVERED || from == COMPLETED` 直接 `return`）必须放在状态机校验**之前**
    ——`DELIVERED→DELIVERED` 本身在状态机里就不是一条定义的合法迁移，不提前幂等短路会直接抛异常
    （虽然被 catch 吞掉，但会污染日志、且后续接的失败上报会产生大量噪音记录）。

---

### EVT-B3 | 退款完成后订单状态永不变化

- 风险: high · 置信度: definite
- **文件**：
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/RefundCompletedEventListener.java`【新增】
- **现状**：payment 模块退款流程走到 `processRefund`（仓库验收通过后）会发布
  `RefundCompletedEvent`（EVT-A1/EVT-A3 已经把这个类迁到 common），但全仓库没有任何监听者
  （第二轮深审 #18）——订单状态永远不会变成 `REFUNDED`，即使退款已经真的完成。
- **期望**：02 §5"更新售后状态"——新增 order 模块监听器，把订单推进到 `REFUNDED`。
  `OrderStateMachine` 里只定义了 `DELIVERED→REFUNDING→REFUNDED` 这一条路径，不要对非 `DELIVERED`
  （比如还在 PAID/PICKING/SHIPPED 就被退款）的订单臆造一条未定义的迁移，只记日志跳过。
- **改法**：新增文件
  `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/RefundCompletedEventListener.java`
  （`failureRecorder` 字段和上报调用**本步骤先不加**，留给 EVT-B4）：

  ```java
  package com.ecommerce.order.listener;

  import com.ecommerce.common.event.RefundCompletedEvent;
  import com.ecommerce.order.entity.Order;
  import com.ecommerce.order.entity.OrderStatus;
  import com.ecommerce.order.repository.OrderRepository;
  import com.ecommerce.order.service.OrderService;
  import com.ecommerce.order.service.OrderStateMachine;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;
  import org.springframework.transaction.annotation.Propagation;
  import org.springframework.transaction.annotation.Transactional;
  import org.springframework.transaction.event.TransactionPhase;
  import org.springframework.transaction.event.TransactionalEventListener;

  /**
   * Advances the order to REFUNDED when payment publishes the shared
   * {@link RefundCompletedEvent} (design-docs/02 §5: order listens to
   * RefundCompletedEvent to "更新售后状态"). {@code RefundService.applyRefund}
   * does not itself touch order status (a refund can be applied any time after
   * a successful payment), so this listener is the only writer of REFUNDING and
   * REFUNDED — both only defined from DELIVERED in {@link OrderStateMachine}.
   *
   * <p>An order that is refunded before reaching DELIVERED (still PAID/PICKING/
   * SHIPPED) has no defined path to REFUNDED in the state machine; this listener
   * only performs the transition the design defines and logs+skips otherwise,
   * rather than inventing an undocumented one.
   *
   * <p>Runs AFTER_COMMIT in its own (REQUIRES_NEW) transaction, matching every
   * other non-critical cross-module listener in this system (design-docs/02 §5):
   * a failure here must never roll back the refund completion itself.
   */
  @Component
  public class RefundCompletedEventListener {

      private static final Logger log = LoggerFactory.getLogger(RefundCompletedEventListener.class);

      private final OrderRepository orderRepository;
      private final OrderStateMachine stateMachine;
      private final OrderService orderService;

      public RefundCompletedEventListener(OrderRepository orderRepository,
                                           OrderStateMachine stateMachine,
                                           OrderService orderService) {
          this.orderRepository = orderRepository;
          this.stateMachine = stateMachine;
          this.orderService = orderService;
      }

      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onRefundCompleted(RefundCompletedEvent event) {
          Long orderId = event.getOrderId();
          try {
              Order order = orderRepository.findById(orderId).orElse(null);
              if (order == null) {
                  log.warn("RefundCompletedEvent for unknown orderId={}, ignoring", orderId);
                  return;
              }

              OrderStatus from = order.getStatus();
              if (from == OrderStatus.REFUNDED || from == OrderStatus.COMPLETED) {
                  return; // idempotent — refund already recorded
              }
              if (from != OrderStatus.DELIVERED && from != OrderStatus.REFUNDING) {
                  log.warn("Order {} refunded while in status {} — no defined path to REFUNDED, skipping",
                          orderId, from);
                  return;
              }

              if (from == OrderStatus.DELIVERED) {
                  stateMachine.validateTransition(OrderStatus.DELIVERED, OrderStatus.REFUNDING);
              }
              stateMachine.validateTransition(OrderStatus.REFUNDING, OrderStatus.REFUNDED);

              order.setStatus(OrderStatus.REFUNDED);
              orderRepository.save(order);

              orderService.recordEvent(orderId, from, OrderStatus.REFUNDED,
                      "REFUNDED", "PAYMENT_SYSTEM",
                      "Refund completed, refundNo=" + event.getRefundNo());

              log.info("Order {} marked REFUNDED on RefundCompletedEvent (from {})", orderId, from);
          } catch (Exception e) {
              log.error("Failed to mark order {} refunded: {}", orderId, e.getMessage(), e);
          }
      }
  }
  ```

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-order -am test` 通过；黑盒场景
  下一笔已 DELIVERED 的订单走完退款审核+仓库验收后，`GET` 订单详情状态变为 `REFUNDED`。
- **勿犯**：
  - 只有 `from == DELIVERED`（需要先过 `DELIVERED→REFUNDING`）或 `from == REFUNDING`（已经在退款
    中，直接 `REFUNDING→REFUNDED`）两种情况才真正执行迁移；其余状态（`PAID`/`PICKING`/`SHIPPED`/
    `CANCELLED`/…）一律只打 warn 日志、直接 `return`，不要给它们发明一条状态机没定义的迁移路径
    ——`stateMachine.validateTransition(...)` 对未定义的迁移会抛异常，这个异常又被 catch 吞掉，
    表面上"看起来没报错"，但订单状态和退款状态从此不一致，比明确跳过更难排查。
  - 幂等分支（`REFUNDED`/`COMPLETED` 直接 `return`）同样要放在最前面。

---

### EVT-B4 | 6 个跨模块监听器的失败只打日志，从不落表，管理接口永远查不到

- 风险: low · 置信度: definite
- **文件**：
  1. `code/ecommerce-common/src/main/java/com/ecommerce/common/event/DomainEventPublisher.java`
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/event/PaymentSucceededInventoryListener.java`（EVT-B1 新增的文件）
  3. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/event/OrderPaidEventListener.java`（EVT-A5 新增的文件）
  4. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/OrderPaidEventListener.java`（EVT-A4 改造的文件）
  5. `code/ecommerce-loyalty/src/main/java/com/ecommerce/loyalty/event/ReviewApprovedEventListener.java`（EVT-A4 改造的文件）
  6. `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/ShipmentDeliveredEventListener.java`（EVT-B2 新增的文件）
  7. `code/ecommerce-order/src/main/java/com/ecommerce/order/listener/RefundCompletedEventListener.java`（EVT-B3 新增的文件）
- **现状**：`DomainEventPublisher.persistFailure(...)`（私有方法）只在 `publish(...)` 方法自身抛
  同步异常时触发（比如序列化失败），而上面 6 个监听器全部是
  `@TransactionalEventListener(phase = AFTER_COMMIT)`，在 `publish(...)` 方法早已正常返回之后才
  执行——它们内部 catch 住的异常压根没有任何机会走到 `DomainEventPublisher.publish` 的 catch 块。
  这 6 个监听器（EVT-A4×2、EVT-A5×1、EVT-B1×1、EVT-B2×1、EVT-B3×1）目前的 catch 块里只有
  `log.error(...)`，`GET /api/v1/admin/events/failures`（冻结契约端点，见附录A）永远查不到这些
  失败（第三轮深审·事件失败落库）。
- **期望**：03 §8——监听器失败要"保存失败记录到本地事件处理表"。`DomainEventPublisher` 新增一个
  公开方法 `recordListenerFailure(Object event, String source, Throwable ex)`，`REQUIRES_NEW` 独立
  事务落 `FailedEventRecord`、且绝不外抛（记录失败本身不能把已经被监听器吞掉的错误升级成硬错误）；
  6 个监听器的 catch 块通过 `@Autowired(required=false)` 字段注入这个 publisher、null 兜底后调用。
  **明确排除** `order.OrderEventListener`（`onOrderCreated`）和
  `payment.PaymentSucceededNotificationListener` 这两个纯发通知的监听器——它们内部调用的
  `LocalNotificationService.send(...)` 自己就会 catch 发送异常并经 `NotificationRecordService`
  落失败记录（03 §7 第4条：通知组件自己负责"失败记录"），给它们叠一层监听器失败上报既是死代码，
  又会把"通知发送失败"这一类错误错误地归到"事件监听失败"表里，污染管理接口的语义边界。
- **改法**：

  **1) `DomainEventPublisher.java`**：
  - import 块新增：
    ```java
    import org.springframework.transaction.annotation.Propagation;
    import org.springframework.transaction.annotation.Transactional;
    ```
  - 在 `publish(AbstractDomainEvent event)` 方法结束之后、`persistFailure(...)` 私有方法之前，
    插入新方法：
    ```java
    /**
     * Persist a failure raised while a listener processed an event, so it becomes
     * visible via {@code GET /api/v1/admin/events/failures} (design-docs/03 §8).
     * Cross-module listeners deliberately swallow their exceptions (so a non-critical
     * listener failure never rolls back the main business transaction), and
     * AFTER_COMMIT listeners run after {@link #publish} has already returned — so
     * their failures never reach publish()'s own catch. Each such listener reports
     * here explicitly. Runs REQUIRES_NEW so the record commits even when the calling
     * listener's own transaction is being rolled back, and never throws (failing to
     * record must not turn a swallowed listener error into a hard error).
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordListenerFailure(Object event, String source, Throwable ex) {
        try {
            FailedEventRecord record = new FailedEventRecord();
            record.setEventType(event != null ? event.getClass().getSimpleName() : "UnknownEvent");
            String payload = "{}";
            if (event != null) {
                try {
                    payload = objectMapper.writeValueAsString(event);
                } catch (Exception ser) {
                    log.warn("Could not serialize failed event {}: {}",
                            event.getClass().getSimpleName(), ser.getMessage());
                }
            }
            record.setEventPayload(payload);
            record.setErrorMessage("[" + source + "] "
                    + (ex != null ? ex.getMessage() : "unknown error"));
            record.setOccurredAt(LocalDateTime.now());
            record.setRetried(false);
            record.setRetryCount(0);
            failedEventRecordRepository.save(record);
            log.warn("Recorded listener failure: event={}, source={}", record.getEventType(), source);
        } catch (Exception e) {
            log.error("Failed to persist listener failure record (source={}): {}", source, e.getMessage(), e);
        }
    }
    ```
    （`LocalDateTime` 已经在这个文件的 import 里，不用新增。）

  **2)-7) 六个监听器文件**，统一做下面这个模式的两处插入（字段名统一叫 `failureRecorder`，用全限定名
  内联写在字段声明上，不新增 import 行）：

  a) 在类的构造函数注入字段（通常是几行 `private final XxxService xxx;`）之后、构造函数之前，
     插入：
     ```java
     // Reports swallowed listener failures to the local event-failure table
     // (design-docs/03 §8). Field-injected + null-guarded so the direct-construction
     // unit tests keep working without this collaborator; Spring wires it in production.
     @org.springframework.beans.factory.annotation.Autowired(required = false)
     private com.ecommerce.common.event.DomainEventPublisher failureRecorder;
     ```

  b) 在 catch 块里紧跟 `log.error(...)` 那一行之后，插入：
     ```java
     if (failureRecorder != null) {
         failureRecorder.recordListenerFailure(event, "<source>", e);
     }
     ```
     `<source>` 每个文件不同，按下表取值：

     | 文件 | `source` 字符串 |
     |---|---|
     | inventory `PaymentSucceededInventoryListener` | `"PaymentSucceededInventoryListener"` |
     | logistics `OrderPaidEventListener` | `"logistics.OrderPaidEventListener"` |
     | loyalty `OrderPaidEventListener` | `"loyalty.OrderPaidEventListener"` |
     | loyalty `ReviewApprovedEventListener` | `"loyalty.ReviewApprovedEventListener"` |
     | order `ShipmentDeliveredEventListener` | `"order.ShipmentDeliveredEventListener"` |
     | order `RefundCompletedEventListener` | `"order.RefundCompletedEventListener"` |

  举例（inventory `PaymentSucceededInventoryListener.java` 改完后的样子，其余 5 个文件按同一模式、
  换对应 `source` 字符串处理）：
  ```java
  @Component
  public class PaymentSucceededInventoryListener {

      private static final Logger log = LoggerFactory.getLogger(PaymentSucceededInventoryListener.class);

      private final InventoryReservationService inventoryReservationService;

      // Reports swallowed listener failures to the local event-failure table
      // (design-docs/03 §8). Field-injected + null-guarded so the direct-construction
      // unit tests keep working without this collaborator; Spring wires it in production.
      @org.springframework.beans.factory.annotation.Autowired(required = false)
      private com.ecommerce.common.event.DomainEventPublisher failureRecorder;

      public PaymentSucceededInventoryListener(InventoryReservationService inventoryReservationService) {
          this.inventoryReservationService = inventoryReservationService;
      }

      @Transactional(propagation = Propagation.REQUIRES_NEW)
      @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
      public void onPaymentSucceeded(PaymentSucceededEvent event) {
          Long orderId = event.getOrderId();
          try {
              inventoryReservationService.deductAfterPayment(orderId);
              log.info("Deducted reserved stock for orderId={} on PaymentSucceededEvent", orderId);
          } catch (Exception e) {
              log.error("Failed to deduct stock for orderId={}: {}", orderId, e.getMessage(), e);
              if (failureRecorder != null) {
                  failureRecorder.recordListenerFailure(event, "PaymentSucceededInventoryListener", e);
              }
          }
      }
  }
  ```

  字段用 `@Autowired(required=false)` 而不是走构造函数注入，是为了不破坏这 6 个类已有的、用
  `new Xxx(a, b, c)` 或 `@InjectMocks` 直接构造实例的单元测试（EVT-A4/EVT-A5/EVT-B1/EVT-B2/EVT-B3
  给出的测试代码都不会给这个字段赋值，字段保持 `null`，`if (failureRecorder != null)` 分支被跳过，
  "失败不传播"的断言依然成立）；Spring 在生产环境会自动把这个字段注入好，因为 `DomainEventPublisher`
  本身就是一个 `@Component`。**这 6 个监听器现有的测试文件不需要因为这一步而修改**（本卡给出的测试
  内容里没有一处依赖或断言 `failureRecorder` 字段）。

- **验收**：`mvn -s maven-settings.xml -f code/pom.xml test` 通过；`DomainEventPublisherTest.java`
  里若已包含 `recordListenerFailure` 相关用例（`testRecordListenerFailure_persistsWithSourcePrefix`、
  `testRecordListenerFailure_swallowsRepositoryError`）应保持通过（这两个测试属于 common 模块批次
  维护范围，本卡不必新增，若已存在则不要删除或改坏）；人工/黑盒验证：制造一次监听器失败（比如故障
  注入 `logistics-create-shipment-failure`）后，`GET /api/v1/admin/events/failures`（冻结契约端点，
  不要新建）能查到对应记录。
- **勿犯**：
  - 不要给 `order.OrderEventListener.onOrderCreated` 或
    `payment.PaymentSucceededNotificationListener` 加 `failureRecorder`——这两个明确排除，加了是
    无效功，也会让管理接口混入不该出现的记录类别。
  - `recordListenerFailure` 方法本身绝对不能抛出任何异常（内部必须有自己的 try/catch，catch 到就
    `log.error` 了事）——如果这个"上报失败"的方法自己抛了异常，又是在监听器的 catch 块里被调用，
    极端情况下会把一个已经被吞掉的业务异常变成一个新的未捕获异常，违反"监听器失败绝不影响主流程"
    这条贯穿全卡的红线。
  - 6 个文件都要改到，漏一个不会导致编译失败或黑盒断言失败（这是纯增量的可观测性改动，不影响 24
    个公开用例的断言），但会导致该监听器的失败在 `/api/v1/admin/events/failures` 里永远查不到——
    如果隐藏用例里有针对这个端点的断言，漏改的那个监听器对应场景会验收不过。

---

## 附：本卡涉及文件总览（按状态分类，便于执行前后自查）

**新增（10 个主文件 + 1 个测试文件已含在下方"改造"计数中）**：
- `ecommerce-common/.../event/{OrderPaidEvent,PaymentSucceededEvent,RefundCompletedEvent,ReviewApprovedEvent,ShipmentDeliveredEvent}.java`（5 个，EVT-A1）
- `ecommerce-inventory/.../event/PaymentSucceededInventoryListener.java`（EVT-B1）
- `ecommerce-logistics/.../event/OrderPaidEventListener.java` + 同目录测试（EVT-A5）
- `ecommerce-order/.../listener/{ShipmentDeliveredEventListener,RefundCompletedEventListener}.java`（EVT-B2/B3）

**删除（8 个）**：
- `ecommerce-order/.../event/OrderPaidEvent.java`（EVT-A2）
- `ecommerce-payment/.../event/{PaymentSucceededEvent,RefundCompletedEvent}.java`（EVT-A3）
- `ecommerce-loyalty/.../event/{OrderPaidEvent,ReviewApprovedEvent}.java`（EVT-A4）
- `ecommerce-review/.../event/ReviewApprovedEvent.java`、
  `ecommerce-review/.../service/ReviewApprovedEventListener.java`、
  `ecommerce-review/.../test/.../event/ReviewApprovedEventListenerTest.java`（EVT-A6，3 个）

**修改（非新增非删除，约 15 个主/测试文件）**：
`AbstractDomainEvent.java`/`DomainEventPublisher.java`（common）；`OrderEventListener.java`/
`OrderLifecycleService.java`/`OrderPaymentEventHandler.java`（order）；`PaymentService.java`/
`RefundService.java`（payment）；`PaymentSucceededNotificationListener.java`（payment，仅当
B06/PAY-A2 已新建该文件时需切 import，见 EVT-A3 改法第 5 步）；`OrderPaidEventListener.java`/`ReviewApprovedEventListener.java`
及其各自测试（loyalty，4 个）；`ReviewModerationService.java`/`ReviewService.java` 及其各自测试
（review，4 个）；`DuplicateClassNameExcludeFilter.java`（app，可选）。

**明确不迁移（保持模块本地，不要动）**：`order.event.OrderCreatedEvent`、
`order.event.OrderCancelledEvent`、`payment.event.PaymentFailedEvent`。
