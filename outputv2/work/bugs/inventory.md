# B09 · inventory — 预占/释放/扣减守恒 · 错误码 · 仓库排序

本批覆盖 `ecommerce-inventory` 模块 `findings.md`「inventory 模块（§6.7）」全部 7 项中的 6 项（跳过 #5，
库存人工调整审计日志缺操作者字段——纯审计基础设施接入，归 `S3-audit.md`/B18，不在本批重复），
以及第二轮深审（§7）里 3 项库存相关发现（#21 错误码、#22 仓库排序、#28 release() 遗漏 DEDUCTED 分支）。
#21 的修复面跨到 `ecommerce-cart`（`CartValidationService`），本文件一并列出。

**依赖顺序**：INV-5（并发控制）建立在 INV-1（守恒修复）改完之后的代码之上，**必须**在 INV-1 之后执行；
其余 7 张卡互不依赖，理论上可任意顺序，但建议按下面的编号顺序（贴合 findings.md 原表顺序 + 深审顺序）
逐张执行，每 2~3 卡编译自检一次。

**不做**（连带排查后明确排除，理由见对应位置）：
- §6.7 #5（库存人工调整审计日志缺操作者字段）——纯 S3 审计基础设施接入项，不在本批。
- `PaymentSucceededInventoryListener` 新增及其触发 `deductAfterPayment()`/`reserve()` 的接线——
  这是 S2 事件批（`S2-events.md` §B / B16）的范围；本文件 INV-3 只负责"`deductAfterPayment()`
  被调用时内部该做什么"，不负责"谁来调它"。

---

### INV-1 | reserve() 同时扣减 onHandStock 与增加 reservedStock，库存守恒被破坏（findings §6.7 #1）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
- **现状**: `reserve(Long orderId, List<ReserveItem> items)` 方法内层循环（基线第 44-60 行，具体是第
  54-60 行）在预占的同时把 `onHandStock` 也扣掉了：

  ```java
                  /*
                   * The on-hand stock is decreased here during reservation along with
                   * increasing reservedStock.
                   */
                  stock.setOnHandStock(stock.getOnHandStock() - toReserve);
                  stock.setReservedStock(stock.getReservedStock() + toReserve);
                  inventoryStockRepository.save(stock);
  ```

  `design-docs/06-库存服务设计.md` §2 定义 `availableStock = onHandStock - reservedStock`；§3
  "下单库存处理"明确创建订单只预占库存：`校验库存可用 → 创建 StockReservation → 增加 reservedStock →
  不减少 onHandStock`，只有支付成功后 `deductAfterPayment()` 才真正减 `onHandStock`。当前实现在预占阶段
  就把 `onHandStock` 减了一次，`deductAfterPayment()`（基线第 116 行）支付后对同一批数量的 `onHandStock`
  又减一次——同一批库存被减了两次；而 `release()`（基线第 95 行）只归还 `reservedStock`，从不归还
  `onHandStock`，取消订单后 `onHandStock` 永久性少了 `toReserve` 那么多，货物"凭空消失"。

  代数验证（初始 onHand=200, reserved=0, available=200）：`reserve(40)` 后现状是 onHand=160,
  reserved=40, available=160-40=120（应为 200-40=160，多扣了 40）；此后若 `release()`：reserved 归零，
  但 onHand 仍=160（应恢复 200，永久短少 40，即使订单从未真正发货）。
- **期望**: `reserve()` 只增加 `reservedStock`，不动 `onHandStock`；`onHandStock` 只在
  `deductAfterPayment()`（支付后真实出库）时才减少。依据: `design-docs/06-库存服务设计.md` §2
  （`availableStock = onHandStock - reservedStock`）+ §3（下单库存处理："增加 reservedStock →
  不减少 onHandStock"）。
- **改法**: 删除第 54-58 行的注释块和 `onHandStock` 那一行，只保留 `reservedStock` 那一行和 `save`：

  原：
  ```java
                  /*
                   * The on-hand stock is decreased here during reservation along with
                   * increasing reservedStock.
                   */
                  stock.setOnHandStock(stock.getOnHandStock() - toReserve);
                  stock.setReservedStock(stock.getReservedStock() + toReserve);
                  inventoryStockRepository.save(stock);
  ```

  改为：
  ```java
                  // Reservation only ever increments reservedStock. onHandStock is
                  // physical stock on the shelf and must stay untouched until
                  // deductAfterPayment() actually ships it (design-docs/06 §3):
                  //   校验库存可用 -> 创建 StockReservation -> 增加 reservedStock -> 不减少 onHandStock
                  stock.setReservedStock(stock.getReservedStock() + toReserve);
                  inventoryStockRepository.save(stock);
  ```

  只改这一处；本方法其余部分（含第 74-77 行"库存不足抛异常"分支）不动——错误码改名是 INV-7 的范围，
  此处保留原 `"INSUFFICIENT_STOCK"` 字符串不动。`deductAfterPayment()`（基线第 104-125 行）与
  `release()`（基线第 84-102 行）本卡不动，分别是 INV-3/INV-9 的范围。

  注：本卡改完后 `inventoryStockRepository.save()` 仍是普通 `save`（非 `saveAndFlush`）；把它升级为
  带乐观锁重试的 `saveAndFlush` 是 INV-5（并发控制）的范围，**INV-5 建立在本卡结果之上，必须在本卡
  之后执行**。
- **验收**: 库存守恒关系——初始 onHand=200, reserved=0：调用 `reserve(orderId, [sku:40])` 后
  onHand=200（不变），reserved=40，availableStock=onHand-reserved=160（改前是 120）。单测层面：
  `InventoryReservationServiceImplTest` 里 `testReserve_decreasesOnHandStock`/
  `testReserve_multipleWarehouses`/`testEmptyStock_isSkipped`/`testFullLifecycle_reserveDeductRelease`
  等断言"onHand 被扣减"的用例需要同步改成断言 onHand 不变、reserved 增加（`code/` 下单测不计分，可
  直接改，但别留红）。`grep -n "setOnHandStock" code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
  在本卡改完、INV-3/INV-9 都还没做之前应该零命中（`deductAfterPayment` 里的那一行也没动过，本来就在，
  不受本卡影响）。

---

### INV-2 | checkAvailability 边界判断用 `>` 应为 `>=`（findings §6.7 #2）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/query/InventoryQueryService.java`
     （仅 javadoc 注释同步，非行为改动）
- **现状**: `checkAvailability(Long skuId, int quantity)`（`InventoryService.java` 基线第 70-80 行，
  具体第 75 行）：

  ```java
          boolean available = totalAvailable > quantity;
  ```

  `design-docs/06-库存服务设计.md` §2 明确"当 `availableStock >= requestQuantity` 时库存充足"。当前用
  严格大于，`requested == available` 这个边界会被误判为不足——例如库存刚好等于购买数量时，
  `POST /api/v1/inventory/check` 返回 `available:false`，任何跨模块经 `InventoryQueryService.checkAvailability`
  查询库存是否够用的调用方（cart/order 等）都会拿到错误结果。接口 `query/InventoryQueryService.java` 的
  javadoc（基线第 26 行）也错误地写着"Returns true when available stock is strictly greater than the
  requested quantity"，与设计文档矛盾还倒过来给这个错误行为背书。
- **期望**: `availableStock >= requestQuantity` 时判定为充足（大于等于，非严格大于）。依据:
  `design-docs/06-库存服务设计.md` §2。
