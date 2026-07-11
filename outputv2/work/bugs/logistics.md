# B14 · logistics — 拣货-面单-出库链 / 回调 / 运费模板

来源：`work/bugs/findings.md`「logistics 模块（§6.8，共 7 项）」——本文件覆盖其中 **6 项**（LOGI-1..
LOGI-3、LOGI-5..LOGI-7）；第 4 项（发货单靠监听 `OrderPaidEvent` 自动创建）本质是"新增事件监听器 +
跨模块 bean 命名/事务语义"，按裁决路由给 `S2-events.md`，不在本文件重复，见文末《本批未覆盖的
§6.8 条目》。另外补 3 张卡：LOGI-4（Task 13 集成缺陷 `BUG-INT-4`，pick 空指针）、LOGI-8（第三轮深审
·跨领域 #9，出库无发货提醒短信）、LOGI-9（第四轮设计-实现对比 #1，面单承运商硬编码占位符）。

**9 张卡全部只改 `ecommerce-logistics` 模块自身文件**，不改 `ecommerce-order`/`ecommerce-loyalty`——
运费模板接线进下单流程、`ShipmentDeliveredEvent` 在 order/loyalty 侧的监听器，都是明确排除在外的
别批范围（各相关卡的「勿犯」有单独提醒）。

**执行前提**：`work/bugs/README.md` 的批次表把本文件排在 `B13 · S2-events.md §A`（事件权威定义迁移
common + 影子类删除）**之后**执行——LOGI-6 依赖 B13 已经建好的 `com.ecommerce.common.event.
ShipmentDeliveredEvent` 与 `DomainEventPublisher`（含 `AbstractDomainEvent` 的 3 参构造函数）。若
脱离既定批次顺序单独跑本文件，请先确认这两个类已存在（`find code/ecommerce-common -iname
ShipmentDeliveredEvent.java`），否则 LOGI-6 无法编译，按 LOGI-6 卡内说明处理。

**卡片按 LOGI-1 → LOGI-8 顺序设计**：LOGI-3/LOGI-4 同改 `pick()`但改不同行、LOGI-2/LOGI-8 同改
`outbound()`但改不同段，均已确认为不重叠的独立小改；LOGI-6/LOGI-8 各给 `ShipmentService` 构造函数
追加一个参数，"改法"按此顺序描述增量。建议按本文件从上到下的顺序逐卡应用；若确需调换顺序，
按"改法"里"在现有构造函数参数列表末尾追加"的增量描述操作，不要整段替换覆盖别卡已加的参数。

修完本批立即 `bash work/harness/ratchet.sh verify`。

---

### LOGI-1 | 发货单创建后直接进 OUTBOUND，跳过拣货/打面单

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- **现状**: `createShipment()`（基线第 68-101 行）在第 81 行 `shipment.setStatus(ShipmentStatus.OUTBOUND)`
  ——发货单一创建就是"已出库"，直接跳过 `CREATED→PICKING→LABEL_PRINTED` 三步。紧接着第 87-96 行
  还立刻记一条 `"OUTBOUND"` 的 `recordTracking` 并把订单物流状态推成 `"OUTBOUND"`，进一步坐实这个
  错误状态。PUB-107（`pub107_shipmentProcessShouldIncludePickAndLabel`）依赖发货单创建后仍处于可
  拣货状态。
- **期望**: 创建后初始状态为 `CREATED`。依据: `design-docs/11-物流服务设计.md` §2（发货流程：
  支付确认→生成拣货单→拣货→打面单→出库……"不得跳过拣货单和面单步骤直接出库"）、§3（状态表，
  `CREATED` 排第一个）。
- **改法**: 在 `createShipment()` 里：
  1. 第 81 行 `shipment.setStatus(ShipmentStatus.OUTBOUND);` 改为
     `shipment.setStatus(ShipmentStatus.CREATED);`
  2. 删除第 87-96 行整段（`// Record tracking event` 注释、`recordTracking(shipment.getId(),
     "OUTBOUND", ...)` 调用、`// Update order logistics status` 注释、及其后的
     `try { orderLogisticsStatusUpdater.updateLogisticsStatus(orderId, "OUTBOUND"); } catch (...) {...}`
     整个 try/catch）——创建时刚 `CREATED`，既没有"出库"这个事实可记录轨迹，也不该把订单物流状态
     推成 `OUTBOUND`。方法结尾保留原有的 `log.info("Shipment created...")` 和 `return shipment;`。
  最终 `createShipment()` 主体应为：
  ```java
  Shipment shipment = new Shipment();
  shipment.setShipmentNo(generateShipmentNo());
  shipment.setOrderId(orderId);
  shipment.setUserId(userId);
  shipment.setStatus(ShipmentStatus.CREATED);
  shipment.setFreightAmount(freightAmount != null ? freightAmount : BigDecimal.ZERO);
  shipment.setAddressSnapshot(addressSnapshot);

  shipment = shipmentRepository.save(shipment);

  log.info("Shipment created: shipmentId={}, shipmentNo={}, status={}",
          shipment.getId(), shipment.getShipmentNo(), shipment.getStatus());
  return shipment;
  ```
- **验收**: 调用 `createShipment(...)` 后返回的 `Shipment.getStatus() == ShipmentStatus.CREATED`；
  该发货单此时没有任何 `ShipmentTracking` 记录（第一条轨迹要等 `pick()` 才产生）。

---

### LOGI-2 | `outbound()` 不校验前置状态，任意状态都能直接出库

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- **现状**: `outbound(Long shipmentId)`（基线第 223-242 行）查到发货单后第 228 行直接
  `shipment.setStatus(ShipmentStatus.OUTBOUND)`，没有任何前置状态判断——哪怕发货单还停在
  `CREATED`（甚至理论上 `EXCEPTION`），调用管理端出库接口都会"成功"。
- **期望**: 出库前必须是 `LABEL_PRINTED`。依据: `design-docs/11` §2（"扫码出库"排在"打印物流面单"
  之后）、§3。
- **改法**: 在 `Shipment shipment = shipmentRepository.findById(...)...` 之后、
  `shipment.setStatus(ShipmentStatus.OUTBOUND);` 之前插入前置校验：
  ```java
  if (shipment.getStatus() != ShipmentStatus.LABEL_PRINTED) {
      throw new ConflictException(
              "Shipment must be LABEL_PRINTED before outbound, was: " + shipment.getStatus());
  }
  ```
  需要 `import com.ecommerce.common.exception.ConflictException;`（用现成的单参数构造函数
  `ConflictException(String message)`，`code` 自动为 `"CONFLICT"`，基线已存在，不依赖任何其他卡）。
  方法其余部分（`shipmentRepository.save`、`recordTracking`、`orderLogisticsStatusUpdater` 那段
  try/catch、结尾 `log.info`）不动。
- **验收**: 对一个刚 `pick()` 完（状态 `PICKING`，尚未 `printLabel()`）的发货单直接调
  `outbound()` → 抛 `ConflictException`（HTTP 409，`code=CONFLICT`）；只有 `LABEL_PRINTED` 状态下
  调用才会成功变为 `OUTBOUND`。

