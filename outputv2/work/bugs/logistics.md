# B14 · logistics — 拣货-面单-出库链 / 回调 / 运费模板 / 订单物流状态推进

来源：`work/bugs/findings.md`「logistics 模块（§6.8，共 7 项）」——本文件覆盖其中 **6 项**（LOGI-1..
LOGI-3、LOGI-5..LOGI-7）；第 4 项（发货单靠监听 `OrderPaidEvent` 自动创建）本质是"新增事件监听器 +
跨模块 bean 命名/事务语义"，按裁决路由给 `S2-events.md`，不在本文件重复，见文末《本批未覆盖的
§6.8 条目》。另外补 5 张卡：LOGI-4（Task 13 集成缺陷 `BUG-INT-4`，pick 空指针）、LOGI-8（第三轮深审
·跨领域 #9，出库无发货提醒短信）、LOGI-9（第四轮设计-实现对比 #1，面单承运商硬编码占位符）、
LOGI-10（findings「已识别但未实施」·物流回调冗余轨迹去重）、LOGI-11（Wave-3 实验实证后的弃项反转：
`OrderLogisticsStatusUpdater` 生产实现，@Primary 方案；LOGI-10/LOGI-11 在文件真末尾、《本批未覆盖》
一节之后）。

**LOGI-1..LOGI-10 共 10 张卡全部只改 `ecommerce-logistics` 模块自身文件**，不改 `ecommerce-order`/
`ecommerce-loyalty`——运费模板接线进下单流程、`ShipmentDeliveredEvent` 在 order/loyalty 侧的监听器，
都是明确排除在外的别批范围（各相关卡的「勿犯」有单独提醒）。**唯一例外是 LOGI-11**（高危卡）：它给
logistics 的跨模块端口补生产实现，按设计只能落在 order（推进服务+单测）与 app（@Primary 适配器）
两个模块——3 个文件全部是【新增】，不触碰任何既有文件，跨模块落地先例见 B05/PROMO-16。

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
- **文件**:
  1. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/controller/AdminLogisticsController.java`
  2. （同步单测）`code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/controller/AdminLogisticsControllerTest.java`
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
- **改法**: 生产侧只改 controller 这一处调用（`ShipmentService.printLabel` 本身不动——它接受 carrier
  形参的设计没有问题），另同步 1 处控制器单测的 mock 期望：
  1. import 块新增（放在 `import com.ecommerce.logistics.dto.FreightTemplateRequest;` 之前，
     保持字母序）：`import com.ecommerce.common.test.RuntimeConfigRegistry;`
  2. 调用行改为：
  ```java
  shipmentService.printLabel(id,
          RuntimeConfigRegistry.getString("logistics.default-carrier", "LOCAL_EXPRESS"));
  ```
  3. 同步 `AdminLogisticsControllerTest.testPrintLabel_authenticated_returnsOk`（约第 92-100 行）——
     该用例原来 mock/verify 的是旧占位符实参 `printLabel(1L, "DEFAULT")`，不改会在
     `mvn -f code/pom.xml test` 模块自检时失败（黑盒门禁不受影响，但不许留一个明知会挂的单测）。
     两处 `eq("DEFAULT")` / `"DEFAULT"` 实参改为 `"LOCAL_EXPRESS"`：
  ```java
  doNothing().when(shipmentService).printLabel(eq(1L), eq("LOCAL_EXPRESS"));
  ...
  // LOGI-9: with no runtime override set, the controller must resolve the
  // carrier from logistics.default-carrier (附录B §1 default LOCAL_EXPRESS),
  // not the old hard-coded "DEFAULT" placeholder.
  verify(shipmentService).printLabel(1L, "LOCAL_EXPRESS");
  ```
- **验收**: 走完整链路（支付成功 → 发货单 → pick → print-label）后
  `GET /api/v1/logistics/order/{orderId}` 响应中承运商字段 = `LOCAL_EXPRESS`；
  `grep -n '"DEFAULT"' code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/controller/AdminLogisticsController.java`
  不再命中；`grep -n 'eq("DEFAULT")\|printLabel(1L, "DEFAULT")' code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/controller/AdminLogisticsControllerTest.java`
  不再命中（改法第 3 步的解释性注释里允许出现 DEFAULT 字样，不算残留——只要 mock/verify 实参不再是它）；
  `mvn -s maven-settings.xml -f code/pom.xml test -pl ecommerce-logistics`
  中 `AdminLogisticsControllerTest` 全绿。
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

---

### LOGI-10 | 物流回调一次事件写两条轨迹，其中一条 trackingNo=null 的冗余行（findings「已识别但未实施」落地）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-logistics/src/main/java/com/ecommerce/logistics/service/ShipmentService.java`
  2. （同步测试）`code/ecommerce-logistics/src/test/java/com/ecommerce/logistics/service/ShipmentServiceTest.java`
