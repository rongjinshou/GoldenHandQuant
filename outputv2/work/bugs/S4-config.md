# B19 · S4-config — 四类限流注解 + 商品详情缓存(复用既有 CacheManager)

本批是执行顺序里的**最后一批**（B19）。5 张卡：CFG-1~CFG-4 是四类限流——`@RateLimit`/
`RateLimitAspect` 基础设施在 `ecommerce-common` 里早就写好且完整可用（`RateLimitException`→429+
`RATE_LIMITED` 已接入 `GlobalExceptionHandler`，`RateLimitAspectTest` 已覆盖切面本身），零处使用，
本批只是把注解分别贴到 4 个方法上，风险都是 low。CFG-5 是商品详情缓存，风险 **high**，是本批
唯一一张要新增类的卡——**上一次评测就是在同类改动上翻的车**：某 agent 加商品缓存时新建了第二个
`CacheManager` bean，Spring 容器直接起不来，24 例黑盒从"部分失败"变成"全部 ERROR"。CFG-5 的
「勿犯」写得比其他卡长得多，动手前完整读一遍，不要跳读。

**先纠正标题里的一个说法**：标题"复用既有 CacheManager"容易让人以为 cart 模块提供了一个 Spring
`CacheManager` 类型的全局 bean，商品缓存应该去注入它——**这个理解是错的**，会直接导向 CFG-5
「勿犯」里描述的那种事故。cart 模块的 `CartCacheConfig` 提供的是一个**裸 Caffeine
`Cache<Long, CartData>` bean**（`com.github.benmanes.caffeine.cache.Cache`），根本不是 Spring 的
`org.springframework.cache.CacheManager`。CFG-5 真正"复用"的是 cart 已经用过的**模式**——"手写一个
独立的 Caffeine `Cache<K,V>` bean + 一个手动 get/put/evict 的 manager 类"，而不是某一个具体的
既有 bean 实例。CFG-5 正文开头会再展开讲一遍这个区分，照 CFG-5 正文做，不要被标题带偏。

修完本批任意一张限流卡后可以继续下一张再统一 verify；但 CFG-5 改完**必须单独立刻**
`bash work/harness/ratchet.sh verify`，不要跟其他卡攒在一起验证——见 CFG-5「勿犯」最后一条。

---

### CFG-1 | 登录接口无限流（同用户名 5 次/分钟）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-user/src/main/java/com/ecommerce/user/controller/UserController.java`
- **现状**: `login()` 方法（`POST /api/v1/users/login`）没有任何限流注解或限流逻辑，文件顶部
  也没有导入 `com.ecommerce.common.ratelimit.RateLimit`。
- **期望**: 同一用户名每分钟最多 5 次登录尝试，第 6 次起返回 429 + 错误码 `RATE_LIMITED`。
  依据：design-docs/03 §4「本地限流」表第一行（"登录 | 同一用户名每分钟 5 次"）+ 同节末句
  "限流触发时返回 429，错误码为 RATE_LIMITED"。**字段名对照**：`LoginRequest` 的冻结字段名是
  `email`（其 javadoc 已注明"The email field also accepts a nickname/username"）——设计文档里的
  "用户名"指的就是这个 `email` 字段，不要另造一个用户名字段或去改 `LoginRequest`。
- **改法**:
  1. 加 import：`import com.ecommerce.common.ratelimit.RateLimit;`
  2. 在 `login` 方法上加注解（与 `@PostMapping` 的相对顺序不影响语义，两种顺序都可以）：
     ```java
     @RateLimit(key = "'login:' + #request.email", permitsPerMinute = 5)
     @PostMapping("/api/v1/users/login")
     public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
     ```
  方法体、参数列表、返回类型一律不动，只加这一个注解 + 一个 import。
- **验收**: 同一 email 连续 6 次调用 `POST /api/v1/users/login`（密码对错不影响限流，限流在业务
  逻辑之前拦截），前 5 次正常进入业务逻辑，第 6 次直接 429，响应体 `code=RATE_LIMITED`；换一个
  不同 email 立刻恢复可用（证明限流桶按 email 隔离，不是全局共享一个桶）。