---

### LOGI-3 | `pick()` 允许从 OUTBOUND 倒退回 PICKING；`printLabel()` 完全没有状态校验

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- **现状**:
  - `pick(Long shipmentId, Long pickerId)` 第 138-143 行的前置判断：
    ```java
    if (shipment.getStatus() != ShipmentStatus.OUTBOUND
            && shipment.getStatus() != ShipmentStatus.CREATED
            && shipment.getStatus() != ShipmentStatus.PICKING) {
        throw new IllegalStateException(
                "Cannot pick shipment in status " + shipment.getStatus());
    }
    ```
    把 `OUTBOUND` 也列为可以"拣货"的合法前置状态——已出库的包裹还能被重新拉回"拣货中"，状态机
    可以倒退。同时用的是 `IllegalStateException`（不在 `com.ecommerce.common.exception` 体系内，
    `GlobalExceptionHandler` 没有专门的 `@ExceptionHandler(IllegalStateException.class)`，只会
    落到兜底的 `handleGeneric(Exception.class)`，返回 500 + `code=INTERNAL_ERROR`——状态冲突这种
    本该 409 的业务语义被误判成"未预期的系统错误"）。
  - `printLabel(Long shipmentId, String carrier)`（基线第 181-216 行）从查到 `shipment` 到直接
    生成面单、`setStatus(ShipmentStatus.LABEL_PRINTED)`，全程**没有一行状态判断**——`CREATED`
    甚至 `DELIVERED` 的发货单都能被打印面单。
- **期望**: 严格 `CREATED → PICKING → LABEL_PRINTED → OUTBOUND`，不得跳跃/倒退。依据:
  `design-docs/11` §2、§3。状态冲突用 409。依据: `design-docs/03` §2（`ConflictException`=409）。
- **改法**:
  1. `pick()` 的前置判断改为只接受 `CREATED`/`PICKING`，并换成 `ConflictException`：
     ```java
     if (shipment.getStatus() != ShipmentStatus.CREATED
             && shipment.getStatus() != ShipmentStatus.PICKING) {
         throw new ConflictException(
                 "Cannot pick shipment in status " + shipment.getStatus());
     }
     ```
     （去掉 `ShipmentStatus.OUTBOUND` 这个分支即可，其余判断逻辑不变；`import` 同 LOGI-2。）
     只改这 5 行判断本身，方法里第 162-163 行 `recordTracking(...)` 那一行**不要动**——那是
     LOGI-4 的范围，两张卡分别改 `pick()` 里不重叠的两处。
  2. `printLabel()` 在 `Shipment shipment = shipmentRepository.findById(shipmentId)
     .orElseThrow(...)` 之后、生成 `labelNo`/`trackingNo` 之前，插入：
     ```java
     if (shipment.getStatus() != ShipmentStatus.PICKING) {
         throw new ConflictException(
                 "Shipment must be PICKING before label can be printed, was: " + shipment.getStatus());
     }
     ```
- **验收**: 对处于 `OUTBOUND` 状态的发货单调 `pick()` → 抛 `ConflictException`（409），不再倒退回
  `PICKING`；对处于 `CREATED`（尚未 `pick()`）的发货单直接调 `printLabel()` → 抛
  `ConflictException`（409）；正常 `CREATED→pick()→printLabel()→outbound()` 顺序调用全部成功。

---

### LOGI-4 | `pick(id, pickerId)` 对 `pickerId` 为 null 时 NPE，整条履约链路被打断（BUG-INT-4）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- **现状**: `pick()` 第 162-163 行：
  ```java
  recordTracking(shipmentId, "PICKING", "Warehouse",
          "Picking started by operator " + pickerId, pickerId.toString());
  ```
  无条件对 `pickerId` 调 `.toString()`。而 `code/ecommerce-logistics/src/main/java/com/ecommerce/
  logistics/controller/AdminLogisticsController.java` 第 46-48 行的 `pick(@PathVariable Long id)`
  端点方法体是 `shipmentService.pick(id, null);`——`pickerId` 恒为 `null`（`POST .../pick` 冻结
  契约里没有请求体承载操作员 ID，`test-cases` 的 `LogisticsFixture#pick` 也确实以 `null` body
  调用）。也就是说**生产环境下这一行必现 NPE**：`AdminLogisticsController.pick(id)` 一调用就
  500，拣货这一步永远无法完成，后续打面单/出库/签收/评价（`REVIEW_PURCHASE_REQUIRED` 要求订单
  到 `DELIVERED`）整条链路一并断掉。`printLabel()`（`label.setCarrier(carrier)`，carrier 直接来自
  controller 传的 `"DEFAULT"` 字符串常量）和 `outbound()`（不涉及任何可能为 null 的操作员参数）
  从设计上就不会遇到这个问题，只有 `pick()` 这一处独有。
- **期望**: `pickerId` 允许为 null（该端点没有承载它的请求体字段），null 时不应抛异常，用
  `"SYSTEM"` 兜底记录，与 `printLabel()`/`outbound()` 里"操作员未知时不解引用、直接传 null 交给
  `recordTracking` 兜底"的既有写法保持一致。**本卡不涉及任何 API 契约字段变更**——`pick` 端点
  本来就没有请求体，不需要、也不允许新增字段去传 pickerId。
- **改法**: 只改第 162-163 行这一处调用，方法其余部分（含 LOGI-3 刚加的前置状态校验）不动：
  ```java
  recordTracking(shipmentId, "PICKING", "Warehouse",
          pickerId != null ? "Picking started by operator " + pickerId : "Picking started",
          pickerId != null ? pickerId.toString() : null);
  ```
  （`recordTracking` 私有方法本身已经对 `operator` 参数做了 `operator != null ? operator :
  "SYSTEM"` 兜底，见方法末尾 `private void recordTracking(...)`，这里不用再改。）
- **验收**: 以 ADMIN token 调 `POST /api/v1/admin/logistics/shipments/{id}/pick`（无请求体，与
  `LogisticsFixture#pick` 一致）→ 200（不再 500）；产生的 `ShipmentTracking` 记录里
  `operator="SYSTEM"`、`description="Picking started"`。

---

### LOGI-5 | 物流回调空实现——不查单、不更新状态、不幂等、不验签

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/LogisticsCallbackService.java`
  2. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/entity/ShipmentTracking.java`
  3. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/repository/ShipmentTrackingRepository.java`
  4. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/repository/ShipmentRepository.java`
  5. （同步测试，避免留红）
     `code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/service/LogisticsCallbackServiceTest.java`