- **现状**: 基线 `ShipmentService.updateStatus(...)`（基线第 247-281 行）内部有一行
  ```java
  recordTracking(shipmentId, newStatus.name(), location, description, "CARRIER");
  ```
  （基线第 263 行）。私有 `recordTracking(...)`（基线第 283 行起）落的 `ShipmentTracking` **不带
  `trackingNo`**（方法根本没有这个参数），`eventTime` 用的是服务器当前时间而非承运商事件时间。
  基线里 `updateStatus` 零调用方（死代码）；LOGI-5 落地后，回调路径
  `LogisticsCallbackService.processCallback` 先调 `updateStatus(...)`（内部写这条 trackingNo=null
  的行），随后又手工 `save` 一条带 `trackingNo` + 承运商 `eventTime` 的完整行——**一次回调事件
  写两条轨迹**，`GET /api/v1/logistics/order/{orderId}` 的 `trackingRecords` 里每个承运商事件都
  出现两遍（一条完整、一条 trackingNo=null 且时间是服务器时间，按 `eventTime` 排序时两条还可能
  被其它事件行隔开）。LOGI-5「勿犯」第 1 条当时明确禁止顺手精简这个重复（当时评估以为要改
  `updateStatus` 签名、判"中风险，本轮不做"）——**本卡就是那个暂缓项的正式落地**，且用的是
  不改签名的更小改法；LOGI-5 的那条临时禁令自本卡起解除，两卡不冲突：先按 LOGI-5 原样实现回调，
  再按本卡去重。
- **期望**: 一个承运商回调事件只落**一条**轨迹，且是带幂等键三要素的那条完整行。依据:
  design-docs/03 §3（幂等规范表：物流回调幂等键 = `trackingNo` + `eventTime` + `status`——
  trackingNo=null 的影子行永远无法参与判重，是纯冗余数据）、design-docs/11 §1（物流轨迹为物流
  服务职责，"事件 → 轨迹"语义一对一）。来源：`findings.md` 第三轮深审「已识别但未实施」条目
  "物流回调每次多写一条 `trackingNo=null` 冗余轨迹（`updateStatus`→`recordTracking` 与
  `LogisticsCallbackService` 手工插入重复）：中价值、中风险（改 `updateStatus` 签名）"。
- **改法**（不改任何方法签名）:
  1. **`ShipmentService.updateStatus(...)`** 里删掉那一行
     `recordTracking(shipmentId, newStatus.name(), location, description, "CARRIER");`，原位留注释
     说明单一写入点（其余全不动：状态落库、`pickupTime`/`deliveredAt` 打点、
     `orderLogisticsStatusUpdater` 推送、DELIVERED 事件发布、方法签名与可见性都保持原样）：
     ```java
     shipmentRepository.save(shipment);

     // Deliberately no recordTracking(...) here: updateStatus's only caller
     // is the carrier-callback path (LogisticsCallbackService.processCallback),
     // which persists the single complete ShipmentTracking for the event —
     // carrying the carrier's trackingNo and eventTime that form the callback
     // idempotency key (design-docs/03 §3: trackingNo+eventTime+status).
     // Writing a second, trackingNo-less row here (with server time instead
     // of the carrier event time) would duplicate every callback event's trace.

     try {
         orderLogisticsStatusUpdater.updateLogisticsStatus(
     ```
     依据：全仓库 `updateStatus` 的调用方只有 `LogisticsCallbackService.processCallback` 一处
     （基线零调用方，LOGI-5 之后恰好一处），而回调路径已由 LOGI-5 落那条完整行，删除后每个事件
     恰好一条轨迹。`recordTracking` 私有方法**保留**——`pick()`/`printLabel()`/`outbound()`
     三处操作轨迹仍在用它。
  2. **`ShipmentServiceTest.java`** 同步三个 `updateStatus` 用例（`testUpdateStatus_toCollected_
     setsPickupTime` / `testUpdateStatus_toDelivered_setsDeliveredAt` / `updateStatus_toDelivered_
     publishesShipmentDeliveredEvent`）：各删掉
     `when(trackingRepository.save(any(ShipmentTracking.class))).thenReturn(new ShipmentTracking());`
     那行桩（MockitoExtension 严格桩模式下，留着会 `UnnecessaryStubbingException` 报红）；并在
     COLLECTED 用例末尾加锁死断言：
     ```java
     // The single ShipmentTracking row for a carrier event is written by
     // LogisticsCallbackService.processCallback (with the carrier's
     // trackingNo/eventTime) — updateStatus itself must not write a second,
     // trackingNo-less duplicate.
     verify(trackingRepository, never()).save(any(ShipmentTracking.class));
     ```
     `pick`/`printLabel`/`outbound` 用例的 `trackingRepository.save` 桩**不要动**（那些路径仍写
     操作轨迹）。`LogisticsCallbackServiceTest` 无需改动——它 mock 了 `ShipmentService`，其
     `verify(trackingRepository).save(...)`（恰好一次、带 trackingNo）在删除后依然成立。