- **勿犯**: key 表达式必须逐字符是 `'login:' + #request.email`——`request` 必须是方法参数名，
  `.email` 必须是 `LoginRequest` 的字段名，任一写错，`RateLimitAspect.resolveKey` 会捕获异常并
  静默退化为把整段表达式**当成一个全局固定字符串 key**：所有用户共享同一个 5 次/分钟的桶，
  会把跟登录无关的其他用户也误限流。`permitsPerMinute` 必须是 `5`（不是注解默认值 60，也不是
  其他阈值），阈值/维度不要自行发挥。

---

### CFG-2 | 商品搜索接口无限流（同 IP 120 次/分钟）

- 风险: low · 置信度: definite（第一轮发现时标注 suspicious，第二/三轮未推翻且已在 参考实现
  实测 24/24 通过，按已验证结果直接落地，不必再犹豫）
- **文件**: `code/ecommerce-product/src/main/java/com/ecommerce/product/controller/ProductController.java`
- **现状**: `searchProducts(ProductSearchRequest request)`（`GET /api/v1/products/search`）没有限流；
  方法当前只有一个参数，拿不到调用方 IP。文件未导入 `RateLimit`，也未导入
  `jakarta.servlet.http.HttpServletRequest`。
- **期望**: 同一客户端 IP 每分钟最多 120 次商品搜索，超限 429/`RATE_LIMITED`。依据：design-docs/03
  §4（"商品搜索 | 同一 IP 每分钟 120 次"）。**维度是 IP**——这是四类限流规则里唯一按 IP 维度的一类
  （其余三类分别是用户名/用户/paymentNo），不要图省事套用别的维度。
- **改法**:
  1. 加 import：`import com.ecommerce.common.ratelimit.RateLimit;` 和
     `import jakarta.servlet.http.HttpServletRequest;`
  2. 给 `searchProducts` 方法新增一个 `HttpServletRequest` 形参（Spring MVC 对该类型有内置参数
     解析器，不需要任何注解即可自动注入；方法体不需要用到它，它只是给注解的 SpEL 提供绑定变量）：
     ```java
     @GetMapping("/search")
     @RateLimit(key = "#httpRequest.getRemoteAddr()", permitsPerMinute = 120)
     public ResponseEntity<PageResponse<ProductListResponse>> searchProducts(ProductSearchRequest request,
                                                                              HttpServletRequest httpRequest) {
     ```
  方法体一律不动。**只改 `searchProducts` 这一个方法**，`listProducts`（`GET /api/v1/products`，
  无 `/search`）是列表默认视图，不是设计文档定义的"商品搜索"，不要加注解。
- **验收**: 同一来源 IP 连续 121 次 `GET /api/v1/products/search`，前 120 次正常，第 121 次
  429/`RATE_LIMITED`；`listProducts` 不受影响、不限流。
- **勿犯**: key 表达式必须逐字符是 `#httpRequest.getRemoteAddr()`，`httpRequest` 必须是新增形参的
  确切名字（两处名字对不上，SpEL 绑定失败，`resolveKey` 静默退化为固定字符串 key，全局所有 IP
  共享一个 120 次/分钟的桶）。`permitsPerMinute` 必须是 `120`。不要把注解加错方法（加到
  `listProducts` 或 `getProductDetail` 上）。

---

### CFG-3 | 创建订单接口无限流（同用户 20 次/分钟）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-order/src/main/java/com/ecommerce/order/controller/OrderController.java`
- **现状**: `createOrder(@Valid @RequestBody CreateOrderRequest request)`（`POST /api/v1/orders/create`）
  没有限流。方法内部通过私有方法 `getCurrentUserId()`（读 `SecurityContextHolder`）取当前用户 id，
  但参数列表里没有 `Authentication`，`@RateLimit` 的 SpEL 表达式拿不到"当前用户"这个绑定变量。
  文件未导入 `RateLimit`，也未导入 `org.springframework.security.core.Authentication`。
- **期望**: 同一用户每分钟最多 20 次创建订单，超限 429/`RATE_LIMITED`。依据：design-docs/03 §4
  （"创建订单 | 同一用户每分钟 20 次"）。**维度是用户，不是 IP**——黑盒测试全部从同一主机/同一 IP
  发起，若按 IP 限流，不同测试方法（各自登录不同用户）会共享同一个 IP 桶，互相误伤。