- **现状**: `processCallback(LogisticsCallbackRequest request)`（基线第 33-39 行）整个方法体只有
  一行 `log.info(...)`，`return` 之外什么都不做——不校验 `request.getSignature()`，不按
  `trackingNo` 查发货单，不做幂等去重，也从不调用已经写好但零调用方的 `mapToShipmentStatus(...)`
  或 `ShipmentService.updateStatus(...)`。等价于这个接口收到任何回调都静默丢弃，物流状态永远
  不会因外部回调而改变。`LogisticsCallbackRequest` DTO 本身字段齐全
  （`trackingNo`/`status`/`location`/`description`/`eventTime`/`signature`），缺的完全是
  service 里的业务逻辑。构造函数当前只注入了 `ShipmentRepository`。
- **期望**: 依据 `design-docs/11` §5（`POST /api/v1/logistics/callback` 认证方式=签名）、
  `design-docs/附录A-API接口参考.md` §9（同一行，认证=签名）、`design-docs/03` §3（幂等规范表：
  物流回调幂等键 = `trackingNo+eventTime+status`，"重复请求应返回第一次处理结果，不得重复……"）：
  1. 校验 `signature` 字段，非法则 401。
  2. 按 `(trackingNo, eventTime, status)` 判重，命中则直接返回（不重复处理）。
  3. 按 `trackingNo` 查到对应发货单（面单打印时生成的 `trackingNo`，见 `printLabel()`），查不到
     404。
  4. 把回调 `status` 字符串映射为 `ShipmentStatus`（已有 `mapToShipmentStatus` 私有方法，直接
     复用），调用 `ShipmentService.updateStatus(...)` 真正推进状态。
  5. 落一条带 `trackingNo` 的 `ShipmentTracking` 记录，供下次同一事件的幂等判重使用。

  **签名字面值**：`LogisticsCallbackRequest.signature` 冻结校验值是字符串字面量
  `"valid-signature"`——这不是我方臆造，是黑盒 fixture 的既定行为，见（只读，不要修改）
  `test-cases/src/test/java/com/ecommerce/blackbox/common/fixture/LogisticsFixture.java` 第 112
  行 `body.put("signature", "valid-signature");`。物流回调的签名是**请求体字段**，不是 HTTP
  请求头——不要和支付回调的 `X-Payment-Signature` 请求头模式搞混。
- **改法**:

  **(1) `ShipmentTracking` 实体加 `trackingNo` 字段**（作为幂等判重的第二个维度，`shipmentId`
  之后插入）：
  ```java
  /**
   * Carrier tracking number this event belongs to. Combined with
   * {@code eventTime}/{@code status}, forms the idempotency key for
   * logistics callbacks (design-docs/03 idempotency keys section).
   */
  @Column(name = "tracking_no", length = 128)
  private String trackingNo;

  public String getTrackingNo() {
      return trackingNo;
  }

  public void setTrackingNo(String trackingNo) {
      this.trackingNo = trackingNo;
  }
  ```
  可选：`@Table` 的 `indexes` 数组里加一条
  `@Index(name = "idx_shipment_trackings_tracking_no", columnList = "trackingNo")`（非必需，量小
  也能过，纯优化）。

  **(2) `ShipmentTrackingRepository` 加一个幂等判重方法**：
  ```java
  import java.time.LocalDateTime;

  /**
   * Idempotency check for logistics carrier callbacks: trackingNo + eventTime + status
   * (design-docs/03 idempotency keys section).
   */
  boolean existsByTrackingNoAndEventTimeAndStatus(String trackingNo, LocalDateTime eventTime, String status);
  ```

  **(3) `ShipmentRepository` 加一个按运单号查发货单的方法**（面单打印时 `trackingNo` 写在
  `Shipment` 本体上，见 `printLabel()` 的 `shipment.setTrackingNo(trackingNo)`）：
  ```java
  /**
   * Find a shipment by its carrier tracking number (assigned at label-print time).
   */
  Optional<Shipment> findByTrackingNo(String trackingNo);
  ```

  **(4) `LogisticsCallbackService.java` 整个类改为**（新增 `@Transactional` 类注解、新增两个
  构造参数、新增签名常量、`processCallback` 方法体重写；`mapToShipmentStatus` 私有方法原样保留
  不动）：
  ```java
  package com.ecommerce.logistics.service;

  import com.ecommerce.common.exception.AuthorizationException;
  import com.ecommerce.common.exception.ResourceNotFoundException;
  import com.ecommerce.logistics.dto.LogisticsCallbackRequest;
  import com.ecommerce.logistics.entity.Shipment;
  import com.ecommerce.logistics.entity.ShipmentStatus;
  import com.ecommerce.logistics.entity.ShipmentTracking;
  import com.ecommerce.logistics.repository.ShipmentRepository;
  import com.ecommerce.logistics.repository.ShipmentTrackingRepository;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Service;
  import org.springframework.transaction.annotation.Transactional;

  @Service
  @Transactional
  public class LogisticsCallbackService {

      private static final Logger log = LoggerFactory.getLogger(LogisticsCallbackService.class);

      /** Mock signature accepted for logistics callbacks — mirrors LogisticsFixture#logisticsCallback. */
      private static final String VALID_SIGNATURE = "valid-signature";

      private final ShipmentRepository shipmentRepository;
      private final ShipmentTrackingRepository trackingRepository;
      private final ShipmentService shipmentService;

      public LogisticsCallbackService(ShipmentRepository shipmentRepository,
                                      ShipmentTrackingRepository trackingRepository,
                                      ShipmentService shipmentService) {
          this.shipmentRepository = shipmentRepository;
          this.trackingRepository = trackingRepository;
          this.shipmentService = shipmentService;
      }

      public void processCallback(LogisticsCallbackRequest request) {
          log.info("Received logistics callback: trackingNo={}, status={}, location={}, "
                          + "description={}, eventTime={}",
                  request.getTrackingNo(), request.getStatus(),
                  request.getLocation(), request.getDescription(), request.getEventTime());

          if (!VALID_SIGNATURE.equals(request.getSignature())) {
              throw AuthorizationException.unauthorized("Invalid logistics callback signature");
          }

          if (trackingRepository.existsByTrackingNoAndEventTimeAndStatus(
                  request.getTrackingNo(), request.getEventTime(), request.getStatus())) {
              log.info("Duplicate logistics callback ignored: trackingNo={}, eventTime={}, status={}",
                      request.getTrackingNo(), request.getEventTime(), request.getStatus());
              return;
          }

          Shipment shipment = shipmentRepository.findByTrackingNo(request.getTrackingNo())
                  .orElseThrow(() -> new ResourceNotFoundException("Shipment with trackingNo", request.getTrackingNo()));

          ShipmentStatus newStatus = mapToShipmentStatus(request.getStatus());
          shipmentService.updateStatus(shipment.getId(), newStatus, request.getLocation(), request.getDescription());

          ShipmentTracking tracking = new ShipmentTracking();
          tracking.setShipmentId(shipment.getId());
          tracking.setTrackingNo(request.getTrackingNo());
          tracking.setEventTime(request.getEventTime());
          tracking.setStatus(request.getStatus());
          tracking.setLocation(request.getLocation());
          tracking.setDescription(request.getDescription());
          tracking.setOperator("CARRIER");
          trackingRepository.save(tracking);

          log.info("Logistics callback processed: shipmentId={}, newStatus={}", shipment.getId(), newStatus);
      }

      // mapToShipmentStatus(...) 私有方法原样保留，不用改
  }
  ```

  **(5) 同步改 `LogisticsCallbackServiceTest`**：基线里 `testProcessCallback_processesRequest()`
  用 `verifyNoInteractions(shipmentRepository)` 断言"回调不碰数据库"——这是在给旧 bug 当回归测试，
  改完后必然失败，需要重写为验证新行为（按 trackingNo 查单、幂等生效、签名错误抛
  `AuthorizationException` 等），或至少把这条断言删掉/替换，不要留红（`code/` 下单测不计分但
  也不能留红扰乱自查）。
