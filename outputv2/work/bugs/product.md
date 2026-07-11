# B08 · product — 搜索 / 上下架 / 库存摘要 / 冲突语义

本文件覆盖 findings.md「product 模块（§6.6）」10 项中的 6 项（#1、#3、#4、#5、#6、#9），外加
「第二轮深审」#26（与 #9 同一根因，合并进同一张卡），以及「第三轮深审·跨领域」的 #2、#3，
去重合并后共 **5 张卡（PRODUCT-1..PRODUCT-5）**。

**范围排除（不在本文件，已跳过）**：

- §6.6 #2（`getSkuForSale` 错误码 `SKU_NOT_AVAILABLE` 应为 `PRODUCT_NOT_FOR_SALE`）——归
  `S1-quick-wins.md`（B01，S1-3 卡，与 cart 模块同码一起改）。
- §6.6 #7（商品上下架无审计日志）——归 `S3-audit.md`（B18，审计基础设施统一接入批次）。
- §6.6 #8（商品详情无 10 分钟缓存）——归 `S4-config.md`（B19，复用既有 CacheManager 的缓存批次）。
- §6.6 #10（商品搜索无限流）——归 `S4-config.md`（B19，4 处 `@RateLimit` 统一接入批次）。

**跨卡协作说明**：

1. PRODUCT-3 一次性覆盖 findings #4 + #5 + #6 + #9（含第二轮 #26）。这四项症状的修复最终都落在
   `ProductSearchService.java` 的同一次 `search()`/`buildSpecification()` 重写里（类目过滤要下推
   DB 层才能让 #6 的分页 total 正确，标签过滤要接入同一套"先解析出允许的 SPU id 集合、再作为
   `spuId IN (...)` 谓词下推"的机制，关键词匹配 SPU 名/卖点也是往同一个 `buildSpecification` 里加
   一段 OR 谓词），拆成互不重叠的独立 patch 反而会来回改同一批代码、容易改漏。按 PRODUCT-3 给出的
   完整文件内容一次性整份替换，不要试图只改其中一部分。
2. PRODUCT-1（库存摘要）只改 `code/ecommerce-product` 下的 `StockInfoFetcher.java` 一个文件——
   已经反复核实 `ecommerce-inventory` 那侧的实现类（`InventoryService`）在未修复的原始代码里就已经
   同时实现了 product 自己声明的 `com.ecommerce.product.query.InventoryQueryService` 接口（见该卡
   "现状"里的证据），**不需要改 `ecommerce-inventory` 下任何文件**。
3. PRODUCT-4（重复编码建 409）与 PRODUCT-5（DELETED 状态冲突建 409）都会改到 `SkuService.java`，
   但 PRODUCT-4 只碰 `createSku()`，PRODUCT-5 只碰 `onShelf()`/`offShelf()`，方法互不重叠，
   两卡顺序无关。`S3-audit.md`（B18，晚于本文件执行）之后会再给 `onShelf`/`offShelf` 加
   `operatorId` 参数与审计埋点、给 `AdminProductController` 加 `Authentication` 形参——那是方法签名
   和方法体末尾的改动，与 PRODUCT-5 改的"DELETED 分支该抛哪个异常类"这一行不冲突，谁先谁后都能叠加。
4. 本文件 5 张卡都不依赖 `S1-quick-wins.md` 新增的 `ConflictException(String code, String message)`
   双参构造函数——PRODUCT-4/PRODUCT-5 用的是基线就已存在的单参 `ConflictException(String message)`
   （错误码恒为通用的 `CONFLICT`），不涉及 README §7.2 那些带专属业务码的 409。

**测试提示（不计分，但建议顺手改，避免模块自测变红）**：`code/ecommerce-product/src/test/java/...`
下的 `SkuServiceTest`、`SpuServiceTest`、`ProductSearchServiceTest`、`StockInfoFetcherTest`（若不存在
可不建）断言了基线的错误行为（如"抛 `ValidationException`""结果包含 OFF_SHELF/DRAFT""返回硬编码
999/0"），改完生产代码后这些断言会变红。这些文件在 `code/` 下允许修改且不计入评分，各卡"验收"里给了
应该改成什么样的断言方向，照改即可。

---