- **验收**:
  - 完整链路 pay → pick → print-label → outbound → callback(`COLLECTED`) → callback(`DELIVERED`)
    后查 `GET /api/v1/logistics/order/{orderId}`：`trackingRecords` 里 COLLECTED / DELIVERED 各
    **恰好一条**，且 `eventTime` 等于回调请求里传的值（不再混入服务器时间的影子行）；PICKING /
    LABEL_PRINTED / OUTBOUND 的操作轨迹不受影响、各一条。
  - 同一 `(trackingNo, eventTime, status)` 重发回调仍幂等 no-op（判重行为完全不变，判重靠的本来
    就是 LOGI-5 手工落的完整行）。
  - `ShipmentServiceTest`/`LogisticsCallbackServiceTest` 全绿；公开 24 例回归全绿（PUB-014/107/108
    走的物流链路只断言状态推进与轨迹存在性，删的是冗余行）。
- **勿犯**: **不要反向去重**（删 `processCallback` 的手工完整行、留 `updateStatus` 的内部行）——
  那样轨迹行会丢失 `trackingNo` 和承运商 `eventTime`，幂等判重
  `existsByTrackingNoAndEventTimeAndStatus(...)` 从此永远查不到已处理事件，回调幂等被打穿（同一
  事件重发一次就多推一次状态）。不要动 `updateStatus` 的方法签名（LOGI-5 当年暂缓就是怕动签名，
  本改法证明根本不需要）。不要删 `recordTracking` 私有方法本身，也不要动 `pick`/`printLabel`/
  `outbound` 里对它的三处调用。

---

### LOGI-11 | `OrderLogisticsStatusUpdater` 全仓无生产实现——物流状态永远推不动订单（11 §3 强制项的整条缺失）

- 风险: high · 置信度: definite
- **文件**（全部【新增】，不改任何既有文件；跨模块落地先例：B05/PROMO-16 经指针卡改 order 文件）：
  1. `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderLogisticsStatusService.java`【新增】
  2. `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderLogisticsStatusServiceTest.java`【新增】
  3. `code/ecommerce-app/src/main/java/com/ecommerce/app/integration/OrderLogisticsStatusUpdaterImpl.java`【新增】
- **现状**：logistics 的跨模块端口 `com.ecommerce.logistics.query.OrderLogisticsStatusUpdater`
  （`ShipmentService` 构造器强依赖，pick/printLabel/outbound/回调四处各调一次）在整个 `code/`
  里**没有任何生产实现**。两个后果：
  1. 黑盒链路里订单状态在支付后永远停在 `PAID`——`pick` 后不进 `PICKING`、`outbound` 后不进
     `SHIPPED`（黑盒能跑只因冻结的 `test-cases/.../BlackboxHarnessConfig` 注册了一个无限定符的
     no-op `@Bean`）；隐藏用例若在出库后断言订单为 `SHIPPED` 必挂。
  2. 独立启动 `ShopHubApplication`（生产入口，无 harness 配置）直接
     `NoSuchBeanDefinitionException`，上下文起不来。
  findings.md 曾把"补生产实现"列为**尽调后明确放弃**项，理由是与 harness no-op bean 类型冲突会
  `NoUniqueBeanDefinitionException` 24 例全灭——该结论**只对无消歧的第二个候选成立**，已被本卡的
  `@Primary` 方案实证推翻（作者侧按本卡全量落地后完整公开套件 24/24 全绿，且生产入口可独立启动，
  Started in ~3.6s）。
- **期望**：`design-docs/11-物流服务设计.md` §3 原文：「**物流状态变更后，必须通过
  `OrderLogisticsStatusUpdater` 更新对应订单的物流状态**」。映射到订单状态机（08 §2）：物流侧
  `PICKING` → 订单 `PICKING`（拣货中）；物流侧 `OUTBOUND`/`COLLECTED`/`IN_TRANSIT` → 订单
  `SHIPPED`（已发货）；`CREATED`/`LABEL_PRINTED`/`EXCEPTION` 不推进订单；`DELIVERED` **不在本卡
  处理**——签收推进由 `ShipmentDeliveredEvent` + order 侧监听器负责（附录D §4，B16/EVT-B2 卡），
  本卡绝不与它抢 DELIVERED 的写权。