- **验收**:
  - `signature` 不等于 `"valid-signature"` → 抛 `AuthorizationException`（401，`code=UNAUTHORIZED`）。
  - `trackingNo` 查无对应发货单 → 抛 `ResourceNotFoundException`（404）。
  - 同一个 `(trackingNo, eventTime, status)` 回调两次 → 第二次是 no-op（发货单状态不因第二次调用
    再变化一次，也不会跑到 `shipmentService.updateStatus` 第二遍）。
  - `status="DELIVERED"` 的合法回调 → 通过 `GET /api/v1/logistics/order/{orderId}` 能看到
    `status=DELIVERED`。
- **勿犯**:
  - 不要为了消除"一次回调写两条 `ShipmentTracking`"（一条来自 `ShipmentService.updateStatus`
    内部的 `recordTracking(...)`，`trackingNo` 为 null；另一条来自本卡在 `processCallback` 里
    手工 `save` 的、带 `trackingNo` 的那条）而去改 `updateStatus`/`recordTracking` 的方法签名。
    这个重复是已经过尽调、明确判定"中风险，本轮不做"的已知项（`findings.md` §8"已识别但未实施"：
    "物流回调每次多写一条 trackingNo=null 冗余轨迹……中价值、中风险（改 updateStatus 签名）"）。
    本卡按上面给的代码原样实现即可，不要"顺手"精简掉这个重复。
  - 不要把签名校验做成读 `X-Payment-Signature` 之类的请求头——物流回调的签名字段在**请求体**里
    （`LogisticsCallbackRequest.signature`），和支付回调的头部签名是两回事。
  - `mapToShipmentStatus` 已经处理了未知/`null` status（兜底 `EXCEPTION`/`IN_TRANSIT`），不要
    重复造轮子。

---

### LOGI-6 | `ShipmentDeliveredEvent` 签收时从未发布

- 风险: high · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- **现状**: `updateStatus(...)`（基线第 247-273 行）在 `newStatus == ShipmentStatus.DELIVERED` 时
  只是 `shipment.setDeliveredAt(LocalDateTime.now())`（第 258 行），全程没有发布任何事件。
  `com.ecommerce.common.event.ShipmentDeliveredEvent` 这个类本身也不存在——`findings.md` §6.8 #6
  原话"全仓库不存在"。后果：order 模块永远收不到"已签收"的信号，订单状态推不到 `DELIVERED`，
  `OrderQueryServiceImpl.verifyPurchase` 只认 `DELIVERED`/`COMPLETED`，评价创建的
  `REVIEW_PURCHASE_REQUIRED` 前置校验永远过不了（PUB-014 依赖这条链路走通）。
- **范围说明（重要）**：`ShipmentDeliveredEvent` 这个事件类本身，连同 `OrderCreatedEvent`/
  `OrderPaidEvent`/`PaymentSucceededEvent`/`ReviewApprovedEvent`/`RefundCompletedEvent` 一起，
  在 `findings.md` §6.0（跨模块系统性模式）里被列为**同一次性架构修复**的对象——"唯一权威定义
  迁到 ecommerce-common"，由 `S2-events.md §A`（对应批次 B13）统一创建，**不在本卡范围**。
  `ShipmentDeliveredEvent` 在 order/loyalty 侧的 `@EventListener`（`附录D` §4：监听方是
  order-service、loyalty-service）同样不在本卡范围，那是 `S2-events.md §B`（B16）的工作
  （对应 Task 13 `BUG-INT-5`）。**本卡只负责 logistics 这一侧：在 `updateStatus()` 签收分支里把
  事件发布出去。**
- **期望**: 签收（状态转 `DELIVERED`）时发布 `com.ecommerce.common.event.ShipmentDeliveredEvent`，
  载荷 `orderId`/`shipmentId`/`deliveredAt`。依据: `design-docs/附录D-本地事件契约.md` §4
  （发布方 logistics-service；监听方 order-service、loyalty-service；载荷正是这三个字段）、
  `design-docs/02-系统架构.md` §5（事件发布/监听方表同一行："更新订单签收状态，失败可重试"）。
- **前置检查（写代码前先做）**: 确认
  `code/ecommerce-common/src/main/java/com/ecommerce/common/event/ShipmentDeliveredEvent.java`
  与 `code/ecommerce-common/src/main/java/com/ecommerce/common/event/DomainEventPublisher.java`
  已存在（应由更早的 B13 批次建好）。**若不存在**：说明本文件是脱离既定批次顺序单独执行的，
  把本卡记为"未完成/阻塞于 B13"如实上报，**不要**在 `com.ecommerce.logistics.event` 包下自己
  新建一个同名事件类"让它先编译过"——那样做等于重新制造 §6.0 刚清理掉的"影子事件类"反模式：
  你自己的类和 common 里（迟早会建的）权威类同名不同包，Spring 按运行时类型分发，order/loyalty
  的监听器引用的是 common 里那个，永远收不到你发布的这个，问题表面消失、实际仍未修复。
- **改法**（确认依赖已就绪后）:
  1. 加两个 import：
     ```java
     import com.ecommerce.common.event.DomainEventPublisher;
     import com.ecommerce.common.event.ShipmentDeliveredEvent;
     ```
  2. 在现有构造函数参数列表末尾追加一个参数 `DomainEventPublisher eventPublisher`，并赋给同名新
     字段 `private final DomainEventPublisher eventPublisher;`（其余已有字段/参数原样保留，不要
     删减）。
  3. `updateStatus()` 里，把 `pickupTime`/`deliveredAt` 的取值源从 `LocalDateTime.now()` 换成
     `com.ecommerce.common.test.SystemClockService.now()`（`ecommerce-common` 里已有的静态工具类，
     `now()` 签名与 `LocalDateTime.now()` 兼容；只是让这两个时间戳能被黑盒测试 harness 的系统时钟
     覆盖/故障注入感知，见 `design-docs/03` §5 黑盒隔离约定）：
     ```java
     if (newStatus == ShipmentStatus.COLLECTED) {
         shipment.setPickupTime(SystemClockService.now());
     } else if (newStatus == ShipmentStatus.DELIVERED) {
         shipment.setDeliveredAt(SystemClockService.now());
     }
     ```
     需要 `import com.ecommerce.common.test.SystemClockService;`。
  4. 在 `orderLogisticsStatusUpdater` 那段 try/catch **之后**、方法结尾的
     `log.info("Shipment {} status updated to {}", ...)` **之前**，插入：
     ```java
     if (newStatus == ShipmentStatus.DELIVERED) {
         eventPublisher.publish(new ShipmentDeliveredEvent(this, shipment.getOrderId(), shipment.getId(),
                 shipment.getDeliveredAt(), String.valueOf(shipment.getId()), null));
     }
     ```