- **改法**:
  1. 加 import：`import com.ecommerce.common.ratelimit.RateLimit;` 和
     `import org.springframework.security.core.Authentication;`
  2. 给 `createOrder` 方法**追加**一个 `Authentication authentication` 形参（Spring Security 对该
     类型有内置解析器，自动注入当前认证主体；user 模块的 `UserController.getCurrentUser(Authentication
     authentication)` 已是同款先例，可以照抄用法）。加在注解和参数列表这两处，**方法体、返回语句
     一律不动，不管方法体现在是什么样子**（哪怕 order 模块另一张卡片已经把返回状态码从 200 改成
     201，也不受影响，两张卡改的不是同一行）：
     ```java
     @RateLimit(key = "'order-create:' + #authentication.name", permitsPerMinute = 20)
     @PostMapping("/create")
     public ResponseEntity<CreateOrderResponse> createOrder(
             @Valid @RequestBody CreateOrderRequest request,
             Authentication authentication) {
     ```
     方法体继续用原有的 `getCurrentUserId()` 取 userId 不要改——新加的 `authentication` 形参只为
     注解服务，不要"顺手"把方法体里的 `SecurityContextHolder` 用法也替换掉。
- **验收**: 同一登录用户连续 21 次 `POST /api/v1/orders/create`，前 20 次正常进入业务逻辑（是否
  真能下单成功取决于库存/余额等业务前置条件，与限流是否放行是两回事），第 21 次直接
  429/`RATE_LIMITED`；换一个不同登录用户立刻恢复可用。
- **勿犯**: key 表达式必须逐字符是 `'order-create:' + #authentication.name`（不是
  `#authentication.principal`，更不是 IP）。`authentication.name` 与 `getCurrentUserId()` 内部
  `SecurityContextHolder.getContext().getAuthentication().getName()` 取的是同一次请求里同一个
  `Authentication` 对象的同一个值，二者不会不一致，**不要**为了"统一"去改写 `getCurrentUserId()`
  的实现或删掉它。`permitsPerMinute` 必须是 `20`。**绝不要按 IP 维度实现这条**——README/设计文档
  没有"创建订单同 IP"这条规则，黑盒 harness 明确同一主机发起多个不同用户的请求，一旦按 IP 限流，
  会把互不相关的测试方法/用户错误地拴进同一个桶，产生跨用例误伤。

---

### CFG-4 | 支付回调接口无限流（同 paymentNo 20 次/分钟）

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-payment/src/main/java/com/ecommerce/payment/controller/PaymentController.java`
- **现状**: `callback(...)`（`POST /api/v1/payment/callback`）没有限流。方法已有
  `PaymentCallbackRequest request` 参数（含 `getPaymentNo()`），限流维度需要的数据已经在手，只是
  没有注解。文件未导入 `RateLimit`。
- **期望**: 同一 `paymentNo` 每分钟最多 20 次回调，超限 429/`RATE_LIMITED`。依据：design-docs/03
  §4（"支付回调 | 同一 paymentNo 每分钟 20 次"）。**维度是 paymentNo，不是 IP 也不是用户**（支付
  网关回调不带用户态 JWT，是匿名端点，签名校验/幂等键都按 `paymentNo` 走，限流沿用同一维度）。
- **改法**:
  1. 加 import：`import com.ecommerce.common.ratelimit.RateLimit;`
  2. 只在 `callback` 方法上加这一行注解，方法的其余部分——包括当前到底有几个参数、是否已经有
     `@RequestHeader("X-Payment-Signature")` 之类的签名校验参数（那是另一张卡片的范围，与本卡
     无关）——**原样不动，一个字符都不要改**：
     ```java
     @RateLimit(key = "'payment-callback:' + #request.paymentNo", permitsPerMinute = 20)
     ```
     加在方法上原有的 `@PostMapping("/callback")` 之上或之下均可。
- **验收**: 同一 `paymentNo` 连续 21 次 `POST /api/v1/payment/callback`，前 20 次正常进入业务逻辑，
  第 21 次直接 429/`RATE_LIMITED`；换一个不同 `paymentNo` 立刻恢复可用。
- **勿犯**: key 表达式必须逐字符是 `'payment-callback:' + #request.paymentNo`——`request` 必须是
  该方法里 `PaymentCallbackRequest` 参数**当前的**形参名；如果这个方法此时已经被别的卡片改过
  签名、形参名不再叫 `request`，把 SpEL 里的变量名跟着同步改掉，不要留旧名字造成绑定失败。
  `permitsPerMinute` 必须是 `20`。不要因为回调"看起来像匿名端点"就套用商品搜索的 IP 维度——四类
  限流规则各自指定了四种不同维度，不能互换，阈值/维度不要自行发挥。