- **改法**:
  1. `InventoryService.java` 第 75 行：
     ```java
             boolean available = totalAvailable > quantity;
     ```
     改为
     ```java
             boolean available = totalAvailable >= quantity;
     ```
  2. `query/InventoryQueryService.java` 第 26 行的 javadoc 同步改成准确描述（纯注释，不影响编译）：
     原：
     ```java
          * Returns true when available stock is strictly greater than the requested quantity.
     ```
     改为：
     ```java
          * Available when availableStock &gt;= requestQuantity (design-docs/06 section 2).
     ```
  只改这两处，**不要动** `CartValidationService.validateStock()`——它是走 `getStockSummary()` 自己做
  `stock.getAvailableStock() < quantity` 判断（等价于 `>=` 才算够，边界逻辑本来就对），与本卡无关。
- **验收**: `checkAvailability(skuId, N)`，当该 SKU 总 `availableStock` 恰好等于 `N` 时返回 `true`
  （改前为 `false`）；`POST /api/v1/inventory/check` 请求体 `quantity` 等于当前可用库存时，响应
  `available:true`。`InventoryServiceTest` 里原 `testCheckAvailability_exactMatch_returnsUnavailable`
  需要同步改断言方向（`code/` 单测不计分但别留红）。

---

### INV-3 | deductAfterPayment() 支付后扣减库存从不生成 OutboundOrder（findings §6.7 #3）

- 风险: high（构造函数签名变更 + 新增代码块） · 置信度: definite
- **文件**: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
- **现状**: `deductAfterPayment(Long orderId)`（基线第 104-125 行）扣减 `onHandStock`/`reservedStock`、
  把预占记录状态置 `DEDUCTED` 后就结束，全程不创建任何 `OutboundOrder`：

  ```java
      @Override
      @Transactional
      public void deductAfterPayment(Long orderId) {
          List<StockReservation> reservations = stockReservationRepository
                  .findByOrderIdAndStatus(orderId, ReservationStatus.RESERVED);

          for (StockReservation reservation : reservations) {
              InventoryStock stock = inventoryStockRepository
                      .findByWarehouseIdAndSkuId(reservation.getWarehouseId(), reservation.getSkuId())
                      .orElseThrow(() -> new ResourceNotFoundException(
                              "InventoryStock not found for deduction"));

              stock.setOnHandStock(stock.getOnHandStock() - reservation.getQuantity());
              stock.setReservedStock(stock.getReservedStock() - reservation.getQuantity());
              inventoryStockRepository.save(stock);

              reservation.setStatus(ReservationStatus.DEDUCTED);
              stockReservationRepository.save(reservation);
          }
          log.info("Stock deducted after payment for orderId={}, reservationsCount={}",
                  orderId, reservations.size());
      }
  ```

  `design-docs/06-库存服务设计.md` §3"支付成功后扣减库存"流程明确第 4 步是"生成 OutboundOrder"，与
  `InventoryService.outbound()`（手工出库）对称——手工出库会建 `OutboundOrder`，支付后自动扣减却不建，
  同一实体在两条路径上行为不一致，出库单据缺失。

  **范围提醒**：谁调用 `deductAfterPayment()` 是另一批（S2 事件批 `S2-events.md` §B / B16，新增
  `PaymentSucceededInventoryListener`）的范围，不属于本卡；本卡只负责"这个方法被调用时内部该做什么"，
  用直接调用 `reservationService.deductAfterPayment(orderId)`（如现有单测）即可验证，与调用方是谁无关。
- **期望**: 支付后扣减库存时，为每条被扣减的预占记录生成一条 `status=COMPLETED` 的 `OutboundOrder`。
  依据: `design-docs/06-库存服务设计.md` §3（"支付成功后扣减库存...生成 OutboundOrder"）。
- **改法**:
  1. 文件顶部 import 区加：
     ```java
     import com.ecommerce.inventory.entity.OutboundOrder;
     import com.ecommerce.inventory.repository.OutboundOrderRepository;
     import java.time.format.DateTimeFormatter;
     ```
     （`LocalDateTime` 已有 import，不用重复加。）
  2. 加字段 + 改构造函数：

     原：
     ```java
         private final InventoryStockRepository inventoryStockRepository;
         private final StockReservationRepository stockReservationRepository;

         public InventoryReservationServiceImpl(InventoryStockRepository inventoryStockRepository,
                                                StockReservationRepository stockReservationRepository) {
             this.inventoryStockRepository = inventoryStockRepository;
             this.stockReservationRepository = stockReservationRepository;
         }
     ```

     改为：
     ```java
         private final InventoryStockRepository inventoryStockRepository;
         private final StockReservationRepository stockReservationRepository;
         private final OutboundOrderRepository outboundOrderRepository;

         public InventoryReservationServiceImpl(InventoryStockRepository inventoryStockRepository,
                                                StockReservationRepository stockReservationRepository,
                                                OutboundOrderRepository outboundOrderRepository) {
             this.inventoryStockRepository = inventoryStockRepository;
             this.stockReservationRepository = stockReservationRepository;
             this.outboundOrderRepository = outboundOrderRepository;
         }
     ```

     `OutboundOrderRepository` 是已有接口（`repository/OutboundOrderRepository.java`，
     `extends JpaRepository<OutboundOrder, Long>`），不用新建、不用加方法。这是唯一一个实现它的 Spring
     bean，构造函数注入没有歧义。
  3. 在 `deductAfterPayment()` 循环体内、`stockReservationRepository.save(reservation);` 之后追加：
     ```java
             // design-docs/06 §3: 支付成功后扣减库存 ... -> 生成 OutboundOrder.
             // Mirrors InventoryService.outbound()'s manual-outbound field set exactly.
             OutboundOrder outboundOrder = new OutboundOrder();
             outboundOrder.setOrderNo("OB" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss")));
             outboundOrder.setWarehouseId(reservation.getWarehouseId());
             outboundOrder.setSkuId(reservation.getSkuId());
             outboundOrder.setQuantity(reservation.getQuantity());
             outboundOrder.setOrderId(orderId);
             outboundOrder.setStatus("COMPLETED");
             outboundOrderRepository.save(outboundOrder);
     ```
- **勿犯**:
  1. 构造函数从 2 参数变 3 参数——这是单构造函数 `@Service`，Spring 会自动按类型注入新参数，生产代码
     没有任何地方手写 `new InventoryReservationServiceImpl(...)`（已用 `grep` 确认零命中），不会
     破坏生产装配；但 `InventoryReservationServiceImplTest` 用 Mockito `@Mock`/`@InjectMocks`，务必同步
     在该测试类加一行 `@Mock private OutboundOrderRepository outboundOrderRepo;`（字段名任意，类型必须
     对），否则 Mockito 会用 `null` 填充第三个构造参数，测试跑到 `deductAfterPayment` 时会 NPE——
     `@InjectMocks` 靠反射，构造函数多一个参数不会导致**编译**失败（`mvn install -DskipTests` 仍会编译
     test 源码但跳过执行），只是该类原有断言 `deductAfterPayment` 的用例会因为 NPE 变红，按 S1 系列的
     先例应顺手把 mock 加上避免留红。
  2. `outboundOrder.setOrderNo(...)` 的格式必须与 `InventoryService.outbound()` 完全一致——`"OB" +
     yyyyMMddHHmmss`（出库都用 `"OB"` 前缀，入库是 `"IB"`，见 `InventoryService.inbound()`，不要抄错）。
  3. 不要把这条新增逻辑放到 `release()` 或 `reserve()` 里——只在 `deductAfterPayment()` 内，且在循环体
     里对每条 reservation 各建一条（不是循环外汇总建一条）。