- **验收**: 单测里给 `ShipmentService` 注入一个 mock/spy 的 `DomainEventPublisher`，调用
  `updateStatus(id, ShipmentStatus.DELIVERED, ...)` 后，`verify(eventPublisher).publish(any
  (ShipmentDeliveredEvent.class))` 恰好触发一次，且事件的 `getOrderId()`/`getShipmentId()`/
  `getDeliveredAt()` 与该发货单一致；`updateStatus(id, ShipmentStatus.COLLECTED, ...)` /
  `IN_TRANSIT` / `EXCEPTION` 不触发发布。端到端：走完 pay→pick→printLabel→outbound→
  `logisticsCallback(trackingNo,"DELIVERED")` 后，只要 order 侧监听器已按 B16 落地，订单能推进到
  `DELIVERED`（该端到端断言不属于本卡验收范围，本卡只保证事件确实发出）。
- **勿犯**:
  - 不要在 `com.ecommerce.logistics` 包下新建 `ShipmentDeliveredEvent`（见上面"前置检查"）。
  - 不要在本卡里顺手实现 order/loyalty 侧的监听器——不是本模块的文件，越界修改容易在其他批次
    重复劳动或冲突。
  - `eventPublisher.publish(...)` 本身内部已经 try/catch 保护、不会向外抛异常（`publish()` 捕获
    同步异常并落 `FailedEventRecord`），不需要你在 `updateStatus()` 这一层再包一层 try/catch。

---