---

### CFG-5 | 商品详情无 10 分钟缓存（全项目最高危改动，逐条照做，不要跳读）

- 风险: high · 置信度: definite
- **文件**（2 个新文件 + 3 个既有文件改动，属于"新增类 + 跨文件结构性改动"）：
  1. 新增 `code/ecommerce-product/src/main/java/com/ecommerce/product/config/ProductCacheConfig.java`
  2. 新增 `code/ecommerce-product/src/main/java/com/ecommerce/product/cache/ProductDetailCacheManager.java`
  3. 改 `code/ecommerce-product/pom.xml`
  4. 改 `code/ecommerce-product/src/main/java/com/ecommerce/product/service/ProductDetailService.java`
  5. 改 `code/ecommerce-product/src/main/java/com/ecommerce/product/service/SkuService.java`

- **现状**: `ProductDetailService.getProductDetail(skuId)`（`GET /api/v1/products/{skuId}`）每次
  调用都直接查 `ProductSkuRepository`/`ProductSpuRepository`/`BrandRepository`/`CategoryRepository`
  四张表拼响应，完全没有缓存层。`ecommerce-product/pom.xml` 从未声明 `caffeine` 依赖——cart 模块
  的 caffeine 依赖不会传递给 product（二者是同级模块，product 不依赖 cart，Maven 子模块之间没有
  自动共享 classpath 这回事）。`SkuService.onShelf`/`offShelf` 改变上下架状态后不做任何缓存失效
  动作（因为现在压根没有缓存可失效）。

- **期望**: 商品详情按 skuId 缓存 10 分钟；SKU 上/下架后详情要立刻反映新状态，不能等 10 分钟自然
  过期。依据：design-docs/02-系统架构.md §7「缓存设计」表（"商品详情 | `product:detail:{skuId}` |
  10 分钟 | product"）。

  **先把"复用既有 CacheManager"这句话拆开讲清楚，动手前必须分清楚这两条路线**：

  - **路线 A（本卡要用的，也是 cart 模块已经在用的）**：手写一个 Caffeine 原生
    `com.github.benmanes.caffeine.cache.Cache<K,V>` 类型的 `@Bean`，业务代码直接
    `.getIfPresent()`/`.put()`/`.invalidate()`，**完全不经过** Spring 的 `org.springframework.cache`
    抽象、不需要 `@EnableCaching`、不需要 `@Cacheable`。cart 模块既有的 `CartCacheConfig`
    （`code/ecommerce-cart/.../config/CartCacheConfig.java`）就是这条路线：它 `@Bean` 出一个
    `Cache<Long, CartData> cartCache()`——**这是一个 `Cache`，不是 `CacheManager`**，类型完全不同。
    本卡片要做的，就是照这个模式在 product 模块新建一对同构的类（`ProductCacheConfig` +
    `ProductDetailCacheManager`），不是去改 `CartCacheConfig` 或注入它已有的 `cartCache` bean
    （两个模块的缓存内容类型不同，`cartCache` 存的是 `CartData`，商品详情需要自己独立的一个
    `Cache<Long, ProductDetailResponse>` bean）。
  - **路线 B（本卡绝不要用，只是标出来避免误用）**：Spring 官方 `org.springframework.cache.CacheManager`
    + `@EnableCaching` + `@Cacheable`/`@CacheEvict` 注解式缓存。如果 inventory 模块的缓存卡片
    （`inventory.md`，B09 批次）已经落地，仓库里会出现一个 `InventoryCacheConfig`，用的正是这条
    路线：它 `@Bean` 出一个显式命名的 `CacheManager inventoryCacheManager()`，并在每个
    `@Cacheable`/`@CacheEvict` 上都显式写 `cacheManager = "inventoryCacheManager"` 来避免和其他
    `CacheManager` bean 混淆。这条路线跟商品详情缓存**没有任何关系**——不要看到 `InventoryCacheConfig`
    就照抄它的写法搬到 product 模块上，也不要觉得"反正都是缓存，统一用 Spring 官方注解更规范"而
    临时改路线。两条路线在这份代码库里长期并存、互不相干，是既有事实，不是本卡片要统一的对象。