- **@Primary 与 harness no-op 共存机理（本卡成立的根基，落笔前必须理解）**：冻结的
  `BlackboxHarnessConfig`（不可改）以 `@Bean` 注册了一个**无限定符、非 @Primary** 的 no-op
  实现（bean 名 `orderLogisticsStatusUpdater`）。本卡的生产实现用 `@Component`（bean 名
  `orderLogisticsStatusUpdaterImpl`，与前者不同名，故不触发同名覆盖）+ **`@Primary`**：黑盒
  上下文里该类型有两个候选，Spring 规范保证 @Primary 者确定性胜出注入 `ShipmentService`，
  harness bean 保持注册但不被注入——无 `NoUniqueBeanDefinitionException`、无需动 harness。
  每个黑盒用例都以 harness 配置启动完整上下文，因此本批 ratchet 全绿即共存被逐例实证。
- **容错语义（第二根基）**：推进服务**绝不抛出**。四个调用点都在物流事务内，订单不存在、或当前
  状态不允许该迁移（如用户已发起取消审核 `CANCEL_REVIEWING`、已退款 `REFUNDING`，而仓库仍在
  作业）属于正常竞态，log warn + 静默跳过——物流端点不能因订单状态竞态而 500（与 EVT-B2 送达
  监听器的容忍范式一致）。合法性校验全部用 `OrderStateMachine.canTransition(...)`（布尔），
  **绝不用会抛异常的 `validateTransition`**。已是目标态/已越过目标态 → 幂等跳过。推进沿
  `PAID→PICKING→SHIPPED` 链逐跳校验（与 EVT-B2 链式校验同范式），跳跃到达（如 `PAID` 时直接
  收到 `OUTBOUND`）也要每跳合法才落最终态。
- **执行顺序**：三个新文件**无任何前置批次依赖**（不用 B13 的 common 事件类；依赖的
  `OrderStateMachine`、`OrderService.recordEvent(6参)`、`OrderRepository`、logistics 端口接口、
  app 模块对 order+logistics 的 pom 依赖全部基线已有，`com.ecommerce.app.integration` 是全新
  包）。B14 时点 order（B03/B04）与 app（B12）批均已固化，单批原子落地即可。送达监听器
  （EVT-B2，B16）的目标代码已内建"订单可能已被本卡推进到 PICKING/SHIPPED"的起点分支，两卡
  按批次表顺序执行即自洽；B14→B16 之间的中间态公开链路已验证安全（评价创建在 B17 之前不校验
  订单状态，PUB-107 只断言发货单状态非空）。