### LOGI-7 | 运费模板无 30 分钟缓存；省份/重量规则字段存了却从未参与计算

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-logistics/pom.xml`
  2. 新增 `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/config/FreightCacheConfig.java`
  3. 新增 `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/cache/FreightTemplateCacheManager.java`
  4. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/FreightCalculator.java`
  5. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/FreightTemplateService.java`
  6. （同步测试，构造函数参数变了必然编译失败）
     `code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/service/FreightCalculatorTest.java`、
     `code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/service/FreightTemplateServiceTest.java`
- **本卡明确要求新增 pom.xml 依赖 + 新增 `@Configuration` 类 + 新增 `@Bean` 方法**——这类改动
  默认属于高危黑名单（见 `work/skills/bug-fixer/SKILL.md`"高危操作黑名单"），但本卡明确要求，
  照做即可，不用因为触碰黑名单而跳过。见下面"为什么这样加不会导致第二个 CacheManager 冲突"。
- **现状**:
  - `FreightTemplate` 实体（`entity/FreightTemplate.java`）本来就有 `provinceRules`/`weightRules`
    两个 JSON 文本列，`FreightTemplateRequest`/`FreightTemplateService.createTemplate/
    updateTemplate` 也已经把这两个字段正常存进去了——**数据层完全没问题**。
  - 问题全在 `FreightCalculator.java`：全文件 `grep provinceRules/weightRules` 零命中——
    `calculateFreight(...)`（基线第 40 行起）不管走哪个重载，只用得到
    `template.getDefaultFreight()`（第 50-51、83-84 行）和 `template.getFreeShippingThreshold()`，
    `provinceRules`/`weightRules` 存了从来没被读过。
  - `findActiveTemplate()`（基线第 94 行）每次都 `freightTemplateRepository.findAll()` 打一次
    DB，没有任何缓存。`design-docs/02-系统架构.md` §7 缓存设计表明确列了
    "运费模板 | `logistics:freight:{templateId}` | 30 分钟 | logistics"。
  - `FreightCalculator(FreightTemplateRepository freightTemplateRepository)`（基线第 30 行）
    构造函数只有一个参数。
- **期望**: 30 分钟缓存（键为 `templateId`，依据 `02§7`）；运费计算先看 `provinceRules`（省份
  精确匹配），再看 `weightRules`（重量分档，落在哪个 `maxWeightKg` 档位内），都没匹配上再退回
  模板自身的 `defaultFreight`。依据: `design-docs/11` §4（"运费模板可按省份、重量和商品件数配置"）。
- **为什么这样加不会导致第二个 CacheManager 冲突**：本卡要新建的
  `Cache<Long, FreightTemplate>` 是 **`com.github.benmanes.caffeine.cache.Cache`**（手写的原生
  Caffeine 缓存对象），**不是** `org.springframework.cache.CacheManager`，不涉及 `@EnableCaching`/
  `@Cacheable`。这是仓库里已经反复验证过、安全共存的既有写法——原样照抄
  `code/ecommerce-cart/src/main/java/com/ecommerce/cart/config/CartCacheConfig.java` +
  `.../cache/CartCacheManager.java` 那一对（`Cache<Long, CartData>` bean + 薄包装
  `@Component`），只是把泛型换成 `<Long, FreightTemplate>`、键从 `userId` 换成 `templateId`。
  `Cache<Long, CartData>` 和 `Cache<Long, FreightTemplate>` 是 Spring 眼里两个不同的 bean 类型
  （`@Bean` 工厂方法的完整泛型签名参与类型匹配），不会冲突、不会二选一。`work/bugs/README.md`
  "绝不做清单" 第 3 条禁止的是新增/多份 `org.springframework.cache.CacheManager`/
  `@EnableCaching`（inventory 模块另有一份用这个真正 Spring 抽象的 `InventoryCacheConfig`，
  同样安全共存，因为它显式命名了自己的 `CacheManager` bean，互不干扰）——本卡完全不碰这个
  抽象，不在禁止之列。
- **改法**:

  **(1) `pom.xml` 加 Caffeine 依赖**，原样照抄 `ecommerce-cart/pom.xml` 里已有的写法（不用写
  `<version>`，由父 POM/Spring Boot BOM 统一管理，cart 模块已经这样用且能正常构建）：
  ```xml
  <dependency>
      <groupId>com.github.ben-manes.caffeine</groupId>
      <artifactId>caffeine</artifactId>
  </dependency>
  ```
  插入到现有 `<dependencies>` 里，`ecommerce-common`/`ecommerce-order` 依赖之后、
  `spring-security-test`（test scope）之前均可。

  **(2) 新增 `config/FreightCacheConfig.java`**（整份新文件，包路径
  `com.ecommerce.logistics.config`）：
  ```java
  package com.ecommerce.logistics.config;

  import com.ecommerce.logistics.entity.FreightTemplate;
  import com.github.benmanes.caffeine.cache.Cache;
  import com.github.benmanes.caffeine.cache.Caffeine;
  import org.springframework.context.annotation.Bean;
  import org.springframework.context.annotation.Configuration;

  import java.time.Duration;

  /**
   * Caffeine cache for resolved freight templates. 30-minute TTL, keyed by
   * templateId (design-docs/02 section 7: logistics:freight:{templateId}).
   */
  @Configuration
  public class FreightCacheConfig {

      private static final Duration FREIGHT_TEMPLATE_TTL = Duration.ofMinutes(30);
      private static final long MAX_FREIGHT_TEMPLATE_ENTRIES = 10_000;

      @Bean
      public Cache<Long, FreightTemplate> freightTemplateCache() {
          return Caffeine.newBuilder()
                  .expireAfterWrite(FREIGHT_TEMPLATE_TTL)
                  .maximumSize(MAX_FREIGHT_TEMPLATE_ENTRIES)
                  .recordStats()
                  .build();
      }
  }
  ```

  **(3) 新增 `cache/FreightTemplateCacheManager.java`**（整份新文件，包路径
  `com.ecommerce.logistics.cache`）：
  ```java
  package com.ecommerce.logistics.cache;

  import com.ecommerce.logistics.entity.FreightTemplate;
  import com.github.benmanes.caffeine.cache.Cache;
  import org.springframework.stereotype.Component;

  @Component
  public class FreightTemplateCacheManager {

      private final Cache<Long, FreightTemplate> freightTemplateCache;

      public FreightTemplateCacheManager(Cache<Long, FreightTemplate> freightTemplateCache) {
          this.freightTemplateCache = freightTemplateCache;
      }

      public FreightTemplate get(Long templateId) {
          return freightTemplateCache.getIfPresent(templateId);
      }

      public void put(Long templateId, FreightTemplate template) {
          freightTemplateCache.put(templateId, template);
      }

      public void evict(Long templateId) {
          freightTemplateCache.invalidate(templateId);
      }
  }
  ```

  **(4) `FreightCalculator.java` 整个文件改为**（新增 `FreightTemplateCacheManager`/`ObjectMapper`
  依赖、新增 4 参重载解析省份/重量规则；两个旧的公开方法签名 `calculateFreight(BigDecimal)` /
  `calculateFreight(BigDecimal, Long)` 保留不变，内部转调新重载，调用方零改动）：
  ```java
  package com.ecommerce.logistics.service;

  import com.ecommerce.logistics.cache.FreightTemplateCacheManager;
  import com.ecommerce.logistics.entity.FreightTemplate;
  import com.ecommerce.logistics.repository.FreightTemplateRepository;
  import com.fasterxml.jackson.core.type.TypeReference;
  import com.fasterxml.jackson.databind.ObjectMapper;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Service;

  import java.math.BigDecimal;
  import java.util.Collections;
  import java.util.Comparator;
  import java.util.HashMap;
  import java.util.List;
  import java.util.Map;

  @Service
  public class FreightCalculator {

      private static final Logger log = LoggerFactory.getLogger(FreightCalculator.class);

      private static final BigDecimal DEFAULT_FREIGHT = new BigDecimal("8.00");
      private static final BigDecimal DEFAULT_FREE_SHIPPING_THRESHOLD = new BigDecimal("199.00");

      private final FreightTemplateRepository freightTemplateRepository;
      private final FreightTemplateCacheManager freightTemplateCacheManager;
      private final ObjectMapper objectMapper;

      public FreightCalculator(FreightTemplateRepository freightTemplateRepository,
                               FreightTemplateCacheManager freightTemplateCacheManager,
                               ObjectMapper objectMapper) {
          this.freightTemplateRepository = freightTemplateRepository;
          this.freightTemplateCacheManager = freightTemplateCacheManager;
          this.objectMapper = objectMapper;
      }

      public BigDecimal calculateFreight(BigDecimal itemTotal) {
          return calculateFreight(itemTotal, null, null, null);
      }

      public BigDecimal calculateFreight(BigDecimal itemTotal, Long templateId) {
          if (templateId == null) {
              return calculateFreight(itemTotal);
          }
          return calculateFreight(itemTotal, templateId, null, null);
      }

      /**
       * @param province optional delivery province, matched against provinceRules
       * @param weight   optional package weight in kg, matched against weightRules
       */
      public BigDecimal calculateFreight(BigDecimal itemTotal, Long templateId, String province, BigDecimal weight) {
          if (itemTotal == null || itemTotal.compareTo(BigDecimal.ZERO) <= 0) {
              return DEFAULT_FREIGHT;
          }

          FreightTemplate template = templateId != null ? loadTemplate(templateId) : findActiveTemplate();

          if (template == null) {
              if (itemTotal.compareTo(DEFAULT_FREE_SHIPPING_THRESHOLD) >= 0) {
                  return BigDecimal.ZERO;
              }
              return DEFAULT_FREIGHT;
          }

          BigDecimal threshold = template.getFreeShippingThreshold() != null
                  ? template.getFreeShippingThreshold() : DEFAULT_FREE_SHIPPING_THRESHOLD;

          if (itemTotal.compareTo(threshold) >= 0) {
              return BigDecimal.ZERO;
          }

          return resolveFreight(template, province, weight);
      }

      private FreightTemplate loadTemplate(Long templateId) {
          FreightTemplate cached = freightTemplateCacheManager.get(templateId);
          if (cached != null) {
              return cached;
          }
          FreightTemplate template = freightTemplateRepository.findById(templateId).orElse(null);
          if (template != null) {
              freightTemplateCacheManager.put(templateId, template);
          }
          return template;
      }

      private BigDecimal resolveFreight(FreightTemplate template, String province, BigDecimal weight) {
          BigDecimal defaultFreight = template.getDefaultFreight() != null
                  ? template.getDefaultFreight() : DEFAULT_FREIGHT;

          if (province != null && !province.isBlank()) {
              BigDecimal provinceRate = parseProvinceRules(template.getProvinceRules()).get(province);
              if (provinceRate != null) {
                  return provinceRate;
              }
          }

          if (weight != null) {
              for (WeightRule rule : parseWeightRules(template.getWeightRules())) {
                  if (rule.getMaxWeightKg() != null && weight.compareTo(rule.getMaxWeightKg()) <= 0) {
                      return rule.getFreight();
                  }
              }
          }

          return defaultFreight;
      }

      /** JSON: [{"province":"Guangdong","freight":5.00}]. Parse failure/blank -> empty map (fall back to default). */
      private Map<String, BigDecimal> parseProvinceRules(String json) {
          if (json == null || json.isBlank()) {
              return Collections.emptyMap();
          }
          try {
              List<ProvinceRule> rules = objectMapper.readValue(json, new TypeReference<List<ProvinceRule>>() { });
              Map<String, BigDecimal> byProvince = new HashMap<>();
              for (ProvinceRule rule : rules) {
                  if (rule.getProvince() != null && rule.getFreight() != null) {
                      byProvince.put(rule.getProvince(), rule.getFreight());
                  }
              }
              return byProvince;
          } catch (Exception e) {
              log.warn("Failed to parse freight template provinceRules, falling back to default freight: {}", e.getMessage());
              return Collections.emptyMap();
          }
      }

      /** JSON: [{"maxWeightKg":1.0,"freight":8.00},{"maxWeightKg":5.0,"freight":15.00}], ascending by maxWeightKg,
       *  first tier the weight fits under wins. Parse failure/blank -> empty list (fall back to default). */
      private List<WeightRule> parseWeightRules(String json) {
          if (json == null || json.isBlank()) {
              return Collections.emptyList();
          }
          try {
              List<WeightRule> rules = objectMapper.readValue(json, new TypeReference<List<WeightRule>>() { });
              rules.sort(Comparator.comparing(WeightRule::getMaxWeightKg, Comparator.nullsLast(Comparator.naturalOrder())));
              return rules;
          } catch (Exception e) {
              log.warn("Failed to parse freight template weightRules, falling back to default freight: {}", e.getMessage());
              return Collections.emptyList();
          }
      }

      private FreightTemplate findActiveTemplate() {
          return freightTemplateRepository.findAll().stream().findFirst().orElse(null);
      }

      private static class ProvinceRule {
          private String province;
          private BigDecimal freight;

          public String getProvince() { return province; }
          public void setProvince(String province) { this.province = province; }
          public BigDecimal getFreight() { return freight; }
          public void setFreight(BigDecimal freight) { this.freight = freight; }
      }

      private static class WeightRule {
          private BigDecimal maxWeightKg;
          private BigDecimal freight;

          public BigDecimal getMaxWeightKg() { return maxWeightKg; }
          public void setMaxWeightKg(BigDecimal maxWeightKg) { this.maxWeightKg = maxWeightKg; }
          public BigDecimal getFreight() { return freight; }
          public void setFreight(BigDecimal freight) { this.freight = freight; }
      }
  }
  ```
  `ObjectMapper` 是 Spring Boot 自动装配的现成 bean（Jackson 已经在 classpath 上，仓库其他模块
  早就在用），不需要为它额外加 pom 依赖或手写 `@Bean`。

  **(5) `FreightTemplateService.java`**：构造函数追加 `FreightTemplateCacheManager` 参数；
  `updateTemplate()` 里 `template = freightTemplateRepository.save(template);` 之后加一行
  `freightTemplateCacheManager.evict(templateId);`；`deleteTemplate()` 里
  `freightTemplateRepository.deleteById(templateId);` 之后加一行
  `freightTemplateCacheManager.evict(templateId);`（改完模板/删模板都要让缓存失效，否则 30
  分钟内还会读到旧值）。`createTemplate()`/`getAllTemplates()`/`getTemplate()` 不用改——新建的
  模板靠 `FreightCalculator.loadTemplate()` 第一次用到时惰性写入缓存即可，不需要提前预热。

  **(6) 测试**：`FreightCalculatorTest`/`FreightTemplateServiceTest` 里直接
  `new FreightCalculator(freightTemplateRepository)` / `new FreightTemplateService
  (freightTemplateRepository)` 的地方，构造函数参数数量变了，编译会先炸——补上新增的 mock
  参数（`FreightTemplateCacheManager`、`ObjectMapper`）即可让它们重新编译通过；`ObjectMapper`
  可以直接 `new ObjectMapper()`，不需要 mock。
- **验收**: `FreightCalculator.calculateFreight(new BigDecimal("50.00"), templateId, "Guangdong",
  null)` 在模板的 `provinceRules` 含 `{"province":"Guangdong","freight":5.00}` 时返回
  `5.00`；只传 `weight` 不传省份时按 `weightRules` 命中对应档位；两者都不传或都不命中时退回
  `template.getDefaultFreight()`；同一个 `templateId` 连续两次调用只打一次
  `freightTemplateRepository.findById`（第二次走缓存）；`updateTemplate`/`deleteTemplate` 后
  再算立刻拿到新值（缓存已被 evict，不用等 30 分钟）。
- **勿犯**:
  - **不要把 `FreightCalculator` 接入 `ecommerce-order` 的下单流程**（`OrderTotalCalculator`
    现在算运费不经过这个类，是另一套固定 8.00/199.00 阈值逻辑）。这是 `findings.md` §8
    "已识别但未实施"里明确记录、评估过"风险高于收益"暂不做的独立事项，不属于本卡范围，改了
    反而可能连累 PUB-104（`payableAmount` 断言）。本卡只保证 `FreightCalculator`/
    `FreightTemplateService` 自身的计算和缓存逻辑正确、可单测验证。
  - 不要引入 `@EnableCaching`/`org.springframework.cache.CacheManager`——见上面"为什么不会冲突"
    的说明，本卡从头到尾只用手写的 Caffeine `Cache<K,V>`。
  - `provinceRules`/`weightRules` JSON 解析失败或为空一律静默退回默认运费（`catch` 里只
    `log.warn`，不抛异常）——不要让格式错误的运维数据把下单/查询接口打成 500。

---

### LOGI-8 | 出库后从不发送"发货提醒"短信（第三轮深审·跨领域 #9）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
- **现状**: `outbound()`（基线第 223-242 行，LOGI-2 会在其开头加前置状态校验）把状态推成
  `OUTBOUND`、记轨迹、更新订单物流状态之后就结束了——`ecommerce-logistics` 全模块搜不到一处
  `LocalNotificationService` 的调用，出库这个对用户最有感知的节点完全没有通知触达。
- **期望**: 包裹出库后发一条"发货提醒"短信。依据: `design-docs/15-本地通知组件设计.md` §2
  （通知类型表："SMS | 支付成功、发货提醒"）。发送必须走 `LocalNotificationService`，不得直接调
  `MockSmsSender`。依据: `design-docs/03` §7（通知规范）。失败必须是 best-effort，不影响出库
  这个主流程。依据: `design-docs/15` §4 第 5 条（"失败时记录失败原因，不影响主业务流程"）、
  `design-docs/03` §7。
- **改法**:
  1. 加两个 import：
     ```java
     import com.ecommerce.common.notification.LocalNotificationService;
     import com.ecommerce.common.notification.NotificationChannel;
     import com.ecommerce.common.notification.NotificationRequest;
     import java.util.Map;
     ```
  2. 在现有构造函数参数列表末尾追加一个参数 `LocalNotificationService notificationService`，
     赋给同名新字段 `private final LocalNotificationService notificationService;`（若 LOGI-6 已经
     应用过、构造函数已经追加过 `DomainEventPublisher eventPublisher`，本卡在那之后继续追加，
     不要把 `eventPublisher` 参数删掉）。
  3. `outbound()` 里，在 `orderLogisticsStatusUpdater` 那段 try/catch **之后**、方法结尾的
     `log.info("Outbound completed for shipmentId={}", shipmentId);` **之前**，插入一行调用：
     ```java
     sendShipmentNotification(shipment);
     ```
  4. 新增一个私有方法（放在 `recordTracking` 私有方法附近即可）：
     ```java
     /**
      * Sends the "发货提醒" notification over SMS (design-docs/15 §2) once the
      * package leaves the warehouse. Swallows any failure so the shipment flow
      * is never affected.
      */
     private void sendShipmentNotification(Shipment shipment) {
         try {
             NotificationRequest request = new NotificationRequest();
             request.setBizType("SHIPMENT_OUTBOUND");
             request.setBizId(shipment.getShipmentNo());
             request.setReceiver(String.valueOf(shipment.getUserId()));
             request.setChannel(NotificationChannel.SMS);
             request.setTemplateCode("shipment_reminder");
             request.setVariables(Map.of(
                     "shipmentNo", shipment.getShipmentNo(),
                     "orderId", String.valueOf(shipment.getOrderId()),
                     "trackingNo", shipment.getTrackingNo() != null ? shipment.getTrackingNo() : ""));
             request.setIdempotencyKey("ship_notify_" + shipment.getShipmentNo());
             notificationService.send(request);
         } catch (Exception e) {
             log.warn("Failed to send shipment notification for shipmentNo={}: {}",
                     shipment.getShipmentNo(), e.getMessage());
         }
     }
     ```
     `idempotencyKey` 按 `shipmentNo` 固定取值，即使 `outbound()` 因为某种原因被重复调用（同一
     发货单不会真的二次出库，但保险起见），`LocalNotificationService` 自己会按
     `idempotencyKey` 去重，不会重复发短信（`design-docs/15` §4 第 1 条）。
- **验收**: 正常走一遍 `pick→printLabel→outbound`，`outbound` 返回 200 后，
  `LocalNotificationService.send(...)` 被调用一次、`channel=SMS`；用 mock
  `LocalNotificationService` 让 `send(...)` 抛异常，`outbound()` 依旧返回 200 且发货单状态仍变为
  `OUTBOUND`（异常不外传、不回滚）。
- **勿犯**: 不要绕开 `LocalNotificationService` 直接引用 `MockSmsSender`——`common` 模块的
  `MockMailSender`/`MockSmsSender` 明确只允许 `LocalNotificationServiceImpl` 自己调用，业务模块
  （包括本模块）一律通过 `NotificationRequest` + `LocalNotificationService.send(...)` 间接触发。

---

### LOGI-9 | 打印面单把承运商硬编码为占位符 "DEFAULT"，违背附录B 默认承运商 LOCAL_EXPRESS（第四轮设计-实现对比 #1）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/controller/AdminLogisticsController.java`
- **现状**: `printLabel` 端点（约第 55~59 行）：
  ```java
  @PostMapping("/shipments/{id}/print-label")
  public ResponseEntity<Void> printLabel(@PathVariable Long id) {
      log.info("POST /api/v1/admin/logistics/shipments/{}/print-label", id);
      shipmentService.printLabel(id, "DEFAULT");
      return ResponseEntity.ok().build();
  }
  ```
  第二个实参硬编码字符串 `"DEFAULT"`（占位符残留）。它经 `ShipmentService.printLabel(shipmentId,
  carrier)` 一路写进 `LabelRecord.carrier`、`Shipment.carrier` 与轨迹描述文案——打完面单后查询
  订单物流，承运商显示为字面量 `DEFAULT`。