- **验收**: 直接调用 `reservationService.deductAfterPayment(orderId)`（预置 1 条 `RESERVED` 状态、
  `quantity=40` 的 reservation），断言 `outboundOrderRepository.save(...)` 恰好被调用 1 次，捕获的
  `OutboundOrder` 满足：`warehouseId`/`skuId`/`quantity=40`/`orderId` 与 reservation 一致，
  `status="COMPLETED"`，`orderNo` 以 `"OB"` 开头。同一 orderId 下 2 条不同 SKU 的 reservation 应生成
  2 条 `OutboundOrder`（不是 1 条）。

---

### INV-4 | 库存摘要查询无 30 秒缓存（findings §6.7 #4）

- 风险: high（新增类 + 3 个既有文件的方法级注解，且涉及 Spring `CacheManager` bean 命名冲突风险）
  · 置信度: definite
- **文件**:
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/config/InventoryCacheConfig.java`
     【新增】
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
  3. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
  4. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/StockAdjustmentService.java`
- **现状**: `InventoryService`（及库存模块其余类）完全没有缓存——`getStockSummary(Long skuId)`
  （`InventoryQueryService` 接口实现，`InventoryService.java` 第 60-64 行左右）每次调用都直接查库；
  `design-docs/02-系统架构.md` §7 缓存策略表明确列了"库存摘要 | `inventory:summary:{skuId}` | 30 秒 |
  inventory"这一条（与购物车 7 天、商品详情 10 分钟、运费模板 30 分钟并列），本模块是唯一一个完全没有
  实现自己那条缓存契约的。
- **期望**: `InventoryQueryService.getStockSummary(Long skuId)` 的返回结果按 `skuId` 缓存 30 秒；任何
  会改变库存数量的写操作（预占/释放/支付扣减/入库/手工出库/人工调整）必须清空该缓存，否则"改库存后
  立即查询必须看到新值"的用例会因为脏缓存失败。依据: `design-docs/02-系统架构.md` §7（缓存策略表）。
- **改法**:
  1. **新建** `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/config/InventoryCacheConfig.java`：
     ```java
     package com.ecommerce.inventory.config;

     import com.github.benmanes.caffeine.cache.Caffeine;
     import org.springframework.cache.CacheManager;
     import org.springframework.cache.annotation.EnableCaching;
     import org.springframework.cache.caffeine.CaffeineCacheManager;
     import org.springframework.context.annotation.Bean;
     import org.springframework.context.annotation.Configuration;

     import java.time.Duration;
     import java.util.List;

     @Configuration
     @EnableCaching
     public class InventoryCacheConfig {

         private static final Duration STOCK_SUMMARY_TTL = Duration.ofSeconds(30);
         private static final long MAX_CACHE_ENTRIES = 10_000;

         @Bean
         public CacheManager inventoryCacheManager() {
             CaffeineCacheManager cacheManager = new CaffeineCacheManager();
             cacheManager.setCacheNames(List.of(com.ecommerce.inventory.service.InventoryService.INVENTORY_SUMMARY_CACHE));
             cacheManager.setCaffeine(Caffeine.newBuilder()
                     .expireAfterWrite(STOCK_SUMMARY_TTL)
                     .maximumSize(MAX_CACHE_ENTRIES)
                     .recordStats());
             return cacheManager;
         }
     }
     ```
     不用改任何 `pom.xml`：`spring-boot-starter-cache` 与 `caffeine` 已在 `ecommerce-common/pom.xml`
     声明，`ecommerce-inventory` 依赖 `ecommerce-common`，两个包在编译期已可见。
  2. **`InventoryService.java`**——加两个 import：
     ```java
     import org.springframework.cache.annotation.CacheEvict;
     import org.springframework.cache.annotation.Cacheable;
     ```
     加缓存名常量（class 字段区任意位置）：
     ```java
         public static final String INVENTORY_SUMMARY_CACHE = "inventory:summary";
     ```
     `getStockSummary` 方法的 `@Override` 上方加一行：
     ```java
         @Override
         @Cacheable(cacheNames = INVENTORY_SUMMARY_CACHE, key = "#skuId", cacheManager = "inventoryCacheManager")
         @Transactional(readOnly = true)
         public StockSummaryDto getStockSummary(Long skuId) {
     ```
     `inbound(...)` 和 `outbound(...)`（写操作）各自 `@Transactional` 上方加：
     ```java
         @CacheEvict(cacheNames = INVENTORY_SUMMARY_CACHE, allEntries = true, cacheManager = "inventoryCacheManager")
         @Transactional
         public InventoryStock inbound(InboundRequest request) {
     ```
     ```java
         @CacheEvict(cacheNames = INVENTORY_SUMMARY_CACHE, allEntries = true, cacheManager = "inventoryCacheManager")
         @Transactional
         public InventoryStock outbound(Long warehouseId, Long skuId, int quantity, Long orderId) {
     ```
     **不要**给 `getStockSummaryResponse(Long skuId)`（`GET /api/v1/inventory/sku/{skuId}` 用的业务方法，
     带两条 `FaultInjectionRegistry.isActive(...)` 检查）加 `@Cacheable`——见"勿犯"第 2 条。
     `checkAvailability`/`listAvailableWarehouses`/`checkAndReport` 也不缓存（design-docs 只对"库存
     摘要"一项承诺缓存）。
  3. **`InventoryReservationServiceImpl.java`**——加 import：
     ```java
     import org.springframework.cache.annotation.CacheEvict;
     ```
     `reserve`/`release`/`deductAfterPayment` 三个 `@Override` 方法各自在 `@Override` 和 `@Transactional`
     之间插入：
     ```java
         @CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true,
                 cacheManager = "inventoryCacheManager")
     ```
     `InventoryService` 与本类同包 `com.ecommerce.inventory.service`，不需要额外 import。
  4. **`StockAdjustmentService.java`**——加 import：
     ```java
     import org.springframework.cache.annotation.CacheEvict;
     ```
     `create(Long warehouseId, Long skuId, int afterQty, String reason)`（4 参数版本）的 `@Transactional`
     上方加：
     ```java
         @CacheEvict(cacheNames = InventoryService.INVENTORY_SUMMARY_CACHE, allEntries = true,
                 cacheManager = "inventoryCacheManager")
         @Transactional
         public StockAdjustment create(Long warehouseId, Long skuId, int afterQty, String reason) {
     ```
     只加这一个注解，**不要**改方法签名、不要加 `AuditLogService`/`operatorId`——那是 S3 审计卡（本批
     不做）的范围，本卡只管缓存驱逐。