- **改法**：三个新文件全文如下，逐字落地。

  1. 新增 `code/ecommerce-order/src/main/java/com/ecommerce/order/service/OrderLogisticsStatusService.java`
  （order 模块内聚服务，只依赖本模块类，对 logistics 零感知）：

  ```java
  package com.ecommerce.order.service;

  import com.ecommerce.order.entity.Order;
  import com.ecommerce.order.entity.OrderStatus;
  import com.ecommerce.order.repository.OrderRepository;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Service;
  import org.springframework.transaction.annotation.Transactional;

  import java.util.List;

  /**
   * Advances an order's fulfilment status when the logistics module reports a
   * shipment status change (design-docs/11 §3: "物流状态变更后，必须通过
   * OrderLogisticsStatusUpdater 更新对应订单的物流状态").
   *
   * <p>This service is the order-module half of that contract: it maps the
   * logistics-side {@code ShipmentStatus} string onto the order lifecycle
   * (design-docs/08 §2) and applies the transition through the
   * {@link OrderStateMachine}:
   *
   * <ul>
   *   <li>{@code PICKING} → order {@code PICKING} (拣货中)</li>
   *   <li>{@code OUTBOUND} / {@code COLLECTED} / {@code IN_TRANSIT} → order
   *       {@code SHIPPED} (已发货 — the parcel has left the warehouse)</li>
   *   <li>{@code CREATED} / {@code LABEL_PRINTED} / {@code EXCEPTION} — no
   *       order-side progression (label printing keeps the order 拣货中;
   *       a carrier exception does not move the order lifecycle)</li>
   *   <li>{@code DELIVERED} — intentionally NOT handled here. Delivery is
   *       propagated by the shared {@code ShipmentDeliveredEvent} and applied by
   *       {@code ShipmentDeliveredEventListener} (design-docs/附录D §4), which
   *       stays the single authoritative DELIVERED writer.</li>
   * </ul>
   *
   * <p><b>Tolerance semantics — this method never throws.</b> It is invoked
   * inside the logistics transaction (pick / print-label / outbound / carrier
   * callback); a missing order or a status race (e.g. the order moved to
   * CANCEL_REVIEWING or REFUNDING while the warehouse kept working) must not
   * 500 the logistics endpoint. Such cases are logged at WARN and skipped —
   * the same tolerance paradigm as {@code ShipmentDeliveredEventListener}.
   * Hops are checked with {@link OrderStateMachine#canTransition} (boolean),
   * never the throwing validator. An order already at or past the target
   * status is an idempotent no-op.
   *
   * <p>Runs in the caller's transaction (default REQUIRED) so the order-status
   * write commits atomically with the shipment-status write that triggered it.
   */
  @Service
  public class OrderLogisticsStatusService {

      private static final Logger log = LoggerFactory.getLogger(OrderLogisticsStatusService.class);

      /**
       * The forward fulfilment chain a paid order walks (design-docs/08 §2).
       * A logistics update may only advance the order along this chain; every
       * hop is still validated against the {@link OrderStateMachine}.
       */
      private static final List<OrderStatus> FULFILMENT_CHAIN =
              List.of(OrderStatus.PAID, OrderStatus.PICKING, OrderStatus.SHIPPED);

      private final OrderRepository orderRepository;
      private final OrderStateMachine stateMachine;
      private final OrderService orderService;

      public OrderLogisticsStatusService(OrderRepository orderRepository,
                                         OrderStateMachine stateMachine,
                                         OrderService orderService) {
          this.orderRepository = orderRepository;
          this.stateMachine = stateMachine;
          this.orderService = orderService;
      }

      /**
       * Apply a logistics-side shipment status to the owning order.
       *
       * @param orderId        the order the shipment belongs to
       * @param shipmentStatus the logistics status name as reported by the
       *                       logistics module (a {@code ShipmentStatus} name)
       */
      @Transactional
      public void applyShipmentStatus(Long orderId, String shipmentStatus) {
          try {
              OrderStatus target = mapToOrderStatus(shipmentStatus);
              if (target == null) {
                  log.debug("Logistics status {} has no order-side progression, orderId={}",
                          shipmentStatus, orderId);
                  return;
              }
              if (orderId == null) {
                  log.warn("Logistics status {} reported without an orderId, skipping", shipmentStatus);
                  return;
              }

              Order order = orderRepository.findById(orderId).orElse(null);
              if (order == null) {
                  log.warn("Logistics status {} for unknown orderId={}, skipping", shipmentStatus, orderId);
                  return;
              }

              OrderStatus from = order.getStatus();
              if (from == target) {
                  return; // idempotent — already at the target status
              }

              int fromIdx = FULFILMENT_CHAIN.indexOf(from);
              int targetIdx = FULFILMENT_CHAIN.indexOf(target);
              if (fromIdx < 0) {
                  if (from == OrderStatus.DELIVERED || from == OrderStatus.COMPLETED
                          || from == OrderStatus.REFUNDING || from == OrderStatus.REFUNDED) {
                      // Late/replayed logistics event after delivery — idempotent no-op.
                      log.debug("Order {} already past fulfilment (status={}), ignoring logistics status {}",
                              orderId, from, shipmentStatus);
                  } else {
                      // e.g. CANCEL_REVIEWING / CANCELLED / CLOSED race with the warehouse.
                      log.warn("Order {} in status {} is not eligible for logistics progression to {}, skipping",
                              orderId, from, target);
                  }
                  return;
              }
              if (fromIdx > targetIdx) {
                  return; // idempotent — already past the target status
              }

              // Validate every hop of the chain (e.g. PAID→PICKING→SHIPPED) instead
              // of jumping — same paradigm as ShipmentDeliveredEventListener.
              for (int i = fromIdx; i < targetIdx; i++) {
                  OrderStatus hopFrom = FULFILMENT_CHAIN.get(i);
                  OrderStatus hopTo = FULFILMENT_CHAIN.get(i + 1);
                  if (!stateMachine.canTransition(hopFrom, hopTo)) {
                      log.warn("Order {} cannot advance {} -> {} (hop {} -> {} not allowed), skipping",
                              orderId, from, target, hopFrom, hopTo);
                      return;
                  }
              }

              order.setStatus(target);
              orderRepository.save(order);

              orderService.recordEvent(orderId, from, target, target.name(), "LOGISTICS_SYSTEM",
                      "Logistics status sync: " + shipmentStatus);

              log.info("Order {} advanced {} -> {} on logistics status {}",
                      orderId, from, target, shipmentStatus);
          } catch (Exception e) {
              // Never propagate: the logistics flow must not fail because the
              // order could not be advanced (design-docs/02 §5 tolerance).
              log.warn("Failed to apply logistics status {} to order {}: {}",
                      shipmentStatus, orderId, e.getMessage(), e);
          }
      }

      /**
       * Map a logistics {@code ShipmentStatus} name to the order status it
       * implies, or {@code null} when the order lifecycle is unaffected.
       */
      private OrderStatus mapToOrderStatus(String shipmentStatus) {
          if (shipmentStatus == null) {
              return null;
          }
          switch (shipmentStatus.toUpperCase()) {
              case "PICKING":
                  return OrderStatus.PICKING;
              case "OUTBOUND":
              case "COLLECTED":
              case "IN_TRANSIT":
                  return OrderStatus.SHIPPED;
              default:
                  // CREATED, LABEL_PRINTED, DELIVERED (event-driven), EXCEPTION, unknown
                  return null;
          }
      }
  }
  ```

  `OrderService.recordEvent(Long, OrderStatus, OrderStatus, String, String, String)` 6 参方法与
  `OrderStateMachine.canTransition(...)` 基线均已存在，无需新建或改签名。

  2. 新增 `code/ecommerce-app/src/main/java/com/ecommerce/app/integration/OrderLogisticsStatusUpdaterImpl.java`
  （`integration` 是全新包，直接建目录）：

  ```java
  package com.ecommerce.app.integration;

  import com.ecommerce.logistics.query.OrderLogisticsStatusUpdater;
  import com.ecommerce.order.service.OrderLogisticsStatusService;
  import org.springframework.context.annotation.Primary;
  import org.springframework.stereotype.Component;

  /**
   * Production implementation of the logistics module's
   * {@link OrderLogisticsStatusUpdater} port (design-docs/11 §3: "物流状态变更后，
   * 必须通过 OrderLogisticsStatusUpdater 更新对应订单的物流状态"). Delegates to the
   * order module's {@link OrderLogisticsStatusService}, which maps the shipment
   * status onto the order lifecycle through the order state machine.
   *
   * <p><b>Why this lives in ecommerce-app:</b> the port interface is declared in
   * {@code com.ecommerce.logistics.query}, but the behaviour belongs to the order
   * module — and ecommerce-logistics already depends on ecommerce-order at the
   * Maven level, so an implementation inside ecommerce-order would require an
   * order→logistics dependency and create a module cycle (design-docs/02 §2 has
   * no order→logistics edge). The app module is the composition root that sees
   * both modules, so the adapter is wired here.
   *
   * <p><b>Why {@code @Primary}:</b> the frozen black-box harness
   * ({@code BlackboxHarnessConfig} in test-cases, which must not be modified)
   * registers an unqualified no-op {@code OrderLogisticsStatusUpdater}
   * {@code @Bean}. With this production bean present there are two candidates of
   * the type; {@code @Primary} makes this one deterministically win type-based
   * injection into {@code ShipmentService} (Spring core semantics), while the
   * harness bean stays registered but un-injected — no
   * {@code NoUniqueBeanDefinitionException}, no harness change. Removing
   * {@code @Primary}, or adding a second {@code @Primary} candidate of this
   * type, would break every black-box test with an ambiguous-bean failure.
   *
   * <p>Never throws: the delegate swallows and logs all failures, because the
   * logistics endpoints must not 500 on an order-status race (e.g. an order
   * already in CANCEL_REVIEWING when the warehouse picks).
   */
  @Component
  @Primary
  public class OrderLogisticsStatusUpdaterImpl implements OrderLogisticsStatusUpdater {

      private final OrderLogisticsStatusService orderLogisticsStatusService;

      public OrderLogisticsStatusUpdaterImpl(OrderLogisticsStatusService orderLogisticsStatusService) {
          this.orderLogisticsStatusService = orderLogisticsStatusService;
      }

      @Override
      public void updateLogisticsStatus(Long orderId, String logisticsStatus) {
          orderLogisticsStatusService.applyShipmentStatus(orderId, logisticsStatus);
      }
  }
  ```

  3. 新增单测 `code/ecommerce-order/src/test/java/com/ecommerce/order/service/OrderLogisticsStatusServiceTest.java`
  （用**真实** `OrderStateMachine`（零依赖组件）+ mock 仓储，锁死三分支语义；作者侧 14 例全绿）：

  ```java
  package com.ecommerce.order.service;

  import com.ecommerce.order.entity.Order;
  import com.ecommerce.order.entity.OrderStatus;
  import com.ecommerce.order.repository.OrderRepository;
  import org.junit.jupiter.api.BeforeEach;
  import org.junit.jupiter.api.DisplayName;
  import org.junit.jupiter.api.Nested;
  import org.junit.jupiter.api.Test;
  import org.junit.jupiter.api.extension.ExtendWith;
  import org.mockito.Mock;
  import org.mockito.junit.jupiter.MockitoExtension;

  import java.util.Optional;

  import static org.assertj.core.api.Assertions.assertThat;
  import static org.assertj.core.api.Assertions.assertThatCode;
  import static org.mockito.ArgumentMatchers.any;
  import static org.mockito.ArgumentMatchers.anyLong;
  import static org.mockito.ArgumentMatchers.eq;
  import static org.mockito.Mockito.never;
  import static org.mockito.Mockito.verify;
  import static org.mockito.Mockito.verifyNoInteractions;
  import static org.mockito.Mockito.when;

  /**
   * Tests for {@link OrderLogisticsStatusService} — the order-module half of the
   * design-docs/11 §3 contract ("物流状态变更后，必须通过 OrderLogisticsStatusUpdater
   * 更新对应订单的物流状态").
   *
   * <p>Uses the real {@link OrderStateMachine} so the legal/illegal edges under
   * test are the production ones.
   */
  @ExtendWith(MockitoExtension.class)
  @DisplayName("OrderLogisticsStatusService")
  class OrderLogisticsStatusServiceTest {

      @Mock
      private OrderRepository orderRepository;

      @Mock
      private OrderService orderService;

      private OrderLogisticsStatusService service;

      @BeforeEach
      void setUp() {
          service = new OrderLogisticsStatusService(
                  orderRepository, new OrderStateMachine(), orderService);
      }

      private Order order(Long id, OrderStatus status) {
          Order order = new Order();
          order.setId(id);
          order.setStatus(status);
          return order;
      }

      @Nested
      @DisplayName("legal progression")
      class LegalProgression {

          @Test
          @DisplayName("PICKING shipment status advances a PAID order to PICKING")
          void paidToPicking() {
              Order order = order(1L, OrderStatus.PAID);
              when(orderRepository.findById(1L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(1L, "PICKING");

              assertThat(order.getStatus()).isEqualTo(OrderStatus.PICKING);
              verify(orderRepository).save(order);
              verify(orderService).recordEvent(eq(1L), eq(OrderStatus.PAID), eq(OrderStatus.PICKING),
                      eq("PICKING"), eq("LOGISTICS_SYSTEM"), any());
          }

          @Test
          @DisplayName("OUTBOUND shipment status advances a PICKING order to SHIPPED")
          void pickingToShipped() {
              Order order = order(2L, OrderStatus.PICKING);
              when(orderRepository.findById(2L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(2L, "OUTBOUND");

              assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
              verify(orderRepository).save(order);
              verify(orderService).recordEvent(eq(2L), eq(OrderStatus.PICKING), eq(OrderStatus.SHIPPED),
                      eq("SHIPPED"), eq("LOGISTICS_SYSTEM"), any());
          }

          @Test
          @DisplayName("OUTBOUND from PAID chains the PAID→PICKING→SHIPPED hops")
          void paidToShippedChainsHops() {
              Order order = order(3L, OrderStatus.PAID);
              when(orderRepository.findById(3L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(3L, "OUTBOUND");

              assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
              verify(orderRepository).save(order);
          }

          @Test
          @DisplayName("carrier COLLECTED / IN_TRANSIT map to SHIPPED")
          void carrierStatusesMapToShipped() {
              Order order = order(4L, OrderStatus.PICKING);
              when(orderRepository.findById(4L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(4L, "COLLECTED");

              assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
          }
      }

      @Nested
      @DisplayName("illegal transition is skipped silently")
      class IllegalTransition {

          @Test
          @DisplayName("order in CANCEL_REVIEWING is not advanced and nothing is thrown")
          void cancelReviewingIsSkipped() {
              Order order = order(10L, OrderStatus.CANCEL_REVIEWING);
              when(orderRepository.findById(10L)).thenReturn(Optional.of(order));

              assertThatCode(() -> service.applyShipmentStatus(10L, "PICKING"))
                      .doesNotThrowAnyException();

              assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCEL_REVIEWING);
              verify(orderRepository, never()).save(any());
              verifyNoInteractions(orderService);
          }

          @Test
          @DisplayName("order in CANCELLED is not advanced")
          void cancelledIsSkipped() {
              Order order = order(11L, OrderStatus.CANCELLED);
              when(orderRepository.findById(11L)).thenReturn(Optional.of(order));

              assertThatCode(() -> service.applyShipmentStatus(11L, "OUTBOUND"))
                      .doesNotThrowAnyException();

              assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
              verify(orderRepository, never()).save(any());
          }

          @Test
          @DisplayName("unknown order is skipped without throwing")
          void unknownOrderIsSkipped() {
              when(orderRepository.findById(99L)).thenReturn(Optional.empty());

              assertThatCode(() -> service.applyShipmentStatus(99L, "PICKING"))
                      .doesNotThrowAnyException();

              verify(orderRepository, never()).save(any());
          }

          @Test
          @DisplayName("repository failure is swallowed, never propagated to logistics")
          void repositoryFailureIsSwallowed() {
              when(orderRepository.findById(anyLong()))
                      .thenThrow(new RuntimeException("db down"));

              assertThatCode(() -> service.applyShipmentStatus(12L, "PICKING"))
                      .doesNotThrowAnyException();
          }
      }

      @Nested
      @DisplayName("idempotency")
      class Idempotency {

          @Test
          @DisplayName("order already at the target status is a no-op")
          void alreadyAtTarget() {
              Order order = order(20L, OrderStatus.PICKING);
              when(orderRepository.findById(20L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(20L, "PICKING");

              verify(orderRepository, never()).save(any());
              verifyNoInteractions(orderService);
          }

          @Test
          @DisplayName("order already past the target status is a no-op (no regression)")
          void alreadyPastTarget() {
              Order order = order(21L, OrderStatus.SHIPPED);
              when(orderRepository.findById(21L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(21L, "PICKING");

              assertThat(order.getStatus()).isEqualTo(OrderStatus.SHIPPED);
              verify(orderRepository, never()).save(any());
          }

          @Test
          @DisplayName("late carrier event after delivery is ignored")
          void deliveredOrderIgnoresLateEvents() {
              Order order = order(22L, OrderStatus.DELIVERED);
              when(orderRepository.findById(22L)).thenReturn(Optional.of(order));

              service.applyShipmentStatus(22L, "IN_TRANSIT");

              assertThat(order.getStatus()).isEqualTo(OrderStatus.DELIVERED);
              verify(orderRepository, never()).save(any());
          }
      }

      @Nested
      @DisplayName("statuses without order-side progression")
      class NoProgressionStatuses {

          @Test
          @DisplayName("LABEL_PRINTED does not touch the order")
          void labelPrintedIsNoOp() {
              service.applyShipmentStatus(30L, "LABEL_PRINTED");
              verifyNoInteractions(orderRepository, orderService);
          }

          @Test
          @DisplayName("DELIVERED is left to ShipmentDeliveredEventListener")
          void deliveredIsNoOpHere() {
              service.applyShipmentStatus(31L, "DELIVERED");
              verifyNoInteractions(orderRepository, orderService);
          }

          @Test
          @DisplayName("EXCEPTION and null do not touch the order")
          void exceptionAndNullAreNoOps() {
              service.applyShipmentStatus(32L, "EXCEPTION");
              service.applyShipmentStatus(32L, null);
              verifyNoInteractions(orderRepository, orderService);
          }
      }
  }
  ```