- **期望**: 打印面单接口（附录A §9）没有承运商请求参数，承运商必须取运行期配置
  `logistics.default-carrier`，默认值 `LOCAL_EXPRESS`（附录B §1 示例配置）。打面单后
  `Shipment.carrier` 与物流查询响应中的 carrier = `LOCAL_EXPRESS`（或被
  `PUT /api/v1/admin/system/configs/logistics.default-carrier` 覆盖后的运行期值）。
- **改法**: 只改 controller 这一处调用（`ShipmentService.printLabel` 本身不动——它接受 carrier
  形参的设计没有问题）：
  1. import 块新增：`import com.ecommerce.common.test.RuntimeConfigRegistry;`
  2. 调用行改为：
  ```java
  shipmentService.printLabel(id,
          RuntimeConfigRegistry.getString("logistics.default-carrier", "LOCAL_EXPRESS"));
  ```
- **验收**: 走完整链路（支付成功 → 发货单 → pick → print-label）后
  `GET /api/v1/logistics/order/{orderId}` 响应中承运商字段 = `LOCAL_EXPRESS`；
  `grep -n '"DEFAULT"' code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/controller/AdminLogisticsController.java`
  不再命中。
- **勿犯**:
  1. `RuntimeConfigRegistry` 在 `com.ecommerce.common.test` 包（黑盒支撑注册表），**不是**
     `com.ecommerce.common.config`——import 写错编译不过。
  2. 不要把默认值下沉到 `ShipmentService` 内部去覆盖调用方传入的 carrier——保留
     `printLabel(id, carrier)` 形参语义，只改 controller 侧实参来源。
  3. 不要给接口新增 carrier 请求参数——附录A 冻结的接口签名没有它。