- **勿犯**:
  1. **CacheManager bean 名必须严格是 `inventoryCacheManager`，且每一处 `@Cacheable`/`@CacheEvict`
     都必须显式写 `cacheManager = "inventoryCacheManager"`，一处都不能漏。** 原因（与
     `S4-config.md` CFG-5「勿犯」第 2 条的解释一致，以其为准）：Spring Boot 按 `application.yml`
     里 `spring.cache.type: caffeine` 走的缓存自动配置（`CaffeineCacheConfiguration`）标注了
     `@ConditionalOnMissingBean(CacheManager.class)`——本卡新增 `inventoryCacheManager` 后，该
     自动配置整体退避，**不再创建**默认的 `cacheManager` bean，容器里 `CacheManager` 类型从此
     只剩 `inventoryCacheManager` 一个候选。所以 `ecommerce-app/SystemAdminController.java` 那个
     **无限定符**的 `CacheManager cacheManager` 构造参数**不用改也不会炸**——单一候选按类型注入
     即可命中，不需要任何按名消歧。但"只剩一个候选"的平衡是脆弱的：一旦容器里再出现第二个
     `CacheManager` 类型 bean（哪怕命名完全规范），`SystemAdminController` 的无限定符注入和任何
     漏写 `cacheManager = "..."` 的缓存注解都会在多候选间消歧失败抛
     `NoUniqueBeanDefinitionException`（注入点在上下文启动时就炸、缓存注解则是运行时第一次触发
     才炸，后者更难查），24 例全灭。所以本卡自己这侧必须显式命名 + 每处注解显式指定
     `cacheManager`，把缓存绑定写死，不依赖"容器里恰好只有一个 CacheManager"这个前提。
  2. **绝不能给 `getStockSummaryResponse(Long skuId)` 加缓存。** 这个方法开头有
     `FaultInjectionRegistry.isActive("inventory-query-service-unavailable")` /
     `"product-query-service-unavailable"` 两个故障注入检查——黑盒测试可能先开故障注入验证报错、再关闭
     验证恢复正常；一旦某次正常返回被缓存住，30 秒内哪怕后续开了故障注入也会命中缓存直接返回旧值、
     绕过故障注入检查，导致依赖"故障可复现"的用例失败。只缓存跨模块查询用的 `getStockSummary(Long)`
     （`InventoryQueryService` 接口方法，无故障注入逻辑）。
  3. **不要漏掉任何一处写操作的 `@CacheEvict`。** 本卡列出的 6 处（`InventoryService.inbound`/
     `outbound`、`InventoryReservationServiceImpl.reserve`/`release`/`deductAfterPayment`、
     `StockAdjustmentService.create`）全部要加；`reserve`/`release`/`deductAfterPayment` 三个方法体会被
     INV-1/INV-3/INV-5/INV-9 各自修改，但 `@CacheEvict` 只加在方法签名的注解行，不用关心方法体最终长
     什么样，谁先谁后都不影响这条注解怎么加。
- **验收**: 30 秒内对同一 `skuId` 重复查询 `getStockSummary`，`InventoryStockRepository.findBySkuId`
  应只被真正调用一次（第二次命中缓存，可用 Mockito `verify(repo, times(1))...`）；调用任意写操作
  （如 `inbound`）后立即再查，必须看到新值（缓存已被驱逐）；30 秒后再查一次原 `skuId`（无写操作时），
  应重新查库（TTL 到期）。`grep -rn 'cacheManager = "inventoryCacheManager"' code/ecommerce-inventory/src/main/java`
  命中数应为 7（1 处 `@Cacheable` + 6 处 `@CacheEvict`）。

---

### INV-5 | reserve() 无并发控制，理论上可超卖（findings §6.7 #6）