- **验收**：
  - `mvn ... -f code/pom.xml -pl ecommerce-order -Dtest=OrderLogisticsStatusServiceTest surefire:test`
    14/14 全绿；`-pl ecommerce-app test` 上下文照常加载（`ShopHubApplicationTest` 的 `@MockBean`
    与 @Primary 兼容：Spring Boot 的 MockitoPostProcessor 对多候选类型按 primary 消歧后替换）。
  - 黑盒链路 pay → pick 后 `GET /api/v1/orders/{id}` 状态为 `PICKING`；outbound 后为 `SHIPPED`；
    DELIVERED 回调后（B16 就位时）为 `DELIVERED`。作者侧完整公开套件 24/24 全绿，日志可见
    `Order N advanced PAID -> PICKING on logistics status PICKING`、`PICKING -> SHIPPED on
    logistics status OUTBOUND`，且送达监听器日志 `marked DELIVERED ... (from SHIPPED)`。
  - 独立启动生产入口成功（基线起不来，本卡附带修复）：
    `mvn ... -pl ecommerce-app spring-boot:run` 出现 `Started ShopHubApplication`。
- **勿犯**（每条都是已尽调的事故通道，逐条对照后再动手）：
  - **绝不能去掉 `@Primary`**——去掉后黑盒上下文中该类型两个候选无消歧，`ShipmentService` 构造
    注入直接 `NoUniqueBeanDefinitionException`，24 例全灭（findings 旧弃项担心的事故就是这个，
    @Primary 正是破解点）。
  - **绝不能给 harness 的 no-op bean "想办法"**（改名/加 @ConditionalOnMissingBean/删除）——
    `test-cases/` 冻结不可改，任何触碰都是评测红线。
  - **绝不能把实现类放进 `ecommerce-order`**——order 看不见 logistics 的接口（Maven 上
    logistics→order，反向 import 无法编译；强加依赖则成环）。实现只能放 app（组合根）。
  - **绝不能出现第二个 `@Primary` 的同类型 bean**——两个 @Primary 同样是无消歧歧义，等价于没加。
  - **绝不能在本服务里改用 `validateTransition`（会抛）**或让任何异常逃逸——四个调用点在物流
    事务内，逃逸的 RuntimeException 穿过 @Transactional 代理会把外层事务标记 rollback-only，
    即便 `ShipmentService` catch 了也会在提交时 `UnexpectedRollbackException`，物流端点 500。
  - **绝不能在本卡处理 `DELIVERED`**——那是 EVT-B2 送达监听器的单一写权；在这里同步写 DELIVERED
    会与 AFTER_COMMIT 监听器形成双写路径。