- **改法**（照下面 5 步逐项做，不要跳步、不要合并简化）：

  1. **`ecommerce-product/pom.xml`** 加 caffeine 依赖（与 cart 模块 `pom.xml` 里的写法完全一致，
     不显式写 `<version>`，走父 POM 的 dependencyManagement）：
     ```xml
     <dependency>
         <groupId>com.github.ben-manes.caffeine</groupId>
         <artifactId>caffeine</artifactId>
     </dependency>
     ```

  2. **新建** `com.ecommerce.product.config.ProductCacheConfig`（`@Configuration`，仿
     `CartCacheConfig` 的写法，只是 TTL/类型/bean 名不同）：
     ```java
     package com.ecommerce.product.config;

     import com.ecommerce.product.dto.ProductDetailResponse;
     import com.github.benmanes.caffeine.cache.Cache;
     import com.github.benmanes.caffeine.cache.Caffeine;
     import org.springframework.context.annotation.Bean;
     import org.springframework.context.annotation.Configuration;

     import java.time.Duration;

     @Configuration
     public class ProductCacheConfig {

         private static final Duration PRODUCT_DETAIL_TTL = Duration.ofMinutes(10);
         private static final long MAX_PRODUCT_DETAIL_ENTRIES = 10_000;

         @Bean
         public Cache<Long, ProductDetailResponse> productDetailCache() {
             return Caffeine.newBuilder()
                     .expireAfterWrite(PRODUCT_DETAIL_TTL)
                     .maximumSize(MAX_PRODUCT_DETAIL_ENTRIES)
                     .recordStats()
                     .build();
         }
     }
     ```
     `@Bean` 方法名**必须**叫 `productDetailCache`，一字不改——第 3 步的
     `ProductDetailCacheManager` 靠这个名字按参数名注入消歧：Java 泛型擦除后
     `Cache<Long,CartData>`（cart 的 `cartCache`）和 `Cache<Long,ProductDetailResponse>`
     （这里的 `productDetailCache`）在运行时是同一个原始类型 `Cache`，容器里会有 2 个候选 bean，
     Spring 靠"构造函数形参名 = bean 名"来消歧；只要这里的 bean 名和第 3 步的形参名保持一致
     （不管取什么名字都行），就不会消歧失败——但**不能**取跟 `cartCache` 相同的名字。

  3. **新建** `com.ecommerce.product.cache.ProductDetailCacheManager`（`@Component`，仿 cart 的
     `CartCacheManager` 手法，包一层 get/put/evict，不直接把 Caffeine 类型暴露给 service 层）：
     ```java
     package com.ecommerce.product.cache;

     import com.ecommerce.product.dto.ProductDetailResponse;
     import com.github.benmanes.caffeine.cache.Cache;
     import org.springframework.stereotype.Component;

     @Component
     public class ProductDetailCacheManager {

         private final Cache<Long, ProductDetailResponse> productDetailCache;

         public ProductDetailCacheManager(Cache<Long, ProductDetailResponse> productDetailCache) {
             this.productDetailCache = productDetailCache;
         }

         public ProductDetailResponse get(Long skuId) {
             return productDetailCache.getIfPresent(skuId);
         }

         public void put(Long skuId, ProductDetailResponse detail) {
             productDetailCache.put(skuId, detail);
         }

         public void evict(Long skuId) {
             productDetailCache.invalidate(skuId);
         }
     }
     ```
     构造函数形参名**必须**叫 `productDetailCache`，跟第 2 步的 `@Bean` 方法名逐字对齐。

  4. **改 `ProductDetailService`**：
     - 加一个字段 `private final ProductDetailCacheManager productDetailCacheManager;`，构造函数
       在现有参数列表**末尾**追加 `ProductDetailCacheManager productDetailCacheManager`（现有的
       `skuRepository`/`spuRepository`/`brandRepository`/`categoryRepository`/`objectMapper`/
       `stockInfoFetcher` 六个参数原样保留、原有顺序不变），并在构造函数体里补
       `this.productDetailCacheManager = productDetailCacheManager;`。
     - `getProductDetail(Long skuId)` 方法：在方法开头、原有的
       `ProductSku sku = skuRepository.findById(skuId)` 这一行**之前**，插入缓存命中直接返回的
       逻辑：
       ```java
       ProductDetailResponse cached = productDetailCacheManager.get(skuId);
       if (cached != null) {
           return cached;
       }
       ```
     - 同一方法：在原有的 `log.debug("Built product detail for skuId={}", skuId);` 这一行
       **之前**（也就是 `return response;` 之前、`response` 的所有字段都已经拼好之后），插入
       写缓存的逻辑：
       ```java
       productDetailCacheManager.put(skuId, response);
       ```
     - 中间原有的查库、拼 `response` 各字段的逻辑**一行都不要动**。

  5. **改 `SkuService`**：
     - 加一个字段 `private final ProductDetailCacheManager productDetailCacheManager;`，构造函数
       追加一个 `ProductDetailCacheManager productDetailCacheManager` 参数（加在现有参数列表
       **末尾**——如果 `SkuService` 此时已经被 S3-audit 那张卡片加过 `AuditLogService
       auditLogService` 参数，就加在它后面；如果 S3-audit 还没落地，就加在 baseline 的
       `ObjectMapper objectMapper` 后面；两种情况都只是"加在当前参数列表末尾"，不要因为想凑顺序
       去挪动别的卡片已经加好的参数）。
     - 在 `onShelf(...)` 和 `offShelf(...)` 两个方法里各找到 `skuRepository.save(sku);` 这一行
       （这一行在 baseline 和任何已改版本里都存在、位置和写法不变，是稳定锚点），紧接着它的
       **下一行**插入：
       ```java
       productDetailCacheManager.evict(skuId);
       ```
       插在 `skuRepository.save(sku);` 之后即可，具体在不在 `auditLogService.record(...)`
       （如果 S3-audit 已加）之前或之后都不影响功能。**两个方法都要加，不能只加一个**。