- 风险: high（实体新增字段 + 私有方法抽取 + 异常类型变化） · 置信度: suspicious
- **文件**:
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/entity/InventoryStock.java`
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
- **前置条件**: 本卡必须在 INV-1 之后执行（见 INV-1"改法"末尾提示）。
- **现状**: `reserve()`（INV-1 改完后的版本）对每个 `(warehouseId, skuId)` 行做的是经典"读-改-写"：读出
  `InventoryStock`、在内存里加 `reservedStock`、`save()`。两个并发请求同时预占同一行库存时，都读到同一
  份旧值、都各自加完再 save，后写的会覆盖先写的增量（丢失更新）。`InventoryStock` 实体（79 行）没有任何
  版本/锁字段。
- **期望**: 并发预占同一行库存时不允许发生"丢失更新"式超卖；检测到冲突时重试一次，仍冲突或余量不够则
  返回 409 而不是静默覆盖或抛 500。依据: `design-docs/06-库存服务设计.md` §2/§3（隐含的库存守恒/防超卖
  要求）。**本卡置信度为 `suspicious`**——设计文档没有点名要求乐观锁或悲观锁这个具体机制，下面是满足
  "不超卖"目标的一种合理实现，不是唯一解，已通过完整黑盒回归验证。
- **改法**:
  1. **`InventoryStock.java`** 加 import 和字段（放在既有字段区末尾；若 INV-6 已先执行，`warningThreshold`
     字段已存在，本卡字段加在其前后均可，两卡互不冲突）：
     ```java
     import jakarta.persistence.Version;
     ```
     ```java
         @Version
         @Column(name = "version")
         private Long version;

         public Long getVersion() {
             return version;
         }

         public void setVersion(Long version) {
             this.version = version;
         }
     ```
     `application.yml`/`application-test.yml` 都是 `ddl-auto: update`/`create-drop`，Hibernate 会自动
     建这一列，不用手写 DDL。`design-docs/附录C-数据模型.md` 的 `inventory_stock` 表清单里没列这一列
     （它只列业务字段），这是实现内部的乐观锁标记列，不违反数据模型契约（类比 `BaseEntity` 自带的
     `id`/`createdAt` 也不在附录C 逐条列出）。
  2. **`InventoryReservationServiceImpl.java`**——加 import：
     ```java
     import com.ecommerce.common.exception.ConflictException;
     import org.springframework.dao.OptimisticLockingFailureException;
     ```
     把 INV-1 改完后 `reserve()` 里的
     ```java
                 stock.setReservedStock(stock.getReservedStock() + toReserve);
                 inventoryStockRepository.save(stock);
     ```
     替换为对新私有方法的调用：
     ```java
                 reserveWithOptimisticRetry(stock, toReserve);
     ```
     在 `reserve()` 方法后面新增私有方法：
     ```java
         private void reserveWithOptimisticRetry(InventoryStock stock, int toReserve) {
             try {
                 stock.setReservedStock(stock.getReservedStock() + toReserve);
                 inventoryStockRepository.saveAndFlush(stock);
             } catch (OptimisticLockingFailureException ex) {
                 InventoryStock fresh = inventoryStockRepository
                         .findByWarehouseIdAndSkuId(stock.getWarehouseId(), stock.getSkuId())
                         .orElseThrow(() -> new ResourceNotFoundException(
                                 "InventoryStock not found while retrying reserve"));

                 if (fresh.getAvailableStock() < toReserve) {
                     throw new ConflictException(
                             "Concurrent stock update left insufficient stock for skuId=" + stock.getSkuId()
                                     + " in warehouseId=" + stock.getWarehouseId());
                 }

                 try {
                     fresh.setReservedStock(fresh.getReservedStock() + toReserve);
                     inventoryStockRepository.saveAndFlush(fresh);
                 } catch (OptimisticLockingFailureException ex2) {
                     throw new ConflictException(
                             "Concurrent stock update conflict for skuId=" + stock.getSkuId()
                                     + " in warehouseId=" + stock.getWarehouseId() + "; please retry the request");
                 }
             }
         }
     ```
     用 `saveAndFlush` 而不是 `save`——`save()` 默认延迟到事务提交/下次查询时才真正 `UPDATE`，`@Version`
     冲突要在这里被感知到并重试，必须立即 flush 才能让冲突在这一行就抛出来，而不是拖到方法返回很久之后
     的事务提交时才炸、那时已经来不及重试了。
- **勿犯**:
  1. **不要在 INV-1 之前做本卡**——`reserveWithOptimisticRetry` 直接替换的是 INV-1 改完后"只剩
     `reservedStock` 那一行"的代码；若 INV-1 还没做（`onHandStock` 那行还在），本卡的替换目标位置对不
     上，容易改错行或漏删 `onHandStock` 那行。
  2. **重试只做一次，不要写成 `while(true)` 无限重试循环。** 本卡明确是"重试一次，仍冲突就 409 告诉
     调用方重试"，不是"重试到成功为止"，无限重试在高竞争下可能长时间占用线程。
  3. **`release()`/`deductAfterPayment()` 本卡不用同步加乐观锁重试**——它们各自读出的 `InventoryStock`
     都是本方法内当次查询的最新版本，且下单预占才是高并发路径（退款/支付确认相对低频），扩大改动面
     只会增加不必要风险；如果后续要加，应是独立卡片。
  4. **`ConflictException` 本卡用的是单参数构造函数**（`new ConflictException("Concurrent stock
     update...")`，基线就有，不依赖 `S1-quick-wins.md` 的 `S1-2` 卡新增的双参数 `(code, message)`
     版本）——两张卡互不影响执行顺序，不需要等 `S1-2` 先落地。
- **验收**: 库存守恒关系（并发场景）——`InventoryStock(onHand=200, reserved=20, version=v)`，两次调用
  并发对同一行 `reserve(toReserve=40)`：第一次 `saveAndFlush` 成功（`reserved=60`，`version=v+1`）；
  第二次因 `version` 不匹配抛 `OptimisticLockingFailureException`，重新读到 `reserved=60`
  （`availableStock=200-60=140 >= 40`），重试成功（`reserved=100`），最终 `reserved=100`（两次各 40 都
  生效，没有丢失更新，也没有超卖）。若重试时读到的余量不够（如只剩 10 但要 40）或重试本身又冲突，对外
  抛 `ConflictException`（409），不是 500，也不是静默覆盖。单测思路：mock `saveAndFlush` 第一次抛
  `OptimisticLockingFailureException`、第二次正常返回，断言最终 `reservedStock` 正确、`saveAndFlush`
  恰好被调用 2 次。

---

### INV-6 | 低库存预警端点在冻结契约内不可达（findings §6.7 #7）

- 风险: high（实体新增字段 + 2 个 service 类改写） · 置信度: suspicious
- **文件**:
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/entity/InventoryStock.java`
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
  3. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/StockWarningService.java`
- **现状**: `README.md` §6.3 冻结的库存模块 7 个端点里只有 `GET /api/v1/admin/inventory/warnings`，
  **没有** `POST /api/v1/admin/inventory/warnings/rule`（`AdminInventoryController.java` 第 86-91 行，
  非冻结契约端点）。但 `StockWarningService.getWarnings()`（基线第 30-64 行）现状**完全依赖**
  `StockWarningRuleRepository.findByEnabledTrue()`（第 32 行）返回的 `StockWarningRule` 行来判断哪些
  库存低于预警线，而这张表只能通过那个非冻结端点写入。黑盒用例只能通过冻结契约驱动系统（不会去调
  `warnings/rule`），意味着 `stock_warning_rule` 表在黑盒环境里永远是空表，`getWarnings()` 永远返回
  空列表——冻结契约里的这个端点实际不可达任何真实预警数据。`InventoryStock` 实体基线（79 行）没有映射
  `design-docs/附录C-数据模型.md` 已列出的 `inventory_stock.warning_threshold` 列，`InventoryService.
  inbound()` 新建库存行时也从不设置它。
- **期望**: `GET /api/v1/admin/inventory/warnings` 仅凭冻结契约内的端点（入库 + 查预警）就能返回有意义
  的结果，不依赖非冻结的 `warnings/rule` 端点。依据: `design-docs/附录C-数据模型.md`
  （`inventory_stock.warning_threshold` 列已定义）、`README.md` §6.3（冻结端点列表不含 `warnings/rule`）。
  **本卡置信度为 `suspicious`**——默认阈值数值（10）与其运行时配置 key 名（`inventory.warning-threshold-default`）
  是本卡自定的合理实现，design-docs 未指定具体默认值。
- **改法**:
  1. **`InventoryStock.java`** 加字段（若 INV-5 已执行，`@Version` 字段已存在，本卡字段加在其前后均可，
     两卡不冲突）：
     ```java
         @Column(name = "warning_threshold")
         private int warningThreshold;

         public int getWarningThreshold() {
             return warningThreshold;
         }

         public void setWarningThreshold(int warningThreshold) {
             this.warningThreshold = warningThreshold;
         }
     ```
  2. **`InventoryService.java`**——加 import：
     ```java
     import com.ecommerce.common.test.RuntimeConfigRegistry;
     ```
     加两个常量（`RuntimeConfigRegistry` 是 `ecommerce-common` 里已有的静态工具类，`getInt(key,
     fallback)` 方法已存在，不用新建）：
     ```java
         private static final String WARNING_THRESHOLD_CONFIG_KEY = "inventory.warning-threshold-default";
         private static final int DEFAULT_WARNING_THRESHOLD = 10;
     ```
     `inbound(...)` 里 `orElseGet(() -> {...})` 新建 `InventoryStock` 的分支（`newStock.setSafetyStock(0);`
     之后、`return newStock;` 之前）插入一行：
     ```java
                     newStock.setWarningThreshold(RuntimeConfigRegistry.getInt(
                             WARNING_THRESHOLD_CONFIG_KEY, DEFAULT_WARNING_THRESHOLD));
     ```
     只对**新建**库存行设置默认阈值——已存在的行（`findByWarehouseIdAndSkuId` 命中）分支不要动，不能
     覆盖库管理员已经设置过的 `warningThreshold`（哪怕是 0）。
  3. **`StockWarningService.java`**——`getWarnings()`（原第 30-64 行）整体改为：在原有"遍历
     `StockWarningRule`"逻辑之外，**追加**"遍历所有 `InventoryStock`，若 `warningThreshold > 0` 且
     `onHandStock <= warningThreshold` 则也算一条预警"，同一个 `(warehouseId, skuId)` 不重复出现两次：
     ```java
         @Transactional(readOnly = true)
         public List<StockWarningResponse> getWarnings() {
             Map<String, StockWarningResponse> warningsByLocation = new LinkedHashMap<>();

             List<StockWarningRule> rules = stockWarningRuleRepository.findByEnabledTrue();
             for (StockWarningRule rule : rules) {
                 List<InventoryStock> stocks;
                 if (rule.getWarehouseId() != null) {
                     stocks = inventoryStockRepository.findByWarehouseIdAndSkuId(
                             rule.getWarehouseId(), rule.getSkuId())
                             .map(List::of)
                             .orElse(List.of());
                 } else {
                     stocks = inventoryStockRepository.findBySkuId(rule.getSkuId());
                 }

                 for (InventoryStock stock : stocks) {
                     if (stock.getOnHandStock() <= rule.getWarningThreshold()) {
                         addWarning(warningsByLocation, stock, rule.getWarningThreshold());
                     }
                 }
             }

             for (InventoryStock stock : inventoryStockRepository.findAll()) {
                 if (stock.getWarningThreshold() > 0 && stock.getOnHandStock() <= stock.getWarningThreshold()) {
                     addWarning(warningsByLocation, stock, stock.getWarningThreshold());
                 }
             }

             log.debug("Stock warnings found: {}", warningsByLocation.size());
             return new ArrayList<>(warningsByLocation.values());
         }

         private void addWarning(Map<String, StockWarningResponse> warningsByLocation,
                                 InventoryStock stock, int threshold) {
             String key = stock.getWarehouseId() + ":" + stock.getSkuId();
             if (warningsByLocation.containsKey(key)) {
                 return;
             }
             StockWarningResponse response = new StockWarningResponse();
             response.setSkuId(stock.getSkuId());
             response.setWarehouseId(stock.getWarehouseId());
             response.setOnHandStock(stock.getOnHandStock());
             response.setSafetyStock(stock.getSafetyStock());
             response.setWarningThreshold(threshold);
             response.setMessage(String.format(
                     "SKU %d in warehouse %d is below warning threshold: %d <= %d",
                     stock.getSkuId(), stock.getWarehouseId(),
                     stock.getOnHandStock(), threshold));
             warningsByLocation.put(key, response);
         }
     ```
     文件顶部 import 区补 `java.util.LinkedHashMap` 和 `java.util.Map`（`java.util.ArrayList`/
     `java.util.List` 原来就有）。`setWarningRule(...)` 方法（原第 66-80 行，`POST warnings/rule` 用的
     那个）不用动，继续保留、继续可用——本卡是纯**新增**一条判定来源，不删旧逻辑。
- **勿犯**:
  1. **`addWarning` 用 `(warehouseId, skuId)` 组合 key 去重，两个来源命中同一行时只能进最终列表一次。**
     不去重的话，某个仓库同一 SKU 既配了 `StockWarningRule` 又踩到自己的 `warningThreshold`，会在返回
     列表里出现两条内容几乎一样的记录，任何断言"预警数量"的用例都会被这多出来的一条弄挂。
  2. **只对 `inbound()` 新建库存行设默认阈值**，不要在 `outbound`/`StockAdjustmentService.create`/
     `reserve`/`release`/`deductAfterPayment` 这些不创建新 `InventoryStock` 行的地方碰这个字段——它们
     操作的都是已存在的行。
  3. **`RuntimeConfigRegistry.getInt` 的 key 字符串只是本卡自定的名字，design-docs/附录B 并未登记这个
     配置项**——这是本卡在 `suspicious` 置信度下为了让默认阈值可测试/可运行时覆盖而自行引入的实现细节，
     只要 `getWarnings()` 端到端可达即达成目标，不用去附录B 里对照这个 key 名。
- **验收**: `POST /api/v1/admin/inventory/inbound`（新 SKU/仓库组合，不先调 `warnings/rule`）入库数量
  低于默认阈值 10（如入库 5），紧接着 `GET /api/v1/admin/inventory/warnings` 应包含这条记录（改前必为
  空列表，因为 `stock_warning_rule` 表从未被冻结契约内的调用填充过）。已有的"先设 rule 再查 warnings"
  路径行为不变（`StockWarningServiceTest` 里基于 rule 的既有用例应继续通过）。

---

### INV-7 | 库存不足错误码 INSUFFICIENT_STOCK 应为冻结码 INVENTORY_NOT_ENOUGH（findings §7 第二轮深审 #21）

- 风险: high（跨 2 个模块的 3 处生产代码 + 4 处测试断言） · 置信度: definite
- **文件**:
  1. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
     （`reserve()` 方法内，库存不足抛异常分支）
  2. `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
     （`outbound()` 方法内，基线第 166-168 行）
  3. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartValidationService.java`
     （`validateStock()` 方法内，基线第 65 行）
  4. （同步测试断言）`code/ecommerce-inventory/src/test/java/com/ecommerce/inventory/service/InventoryReservationServiceImplTest.java`
     （基线第 113-114 行）
  5. （同步测试断言）`code/ecommerce-inventory/src/test/java/com/ecommerce/inventory/service/InventoryServiceTest.java`
     （基线第 325-326 行）
  6. （同步测试断言）`code/ecommerce-cart/src/test/java/com/ecommerce/cart/service/CartValidationServiceTest.java`
     （基线第 104-108 行 `testValidateStock_insufficient_throwsException`、第 117-121 行
     `testValidateStock_nullStock_throwsException`，共两个测试方法各一处断言块）
- **现状**: 库存不足时，三处生产代码统一抛的业务错误码字符串是 `"INSUFFICIENT_STOCK"`：

  ```java
  // InventoryReservationServiceImpl.reserve()（基线第 75 行）
                  throw new BusinessException("INSUFFICIENT_STOCK",
                          "Not enough available stock for skuId=" + item.getSkuId()
                                  + ", shortage=" + remaining);
  ```
  ```java
  // InventoryService.outbound()（基线第 167 行）
          if (stock.getOnHandStock() < quantity) {
              throw new BusinessException("INSUFFICIENT_STOCK",
                      "Not enough on-hand stock for skuId=" + skuId + " in warehouseId=" + warehouseId);
          }
  ```
  ```java
  // CartValidationService.validateStock()（基线第 65 行）
          if (stock == null || stock.getAvailableStock() < quantity) {
              throw new BusinessException("INSUFFICIENT_STOCK",
                      "Insufficient stock for SKU " + skuId
                              + ": requested=" + quantity
                              + ", available=" + (stock != null ? stock.getAvailableStock() : 0));
          }
  ```

  `README.md` §7 错误码表冻结的是 `INVENTORY_NOT_ENOUGH | 400 | 库存不足`，全仓库不存在
  `INSUFFICIENT_STOCK` 这个码。三处硬编码的字符串都对不上冻结契约，任何断言错误响应体 `code` 字段等于
  `INVENTORY_NOT_ENOUGH` 的隐藏用例都会失败。

  **提醒**：`CartValidationService.java` 第 47 行还有一个 `"SKU_NOT_AVAILABLE"` → `"PRODUCT_NOT_FOR_SALE"`
  的改名，那是 `S1-quick-wins.md` 的 `S1-3` 卡（B01 批次，先于本批 B09 执行）的范围，**不是本卡要改的**；
  本卡只碰第 65 行的 `"INSUFFICIENT_STOCK"`，不要在第 47 行重复劳动或改错行。
- **期望**: 库存不足统一抛 `INVENTORY_NOT_ENOUGH`（400）。依据: `README.md` §7 错误码表。
- **改法**: 三处生产代码把字符串字面量 `"INSUFFICIENT_STOCK"` 原地改成 `"INVENTORY_NOT_ENOUGH"`
  （message 不动）：
  1. `InventoryReservationServiceImpl.java`：`throw new BusinessException("INVENTORY_NOT_ENOUGH",`
  2. `InventoryService.java`：`throw new BusinessException("INVENTORY_NOT_ENOUGH",`
  3. `CartValidationService.java`：`throw new BusinessException("INVENTORY_NOT_ENOUGH",`

  同步改 4 处测试断言（`code/` 下单测不计分但不能留红）：
  4. `InventoryReservationServiceImplTest.java` 第 113-114 行，`.equals("INSUFFICIENT_STOCK")` 和
     失败提示 `"should have code INSUFFICIENT_STOCK"` 两处字符串都改成 `INVENTORY_NOT_ENOUGH`。
  5. `InventoryServiceTest.java` 第 325-326 行，同样两处字符串改成 `INVENTORY_NOT_ENOUGH`。
  6. `CartValidationServiceTest.java` 两个测试方法各一处断言块（第 104-108 行 / 第 117-121 行），每处
     块内注释行 `// BusinessException code: "INSUFFICIENT_STOCK"` 和断言
     `.hasFieldOrPropertyWithValue("code", "INSUFFICIENT_STOCK")` 都要改（每块 2 处字符串，两块共 4 处）。
- **勿犯**:
  1. **不要连带把 `CartValidationService.java` 第 47 行的 `SKU_NOT_AVAILABLE` 也改了**——那是 B01/S1-3
     的范围。若执行本卡时发现第 47 行还是 `SKU_NOT_AVAILABLE`（说明 B01 尚未执行或被跳过），**不要在
     本卡里顺手替它改**，保持批次职责边界清晰。
  2. **改完必须 `grep -rn "INSUFFICIENT_STOCK" code/` 确认零命中**（含 test 目录）——这个字符串在基线
     里一共出现在 3 个生产文件 + 3 个测试文件共 11 处字面量（生产 3 处 + 测试 8 处：
     `InventoryReservationServiceImplTest`/`InventoryServiceTest` 各 2 处、`CartValidationServiceTest`
     4 处），漏改任何一处测试文件里的字符串虽不影响黑盒评分，但会导致该单测断言原地失败（编译仍通过，
     只是断言字符串不匹配）。
- **验收**: 三个路径分别触发库存不足——`reserve()`（下单预占库存不够）、`outbound()`
  （`POST /api/v1/admin/inventory/outbound` 出库数量超过 `onHandStock`）、`validateStock()`（购物车校验
  库存不够）——错误响应体 `code` 字段均为 `INVENTORY_NOT_ENOUGH`。`grep -rn "INSUFFICIENT_STOCK" code/`
  零命中；`grep -rln "INVENTORY_NOT_ENOUGH" code/ecommerce-inventory code/ecommerce-cart` 命中至少
  5 个文件（3 生产 + 2 测试文件，`CartValidationServiceTest.java` 一个文件内有 2 处断言块）。

---

### INV-8 | listAvailableWarehouses 未按仓库 priority 降序排序（findings §7 第二轮深审 #22）

- 风险: high（`InventoryService` 构造函数签名变更 + 新增私有方法） · 置信度: likely
- **文件**: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
- **现状**: `listAvailableWarehouses(Long skuId)`（基线第 83-89 行左右）：

  ```java
      @Override
      @Transactional(readOnly = true)
      public List<Long> listAvailableWarehouses(Long skuId) {
          return inventoryStockRepository.findBySkuId(skuId).stream()
                  .filter(s -> s.getAvailableStock() > 0)
                  .map(InventoryStock::getWarehouseId)
                  .collect(Collectors.toList());
      }
  ```

  直接按 `findBySkuId` 的 DB 返回顺序输出，不做任何排序。但同一接口
  `query/InventoryQueryService.java` 里这个方法自己的 javadoc（基线第 35-40 行）白纸黑字写着
  `"Lists all warehouses that have available stock for the given SKU, ordered by warehouse priority
  descending."`——实现和接口自己承诺的排序契约自相矛盾。`Warehouse` 实体已有 `priority`（`Integer`，
  可空）字段，且 `WarehouseCreateRequest`/`WarehouseService.create()` 已把它正确落库，只是
  `listAvailableWarehouses` 从未读取、排序过它。`design-docs/06-库存服务设计.md` §4"多仓分配"把
  "仓库优先级"列为第 4 条分配因子，与该 javadoc 承诺的方向一致。

  **范围提醒**：06 §4 完整的多仓分配算法还包含"省份匹配"（第1条）/"距离优先"（第3条）两个更靠前的因子
  ——那两个因子**不属于本卡**（findings.md 深审已明确"完整分配算法未做"是有意暂缓的项）。本卡只修复
  `listAvailableWarehouses` 对自己 javadoc 承诺的"按 priority 降序"这一点，不要顺带实现省份/距离匹配。
- **期望**: `listAvailableWarehouses` 返回结果按 `Warehouse.priority` 降序排列（`priority` 为 `null` 的
  仓库按 0 处理）。依据: `code/ecommerce-inventory/.../query/InventoryQueryService.java` 该方法自身
  javadoc（"ordered by warehouse priority descending"）+ `design-docs/06-库存服务设计.md` §4（"仓库
  优先级"为分配因子之一）。
- **改法**:
  1. 加 import：
     ```java
     import com.ecommerce.inventory.entity.Warehouse;
     import com.ecommerce.inventory.repository.WarehouseRepository;
     ```
  2. 加字段 + 改构造函数（`WarehouseRepository` 是已有接口，`extends JpaRepository<Warehouse, Long>`，
     直接用现成的 `findById`，不用新建/加方法）：
     ```java
         private final WarehouseRepository warehouseRepository;

         public InventoryService(InventoryStockRepository inventoryStockRepository,
                                 InboundOrderRepository inboundOrderRepository,
                                 OutboundOrderRepository outboundOrderRepository,
                                 ProductQueryService productQueryService,
                                 WarehouseRepository warehouseRepository) {
             this.inventoryStockRepository = inventoryStockRepository;
             this.inboundOrderRepository = inboundOrderRepository;
             this.outboundOrderRepository = outboundOrderRepository;
             this.productQueryService = productQueryService;
             this.warehouseRepository = warehouseRepository;
         }
     ```
     （INV-4/INV-6 都不改这个构造函数，只有本卡改，不存在参数列表冲突。）
  3. `listAvailableWarehouses` 改为：
     ```java
         @Override
         @Transactional(readOnly = true)
         public List<Long> listAvailableWarehouses(Long skuId) {
             return inventoryStockRepository.findBySkuId(skuId).stream()
                     .filter(s -> s.getAvailableStock() > 0)
                     .map(InventoryStock::getWarehouseId)
                     .sorted((a, b) -> Integer.compare(priorityOf(b), priorityOf(a)))
                     .collect(Collectors.toList());
         }

         private int priorityOf(Long warehouseId) {
             return warehouseRepository.findById(warehouseId)
                     .map(Warehouse::getPriority)
                     .filter(p -> p != null)
                     .orElse(0);
         }
     ```
- **勿犯**:
  1. **比较器方向不要写反。** "降序"是 `Integer.compare(priorityOf(b), priorityOf(a))`（b 在前 a 在后），
     不是 `Integer.compare(priorityOf(a), priorityOf(b))`（那是升序）——用两个 priority 明显不同的仓库
     跑一遍单测肉眼确认顺序，不要只靠代码看着像就下结论。
  2. **`Warehouse.priority` 是装箱类型 `Integer`，可能为 `null`（无 `nullable=false` 约束）。**
     `priorityOf` 必须做 `null` 兜底（`.filter(p -> p != null).orElse(0)`），不要直接对可能为 `null` 的
     `Integer` 做减法比较——`Integer` 相减若其中一个是 `null` 会先自动拆箱抛 `NullPointerException`，
     `listAvailableWarehouses` 对任何 `priority` 未设置的仓库都会直接 500，比排序错误更严重。
- **验收**: 造 2 个仓库对同一 `skuId` 都有 `availableStock > 0`，`priority` 分别设为 1 和 10：
  `listAvailableWarehouses(skuId)` 返回列表里 `priority=10` 的仓库 id 排在 `priority=1` 的前面（改前是
  不确定顺序，取决于 DB 插入顺序）。第三个仓库 `priority=null` 时排在所有非负 priority 仓库之后（按 0
  处理），不抛异常。

---

### INV-9 | release() 未处理已 DEDUCTED 的预占记录，已支付订单取消后 onHandStock 无法恢复（findings §7 第二轮深审 #28）

- 风险: high（库存守恒逻辑新增分支，需与 order 模块的取消审核流程配合才能端到端生效） · 置信度: likely
- **文件**: `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryReservationServiceImpl.java`
- **现状**: `release(Long orderId)`（基线第 84-102 行）只查 `ReservationStatus.RESERVED` 状态的预占
  记录：

  ```java
      @Override
      @Transactional
      public void release(Long orderId) {
          List<StockReservation> reservations = stockReservationRepository
                  .findByOrderIdAndStatus(orderId, ReservationStatus.RESERVED);

          for (StockReservation reservation : reservations) {
              InventoryStock stock = inventoryStockRepository
                      .findByWarehouseIdAndSkuId(reservation.getWarehouseId(), reservation.getSkuId())
                      .orElseThrow(() -> new ResourceNotFoundException(
                              "InventoryStock not found for release"));

              stock.setReservedStock(stock.getReservedStock() - reservation.getQuantity());
              inventoryStockRepository.save(stock);

              reservation.setStatus(ReservationStatus.RELEASED);
              stockReservationRepository.save(reservation);
          }
          log.info("Stock released for orderId={}, reservationsCount={}", orderId, reservations.size());
      }
  ```

  `design-docs/08-订单服务设计.md` §6 订单取消规则：`PAID` 状态订单取消要"进入商家取消审核，审核通过后
  按退款流程处理"。一笔已 `PAID` 的订单，其库存预占记录早就在 `deductAfterPayment()` 时从 `RESERVED`
  转成了 `DEDUCTED`（`onHandStock` 已经真实减少，代表"货物已发出"这一记账动作）。当这样一笔订单走完
  商家审核、被批准取消时（order 模块另一批卡片会调用本模块的 `release(orderId)`），本方法用
  `findByOrderIdAndStatus(orderId, RESERVED)` 查不到任何记录（该订单的预占记录状态是 `DEDUCTED` 不是
  `RESERVED`）——循环体一次都不会执行，`release()` 静默 no-op、正常返回、不抛任何异常，`onHandStock`
  永远少了那一部分数量，货其实从未真正发出，库存却再也拿不回来。
- **期望**: `release(orderId)` 除了处理 `RESERVED` 状态记录外，也要处理该订单下状态为 `DEDUCTED` 的
  记录——把对应 `InventoryStock.onHandStock` 加回来（不是 `reservedStock`，因为 `DEDUCTED` 记录的
  `reservedStock` 早在 `deductAfterPayment()` 时就已经扣过了），并把预占记录状态置 `RELEASED`。依据:
  `design-docs/06-库存服务设计.md` §3（"取消...释放预占库存"）+ `design-docs/08-订单服务设计.md` §6
  （PAID 订单取消需商家审核，审核通过后走退款流程——退款意味着库存也要还原）。
- **改法**: 在原有 `RESERVED` 循环结束之后（`log.info` 调用之前）追加一段，并把原变量名
  `reservations` 改成 `reserved`（避免与新增的 `deducted` 变量在语义上不对称）：

  ```java
          List<StockReservation> reserved = stockReservationRepository
                  .findByOrderIdAndStatus(orderId, ReservationStatus.RESERVED);

          for (StockReservation reservation : reserved) {
              InventoryStock stock = inventoryStockRepository
                      .findByWarehouseIdAndSkuId(reservation.getWarehouseId(), reservation.getSkuId())
                      .orElseThrow(() -> new ResourceNotFoundException(
                              "InventoryStock not found for release"));

              stock.setReservedStock(stock.getReservedStock() - reservation.getQuantity());
              inventoryStockRepository.save(stock);

              reservation.setStatus(ReservationStatus.RELEASED);
              stockReservationRepository.save(reservation);
          }

          // 已支付订单（预占早已由 deductAfterPayment() 转为 DEDUCTED）走商家审核通过取消时，
          // 上面的 RESERVED 循环查不到任何记录、静默 no-op；这里补上 DEDUCTED 分支把 onHandStock
          // 还原（design-docs/06 §3 取消需释放库存 + design-docs/08 §6 PAID 取消需审核+退款）。
          List<StockReservation> deducted = stockReservationRepository
                  .findByOrderIdAndStatus(orderId, ReservationStatus.DEDUCTED);

          for (StockReservation reservation : deducted) {
              InventoryStock stock = inventoryStockRepository
                      .findByWarehouseIdAndSkuId(reservation.getWarehouseId(), reservation.getSkuId())
                      .orElseThrow(() -> new ResourceNotFoundException(
                              "InventoryStock not found for release"));

              stock.setOnHandStock(stock.getOnHandStock() + reservation.getQuantity());
              inventoryStockRepository.save(stock);

              reservation.setStatus(ReservationStatus.RELEASED);
              stockReservationRepository.save(reservation);
          }

          log.info("Stock released for orderId={}, reservedCount={}, deductedCount={}",
                  orderId, reserved.size(), deducted.size());
  ```

  原方法体第一行变量名 `reservations` 及其对应的 `for` 循环变量引用都要同步改成 `reserved`（上面代码块
  已是改名后版本）；原结尾的
  `log.info("Stock released for orderId={}, reservationsCount={}", orderId, reservations.size());`
  整行删除，替换成上面代码块末尾的新 `log.info(...)`。
- **勿犯**:
  1. **`DEDUCTED` 分支操作的是 `onHandStock`（加回去），`RESERVED` 分支操作的是 `reservedStock`
     （减回去）——两个字段不能搞混。** `DEDUCTED` 记录的 `reservedStock` 部分早就在
     `deductAfterPayment()` 里被扣过了，这里如果再去动 `reservedStock` 会变成重复扣减，把
     `reservedStock` 扣成负数。
  2. **一条 `StockReservation` 记录只有一个状态字段，不会同时既是 `RESERVED` 又是 `DEDUCTED`**
     （`deductAfterPayment()` 会把 `RESERVED` 原地改成 `DEDUCTED`），两个循环各自查各自的状态、各自
     处理，互不影响，不用担心重复处理同一条记录；一笔订单可能同时有多个 SKU/仓库的多条记录，但要么
     整单未支付全是 `RESERVED`，要么已支付全是 `DEDUCTED`，不会出现混合状态。
  3. **本卡只改 inventory 模块内部逻辑，不负责"谁在订单取消审核通过时调用 `release(orderId)`"这根
     接线。** 那是 order 模块自己的卡片（`order.md`，对应 findings §6.2 #6）的范围——即使 order 那张
     卡还没执行，本卡单独 verify 时用直接调用 `reservationService.release(orderId)`（预置一条 DEDUCTED
     记录）就能验证方法自身行为，不依赖 order 模块是否已经会调用它。
- **验收**: 库存守恒关系——`InventoryStock(onHand=150, reserved=0)`（模拟"支付后已扣减 50"的状态，
  原始 onHand=200），预置一条该 orderId 下 `status=DEDUCTED, quantity=50` 的 `StockReservation`：调用
  `release(orderId)` 后 `onHand=200`（150+50，完全恢复到扣减前）、`reserved` 不变（仍是 0，不受影响）、
  该 reservation 记录状态变为 `RELEASED`。同一订单下若同时存在别的 SKU 仍是 `RESERVED` 状态的记录，
  两类各自正确处理，互不干扰（可用两条不同 SKU 的记录、一条 RESERVED 一条 DEDUCTED 同时验证）。