### PRODUCT-1 | 库存摘要硬编码 999/0，`StockInfoFetcher` 从未接入 `InventoryQueryService`

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/StockInfoFetcher.java`
- **现状**: 全文件只有 26 行：

  ```java
  package com.ecommerce.product.service;

  import com.ecommerce.product.query.StockSummaryDto;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;

  /**
   * A local stock data fetcher that generates stock summaries internally.
   */
  @Component
  public class StockInfoFetcher {

      private static final Logger log = LoggerFactory.getLogger(StockInfoFetcher.class);

      /**
       * Fetches stock info for a given SKU.
       *
       * @param skuId the SKU id
       * @return a stock summary
       */
      public StockSummaryDto fetch(Long skuId) {
          log.debug("StockInfoFetcher fetching stock for skuId={}", skuId);
          return new StockSummaryDto(999, 0);
      }
  }
  ```

  第 24 行 `fetch(Long skuId)` 无论传入什么 `skuId`，永远返回硬编码的
  `new StockSummaryDto(999, 0)`，从未查询任何真实库存数据。该类是
  `ProductDetailService`（`code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductDetailService.java`
  第 39/46/52 行注入，第 73 行 `response.setStockSummary(stockInfoFetcher.fetch(skuId));`）
  的唯一协作者，也就是 `GET /api/v1/products/{skuId}` 商品详情接口里 `stockSummary` 字段的唯一数据来源。

  product 模块自己在 `code/ecommerce-product/src/main/java/com/ecommerce/product/query/InventoryQueryService.java`
  声明了一个"consumer-owned"接口（javadoc 原文："The inventory module provides the implementation of
  this interface"），方法签名为 `StockSummaryDto getStockSummary(Long skuId)`，与
  `code/ecommerce-product/src/main/java/com/ecommerce/product/query/StockSummaryDto.java`
  （`availableStock`/`reservedStock` 两个 int 字段）配套。**这个接口在基线上已经有实现**——
  `code/ecommerce-inventory/src/main/java/com/ecommerce/inventory/service/InventoryService.java`
  的类声明（该文件第 38-39 行）就是：

  ```java
  public class InventoryService implements InventoryQueryService,
          com.ecommerce.product.query.InventoryQueryService {
  ```

  （此处 `InventoryQueryService` 无限定符指的是同文件 import 的
  `com.ecommerce.inventory.query.InventoryQueryService`，inventory 模块自己那个更大的接口，多声明了
  `checkAvailability`/`listAvailableWarehouses` 两个方法；第二个全限定名才是 product 声明的那个。）
  它的 `getStockSummary(Long skuId)` 方法体（该文件约第 60-66 行）已经查真实的
  `InventoryStockRepository` 数据并汇总返回，返回类型就是 `com.ecommerce.product.query.StockSummaryDto`
  （该文件第 17 行已 import）——参数、返回类型跟 product 声明的接口逐字匹配，一份方法体天然同时满足
  两个接口，**这部分代码不用改，也不要改**。`ecommerce-cart` 模块的
  `CartValidationService.java`（第 5、26、29 行）同样构造函数注入这个 `InventoryQueryService`
  接口且能正常工作，是"这个 bean 从基线起就已经在 Spring 容器里"的现成佐证。真正的 bug 只在
  `StockInfoFetcher` 自己从来没有引用这个接口、没有走这条已经打通的路。
- **期望**: 商品详情的库存摘要必须是真实库存数据，且必须通过 `InventoryQueryService.getStockSummary(skuId)`
  获取，不得直接访问库存表或注入库存模块 Repository。依据: `design-docs/05-商品服务设计.md` §3（第38行：
  "库存摘要必须通过 `InventoryQueryService.getStockSummary(skuId)` 获取，不得直接访问库存表或注入库存
  模块 Repository"）、`design-docs/02-系统架构.md` §3/§4（跨模块查询必须通过 QueryService 接口；
  `InventoryQueryService` 的使用方含 product）、`design-docs/附录A-API接口参考.md` §3（商品详情 Response
  示例：`"stockSummary": {"availableStock": 100, "reservedStock": 0}`，字段名冻结，不得改名）。
- **改法**: 整份替换为下面的内容（只改这一个文件，不涉及 `pom.xml`——product 模块引用的是自己包内的
  接口类型，不需要新增对 `ecommerce-inventory` 的 Maven 依赖；`ecommerce-inventory` 也早已经依赖
  `ecommerce-product`，不要反向加依赖，那样会形成 Maven 循环依赖导致 reactor 构建失败）：

  ```java
  package com.ecommerce.product.service;

  import com.ecommerce.product.query.InventoryQueryService;
  import com.ecommerce.product.query.StockSummaryDto;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.stereotype.Component;

  /**
   * Fetches stock info by delegating to the inventory module's {@link InventoryQueryService}.
   *
   * <p>The inventory module provides the runtime implementation of this
   * product-owned interface (design-docs/05 section 3: "库存摘要必须通过
   * InventoryQueryService.getStockSummary(skuId) 获取，不得直接访问库存表或注入库存模块 Repository").
   */
  @Component
  public class StockInfoFetcher {

      private static final Logger log = LoggerFactory.getLogger(StockInfoFetcher.class);

      private final InventoryQueryService inventoryQueryService;

      public StockInfoFetcher(InventoryQueryService inventoryQueryService) {
          this.inventoryQueryService = inventoryQueryService;
      }

      /**
       * Fetches stock info for a given SKU.
       *
       * @param skuId the SKU id
       * @return a stock summary
       */
      public StockSummaryDto fetch(Long skuId) {
          log.debug("StockInfoFetcher fetching stock for skuId={}", skuId);
          return inventoryQueryService.getStockSummary(skuId);
      }
  }
  ```
- **验收**: 管理员先对某 SKU 走 `POST /api/v1/admin/inventory/inbound` 入库一批数量，再
  `GET /api/v1/products/{skuId}` 查详情，`stockSummary.availableStock` 应反映真实入库数量而不是
  999；一个从未入库过的 SKU，`stockSummary.availableStock`/`reservedStock` 应为 0 而不是 999/0
  的固定组合（用一个真实无库存的场景验证不再是巧合碰上 999）。`grep -rn "StockSummaryDto(999" code/*/src/main/java`
  零命中。跑一次黑盒/`mvn -f code/pom.xml install -DskipTests` 确认 Spring 上下文正常启动，不抛
  `NoSuchBeanDefinitionException`/`UnsatisfiedDependencyException`（针对
  `com.ecommerce.product.query.InventoryQueryService`）——不应该抛，因为实现类本来就在，只是没人用。
- **勿犯**: 不要因为"接口 javadoc 说 inventory 模块提供实现"就去 `ecommerce-inventory` 里新建一个
  独立的 `@Component`/适配器类去实现 `com.ecommerce.product.query.InventoryQueryService`——那会造出
  第二个同类型 bean，`StockInfoFetcher` 的单构造函数注入会因为 Spring 找到两个候选 bean 而报
  `NoUniqueBeanDefinitionException`（这正是 findings.md 记录的 BUG-INT-1 bean 冲突事故的同类重演）。
  `InventoryService` 已经实现了，本卡唯一要动的就是 `StockInfoFetcher.java` 这一个文件。

---

### PRODUCT-2 | 搜索默认 `onlyOnShelf=false`，未上架/草稿商品对匿名用户可见

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-product/src/main/java/com/ecommerce/product/dto/ProductSearchRequest.java`
- **现状**: 第 31 行 `private boolean onlyOnShelf = false;`，默认值为 `false`。类头 javadoc（第
  9-10 行）如实写着"The `onlyOnShelf` field defaults to `false`, which causes the search to include
  OFF_SHELF and DRAFT products."。`GET /api/v1/products`、`GET /api/v1/products/search` 是匿名端点
  （README §6.2、`ProductController` 无 `@PreAuthorize`），请求参数由 `ProductSearchRequest` 直接绑定
  查询字符串（`ProductController.listProducts(ProductSearchRequest request)`/`searchProducts(...)`
  方法签名是裸 DTO 形参，没有 `@RequestParam`）。只要调用方不在 query string 里显式传
  `onlyOnShelf=true`，OFF_SHELF（已下架）和 DRAFT（草稿，尚未上架过）的 SKU 都会出现在公开搜索/列表
  结果里。
- **期望**: 搜索/列表默认只展示 `ON_SHELF` 商品；调用方需要显式传 `onlyOnShelf=false` 才能看到
  OFF_SHELF/DRAFT。依据: `design-docs/05-商品服务设计.md` §4（"默认只展示 `ON_SHELF` 商品"）。
- **改法**: 只改一行字段默认值和相邻两处注释，其余全部不动：

  第 9-10 行类头 javadoc 由：
  ```java
   * <p>The {@code onlyOnShelf} field defaults to {@code false},
   * which causes the search to include OFF_SHELF and DRAFT products.
  ```
  改为：
  ```java
   * <p>The {@code onlyOnShelf} field defaults to {@code true} (design-docs/05 section 4:
   * "默认只展示 ON_SHELF 商品"), so anonymous browsing/search only ever surfaces ON_SHELF
   * products unless the caller explicitly opts in to seeing OFF_SHELF/DRAFT items.
  ```

  第 27-31 行字段注释+声明由：
  ```java
      /**
       * When false, the search includes all non-DELETED products (ON_SHELF, OFF_SHELF, DRAFT).
       * When true, only ON_SHELF products are shown.
       * Defaults to false.
       */
      private boolean onlyOnShelf = false;
  ```
  改为：
  ```java
      /**
       * When false, the search includes all non-DELETED products (ON_SHELF, OFF_SHELF, DRAFT).
       * When true, only ON_SHELF products are shown.
       * Defaults to true.
       */
      private boolean onlyOnShelf = true;
  ```

  `ProductSearchService.java` 里 `if (request.isOnlyOnShelf()) {...} else {...}` 的分支逻辑本身没问题
  （值为 true 时只查 ON_SHELF，false 时排除 DELETED 之外全都要）——该文件的其它问题（类目/标签/分页/
  关键词）在 PRODUCT-3 处理，本卡不用碰 `ProductSearchService.java`。
- **验收**: 构造一个 OFF_SHELF 的 SKU 和一个 DRAFT 的 SKU（`skuCode`/`name` 用关键词能唯一命中的值），
  不带 `onlyOnShelf` 参数调用 `GET /api/v1/products/search?keyword=xxx`，两者都不应出现在结果里；
  显式加 `&onlyOnShelf=false` 后两者都应出现。

---

### PRODUCT-3 | 商品搜索：类目不含子类目、标签过滤未接入、分页 total 算错、关键词漏配 SPU 名与卖点（4 症状 1 次改完）

- 风险: high · 置信度: definite（症状 1-3：类目/标签/分页 total）+ likely（症状 4：关键词匹配 SPU
  名与卖点——findings 第一轮 §6.6 #9 原评 `suspicious`，第二轮深审 #26 复核后升级为 `likely`；
  `design-docs/05-商品服务设计.md` §4 对"keyword | 商品名称、卖点模糊匹配"的要求本身是明文规定，
  不确定性只在于"具体该不该实现"，参考实现里已连带单测/集成测试一起验证过，实现本身无歧义）
- **文件**（4 个，1 改 1 改 2 新增）:
  1. `code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductSearchService.java`（整份重写）
  2. `code/ecommerce-product/src/main/java/com/ecommerce/product/repository/ProductSpuRepository.java`（新增 4 个查询方法）
  3. `code/ecommerce-product/src/main/java/com/ecommerce/product/entity/SpuTagRelation.java` 【新增】
  4. `code/ecommerce-product/src/main/java/com/ecommerce/product/repository/SpuTagRelationRepository.java` 【新增】
- **现状**（基线 `ProductSearchService.java` 共 154 行；4 个症状分别对应下面 4 段）:

  1. **类目过滤不含子类目**（findings §6.6 #4，位置第 121-130 行）：
     ```java
         /**
          * Checks whether the SKU's SPU belongs to the given category or any of its descendants.
          */
         private boolean matchesCategory(ProductSku sku, Map<Long, ProductSpu> spuMap, Long categoryId) {
             if (categoryId == null) {
                 return true;
             }
             ProductSpu spu = spuMap.get(sku.getSpuId());
             return spu != null && categoryId.equals(spu.getCategoryId());
         }
     ```
     方法名和 javadoc 都在讲"或其任意后代类目"，但方法体只做了 `categoryId.equals(spu.getCategoryId())`
     直接相等比较——按父类目搜索时，挂在子类目下的商品一个都搜不到。

  2. **标签过滤字段完全没被读取**（findings §6.6 #5）：`ProductSearchRequest.getTags()`
     （`List<String> tags` 字段）在整个 `ProductSearchService.java` 里被引用次数为 **0**
     （`grep -n "getTags\|tags" ProductSearchService.java` 零命中）——请求带不带 `tags` 参数，
     结果完全没有区别。且当前仓库压根没有"SPU 关联了哪些标签"这张关系表：`ProductTag`
     实体（`code/ecommerce-product/src/main/java/com/ecommerce/product/entity/ProductTag.java`）
     只是一个独立标签目录（`id`/`name`/`color`），没有任何字段/关联表把它和 `ProductSpu` 绑在一起。

  3. **分页 total 在类目/品牌过滤时算错**（findings §6.6 #6，位置第 61-86 行的 `search()` 方法核心段）：
     ```java
             Specification<ProductSku> spec = buildSpecification(request);
             PageRequest pageRequest = PageRequest.of(request.getPage(), request.getSize(),
                     Sort.by(Sort.Direction.DESC, "sortOrder"));
             Page<ProductSku> page = skuRepository.findAll(spec, pageRequest);
             // ...
             List<ProductListResponse> items = page.getContent().stream()
                     .filter(sku -> matchesCategory(sku, spuMap, request.getCategoryId()))
                     .filter(sku -> matchesBrand(sku, spuMap, request.getBrandId()))
                     .map(sku -> toListResponse(sku, spuMap.get(sku.getSpuId())))
                     .collect(Collectors.toList());
             return PageResponse.of(request.getPage(), request.getSize(), page.getTotalElements(), items);
     ```
     `buildSpecification(request)` 传给数据库分页查询的 `Specification` 只表达了 status/keyword/
     price 三类条件（见第 92-119 行），**不含类目和品牌**；类目、品牌过滤是在数据库已经按
     `pageRequest` 分好页**之后**，对这一页的 `page.getContent()` 再做一次内存 `filter`。这样有
     两个后果：(a) 返回的 `total`（`page.getTotalElements()`）是"过滤类目/品牌之前"的总数，跟真正
     符合条件的商品数不一致；(b) 只要传了 `categoryId`/`brandId` 且结果跨页，后面几页会丢商品
     （比如第 0 页 20 条里刚好只有 3 条属于该类目，返回的 `items` 就只有 3 条，但 `total` 却是
     "所有状态/关键词/价格匹配的总数"，客户端按 `total`/`size` 算页数会算错，且换页也翻不出该类目
     下页码更靠后的商品）。

  4. **关键词只匹配 SKU 名，不匹配 SPU 名/卖点**（findings §6.6 #9 + 第二轮深审 #26，同一根因合并）：
     `buildSpecification` 里关键词谓词（第 104-106 行）：
     ```java
             if (request.getKeyword() != null && !request.getKeyword().isBlank()) {
                 predicates.add(cb.like(cb.lower(root.get("name")),
                         "%" + request.getKeyword().toLowerCase() + "%"));
             }
     ```
     `root` 是 `ProductSku`，`root.get("name")` 只查 SKU 自己的名称，从未涉及 `ProductSpu.name`
     （商品名称）或 `ProductSpu.description`（卖点）。设计要求关键词能匹配到"商品名称、卖点"，
     基线只覆盖了 SKU 名这一种。

- **期望**（逐条对应上面 4 个症状）: 依据均为 `design-docs/05-商品服务设计.md` §4（搜索条件表）：
  1. `categoryId | 类目过滤，包含子类目`——按某类目搜索必须同时命中该类目自身及其全部后代类目下的商品。
  2. `tags | 标签过滤`——传 `tags` 时只返回关联了其中任一标签的 SPU 下的商品。
  3. 分页 `{page,size,total,items}`（`design-docs/01-项目概述.md` §6/§7 统一格式）里的 `total` 必须
     反映应用了全部激活过滤条件（含类目、品牌、标签）后的真实总数，且任意页码都不能漏商品——即类目/
     品牌/标签过滤必须在数据库层面、与分页同一次查询里生效，不能等分页取完一页后再在内存里二次过滤。
  4. `keyword | 商品名称、卖点模糊匹配`——关键词至少要能匹配 SKU 名、SPU 名（"商品名称"）、SPU
     的 `description`（"卖点"）三者之一。
- **改法**: 分四步。**新增两个类**、**给 `ProductSpuRepository` 追加 4 个方法**、**整份重写
  `ProductSearchService.java`**。请求/响应 DTO（`ProductSearchRequest`、`ProductListResponse`）、
  REST 端点（`GET /api/v1/products`、`/search`）、分页信封字段名 `{page,size,total,items}`
  一律不动。

  **第 1 步 —— 新增 `code/ecommerce-product/src/main/java/com/ecommerce/product/entity/SpuTagRelation.java`**
  （逐字照抄，`design-docs/附录C-数据模型.md` 只列了 `product_spu`/`product_sku` 两张表，属于
  非穷尽列举——`product_tag` 表本身在基线上也不在附录C 里却已存在，新增一张关系表不违反冻结契约；
  应用 `ddl-auto: create-drop`，新 `@Entity` 会自动建表，不需要任何 schema.sql/migration）：

  ```java
  package com.ecommerce.product.entity;

  import com.ecommerce.common.model.BaseEntity;
  import jakarta.persistence.Column;
  import jakarta.persistence.Entity;
  import jakarta.persistence.Table;

  /**
   * Associates a {@link ProductSpu} with a tag name for search/filtering purposes
   * (design-docs/05 section 4: "tags | 标签过滤"). Tag names are stored directly
   * (rather than a foreign key to {@link ProductTag}) since {@code ProductSearchRequest#getTags()}
   * is a list of tag names, not tag ids — consistent with the rest of this module's
   * id-based (not JPA-relationship-based) cross-entity references.
   */
  @Entity
  @Table(name = "product_spu_tag")
  public class SpuTagRelation extends BaseEntity {

      @Column(name = "spu_id", nullable = false)
      private Long spuId;

      @Column(name = "tag_name", nullable = false, length = 64)
      private String tagName;

      public SpuTagRelation() {
      }

      public SpuTagRelation(Long spuId, String tagName) {
          this.spuId = spuId;
          this.tagName = tagName;
      }

      public Long getSpuId() {
          return spuId;
      }

      public void setSpuId(Long spuId) {
          this.spuId = spuId;
      }

      public String getTagName() {
          return tagName;
      }

      public void setTagName(String tagName) {
          this.tagName = tagName;
      }
  }
  ```

  **第 2 步 —— 新增 `code/ecommerce-product/src/main/java/com/ecommerce/product/repository/SpuTagRelationRepository.java`**
  （逐字照抄）：

  ```java
  package com.ecommerce.product.repository;

  import com.ecommerce.product.entity.SpuTagRelation;
  import org.springframework.data.jpa.repository.JpaRepository;
  import org.springframework.stereotype.Repository;

  import java.util.Collection;
  import java.util.List;

  @Repository
  public interface SpuTagRelationRepository extends JpaRepository<SpuTagRelation, Long> {

      List<SpuTagRelation> findByTagNameIn(Collection<String> tagNames);
  }
  ```

  **第 3 步 —— `ProductSpuRepository.java` 追加 4 个 Spring Data 派生查询方法**（只在接口体内追加方法，
  不改已有的 `findBySpuCode`）。改后整份内容：

  ```java
  package com.ecommerce.product.repository;

  import com.ecommerce.product.entity.ProductSpu;
  import org.springframework.data.jpa.repository.JpaRepository;
  import org.springframework.stereotype.Repository;

  import java.util.Collection;
  import java.util.List;
  import java.util.Optional;

  @Repository
  public interface ProductSpuRepository extends JpaRepository<ProductSpu, Long> {

      Optional<ProductSpu> findBySpuCode(String spuCode);

      List<ProductSpu> findByCategoryIdIn(Collection<Long> categoryIds);

      List<ProductSpu> findByBrandId(Long brandId);

      List<ProductSpu> findByNameContainingIgnoreCase(String keyword);

      List<ProductSpu> findByDescriptionContainingIgnoreCase(String keyword);
  }
  ```

  **第 4 步 —— `ProductSearchService.java` 整份替换**（新增 `CategoryRepository`——已存在，`findByParentId`
  基线就有，只是之前没被这个类注入过——和 `SpuTagRelationRepository` 两个构造函数依赖；核心思路：
  类目/品牌/标签三类"限制性"过滤先各自解析成一个 SPU id 集合、取交集，作为 `spuId IN (...)` 谓词跟
  status/keyword/price 一起下推进同一个 `Specification`；关键词额外解析出"SPU 名或卖点匹配"的
  SPU id 集合，作为 `OR` 谓词加宽 SKU 名匹配，而不是收窄）：

  ```java
  package com.ecommerce.product.service;

  import com.ecommerce.common.dto.PageResponse;
  import com.ecommerce.product.dto.ProductListResponse;
  import com.ecommerce.product.dto.ProductSearchRequest;
  import com.ecommerce.product.entity.ProductSku;
  import com.ecommerce.product.entity.ProductSpu;
  import com.ecommerce.product.entity.SkuStatus;
  import com.ecommerce.product.entity.SpuTagRelation;
  import com.ecommerce.product.repository.CategoryRepository;
  import com.ecommerce.product.repository.ProductSkuRepository;
  import com.ecommerce.product.repository.ProductSpuRepository;
  import com.ecommerce.product.repository.SpuTagRelationRepository;
  import jakarta.persistence.criteria.Predicate;
  import org.slf4j.Logger;
  import org.slf4j.LoggerFactory;
  import org.springframework.data.domain.Page;
  import org.springframework.data.domain.PageRequest;
  import org.springframework.data.domain.Sort;
  import org.springframework.data.jpa.domain.Specification;
  import org.springframework.stereotype.Service;
  import org.springframework.transaction.annotation.Transactional;

  import java.util.ArrayDeque;
  import java.util.ArrayList;
  import java.util.Collections;
  import java.util.Deque;
  import java.util.HashSet;
  import java.util.List;
  import java.util.Map;
  import java.util.Set;
  import java.util.stream.Collectors;

  /**
   * Handles product search with keyword, category, brand, price range, and tag filters.
   *
   * <p>Only {@code ON_SHELF} products are returned by default (design-docs/05 section 4:
   * "默认只展示 ON_SHELF 商品"); callers may explicitly pass {@code onlyOnShelf=false} to also
   * see OFF_SHELF/DRAFT items. Category filtering includes all descendant categories. Category,
   * brand, and tag filters are all resolved to a restricted set of SPU ids and pushed into the
   * database-level {@link Specification} (never applied in-memory after the page is fetched),
   * so that both the returned page contents and the reported {@code total} consistently reflect
   * every active filter.
   */
  @Service
  public class ProductSearchService {

      private static final Logger log = LoggerFactory.getLogger(ProductSearchService.class);

      private final ProductSkuRepository skuRepository;
      private final ProductSpuRepository spuRepository;
      private final CategoryRepository categoryRepository;
      private final SpuTagRelationRepository spuTagRelationRepository;

      public ProductSearchService(ProductSkuRepository skuRepository,
                                  ProductSpuRepository spuRepository,
                                  CategoryRepository categoryRepository,
                                  SpuTagRelationRepository spuTagRelationRepository) {
          this.skuRepository = skuRepository;
          this.spuRepository = spuRepository;
          this.categoryRepository = categoryRepository;
          this.spuTagRelationRepository = spuTagRelationRepository;
      }

      /**
       * Searches for products matching the given criteria.
       */
      @Transactional(readOnly = true)
      public PageResponse<ProductListResponse> search(ProductSearchRequest request) {
          log.debug("Product search: keyword={}, categoryId={}, brandId={}, tags={}, onlyOnShelf={}",
                  request.getKeyword(), request.getCategoryId(), request.getBrandId(),
                  request.getTags(), request.isOnlyOnShelf());

          // Resolve category/brand/tag filters to a restricted set of matching SPU ids
          // *before* querying, so the restriction is applied at the database level rather
          // than in-memory after the page is fetched (which would corrupt both the page
          // contents and the reported total for any page beyond the first).
          Set<Long> allowedSpuIds = resolveAllowedSpuIds(request);
          if (allowedSpuIds != null && allowedSpuIds.isEmpty()) {
              return PageResponse.of(request.getPage(), request.getSize(), 0L, Collections.emptyList());
          }

          Set<Long> keywordSpuIds = resolveKeywordSpuIds(request.getKeyword());

          Specification<ProductSku> spec = buildSpecification(request, allowedSpuIds, keywordSpuIds);

          PageRequest pageRequest = PageRequest.of(
                  request.getPage(),
                  request.getSize(),
                  Sort.by(Sort.Direction.DESC, "sortOrder"));

          Page<ProductSku> page = skuRepository.findAll(spec, pageRequest);

          // Load SPU data purely for display purposes (name/image) -- every filter has
          // already been applied at the database level above, so no further in-memory
          // filtering happens here.
          List<Long> spuIds = page.getContent().stream()
                  .map(ProductSku::getSpuId)
                  .distinct()
                  .collect(Collectors.toList());
          Map<Long, ProductSpu> spuMap = spuRepository.findAllById(spuIds).stream()
                  .collect(Collectors.toMap(ProductSpu::getId, spu -> spu));

          List<ProductListResponse> items = page.getContent().stream()
                  .map(sku -> toListResponse(sku, spuMap.get(sku.getSpuId())))
                  .collect(Collectors.toList());

          return PageResponse.of(request.getPage(), request.getSize(), page.getTotalElements(), items);
      }

      /**
       * Resolves the set of SPU ids allowed by the category/brand/tag filters combined
       * (intersection of each active filter). Returns {@code null} when none of these
       * filters are present, meaning no restriction should be applied at all.
       */
      private Set<Long> resolveAllowedSpuIds(ProductSearchRequest request) {
          Set<Long> allowed = null;

          if (request.getCategoryId() != null) {
              Set<Long> categoryIds = resolveDescendantCategoryIds(request.getCategoryId());
              Set<Long> spuIds = spuRepository.findByCategoryIdIn(categoryIds).stream()
                      .map(ProductSpu::getId)
                      .collect(Collectors.toSet());
              allowed = spuIds;
          }

          if (request.getBrandId() != null) {
              Set<Long> spuIds = spuRepository.findByBrandId(request.getBrandId()).stream()
                      .map(ProductSpu::getId)
                      .collect(Collectors.toSet());
              allowed = intersect(allowed, spuIds);
          }

          List<String> tags = sanitizedTags(request.getTags());
          if (!tags.isEmpty()) {
              Set<Long> spuIds = spuTagRelationRepository.findByTagNameIn(tags).stream()
                      .map(SpuTagRelation::getSpuId)
                      .collect(Collectors.toSet());
              allowed = intersect(allowed, spuIds);
          }

          return allowed;
      }

      private List<String> sanitizedTags(List<String> tags) {
          if (tags == null || tags.isEmpty()) {
              return Collections.emptyList();
          }
          return tags.stream()
                  .filter(tag -> tag != null && !tag.isBlank())
                  .collect(Collectors.toList());
      }

      /**
       * Intersects {@code other} into {@code current}. When {@code current} is {@code null}
       * (no restriction applied yet), {@code other} becomes the new restriction.
       */
      private Set<Long> intersect(Set<Long> current, Set<Long> other) {
          if (current == null) {
              return other;
          }
          Set<Long> result = new HashSet<>(current);
          result.retainAll(other);
          return result;
      }

      /**
       * Resolves the set of SPU ids whose SPU-level name OR description ("卖点") matches
       * the keyword, so that search can match on the SKU name, the SPU name, or the SPU's
       * selling-point description -- per design-docs/05 section 4 ("keyword | 商品名称、
       * 卖点模糊匹配"). Returns an empty set when there is no keyword or nothing matches at
       * the SPU level; an empty set here only widens (never narrows) the keyword predicate,
       * so it never excludes SKU-name matches.
       */
      private Set<Long> resolveKeywordSpuIds(String keyword) {
          if (keyword == null || keyword.isBlank()) {
              return Collections.emptySet();
          }
          Set<Long> ids = spuRepository.findByNameContainingIgnoreCase(keyword).stream()
                  .map(ProductSpu::getId)
                  .collect(Collectors.toCollection(HashSet::new));
          spuRepository.findByDescriptionContainingIgnoreCase(keyword)
                  .forEach(spu -> ids.add(spu.getId()));
          return ids;
      }

      /**
       * Resolves the category itself plus every descendant category (recursively), so that
       * filtering by a parent category also includes products filed under any sub-category
       * (design-docs/05 section 4: "categoryId | 类目过滤，包含子类目").
       */
      private Set<Long> resolveDescendantCategoryIds(Long rootCategoryId) {
          Set<Long> result = new HashSet<>();
          Deque<Long> toVisit = new ArrayDeque<>();
          toVisit.add(rootCategoryId);
          while (!toVisit.isEmpty()) {
              Long current = toVisit.poll();
              if (!result.add(current)) {
                  continue;
              }
              categoryRepository.findByParentId(current).forEach(child -> toVisit.add(child.getId()));
          }
          return result;
      }

      /**
       * Builds a JPA Specification for the search criteria. Category, brand, and tag filters
       * are expressed as a {@code spuId IN (...)} predicate resolved ahead of time (see
       * {@link #resolveAllowedSpuIds}), and keyword matching is widened with an OR'd
       * {@code spuId IN (...)} predicate (see {@link #resolveKeywordSpuIds}), so that every
       * filter -- including pagination totals -- is evaluated by the database in one query.
       */
      private Specification<ProductSku> buildSpecification(ProductSearchRequest request,
                                                            Set<Long> allowedSpuIds,
                                                            Set<Long> keywordSpuIds) {
          return (root, query, cb) -> {
              List<Predicate> predicates = new ArrayList<>();

              if (request.isOnlyOnShelf()) {
                  predicates.add(cb.equal(root.get("status"), SkuStatus.ON_SHELF));
              } else {
                  // Explicitly opted out of the ON_SHELF-only default: show all non-DELETED products.
                  predicates.add(cb.notEqual(root.get("status"), SkuStatus.DELETED));
              }

              if (request.getKeyword() != null && !request.getKeyword().isBlank()) {
                  Predicate skuNameMatches = cb.like(cb.lower(root.get("name")),
                          "%" + request.getKeyword().toLowerCase() + "%");
                  if (!keywordSpuIds.isEmpty()) {
                      predicates.add(cb.or(skuNameMatches, root.get("spuId").in(keywordSpuIds)));
                  } else {
                      predicates.add(skuNameMatches);
                  }
              }

              if (request.getMinPrice() != null) {
                  predicates.add(cb.greaterThanOrEqualTo(root.get("price"), request.getMinPrice()));
              }

              if (request.getMaxPrice() != null) {
                  predicates.add(cb.lessThanOrEqualTo(root.get("price"), request.getMaxPrice()));
              }

              if (allowedSpuIds != null) {
                  predicates.add(root.get("spuId").in(allowedSpuIds));
              }

              return cb.and(predicates.toArray(new Predicate[0]));
          };
      }

      private ProductListResponse toListResponse(ProductSku sku, ProductSpu spu) {
          ProductListResponse response = new ProductListResponse();
          response.setSkuId(sku.getId());
          response.setSpuId(sku.getSpuId());
          response.setName(sku.getName());
          response.setPrice(sku.getPrice());
          response.setStatus(sku.getStatus().name());
          response.setMainImage(spu != null ? spu.getMainImage() : sku.getImage());
          response.setSalesCount(sku.getSalesCount());
          return response;
      }
  }
  ```

  注意 `matchesCategory`/`matchesBrand` 两个旧的私有方法整个被删除（其逻辑已经被
  `resolveAllowedSpuIds`/`resolveDescendantCategoryIds` 取代），`toListResponse` 原样保留在文件末尾。
- **验收**（可仿照 `code/ecommerce-product/src/test/java/com/ecommerce/product/service/` 下用
  `@DataJpaTest` 起真实 H2 的方式各写一个用例，也可以走 REST 端到端验证）:
  1. 类目含子类目 + 分页 total 正确：建一个父类目挂 3 个 SPU、其子类目再挂 3 个 SPU、另一个无关类目挂
     1 个 SPU；按父类目 id 搜索、`size=4`：第 0 页 `total=6`、`items.size()=4`；第 1 页 `total=6`、
     `items.size()=2`；那个无关类目的 SPU 永远不出现、不计入 `total`。
  2. 标签过滤：给某个 SPU 关联一条 `SpuTagRelation(spuId, "clearance")`，其余 SPU 不关联；按
     `tags=["clearance"]` 搜索，`total=1` 且命中的正是那个 SPU。不传 `tags` 时不受影响（且不应该
     触发 `spuTagRelationRepository` 查询，避免无谓开销）。
  3. 关键词匹配 SPU 名：关键词设为某个 SPU 的 `name`（这个词完全不出现在任何 SKU 自己的 `name` 里），
     该 SPU 下的 SKU 仍应被搜到。
  4. 关键词匹配卖点：关键词设为某个 SPU 的 `description` 里的一段文字（同样不出现在任何 SPU/SKU 的
     `name` 里），该 SPU 下的 SKU 仍应被搜到——用于验证 `findByDescriptionContainingIgnoreCase`
     确实被调用到（不是只测了名称那一半）。
  5. 关键词仍能匹配纯 SKU 名（不出现在任何 SPU 名/description 里的词）——确认加宽逻辑没有破坏原有
     行为。
  6. `PageResponse` 的 JSON 字段名仍是 `page`/`size`/`total`/`items`，未改名。
- **勿犯**:
  1. 不要改动 `ProductSearchRequest`/`ProductListResponse` 的任何已有字段名或 `PageResponse` 的
     `{page,size,total,items}` 结构——这是 README 冻结契约（`design-docs/01-项目概述.md` §6/§7）,
     本卡引入的新字段（`tags` 的实际使用）不改变既有 JSON 形状。
  2. 不要把类目/品牌/标签过滤留在内存 `filter` 里"顺手"解决——那正是 #6 的病根；必须落实成
     `Specification` 里的 `spuId IN (...)` 谓词，让同一次 `skuRepository.findAll(spec, pageRequest)`
     算出的 `Page.getTotalElements()` 直接就是正确答案。
  3. `SpuTagRelation`/`SpuTagRelationRepository` 是全新类，仓库里目前没有任何 REST 端点（含
     `SpuCreateRequest`）能把标签关联写进去——`AdminProductController`/`SpuService.createSpu` 均不受
     本卡影响、不需要改，也不要顺手加一个打标签的端点（超出本卡范围，README 冻结的商品接口列表里没有
     这个端点）。测试/自查只能通过直接持久化 `SpuTagRelation` 实体（如 `@DataJpaTest`）来验证标签过滤
     的查询逻辑本身是对的。
  4. `resolveDescendantCategoryIds` 用的是显式 `Deque` 广度优先遍历，不是 JPA 关联/递归 CTE；类目树
     很浅（设计上是有限层级），不要为了"优化"改成递归 SQL 或给 `Category` 加 `@OneToMany` 双向关联，
     那会引入新的复杂度且不是本卡范围。
  5. 不要删除或改写 `ProductSearchService` 之外的其它文件（`ProductController`、
     `ProductListResponse`、`ProductSpu`、`Category`、`CategoryRepository` 均不需要改，
     `CategoryRepository.findByParentId` 基线就有）。

---

### PRODUCT-4 | 重复 `skuCode`/`spuCode` 创建抛 400（`ValidationException`），应 409（`ConflictException`）

- 风险: low · 置信度: definite
- **文件**:
  1. `code/ecommerce-product/src/main/java/com/ecommerce/product/service/SkuService.java`
  2. `code/ecommerce-product/src/main/java/com/ecommerce/product/service/SpuService.java`
- **现状**:
  1. `SkuService.createSku()` 第 46-48 行：
     ```java
             if (skuRepository.findBySkuCode(request.getSkuCode()).isPresent()) {
                 throw new ValidationException("skuCode", "SKU code already exists: " + request.getSkuCode());
             }
     ```
  2. `SpuService.createSpu()` 第 36-38 行：
     ```java
             if (spuRepository.findBySpuCode(request.getSpuCode()).isPresent()) {
                 throw new ValidationException("spuCode", "SPU code already exists: " + request.getSpuCode());
             }
     ```
  两处编码唯一性冲突都抛 `ValidationException`（`GlobalExceptionHandler.handleValidation` 映射为
  400 `VALIDATION_FAILED`），但这不是"参数格式不对"，而是"资源已存在的重复请求"，属于状态冲突。
- **期望**: 创建时 `skuCode`/`spuCode` 已存在应返回 409，而不是 400。依据:
  `design-docs/03-通用规范与非功能设计.md` §2（异常表："`ConflictException` | 状态冲突、重复提交 | 409"）、
  `README.md` §7.1 通用错误码表（"`CONFLICT` | 409 | 状态冲突或重复请求"）——与仓库里 user 注册、
  review 重复提交、settlement 等处理"已存在/重复提交"场景时的一贯模式一致。
- **改法**: 各自只改一行 `throw`，其余方法体（含 `ResourceNotFoundException` 校验、字段赋值、
  `ValidationException` 用于 specs/images 序列化失败的另一处用法）完全不动，两个文件都要在 import
  区加一行 `import com.ecommerce.common.exception.ConflictException;`（`ValidationException` 的
  import 继续保留，两个文件里都还有别的地方在用它）。

  `SkuService.java` 第 46-48 行改为：
  ```java
          if (skuRepository.findBySkuCode(request.getSkuCode()).isPresent()) {
              // Duplicate unique code on create is a conflict (409), consistent with
              // README §7 (CONFLICT = 状态冲突或重复请求) and the same pattern used by
              // user registration, review, settlement, etc. — not a 400 param error.
              throw new ConflictException("SKU code already exists: " + request.getSkuCode());
          }
  ```

  `SpuService.java` 第 36-38 行改为：
  ```java
          if (spuRepository.findBySpuCode(request.getSpuCode()).isPresent()) {
              // Duplicate unique code on create is a conflict (409), consistent with
              // README §7 and the user/review/settlement "already exists" pattern.
              throw new ConflictException("SPU code already exists: " + request.getSpuCode());
          }
  ```

  本卡与 PRODUCT-5 都会改 `SkuService.java`，但本卡只碰 `createSku()`、PRODUCT-5 只碰
  `onShelf()`/`offShelf()`，互不重叠，两卡顺序无关，可一次性改完再编译自检。
- **验收**: 用同一个 `skuCode` 连续 `POST /api/v1/admin/products/sku` 两次，第二次返回 409，响应体
  `code` 字段为 `CONFLICT`；`spuCode` 同理对 `POST /api/v1/admin/products/spu` 验证。若顺手同步
  `code/ecommerce-product/src/test/java/.../SkuServiceTest.java`/`SpuServiceTest.java`
  里断言"抛 `ValidationException`"的用例，改成断言 `ConflictException`（`isInstanceOf(ConflictException.class)`），
  `hasMessageContaining` 的消息文本不变。

---

### PRODUCT-5 | 对 `DELETED` 状态的 SKU 上/下架抛 400，应 409（状态机非法迁移）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-product/src/main/java/com/ecommerce/product/service/SkuService.java`
- **现状**: SKU 状态机是 `DRAFT -> ON_SHELF -> OFF_SHELF -> DELETED`（`DRAFT` 也可直接到
  `DELETED`），定义在
  `code/ecommerce-product/src/main/java/com/ecommerce/product/entity/SkuStatus.java` 的注释里。
  `onShelf()` 第 78-87 行：
  ```java
      @Transactional
      public void onShelf(Long skuId) {
          ProductSku sku = findSku(skuId);
          if (sku.getStatus() == SkuStatus.DELETED) {
              throw new ValidationException("status", "Cannot put a DELETED SKU on shelf");
          }
          sku.setStatus(SkuStatus.ON_SHELF);
          skuRepository.save(sku);
          log.info("SKU on shelf: skuId={}, skuCode={}", skuId, sku.getSkuCode());
      }
  ```
  `offShelf()` 第 92-101 行结构相同：
  ```java
      @Transactional
      public void offShelf(Long skuId) {
          ProductSku sku = findSku(skuId);
          if (sku.getStatus() == SkuStatus.DELETED) {
              throw new ValidationException("status", "Cannot take a DELETED SKU off shelf");
          }
          sku.setStatus(SkuStatus.OFF_SHELF);
          skuRepository.save(sku);
          log.info("SKU off shelf: skuId={}, skuCode={}", skuId, sku.getSkuCode());
      }
  ```
  对已 `DELETED` 的 SKU 请求上架/下架，两处都抛 `ValidationException`→400。这不是参数格式问题，是
  试图把状态机往非法方向迁移（`DELETED` 是终态，不能再回到 `ON_SHELF`/`OFF_SHELF`），属于状态冲突。
- **期望**: 对 `DELETED` SKU 请求上架/下架应返回 409。依据: `design-docs/03-通用规范与非功能设计.md`
  §2（`ConflictException` = 状态冲突、重复提交 = 409）、`README.md` §7.1（`CONFLICT`/409）——与
  order/payment/logistics 模块里"状态机非法迁移一律 409"的处理范式一致。
- **改法**: 各自只改 `if (sku.getStatus() == SkuStatus.DELETED)` 块内的一行 `throw`，方法的其余部分
  （查 SKU、`setStatus`、`save`、日志）都不动，也不改方法签名/不加参数（`onShelf(Long skuId)`/
  `offShelf(Long skuId)` 形参维持基线的样子——之后 `S3-audit.md` 会另外给这两个方法加
  `operatorId` 参数用于审计，与本卡改动的行不冲突，不需要本卡预先处理）。需要在 import 区加
  `import com.ecommerce.common.exception.ConflictException;`（`ValidationException` 的 import
  继续保留，`createSku` 的 specs 序列化失败分支还在用）。

  `onShelf()` 里的 `if` 块改为：
  ```java
          if (sku.getStatus() == SkuStatus.DELETED) {
              // Illegal state-machine transition (DELETED → ON_SHELF) is a conflict (409),
              // consistent with README §7 and order/payment/logistics state handling.
              throw new ConflictException("Cannot put a DELETED SKU on shelf");
          }
  ```

  `offShelf()` 里的 `if` 块改为：
  ```java
          if (sku.getStatus() == SkuStatus.DELETED) {
              // Illegal state-machine transition (DELETED → OFF_SHELF) is a conflict (409).
              throw new ConflictException("Cannot take a DELETED SKU off shelf");
          }
  ```
- **验收**: 构造一个 `DELETED` 状态的 SKU（当前生产代码没有对外的"删除 SKU"端点，可在测试里直接
  `sku.setStatus(SkuStatus.DELETED)` 后 `save`），调用 `skuService.onShelf(skuId)`/`offShelf(skuId)`
  应抛 `ConflictException` 而非 `ValidationException`；走 HTTP 层
  `POST /api/v1/admin/products/sku/{skuId}/on-shelf`/`off-shelf` 对该 SKU 请求应返回 409。若顺手
  同步 `SkuServiceTest.java` 里对应两个用例的异常类型断言（`isInstanceOf(ConflictException.class)`），
  消息文本不变。