- **验收**（按顺序做，第 1 条不过不要往下走）：
  1. **上下文必须能正常启动**：`mvn -s maven-settings.xml -f code/pom.xml install -DskipTests`
     成功；再跑任意一个黑盒用例（如
     `mvn -s maven-settings.xml -f test-cases/pom.xml -Dtest=PubBasicFlowTest#pub008_createBasicOrder test`），
     不出现 `NoUniqueBeanDefinitionException`/`ConflictingBeanDefinitionException`/
     `BeanCreationException`/`ApplicationContextException` 之类的容器启动错误（区别于普通的断言
     失败——这类异常意味着 Spring 容器根本没起来，比黑盒用例本身失败严重得多）。
  2. 连续两次 `GET /api/v1/products/{skuId}` 查同一个 skuId，两次返回体内容一致；单测层面可参照
    参考实现里 `ProductDetailServiceTest`/`ProductDetailCacheManagerTest` 的写法：mock 掉
     `ProductDetailCacheManager`，验证缓存命中时 `skuRepository`/`spuRepository` 等零调用，缓存
     未命中时查完库后 `put` 恰好被调用一次。
  3. 对某 skuId 调用上架/下架接口后，立刻再 `GET` 该 skuId 详情，`status` 字段是新状态，不是缓存
     里的旧状态。
  4. `mvn -s maven-settings.xml -f code/pom.xml test` 全绿 + 完整黑盒 24/24
     （`mvn -s maven-settings.xml -f test-cases/pom.xml test`）。