---

## 本批未覆盖的 §6.8 条目

### §6.8 #4 | 发货单从不通过事件监听器自动创建（跳过，路由给 S2）

`findings.md` 原文："发货单从不通过事件监听器自动创建（`createShipment` 零调用方，死代码）| 全模块
无 `@EventListener` | definite | 附录D §2（`OrderPaidEvent` 监听方含 logistics）、02 §5 | 加
`OrderPaidEvent` 监听器（结合 §6.0 事件类统一）"。

跳过理由：这一项的修复本质是"新增一个跨模块事件监听器"——不仅要新建
`com.ecommerce.logistics.event.OrderPaidEventListener`，还牵扯：
- 引用 `S2-events.md §A`（B13）迁到 `ecommerce-common` 的权威 `OrderPaidEvent` 类（而不是自己
  臆造一个本模块的影子类，重蹈 §6.0 描述的覆辙）；
  Task 13 `BUG-INT-1`：与 `ecommerce-loyalty` 同样新增的 `OrderPaidEventListener` 简单类名相同，
  默认 bean 名冲突（`ConflictingBeanDefinitionException`，Spring 上下文起不来，24 例全灭），
  必须显式限定 bean 名（如 `@Component("logisticsOrderPaidEventListener")`）；
- Task 13 `BUG-INT-3`：监听器必须用 `@TransactionalEventListener(phase = AFTER_COMMIT)` +
  `@Transactional(propagation = REQUIRES_NEW)`，否则发货单在 `AFTER_COMMIT` 阶段无存活事务、
  `save()` 从不落库。

这些恰好是任务交底里明确要排除的"OrderPaidEventListener 的事务语义/bean 名（S2 事件批）"，且
命中"若某条修复本质是事件监听器改造，跳过归 S2"的通用规则，因此本文件不出这张卡，由
`S2-events.md`（对应 `work/bugs/README.md` 批次表 B13/B16）统一处理。`work/checklist/
logistics.md`（在线复核清单）仍然列了这条要求，验证阶段会按该清单核对，不会因为本文件跳过而
漏检。