- **勿犯**（本卡是全项目风险最高的一张，以下每条都对应一种已知会导致 24 例全灭的具体操作，
  落笔前逐条对照，改完再逐条复查一遍）：
  1. **绝不**给商品详情缓存引入 Spring 的 `org.springframework.cache.CacheManager` /
     `@EnableCaching` / `@Cacheable` / `@CacheEvict`。本卡片"改法"里写的是**手写 Caffeine
     `Cache<Long, ProductDetailResponse>` bean + 手动 get/put/evict**，跟 inventory 模块（如果它
     的缓存卡已落地）用的 Spring 官方缓存注解是两条完全独立、长期并存的技术路线，不要混用。
  2. **绝不新建任何类型是 `CacheManager` 的 Spring bean**，不管起什么名字、不管出于什么"顺手"
     的理由。技术原因（这是上一次评测"某 agent 加商品缓存导致 24 例全部归零"的确切复现路径，
     必须理解到这一步再动手，不能只当口号记）：baseline 的 `ShopHubApplication` 上已经有
     `@EnableCaching`，`application.yml` 里配了 `spring.cache.type: caffeine`；Spring Boot 的缓存
     自动配置类都标了 `@ConditionalOnMissingBean(CacheManager.class)`——**只要容器里出现了任意
     一个用户自定义的 `CacheManager` 类型 bean（哪怕只有一个、哪怕命名完全规范），这份自动配置
     就整体退避，不再创建默认的 `cacheManager` bean**。如果这时候容器里同时存在**另一个**独立的
     自定义 `CacheManager` bean（例如 inventory 模块可能已有的 `inventoryCacheManager`），就会
     出现 ≥2 个 `CacheManager` 类型的 bean 同时存在；而 `ecommerce-app` 的 `SystemAdminController`
     历史上一直以**不带 `@Qualifier` 的构造函数参数**直接注入 `CacheManager cacheManager`（除非
     它已经被 app 模块「删除 reset-sandbox/bootstrap-admin」那张卡片摘掉了这个字段——那张卡片
     不属于本批，落地与否本卡无法保证），Spring 在 2 个候选 bean 之间既按类型也按参数名都消歧不了，
     直接抛 `NoUniqueBeanDefinitionException`，**整个 Spring 容器启动失败，24 例黑盒从"部分断言
     失败"变成"全部 ERROR"**。这不是一个理论风险，是这份代码库里能逐行验证的确定因果链。本卡片
     指定的"裸 Caffeine `Cache<K,V>` bean"写法从根上避开这个坑：`Cache<K,V>`
     （`com.github.benmanes.caffeine.cache.Cache`）跟 `CacheManager`
     （`org.springframework.cache.CacheManager`）是两个完全不同的类型，既不会触发上面说的自动
     配置退避逻辑，也不会被 `SystemAdminController` 的注入点当成同一种东西。
  3. **绝不**把新的 `@Bean Cache<Long, ProductDetailResponse>` 方法或
     `ProductDetailCacheManager` 构造函数形参命名为 `cartCache`（会跟 cart 模块已有的同名 bean
     冲突）；也不要在两处使用不一致的名字（`@Bean` 方法名和消费方构造函数形参名必须逐字一致，
     这是 Spring 按名消歧同类型 bean 的唯一依据，本卡片统一用 `productDetailCache`）。
  4. **绝不漏掉** `ecommerce-product/pom.xml` 里的 caffeine 依赖——baseline 该模块从未依赖过
     Caffeine，漏了这一步 `Cache`/`Caffeine` 两个类型直接编译不过，product 模块编译失败（比
     容器启动失败更早、更彻底地把黑盒全部拦死）。
  5. **绝不跳过** `SkuService.onShelf`/`offShelf` 里的 `evict()` 调用——少了任何一个，上/下架后
     10 分钟内详情接口会返回过期状态，这本身就是"期望"里明确要求的行为，不是锦上添花的可选项。
  6. 改完**立刻单独**跑一次 `bash work/harness/ratchet.sh verify`，不要跟 CFG-1~4 或其他批次的
     改动攒在一起才验证。只要看到任何形式的 Spring 容器启动异常（不是断言失败，是
     `BeanCreationException`/`NoUniqueBeanDefinitionException`/`ConflictingBeanDefinitionException`/
     `ApplicationContextException`），第一反应是检查是不是引入了第二个 `CacheManager` 或改错了
     bean 名，原地修，不要带着这个状态往下一张卡片走。
