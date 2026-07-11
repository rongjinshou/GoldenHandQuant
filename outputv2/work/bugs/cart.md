# B10 · cart — 纯缓存购物车 · 估价同源

覆盖 `findings.md`「cart 模块（§6.5，共 4 项）」**全部 4 条**，加「第三轮深审·跨领域」#6（估价配置
不同源），一共 5 条发现、4 张卡片（§6.5 #1 与 #4 同根同解，合并成一张）。这 5 条发现最终全部落在
同一个文件 `CartService.java` 身上——JPA→缓存的存储介质切换（#1/#4）几乎重写了这个文件的每一个方法，
累加语义（#2）、促销接入（#3）、配置同源（第三轮深审·跨领域 #6）又都分别改在这份重写之后的 `addItem`/`estimate`
方法内部。

**为什么不拆成 4 次分别对 `CartService.java` 打补丁**：这个文件从"JPA 实体 + 两个 Repository"改成
"缓存 POJO + CartCacheManager"是不可切半步的结构性变化（字段类型、构造器参数、几乎每个方法体都变），
如果再叠加 3 次相互交织的二次编辑，锚点极易在中途失配。所以 **CART-1 一次性给出已经验证过、能过全部
24 例黑盒的最终版 `CartService.java`/`CartServiceTest.java`**（这份最终版天然已经包含 CART-2/CART-4
要求的行为）；CART-2/CART-3/CART-4 分别做**定位说明 + 各自独立的设计依据与验收**，其中 CART-3 还有
`pom.xml`、`CartEstimateResponse.java` 两个 CART-1 完全不涉及的独立文件要单独编辑。

**执行顺序：先完整应用 CART-1（删 5 个文件 + 整份替换 `CartService.java` + 整份替换
`CartServiceTest.java`），再依次核对 CART-2 → CART-3 → CART-4。CART-3 在 CART-1 之后还必须单独编辑
`pom.xml` 与 `CartEstimateResponse.java`。**

不在本文件范围内、不要顺手改的两处（同一批文件里但归属别的卡片）：
- `CartValidationService.java` 里 `validateSku` 的 `"SKU_NOT_AVAILABLE"` → `"PRODUCT_NOT_FOR_SALE"`：
  归 `S1-quick-wins.md` 的 S1-3。
- 同文件 `validateStock` 里的 `"INSUFFICIENT_STOCK"` → `"INVENTORY_NOT_ENOUGH"`：归 inventory 批
  （`inventory.md`）。
- 这两处连带的 `CartValidationServiceTest.java` 断言更新也不属于本文件。

---

### CART-1 | 购物车用 JPA `@Entity` 落到 H2 真表，应为纯 Caffeine 缓存（含 TTL 从未生效）

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/Cart.java` 【删除】
  2. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/CartItem.java` 【删除】
  3. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/entity/CartStatus.java` 【删除】
  4. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartRepository.java` 【删除】
  5. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/repository/CartItemRepository.java` 【删除】
  6. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartService.java`（整份重写）
  7. `code/ecommerce-cart/src/test/java/com/ecommerce/cart/service/CartServiceTest.java`（整份重写；
     不计分，但删完实体后它是仓库里第二个、也是最后一个还编译不过的文件，必须同步改）

- **现状**:
  - `Cart.java`（全文 46 行）：`@Entity @Table(name = "cart")`，字段 `userId`/`status`
    （`CartStatus` 枚举），真实建表。
  - `CartItem.java`（全文 85 行）：`@Entity @Table(name = "cart_item")`，`@ManyToOne` 关联 `Cart`，
    字段 `skuId`/`skuName`/`price`/`quantity`，同样真实建表。
  - `CartStatus.java`：`ACTIVE`/`CONVERTED`/`EXPIRED` 三态枚举，只被 `Cart.java` 引用。
  - `CartRepository.java` / `CartItemRepository.java`：标准 `JpaRepository<Cart, Long>` /
    `JpaRepository<CartItem, Long>`。
  - `CartService.java` 类注释（baseline 第 30-34 行）自己承认
    `"Uses JPA entities ({@link Cart}, {@link CartItem}) and repositories ... to persist cart data to H2."`；
    字段 `cartRepository`/`cartItemRepository`（第 45-46 行）、构造器（第 51-61 行）、
    `addItem`（第 66-117 行）、`getCart`（第 122-132 行）、`updateItem`（第 137-155 行）、
    `removeItem`（第 160-169 行）、`clearCart`（第 174-183 行）、私有辅助方法
    `getOrCreateCart`/`findCartByUserId`/`findCartItemBySkuId`（第 257 行起）全部经
    `cartRepository`/`cartItemRepository` 读写，且每个公开方法都标了 `@Transactional`
    （第 66/122/137/160/174/192 行）——每次加购、查询、清空都是一次真实的 H2 事务读写。
  - 与此同时，`ecommerce-cart/cache/CartCacheManager.java`（Caffeine，7 天 TTL）+
    `config/CartCacheConfig.java`（已经 `@Bean` 注册了 `Cache<Long, CartData>`）+
    `cache/CartData.java`/`cache/CartItemData.java`（缓存 POJO）**在 baseline 里已经写好、编译通过、
    且有独立单测 `CartCacheManagerTest.java`（5 个用例，覆盖 get/save/TTL 过期/remove/覆盖写）全绿**
    ——但整个 `CartService` 没有一处 `import` 它们，是彻底的死代码。
  - 反证：`design-docs/附录C-数据模型.md` 按用户域/商品域/库存域/订单域/支付域/促销域/物流积分评价域
    逐一列出全系统所有持久化表，**没有任何 cart/cart_item 表**——数据库压根不该有购物车表。
  - TTL（findings §6.5 #4）与 #1 是同一根因：`CartCacheConfig` 里 `Duration.ofDays(7)` 的 TTL 设置本身
    没问题，只是因为 `CartService` 从未使用这个缓存 bean，TTL 无从"生效"——不是 TTL 数值配错，是整条
    路径没被走到。

- **期望**: 购物车是临时数据，只能活在本地 Caffeine Cache（key 为 userId，7 天 TTL），绝不落库。
  依据: `design-docs/07-购物车服务设计.md` §1
  「购物车是临时数据，必须存储在本地 Caffeine Cache 中...TTL 为 7 天。数据库只保存已提交订单，不保存
  临时购物车。」+ 附录B `cart.ttl-days=7`。

- **改法**:
  1. 删除上面 5 个文件。
  2. 删除前后各跑一次 grep 核实引用范围（已经在 baseline 上核实过：除下面要重写的两个文件外，
     `code/` 全仓库没有第三处引用这 5 个类——包括其它 11 个模块都没有任何一处 import）：
     ```bash
     grep -rnE "cart\.(entity|repository)\.(Cart|CartItem|CartStatus)\b" code/
     ```
     删除 + 重写后应为零命中。
  3. `CartService.java` 整份替换为下面这份内容（已通过 `mvn -f code/pom.xml test` +
     全部 24 例黑盒验证）。构造器参数从
     `(CartRepository, CartItemRepository, ProductQueryService, InventoryQueryService, CartValidationService)`
     换成 `(CartCacheManager, CartValidationService, ProductQueryService, PromotionCalculationService)`——
     `InventoryQueryService` 字段在 baseline 里其实从未被任何方法体用到（校验库存的活一直是
     `CartValidationService` 在做），直接一并去掉；`PromotionCalculationService` 是 CART-3 要接的新依赖，
     这里把构造器签名一次性定好。类不再需要 `@Transactional`——纯内存缓存操作没有数据库事务可言，
     Caffeine 的 `Cache.put`/`getIfPresent` 不是 Spring 事务性资源：

     ```java
     package com.ecommerce.cart.service;

     import com.ecommerce.cart.cache.CartCacheManager;
     import com.ecommerce.cart.cache.CartData;
     import com.ecommerce.cart.cache.CartItemData;
     import com.ecommerce.cart.dto.AddCartItemRequest;
     import com.ecommerce.cart.dto.CartEstimateRequest;
     import com.ecommerce.cart.dto.CartEstimateResponse;
     import com.ecommerce.cart.dto.CartItemResponse;
     import com.ecommerce.cart.dto.CartResponse;
     import com.ecommerce.cart.dto.UpdateCartItemRequest;
     import com.ecommerce.common.exception.BusinessException;
     import com.ecommerce.common.exception.ResourceNotFoundException;
     import com.ecommerce.common.money.MonetaryUtil;
     import com.ecommerce.common.test.RuntimeConfigRegistry;
     import com.ecommerce.product.query.ProductQueryService;
     import com.ecommerce.product.query.SkuDto;
     import com.ecommerce.promotion.dto.PromotionCalculateRequest;
     import com.ecommerce.promotion.dto.PromotionCalculateResponse;
     import com.ecommerce.promotion.service.PromotionCalculationService;
     import org.slf4j.Logger;
     import org.slf4j.LoggerFactory;
     import org.springframework.stereotype.Service;

     import java.math.BigDecimal;
     import java.util.ArrayList;
     import java.util.Collections;
     import java.util.List;

     /**
      * Core service for shopping cart operations.
      *
      * <p>Carts are transient data — per design-docs/07 §1 they must live only in the
      * local Caffeine cache ({@link CartCacheManager}, 7-day TTL) and are never persisted
      * to a database table. There is no {@code CartRepository}/{@code CartItem} JPA entity;
      * a "cart" is just a {@link CartData} keyed by userId in the cache.
      */
     @Service
     public class CartService {

         private static final Logger log = LoggerFactory.getLogger(CartService.class);

         private static final BigDecimal SHIPPING_FEE = new BigDecimal("8.00");
         private static final BigDecimal PACKAGING_FEE = new BigDecimal("2.00");
         private static final BigDecimal FREE_SHIPPING_THRESHOLD = new BigDecimal("199.00");

         private final CartCacheManager cartCacheManager;
         private final CartValidationService cartValidationService;
         private final ProductQueryService productQueryService;
         private final PromotionCalculationService promotionCalculationService;

         public CartService(CartCacheManager cartCacheManager,
                             CartValidationService cartValidationService,
                             ProductQueryService productQueryService,
                             PromotionCalculationService promotionCalculationService) {
             this.cartCacheManager = cartCacheManager;
             this.cartValidationService = cartValidationService;
             this.productQueryService = productQueryService;
             this.promotionCalculationService = promotionCalculationService;
         }

         /**
          * Adds an item to the user's cart. If the cart does not exist, it is created.
          *
          * <p>If the SKU is already present in the cart, the requested quantity is
          * ADDED to the existing quantity rather than overwriting it (design-docs/07 §2:
          * "同一个 SKU 重复加入购物车时，数量累加"). The accumulated total is then what
          * gets re-validated against the per-item quantity limit and available stock.
          */
         public CartItemResponse addItem(Long userId, AddCartItemRequest request) {
             log.debug("Adding item to cart: userId={}, skuId={}, quantity={}",
                     userId, request.getSkuId(), request.getQuantity());

             cartValidationService.validateQuantity(request.getQuantity());
             SkuDto sku = cartValidationService.validateSku(request.getSkuId());

             CartData cart = getOrCreateCart(userId);
             CartItemData existingItem = findItem(cart, request.getSkuId());
             int previousQuantity = existingItem != null ? existingItem.getQuantity() : 0;
             int newQuantity = previousQuantity + request.getQuantity();

             // Re-validate the ACCUMULATED total (not just the delta being added) against
             // both the per-item quantity limit and current stock.
             cartValidationService.validateQuantity(newQuantity);
             cartValidationService.validateStock(request.getSkuId(), newQuantity);

             if (existingItem != null) {
                 existingItem.setQuantity(newQuantity);
                 existingItem.setSkuName(sku.getName());
                 existingItem.setPrice(sku.getPrice());
             } else {
                 cartValidationService.validateCartSize(cart.getItems().size(), 1);
                 cart.getItems().add(new CartItemData(sku.getSkuId(), sku.getName(), sku.getPrice(), newQuantity));
             }

             cartCacheManager.saveCart(cart);

             CartItemData result = findItem(cart, request.getSkuId());
             BigDecimal subtotal = MonetaryUtil.multiply(result.getPrice(), BigDecimal.valueOf(result.getQuantity()));
             log.debug("Cart item upserted: userId={}, skuId={}, quantity={}", userId, request.getSkuId(), result.getQuantity());
             return new CartItemResponse(result.getSkuId(), result.getSkuName(), result.getPrice(),
                     result.getQuantity(), subtotal);
         }

         /**
          * Retrieves the full cart for the given user. Never creates or caches an
          * entry as a side effect of a plain read.
          */
         public CartResponse getCart(Long userId) {
             log.debug("Getting cart for userId={}", userId);

             CartData cart = cartCacheManager.getCart(userId);
             if (cart == null) {
                 return buildEmptyCartResponse();
             }
             return buildCartResponse(cart.getItems());
         }

         /**
          * Updates the quantity of an existing item in the cart to the exact value
          * given (no accumulation — unlike {@link #addItem}, this sets rather than adds).
          */
         public CartItemResponse updateItem(Long userId, Long skuId, UpdateCartItemRequest request) {
             log.debug("Updating cart item: userId={}, skuId={}, quantity={}", userId, skuId, request.getQuantity());

             cartValidationService.validateQuantity(request.getQuantity());
             cartValidationService.validateStock(skuId, request.getQuantity());

             CartData cart = requireCart(userId);
             CartItemData item = requireItem(cart, skuId);

             item.setQuantity(request.getQuantity());
             cartCacheManager.saveCart(cart);

             BigDecimal subtotal = MonetaryUtil.multiply(item.getPrice(), BigDecimal.valueOf(item.getQuantity()));
             log.debug("Updated item quantity: skuId={}, newQuantity={}", skuId, item.getQuantity());
             return new CartItemResponse(item.getSkuId(), item.getSkuName(), item.getPrice(),
                     item.getQuantity(), subtotal);
         }

         /**
          * Removes a single item from the cart.
          */
         public void removeItem(Long userId, Long skuId) {
             log.debug("Removing item from cart: userId={}, skuId={}", userId, skuId);

             CartData cart = requireCart(userId);
             CartItemData item = requireItem(cart, skuId);

             cart.getItems().remove(item);
             cartCacheManager.saveCart(cart);
             log.debug("Removed item: skuId={} from cart of userId={}", skuId, userId);
         }

         /**
          * Clears the cart by evicting it from the cache entirely. A no-op if the
          * user has no cached cart.
          */
         public void clearCart(Long userId) {
             log.debug("Clearing cart for userId={}", userId);
             cartCacheManager.removeCart(userId);
         }

         /**
          * Estimates the total price for the cart including shipping, packaging and
          * promotion discounts.
          *
          * <p>Discount amount and applicable coupons are computed by delegating to
          * {@link PromotionCalculationService} (design-docs/07 §3: 满减优惠 + 优惠券可用列表
          * + 会员折扣 are all promotion-module concerns). Points-based deduction stays
          * zero here — loyalty redemption wiring is out of this module's scope.
          */
         public CartEstimateResponse estimate(Long userId, CartEstimateRequest request) {
             log.debug("Estimating cart for userId={}, couponIds={}, redeemPoints={}",
                     userId, request.getCouponIds(), request.getRedeemPoints());

             CartData cart = cartCacheManager.getCart(userId);
             if (cart == null || cart.getItems().isEmpty()) {
                 return buildEmptyEstimateResponse();
             }

             BigDecimal itemTotal = BigDecimal.ZERO;
             List<PromotionCalculateRequest.CalculateItem> calculateItems = new ArrayList<>();
             for (CartItemData item : cart.getItems()) {
                 SkuDto sku = productQueryService.getSkuForSale(item.getSkuId());
                 if (sku == null) {
                     throw new BusinessException("SKU_NOT_FOUND",
                             "SKU " + item.getSkuId() + " is no longer available");
                 }
                 BigDecimal lineTotal = MonetaryUtil.multiply(sku.getPrice(),
                         BigDecimal.valueOf(item.getQuantity()));
                 itemTotal = MonetaryUtil.add(itemTotal, lineTotal);
                 calculateItems.add(toCalculateItem(item.getSkuId(), sku.getPrice(), item.getQuantity()));
             }

             // Read the same runtime-overridable config keys as OrderTotalCalculator so a
             // cart estimate and the eventual order share one source of truth (附录B
             // order.free-shipping-threshold=199.00, order.packaging-fee=2.00). Fallbacks
             // preserve the historical 199.00/2.00 when no admin override is set.
             BigDecimal freeShippingThreshold = RuntimeConfigRegistry.getBigDecimal(
                     "order.free-shipping-threshold", FREE_SHIPPING_THRESHOLD);
             BigDecimal shippingFee = itemTotal.compareTo(freeShippingThreshold) >= 0
                     ? BigDecimal.ZERO : SHIPPING_FEE;

             BigDecimal packagingFee = MonetaryUtil.roundToCent(
                     RuntimeConfigRegistry.getBigDecimal("order.packaging-fee", PACKAGING_FEE));

             PromotionCalculateRequest promoRequest = new PromotionCalculateRequest();
             promoRequest.setUserId(userId);
             promoRequest.setCouponIds(request.getCouponIds());
             promoRequest.setItems(calculateItems);
             PromotionCalculateResponse promoResponse = promotionCalculationService.calculate(promoRequest);

             BigDecimal discountAmount = promoResponse.getTotalDiscount() != null
                     ? promoResponse.getTotalDiscount() : BigDecimal.ZERO;
             // Loyalty points redemption is not wired into cart estimate yet — out of scope here.
             BigDecimal pointsDeductionAmount = BigDecimal.ZERO;

             // Payable amount = itemTotal + shippingFee + packagingFee - discountAmount - pointsDeduction
             BigDecimal payableAmount = MonetaryUtil.add(itemTotal, shippingFee);
             payableAmount = MonetaryUtil.add(payableAmount, packagingFee);
             payableAmount = MonetaryUtil.subtract(payableAmount, discountAmount);
             payableAmount = MonetaryUtil.subtract(payableAmount, pointsDeductionAmount);

             if (payableAmount.compareTo(BigDecimal.ZERO) < 0) {
                 payableAmount = BigDecimal.ZERO;
             }

             CartEstimateResponse response = new CartEstimateResponse();
             response.setItemTotal(itemTotal);
             response.setShippingFee(shippingFee);
             response.setPackagingFee(packagingFee);
             response.setDiscountAmount(discountAmount);
             response.setPointsDeductionAmount(pointsDeductionAmount);
             response.setPayableAmount(payableAmount);
             response.setApplicableCoupons(promoResponse.getApplicableCoupons() != null
                     ? promoResponse.getApplicableCoupons() : Collections.emptyList());

             log.debug("Cart estimate: itemTotal={}, shipping={}, packaging={}, discount={}, payable={}",
                     itemTotal, shippingFee, packagingFee, discountAmount, payableAmount);
             return response;
         }

         // ---- private helpers ----

         private CartData getOrCreateCart(Long userId) {
             CartData cart = cartCacheManager.getCart(userId);
             if (cart == null) {
                 cart = new CartData(userId);
                 log.debug("Created new in-memory cart for userId={}", userId);
             }
             return cart;
         }

         private CartData requireCart(Long userId) {
             CartData cart = cartCacheManager.getCart(userId);
             if (cart == null) {
                 throw new ResourceNotFoundException("Cart for user " + userId + " not found");
             }
             return cart;
         }

         private CartItemData requireItem(CartData cart, Long skuId) {
             CartItemData item = findItem(cart, skuId);
             if (item == null) {
                 throw new ResourceNotFoundException(
                         "CartItem for skuId " + skuId + " not found in cart of user " + cart.getUserId());
             }
             return item;
         }

         private CartItemData findItem(CartData cart, Long skuId) {
             for (CartItemData item : cart.getItems()) {
                 if (item.getSkuId().equals(skuId)) {
                     return item;
                 }
             }
             return null;
         }

         private PromotionCalculateRequest.CalculateItem toCalculateItem(Long skuId, BigDecimal price, Integer quantity) {
             PromotionCalculateRequest.CalculateItem calculateItem = new PromotionCalculateRequest.CalculateItem();
             calculateItem.setSkuId(skuId);
             calculateItem.setPrice(price);
             calculateItem.setQuantity(quantity);
             return calculateItem;
         }

         private CartResponse buildCartResponse(List<CartItemData> items) {
             List<CartItemResponse> itemResponses = new ArrayList<>();
             BigDecimal totalAmount = BigDecimal.ZERO;
             int totalItems = 0;

             for (CartItemData item : items) {
                 BigDecimal subtotal = MonetaryUtil.multiply(item.getPrice(),
                         BigDecimal.valueOf(item.getQuantity()));
                 CartItemResponse itemResponse = new CartItemResponse(
                         item.getSkuId(), item.getSkuName(), item.getPrice(),
                         item.getQuantity(), subtotal);
                 itemResponses.add(itemResponse);
                 totalItems += item.getQuantity();
                 totalAmount = MonetaryUtil.add(totalAmount, subtotal);
             }

             return new CartResponse(itemResponses, totalItems, totalAmount);
         }

         private CartResponse buildEmptyCartResponse() {
             return new CartResponse(new ArrayList<>(), 0, BigDecimal.ZERO);
         }

         private CartEstimateResponse buildEmptyEstimateResponse() {
             CartEstimateResponse empty = new CartEstimateResponse();
             empty.setItemTotal(BigDecimal.ZERO);
             empty.setShippingFee(BigDecimal.ZERO);
             empty.setPackagingFee(BigDecimal.ZERO);
             empty.setDiscountAmount(BigDecimal.ZERO);
             empty.setPointsDeductionAmount(BigDecimal.ZERO);
             empty.setPayableAmount(BigDecimal.ZERO);
             empty.setApplicableCoupons(Collections.emptyList());
             return empty;
         }
     }
     ```

     方法与本卡（#1/#4）直接相关的落点小结：不再有 `cartRepository`/`cartItemRepository` 字段，换成
     `cartCacheManager`；不再有任何 `@Transactional`；`getCart`/`updateItem`/`removeItem`/`clearCart`
     改走 `cartCacheManager.getCart(userId)` / `saveCart(cart)` / `removeCart(userId)`；`clearCart`
     从"按 cartId 删所有 CartItem 行"简化成一行 `cartCacheManager.removeCart(userId)`；
     `getOrCreateCart`/`findCartByUserId`/`findCartItemBySkuId` 三个私有辅助方法换成
     `getOrCreateCart`/`requireCart`/`findItem`/`requireItem`，返回 `CartData`/`CartItemData` 而非
     JPA 实体；`buildCartResponse` 入参类型从 `List<CartItem>` 改成 `List<CartItemData>`。
     `addItem` 的累加语义见 CART-2，`estimate` 的促销接入/配置同源见 CART-3/CART-4——都已经在上面
     这份文件里，不需要再对 `CartService.java` 做二次编辑。

  4. `CartServiceTest.java` 整份替换为下面这份内容（同样已验证通过）：

     ```java
     package com.ecommerce.cart.service;

     import com.ecommerce.cart.cache.CartCacheManager;
     import com.ecommerce.cart.cache.CartData;
     import com.ecommerce.cart.cache.CartItemData;
     import com.ecommerce.cart.dto.AddCartItemRequest;
     import com.ecommerce.cart.dto.CartEstimateRequest;
     import com.ecommerce.cart.dto.CartEstimateResponse;
     import com.ecommerce.cart.dto.CartItemResponse;
     import com.ecommerce.cart.dto.CartResponse;
     import com.ecommerce.cart.dto.UpdateCartItemRequest;
     import com.ecommerce.common.exception.ResourceNotFoundException;
     import com.ecommerce.product.query.ProductQueryService;
     import com.ecommerce.product.query.SkuDto;
     import com.ecommerce.promotion.dto.PromotionCalculateRequest;
     import com.ecommerce.promotion.dto.PromotionCalculateResponse;
     import com.ecommerce.promotion.service.PromotionCalculationService;
     import org.junit.jupiter.api.BeforeEach;
     import org.junit.jupiter.api.DisplayName;
     import org.junit.jupiter.api.Test;
     import org.junit.jupiter.api.extension.ExtendWith;
     import org.mockito.ArgumentCaptor;
     import org.mockito.InjectMocks;
     import org.mockito.Mock;
     import org.mockito.junit.jupiter.MockitoExtension;

     import java.math.BigDecimal;
     import java.util.ArrayList;
     import java.util.List;

     import static org.assertj.core.api.Assertions.assertThat;
     import static org.assertj.core.api.Assertions.assertThatThrownBy;
     import static org.mockito.ArgumentMatchers.any;
     import static org.mockito.ArgumentMatchers.anyInt;
     import static org.mockito.Mockito.never;
     import static org.mockito.Mockito.verify;
     import static org.mockito.Mockito.verifyNoMoreInteractions;
     import static org.mockito.Mockito.when;

     /**
      * Unit tests for {@link CartService} against its cache-backed rewrite.
      *
      * <p>Cart data lives only in {@link CartCacheManager} (Caffeine, 7-day TTL) —
      * there is no JPA {@code CartRepository}/{@code CartItemRepository} anymore
      * (design-docs/07 §1), and repeat-adding the same SKU accumulates quantity
      * rather than overwriting it (design-docs/07 §2).
      */
     @DisplayName("CartService")
     @ExtendWith(MockitoExtension.class)
     class CartServiceTest {

         @Mock
         private CartCacheManager cartCacheManager;

         @Mock
         private CartValidationService cartValidationService;

         @Mock
         private ProductQueryService productQueryService;

         @Mock
         private PromotionCalculationService promotionCalculationService;

         @InjectMocks
         private CartService cartService;

         private static final Long USER_ID = 1L;
         private static final Long SKU_ID = 100L;

         private SkuDto skuDto;

         @BeforeEach
         void setUp() {
             skuDto = new SkuDto();
             skuDto.setSkuId(SKU_ID);
             skuDto.setName("Test SKU");
             skuDto.setPrice(new BigDecimal("25.00"));
             skuDto.setStatus("ON_SHELF");
         }

         // ---------------------------------------------------------------
         // addItem
         // ---------------------------------------------------------------

         @Test
         @DisplayName("addItem creates a new cache entry when SKU is not already in cart")
         void testAddItem_newSku_createsCartItem() {
             when(cartCacheManager.getCart(USER_ID)).thenReturn(null);
             when(cartValidationService.validateSku(SKU_ID)).thenReturn(skuDto);

             CartItemResponse response = cartService.addItem(USER_ID, new AddCartItemRequest(SKU_ID, 3));

             assertThat(response).isNotNull();
             assertThat(response.getSkuId()).isEqualTo(SKU_ID);
             assertThat(response.getSkuName()).isEqualTo("Test SKU");
             assertThat(response.getQuantity()).isEqualTo(3);
             assertThat(response.getPrice()).isEqualByComparingTo(new BigDecimal("25.00"));
             assertThat(response.getSubtotal()).isEqualByComparingTo(new BigDecimal("75.00"));

             verify(cartValidationService).validateCartSize(0, 1);
             ArgumentCaptor<CartData> captor = ArgumentCaptor.forClass(CartData.class);
             verify(cartCacheManager).saveCart(captor.capture());
             assertThat(captor.getValue().getUserId()).isEqualTo(USER_ID);
             assertThat(captor.getValue().getItems()).hasSize(1);
         }

         @Test
         @DisplayName("adding the same SKU twice ACCUMULATES quantity rather than overwriting it (design-docs/07 §2)")
         void testAddItem_sameSkuTwice_accumulatesQuantity() {
             CartData existingCart = new CartData(USER_ID);
             existingCart.getItems().add(new CartItemData(SKU_ID, "Test SKU", new BigDecimal("25.00"), 3));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(existingCart);
             when(cartValidationService.validateSku(SKU_ID)).thenReturn(skuDto);

             CartItemResponse response = cartService.addItem(USER_ID, new AddCartItemRequest(SKU_ID, 2));

             assertThat(response.getQuantity()).isEqualTo(5);
             assertThat(response.getQuantity()).isNotEqualTo(2);
             assertThat(response.getSubtotal()).isEqualByComparingTo(new BigDecimal("125.00"));
             assertThat(existingCart.getItems()).hasSize(1);
         }

         @Test
         @DisplayName("addItem re-validates stock against the ACCUMULATED total, not just the newly requested delta")
         void testAddItem_accumulation_revalidatesStockAgainstAccumulatedTotal() {
             CartData existingCart = new CartData(USER_ID);
             existingCart.getItems().add(new CartItemData(SKU_ID, "Test SKU", new BigDecimal("25.00"), 8));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(existingCart);
             when(cartValidationService.validateSku(SKU_ID)).thenReturn(skuDto);

             cartService.addItem(USER_ID, new AddCartItemRequest(SKU_ID, 5)); // 8 + 5 = 13

             verify(cartValidationService).validateStock(SKU_ID, 13);
             verify(cartValidationService, never()).validateStock(SKU_ID, 5);
         }

         @Test
         @DisplayName("accumulating an existing SKU does not count toward the distinct-item cart-size limit")
         void testAddItem_accumulation_doesNotCountTowardCartSizeLimit() {
             CartData existingCart = new CartData(USER_ID);
             existingCart.getItems().add(new CartItemData(SKU_ID, "Test SKU", new BigDecimal("25.00"), 3));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(existingCart);
             when(cartValidationService.validateSku(SKU_ID)).thenReturn(skuDto);

             cartService.addItem(USER_ID, new AddCartItemRequest(SKU_ID, 2));

             verify(cartValidationService, never()).validateCartSize(anyInt(), anyInt());
         }

         // ---------------------------------------------------------------
         // getCart
         // ---------------------------------------------------------------

         @Test
         @DisplayName("getCart returns all items with computed totalItems and totalAmount")
         void testGetCart_returnsAllItemsWithTotals() {
             CartData cart = new CartData(USER_ID);
             cart.getItems().add(new CartItemData(100L, "Item A", new BigDecimal("10.00"), 2));
             cart.getItems().add(new CartItemData(200L, "Item B", new BigDecimal("15.00"), 1));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             CartResponse response = cartService.getCart(USER_ID);

             assertThat(response).isNotNull();
             assertThat(response.getItems()).hasSize(2);
             assertThat(response.getTotalItems()).isEqualTo(3); // 2 + 1
             // totalAmount = 10*2 + 15*1 = 35.00
             assertThat(response.getTotalAmount()).isEqualByComparingTo(new BigDecimal("35.00"));

             CartItemResponse firstItem = response.getItems().get(0);
             assertThat(firstItem.getSkuId()).isEqualTo(100L);
             assertThat(firstItem.getSkuName()).isEqualTo("Item A");
             assertThat(firstItem.getQuantity()).isEqualTo(2);
             assertThat(firstItem.getSubtotal()).isEqualByComparingTo(new BigDecimal("20.00"));
         }

         @Test
         @DisplayName("getCart returns an empty cart when the user has no cached cart")
         void testGetCart_noCart_returnsEmptyCart() {
             when(cartCacheManager.getCart(USER_ID)).thenReturn(null);

             CartResponse response = cartService.getCart(USER_ID);

             assertThat(response.getItems()).isEmpty();
             assertThat(response.getTotalItems()).isEqualTo(0);
             assertThat(response.getTotalAmount()).isEqualByComparingTo(BigDecimal.ZERO);
         }

         // ---------------------------------------------------------------
         // updateItem
         // ---------------------------------------------------------------

         @Test
         @DisplayName("updateItem sets the exact quantity given and does NOT accumulate")
         void testUpdateItem_setsExactQuantity_doesNotAccumulate() {
             CartData cart = new CartData(USER_ID);
             cart.getItems().add(new CartItemData(SKU_ID, "Test SKU", new BigDecimal("25.00"), 3));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             CartItemResponse response = cartService.updateItem(USER_ID, SKU_ID, new UpdateCartItemRequest(7));

             assertThat(response).isNotNull();
             assertThat(response.getQuantity()).isEqualTo(7);
             assertThat(response.getSkuId()).isEqualTo(SKU_ID);
             verify(cartCacheManager).saveCart(cart);
         }

         @Test
         @DisplayName("updateItem throws ResourceNotFoundException when the SKU is not in the cart")
         void testUpdateItem_itemNotFound_throwsException() {
             CartData cart = new CartData(USER_ID); // no items
             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             assertThatThrownBy(() -> cartService.updateItem(USER_ID, SKU_ID, new UpdateCartItemRequest(5)))
                     .isInstanceOf(ResourceNotFoundException.class);
         }

         @Test
         @DisplayName("updateItem throws ResourceNotFoundException when the user has no cart at all")
         void testUpdateItem_cartNotFound_throwsException() {
             when(cartCacheManager.getCart(USER_ID)).thenReturn(null);

             assertThatThrownBy(() -> cartService.updateItem(USER_ID, SKU_ID, new UpdateCartItemRequest(5)))
                     .isInstanceOf(ResourceNotFoundException.class);
         }

         // ---------------------------------------------------------------
         // removeItem
         // ---------------------------------------------------------------

         @Test
         @DisplayName("removeItem deletes the item from the cached cart")
         void testRemoveItem_deletesItem() {
             CartData cart = new CartData(USER_ID);
             cart.getItems().add(new CartItemData(SKU_ID, "Test SKU", new BigDecimal("25.00"), 1));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             cartService.removeItem(USER_ID, SKU_ID);

             assertThat(cart.getItems()).isEmpty();
             verify(cartCacheManager).saveCart(cart);
         }

         @Test
         @DisplayName("removeItem throws ResourceNotFoundException when cart does not exist")
         void testRemoveItem_cartNotFound_throwsException() {
             when(cartCacheManager.getCart(USER_ID)).thenReturn(null);

             assertThatThrownBy(() -> cartService.removeItem(USER_ID, SKU_ID))
                     .isInstanceOf(ResourceNotFoundException.class);
         }

         @Test
         @DisplayName("removeItem throws ResourceNotFoundException when the SKU is not in the cart")
         void testRemoveItem_itemNotFound_throwsException() {
             CartData cart = new CartData(USER_ID); // no items
             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             assertThatThrownBy(() -> cartService.removeItem(USER_ID, SKU_ID))
                     .isInstanceOf(ResourceNotFoundException.class);
         }

         // ---------------------------------------------------------------
         // clearCart
         // ---------------------------------------------------------------

         @Test
         @DisplayName("clearCart evicts the user's cart from the cache")
         void testClearCart_evictsCacheEntry() {
             cartService.clearCart(USER_ID);

             verify(cartCacheManager).removeCart(USER_ID);
         }

         // ---------------------------------------------------------------
         // estimate
         // ---------------------------------------------------------------

         @Test
         @DisplayName("estimate calculates itemTotal/shipping/packaging and delegates discount to PromotionCalculationService")
         void testEstimate_calculatesCorrectTotal_delegatesToPromotionService() {
             CartData cart = new CartData(USER_ID);
             cart.getItems().add(new CartItemData(100L, "Item A", new BigDecimal("10.00"), 2));
             cart.getItems().add(new CartItemData(200L, "Item B", new BigDecimal("15.00"), 1));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             SkuDto sku1 = new SkuDto();
             sku1.setSkuId(100L);
             sku1.setPrice(new BigDecimal("50.00"));
             SkuDto sku2 = new SkuDto();
             sku2.setSkuId(200L);
             sku2.setPrice(new BigDecimal("30.00"));
             when(productQueryService.getSkuForSale(100L)).thenReturn(sku1);
             when(productQueryService.getSkuForSale(200L)).thenReturn(sku2);

             PromotionCalculateResponse promoResponse = new PromotionCalculateResponse();
             promoResponse.setTotalDiscount(BigDecimal.ZERO);
             promoResponse.setApplicableCoupons(new ArrayList<>());
             when(promotionCalculationService.calculate(any(PromotionCalculateRequest.class))).thenReturn(promoResponse);

             CartEstimateResponse response = cartService.estimate(USER_ID, new CartEstimateRequest());

             // itemTotal = 50*2 + 30*1 = 130.00
             assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("130.00"));
             // shipping = 8.00 (since 130 < 199)
             assertThat(response.getShippingFee()).isEqualByComparingTo(new BigDecimal("8.00"));
             // packaging = 2.00
             assertThat(response.getPackagingFee()).isEqualByComparingTo(new BigDecimal("2.00"));
             assertThat(response.getDiscountAmount()).isEqualByComparingTo(BigDecimal.ZERO);
             assertThat(response.getPointsDeductionAmount()).isEqualByComparingTo(BigDecimal.ZERO);
             // payable = 130 + 8 + 2 = 140.00
             assertThat(response.getPayableAmount()).isEqualByComparingTo(new BigDecimal("140.00"));

             ArgumentCaptor<PromotionCalculateRequest> captor = ArgumentCaptor.forClass(PromotionCalculateRequest.class);
             verify(promotionCalculationService).calculate(captor.capture());
             assertThat(captor.getValue().getUserId()).isEqualTo(USER_ID);
             assertThat(captor.getValue().getItems()).hasSize(2);
         }

         @Test
         @DisplayName("estimate applies free shipping when itemTotal >= 199")
         void testEstimate_freeShippingOver199() {
             CartData cart = new CartData(USER_ID);
             cart.getItems().add(new CartItemData(100L, "Expensive Item", new BigDecimal("100.00"), 2));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             SkuDto sku = new SkuDto();
             sku.setSkuId(100L);
             sku.setPrice(new BigDecimal("100.00"));
             when(productQueryService.getSkuForSale(100L)).thenReturn(sku);

             PromotionCalculateResponse promoResponse = new PromotionCalculateResponse();
             promoResponse.setTotalDiscount(BigDecimal.ZERO);
             promoResponse.setApplicableCoupons(new ArrayList<>());
             when(promotionCalculationService.calculate(any(PromotionCalculateRequest.class))).thenReturn(promoResponse);

             CartEstimateResponse response = cartService.estimate(USER_ID, new CartEstimateRequest());

             // itemTotal = 100*2 = 200.00
             assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("200.00"));
             // shipping = 0 (since 200 >= 199)
             assertThat(response.getShippingFee()).isEqualByComparingTo(BigDecimal.ZERO);
             // packaging = 2.00
             assertThat(response.getPackagingFee()).isEqualByComparingTo(new BigDecimal("2.00"));
             // payable = 200 + 0 + 2 = 202.00
             assertThat(response.getPayableAmount()).isEqualByComparingTo(new BigDecimal("202.00"));
         }

         @Test
         @DisplayName("estimate returns zero for empty/missing cart and never calls PromotionCalculationService")
         void testEstimate_emptyCart_returnsZero_skipsPromotionCall() {
             when(cartCacheManager.getCart(USER_ID)).thenReturn(null);

             CartEstimateResponse response = cartService.estimate(USER_ID, new CartEstimateRequest());

             assertThat(response.getItemTotal()).isEqualByComparingTo(BigDecimal.ZERO);
             assertThat(response.getShippingFee()).isEqualByComparingTo(BigDecimal.ZERO);
             assertThat(response.getPackagingFee()).isEqualByComparingTo(BigDecimal.ZERO);
             assertThat(response.getDiscountAmount()).isEqualByComparingTo(BigDecimal.ZERO);
             assertThat(response.getPayableAmount()).isEqualByComparingTo(BigDecimal.ZERO);
             assertThat(response.getApplicableCoupons()).isEmpty();

             verify(promotionCalculationService, never()).calculate(any());
         }

         @Test
         @DisplayName("estimate reflects a REAL discount and applicable coupons computed by PromotionCalculationService, not a hardcoded zero")
         void testEstimate_withPromotionDiscount_reflectsRealDiscountAndCoupons() {
             CartData cart = new CartData(USER_ID);
             cart.getItems().add(new CartItemData(SKU_ID, "Test SKU", new BigDecimal("100.00"), 1));

             when(cartCacheManager.getCart(USER_ID)).thenReturn(cart);

             SkuDto sku = new SkuDto();
             sku.setSkuId(SKU_ID);
             sku.setPrice(new BigDecimal("100.00"));
             when(productQueryService.getSkuForSale(SKU_ID)).thenReturn(sku);

             PromotionCalculateResponse.ApplicableCoupon coupon = new PromotionCalculateResponse.ApplicableCoupon();
             coupon.setCouponId(9L);
             coupon.setCouponCode("SAVE20");
             coupon.setName("20% off");
             coupon.setDiscountAmount(new BigDecimal("20.00"));

             PromotionCalculateResponse promoResponse = new PromotionCalculateResponse();
             promoResponse.setTotalDiscount(new BigDecimal("20.00"));
             promoResponse.setApplicableCoupons(List.of(coupon));
             when(promotionCalculationService.calculate(any(PromotionCalculateRequest.class))).thenReturn(promoResponse);

             CartEstimateRequest request = new CartEstimateRequest();
             request.setCouponIds(List.of(9L));

             CartEstimateResponse response = cartService.estimate(USER_ID, request);

             // itemTotal = 100.00 (< 199 -> shipping 8.00); payable = 100 + 8 + 2 - 20 = 90.00
             assertThat(response.getDiscountAmount()).isEqualByComparingTo(new BigDecimal("20.00"));
             assertThat(response.getPayableAmount()).isEqualByComparingTo(new BigDecimal("90.00"));
             assertThat(response.getApplicableCoupons()).hasSize(1);
             assertThat(response.getApplicableCoupons().get(0).getCouponCode()).isEqualTo("SAVE20");

             ArgumentCaptor<PromotionCalculateRequest> captor = ArgumentCaptor.forClass(PromotionCalculateRequest.class);
             verify(promotionCalculationService).calculate(captor.capture());
             assertThat(captor.getValue().getCouponIds()).containsExactly(9L);
         }

         // ---------------------------------------------------------------
         // Cart is never persisted to a database (design-docs/07 §1)
         // ---------------------------------------------------------------

         @Test
         @DisplayName("cart data is only ever written through CartCacheManager — no JPA repository exists for it anymore")
         void testCart_neverPersistedViaJpaRepository_onlyCacheManager() {
             when(cartCacheManager.getCart(USER_ID)).thenReturn(null);
             when(cartValidationService.validateSku(SKU_ID)).thenReturn(skuDto);

             cartService.addItem(USER_ID, new AddCartItemRequest(SKU_ID, 1));

             // The only persistence interaction is with the Caffeine-backed CartCacheManager.
             // CartRepository/CartItemRepository/Cart/CartItem were deleted from this module
             // entirely, so there is no JPA persistence path left for cart data to take.
             verify(cartCacheManager).getCart(USER_ID);
             verify(cartCacheManager).saveCart(any(CartData.class));
             verifyNoMoreInteractions(cartCacheManager);
         }
     }
     ```

  5. **不要动** `CartCacheManager.java`/`CartData.java`/`CartItemData.java`/`CartCacheConfig.java`——
     这 4 个文件在 baseline 已经正确、已经有独立单测覆盖，原样复用，本卡不改它们一行。
  6. `CartControllerTest.java` 直接 mock `CartService`（不 mock 仓储/缓存），不受本卡影响，不用碰。

- **验收**:
  - `entity/`、`repository/` 两个目录下已经没有 `Cart.java`/`CartItem.java`/`CartStatus.java`/
    `CartRepository.java`/`CartItemRepository.java`。
  - `grep -rnE "cart\.(entity|repository)\.(Cart|CartItem|CartStatus)\b" code/` 零命中。
  - `mvn -s maven-settings.xml -f code/pom.xml test-compile` 编译通过（`ecommerce-cart` 模块）。
  - `mvn -s maven-settings.xml -f code/pom.xml test -pl ecommerce-cart -am` 全绿，含既有的
    `CartCacheManagerTest`（5 例）、`CartControllerTest`、`CartValidationServiceTest`，以及新
    `CartServiceTest`。
  - 黑盒场景：加购后立刻 `GET /api/v1/cart` 能读到（走缓存，不查库）。

- **勿犯**:
  - 5 个文件必须一次删满，不能只删 Repository 漏删 entity（反之亦然）；删除前后各跑一次上面的
    `grep`——第一次核实"确实只有这 7 个文件相关"，第二次核实"改完之后零残留"。
  - 别把要删的 `Cart`/`CartItem`/`CartStatus`（包名 `cart.entity`，JPA 实体）跟要保留的
    `CartData`/`CartItemData`（包名 `cart.cache`，缓存 POJO）搞混——名字很像、包不一样，前者删、
    后者原样保留、一行都不要改。
  - 别漏改 `CartServiceTest.java`：只改 `CartService.java` 主代码不同步改测试文件，
    `mvn install -DskipTests`（黑盒测试前必须先跑这条）会在 test-compile 阶段直接炸掉——
    `-DskipTests` 只跳过"运行"测试，不跳过"编译"测试，这不是能延后的小事。
  - 不要给新 `CartService` 加回 `@Transactional`（无数据库可事务；上面这份验证过的版本没有这个
    注解，也没有 `org.springframework.transaction.annotation.Transactional` 这个 import）。
  - `CartController.java` 不在本卡改动范围，签名和实现都不需要变。`CartValidationService.java`
    与 `CartValidationServiceTest.java` 也不在本卡改动范围——那两处错误码改动分别属于 S1 和
    inventory 批，不要在本卡顺手改掉，避免和那两张卡片产生冲突的重复改动。

---

### CART-2 | 同一 SKU 重复加入购物车是覆盖数量，应累加

- 风险: low · 置信度: definite
- **文件**: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartService.java`
  （`addItem` 方法；已随 CART-1 整份重写落地，本卡是对那份文件里 `addItem` 部分的定位说明 +
  独立验收，**不需要在 CART-1 之外再单独编辑文件**）
- **现状**: baseline `addItem()`（第 66-117 行）里，命中已存在 SKU 的分支（第 89-98 行）：
  ```java
  if (existingItem.isPresent()) {
      CartItem item = existingItem.get();
      item.setQuantity(request.getQuantity());   // 第 91 行：直接覆盖，不是累加
      cartItemRepository.save(item);
      ...
  }
  ```
  重复调用 `POST /api/v1/cart/items`（同一 skuId、不同 quantity）会把原有数量整个替换掉，而不是叠加。
  而且校验也只针对**本次请求的增量**：方法开头（第 72、78 行）`validateQuantity`/`validateStock`
  用的都是 `request.getQuantity()`，从未校验过累加后的总量。
- **期望**: 同一 SKU 重复加入购物车，数量累加；累加后的**总量**（不是本次增量）要重新过一遍数量上限
  与库存校验。依据: `design-docs/07-购物车服务设计.md` §2「同一个 SKU 重复加入购物车时，数量累加。」
- **改法**: CART-1 落地的最终 `CartService.java` 里，`addItem` 对应这一段：
  ```java
  CartData cart = getOrCreateCart(userId);
  CartItemData existingItem = findItem(cart, request.getSkuId());
  int previousQuantity = existingItem != null ? existingItem.getQuantity() : 0;
  int newQuantity = previousQuantity + request.getQuantity();

  // Re-validate the ACCUMULATED total (not just the delta being added) against
  // both the per-item quantity limit and current stock.
  cartValidationService.validateQuantity(newQuantity);
  cartValidationService.validateStock(request.getSkuId(), newQuantity);

  if (existingItem != null) {
      existingItem.setQuantity(newQuantity);
      existingItem.setSkuName(sku.getName());
      existingItem.setPrice(sku.getPrice());
  } else {
      cartValidationService.validateCartSize(cart.getItems().size(), 1);
      cart.getItems().add(new CartItemData(sku.getSkuId(), sku.getName(), sku.getPrice(), newQuantity));
  }
  ```
  两个关键点：(a) `validateQuantity` 被调用两次——方法开头对 `request.getQuantity()`（本次请求的增量）
  先做一次范围合法性快速拒绝，然后对累加后的 `newQuantity` 再做一次；(b) `validateStock` 只调用一次，
  且传的是 `newQuantity`（累加后的总量），不是 `request.getQuantity()`——如果这里传错成增量，会漏判
  "累加后超库存"的场景。新增分支（`else`）里 `validateCartSize` 仍然只在真正新增一个 SKU 种类时调用，
  累加同一 SKU 不算新增种类，不应该触发这个校验。
- **验收**:
  - 先 `POST /cart/items {skuId:100, quantity:3}` 再 `POST /cart/items {skuId:100, quantity:2}`，
    第二次响应 `quantity=5`（不是 2）。
  - 库存=5 的 SKU，先加 3 再加 3（累计 6 > 5），第二次请求应该因为库存不足被拒绝，即使单看第二次
    请求本身的 `quantity=3` 是合法值（单独校验会通过，必须按累加后的 6 判定）。
  - 累加同一 SKU 不应触发 `CART_FULL`（100 种上限）——第二次调用不应再调 `validateCartSize`。

---

### CART-3 | 价格预估的优惠金额硬编码为 0，未接入促销计算

- 风险: high · 置信度: definite
- **文件**:
  1. `code/ecommerce-cart/pom.xml`
  2. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/dto/CartEstimateResponse.java`
  3. `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartService.java`（`estimate`
     方法；随 CART-1 整份重写落地，本卡是该重写里促销接入部分的定位说明）
- **现状**:
  - `pom.xml`：`<dependencies>` 只有 `ecommerce-common`/`ecommerce-product`/`ecommerce-inventory`/
    `caffeine`/`spring-security-test`，**没有 `ecommerce-promotion`**——`CartService` 物理上拿不到
    `PromotionCalculationService`。
  - `CartService.estimate()`（baseline 第 192-255 行）第 230-232 行：
    ```java
    // Discount and points deduction — placeholder (requires PromotionCalculationService)
    BigDecimal discountAmount = BigDecimal.ZERO;
    BigDecimal pointsDeductionAmount = BigDecimal.ZERO;
    ```
    注释自己承认是占位符；不管购物车里有没有可用满减/优惠券，`discountAmount` 恒为 0，
    `payableAmount` 因此系统性偏高，且用户传的 `couponIds`（`CartEstimateRequest.couponIds`）从头到
    尾没被用过。
  - `CartEstimateResponse.java`（baseline 全文 68 行）没有 `applicableCoupons` 字段，就算促销侧算出
    可用券列表也没地方装。
- **期望**: 价格预估要把满减优惠 + 优惠券可用列表接进来（会员折扣已经在 `PromotionCalculationService`
  内部合并进折扣总额）。依据: `design-docs/07` §3「购物车价格预估返回：...2.满减优惠 3.优惠券可用
  列表 4.会员折扣...」+ `design-docs/02-系统架构.md` §4（跨模块查询/计算走对方模块暴露的
  `*QueryService`/领域服务接口——`PromotionCalculationService` 正是促销模块对外的计算服务，
  `com.ecommerce.promotion.service.PromotionCalculationService`，唯一实现类，直接注入）。
- **改法**:
  1. `pom.xml` 加一个 `<dependency>`（写法跟现有 `ecommerce-product`/`ecommerce-inventory` 那两块
     一致，放在它们后面）：
     ```xml
     <dependency>
         <groupId>com.ecommerce</groupId>
         <artifactId>ecommerce-promotion</artifactId>
         <version>${project.version}</version>
     </dependency>
     ```
     不会形成循环依赖——已核实 `ecommerce-promotion/pom.xml` 只依赖 `ecommerce-common`，不反向依赖
     `ecommerce-cart`。
  2. `CartEstimateResponse.java` 整份替换为（只新增一个字段 + 对应 getter/setter + 两个 import，其余
     六个既有字段/getter/setter 原样保留）：
     ```java
     package com.ecommerce.cart.dto;

     import com.ecommerce.promotion.dto.PromotionCalculateResponse;

     import java.math.BigDecimal;
     import java.util.List;

     /**
      * Response DTO for cart price estimation.
      */
     public class CartEstimateResponse {

         private BigDecimal itemTotal;
         private BigDecimal shippingFee;
         private BigDecimal packagingFee;
         private BigDecimal discountAmount;
         private BigDecimal pointsDeductionAmount;
         private BigDecimal payableAmount;
         private List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons;

         public CartEstimateResponse() {
         }

         public BigDecimal getItemTotal() {
             return itemTotal;
         }

         public void setItemTotal(BigDecimal itemTotal) {
             this.itemTotal = itemTotal;
         }

         public BigDecimal getShippingFee() {
             return shippingFee;
         }

         public void setShippingFee(BigDecimal shippingFee) {
             this.shippingFee = shippingFee;
         }

         public BigDecimal getPackagingFee() {
             return packagingFee;
         }

         public void setPackagingFee(BigDecimal packagingFee) {
             this.packagingFee = packagingFee;
         }

         public BigDecimal getDiscountAmount() {
             return discountAmount;
         }

         public void setDiscountAmount(BigDecimal discountAmount) {
             this.discountAmount = discountAmount;
         }

         public BigDecimal getPointsDeductionAmount() {
             return pointsDeductionAmount;
         }

         public void setPointsDeductionAmount(BigDecimal pointsDeductionAmount) {
             this.pointsDeductionAmount = pointsDeductionAmount;
         }

         public BigDecimal getPayableAmount() {
             return payableAmount;
         }

         public void setPayableAmount(BigDecimal payableAmount) {
             this.payableAmount = payableAmount;
         }

         public List<PromotionCalculateResponse.ApplicableCoupon> getApplicableCoupons() {
             return applicableCoupons;
         }

         public void setApplicableCoupons(List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons) {
             this.applicableCoupons = applicableCoupons;
         }
     }
     ```
     这是新增字段，不改名、不删除任何既有字段——不触碰冻结契约里已有的响应字段。
  3. `CartService` 构造器加一个 `PromotionCalculationService promotionCalculationService` 依赖
     （CART-1 目标文件的构造器第 4 个参数就是它），`estimate()` 里把 CART-1 目标文件中的这一段对上
     （对应 baseline 第 210-232 行原来"算 itemTotal + 硬编码 0 折扣"的位置）：
     ```java
     BigDecimal itemTotal = BigDecimal.ZERO;
     List<PromotionCalculateRequest.CalculateItem> calculateItems = new ArrayList<>();
     for (CartItemData item : cart.getItems()) {
         SkuDto sku = productQueryService.getSkuForSale(item.getSkuId());
         if (sku == null) {
             throw new BusinessException("SKU_NOT_FOUND",
                     "SKU " + item.getSkuId() + " is no longer available");
         }
         BigDecimal lineTotal = MonetaryUtil.multiply(sku.getPrice(),
                 BigDecimal.valueOf(item.getQuantity()));
         itemTotal = MonetaryUtil.add(itemTotal, lineTotal);
         calculateItems.add(toCalculateItem(item.getSkuId(), sku.getPrice(), item.getQuantity()));
     }
     ...
     PromotionCalculateRequest promoRequest = new PromotionCalculateRequest();
     promoRequest.setUserId(userId);
     promoRequest.setCouponIds(request.getCouponIds());
     promoRequest.setItems(calculateItems);
     PromotionCalculateResponse promoResponse = promotionCalculationService.calculate(promoRequest);

     BigDecimal discountAmount = promoResponse.getTotalDiscount() != null
             ? promoResponse.getTotalDiscount() : BigDecimal.ZERO;
     // Loyalty points redemption is not wired into cart estimate yet — out of scope here.
     BigDecimal pointsDeductionAmount = BigDecimal.ZERO;
     ```
     （代码里的 `...` 是本卡故意跳过的一段——`freeShippingThreshold`/`shippingFee`/`packagingFee` 的
     读取，那是 CART-4 的地盘，两段在 CART-1 目标文件里紧挨着但互不依赖，谁先落地不影响另一个；
     完整顺序以 CART-1 目标文件为准，这里不重复贴一遍。）
     以及组装响应时加 `response.setApplicableCoupons(promoResponse.getApplicableCoupons() != null
     ? promoResponse.getApplicableCoupons() : Collections.emptyList())`。
     `pointsDeductionAmount` 保持 0——积分抵扣接入购物车预估不在这 5 项范围内，design-docs/07 §3
     第 4 点"会员折扣"已经由 `PromotionCalculationService` 内部算进 `totalDiscount`，购物车这边不用
     单独处理。
     空购物车分支（baseline 第 199-208 行，对应 CART-1 目标文件里的 `buildEmptyEstimateResponse()`）
     要同步给 `applicableCoupons` 一个 `Collections.emptyList()` 兜底，不能留 `null`（避免序列化成
     JSON `null` 而不是 `[]`）——CART-1 已经这样处理了，这里只是标出对应位置。
- **验收**:
  - `mvn -s maven-settings.xml -f code/pom.xml -pl ecommerce-cart dependency:tree` 能看到
    `ecommerce-promotion` 出现在 `ecommerce-cart` 的编译期依赖里。
  - 购物车里有满足满减门槛的商品时，`POST /cart/estimate` 的 `discountAmount` 不再恒为 0，且与
    `PromotionCalculationService` 独立算出来的结果一致。
  - 传入的 `couponIds` 若命中可用优惠券，响应体 `applicableCoupons` 非空，元素带
    `couponCode`/`discountAmount`。
  - 空购物车时 `applicableCoupons` 是 `[]` 不是 `null`，且不调用
    `promotionCalculationService.calculate(...)`（省一次没必要的跨模块调用）。
- **勿犯**:
  - `PromotionCalculationService` 是 `com.ecommerce.promotion.service` 包下唯一的具体 `@Service`
    类（不是接口），不要多建一层接口或多个实现——直接构造器注入即可。
  - 不要在 `CartEstimateResponse` 里重命名或删除任何既有字段（`itemTotal`/`shippingFee`/
    `packagingFee`/`discountAmount`/`pointsDeductionAmount`/`payableAmount`）——这些都是冻结响应体
    的既有字段，本卡只**新增** `applicableCoupons`，新增不算破坏契约，但改名/删字段就会。
  - `pointsDeductionAmount` 不要顺手接积分抵扣逻辑——那是更大的一块功能面（loyalty 模块的抵扣汇率、
    上限比例等），不在这 5 项范围内，加了反而可能引入未经设计文档验证的行为。

---

### CART-4 | 价格预估的运费阈值/包装费硬编码，与订单侧配置来源不一致

- 风险: low · 置信度: likely
- **文件**: `code/ecommerce-cart/src/main/java/com/ecommerce/cart/service/CartService.java`
  （`estimate` 方法；随 CART-1 整份重写落地，本卡是该重写里配置读取部分的定位说明）
- **现状**: baseline `estimate()` 第 223-228 行：
  ```java
  // Shipping fee: 8.00, free if itemTotal >= 199.00 (correct boundary: >=)
  BigDecimal shippingFee = itemTotal.compareTo(FREE_SHIPPING_THRESHOLD) >= 0
          ? BigDecimal.ZERO : SHIPPING_FEE;

  // Packaging fee: always 2.00
  BigDecimal packagingFee = PACKAGING_FEE;
  ```
  `FREE_SHIPPING_THRESHOLD`（199.00）/`PACKAGING_FEE`（2.00）是类内 `private static final` 常量
  （baseline 第 41-43 行），永远读不到管理员通过 `RuntimeConfigRegistry` 对
  `order.free-shipping-threshold`/`order.packaging-fee` 的运行时覆盖。下单侧
  `ecommerce-order/.../OrderTotalCalculator` 读的正是这两个 key（该文件另有 order 批的卡片负责修，
  与本卡相互独立、不冲突）——一旦管理员改了配置，`/cart/estimate` 与 `/orders/create` 就会对同一个
  购物车给出两个不一致的金额。
- **期望**: 购物车预估要跟下单侧读同一份运行时配置、同规则、同来源。依据: `design-docs/07` §3
  （预估与下单应遵循一致规则）+ `design-docs/附录B-配置参考.md`（`order.free-shipping-threshold`
  默认 199.00、`order.packaging-fee` 默认 2.00，均为运行时可覆盖项——注意：附录B **没有**给运费本身
  开配置项，只有阈值和包装费可配置；运费金额本身（8.00）两侧都应继续保留硬编码常量，不要为它新造一个
  不存在的配置键）。
- **改法**: CART-1 落地的最终 `CartService.java` 里，对应这一段：
  ```java
  // Read the same runtime-overridable config keys as OrderTotalCalculator so a
  // cart estimate and the eventual order share one source of truth (附录B
  // order.free-shipping-threshold=199.00, order.packaging-fee=2.00). Fallbacks
  // preserve the historical 199.00/2.00 when no admin override is set.
  BigDecimal freeShippingThreshold = RuntimeConfigRegistry.getBigDecimal(
          "order.free-shipping-threshold", FREE_SHIPPING_THRESHOLD);
  BigDecimal shippingFee = itemTotal.compareTo(freeShippingThreshold) >= 0
          ? BigDecimal.ZERO : SHIPPING_FEE;

  BigDecimal packagingFee = MonetaryUtil.roundToCent(
          RuntimeConfigRegistry.getBigDecimal("order.packaging-fee", PACKAGING_FEE));
  ```
  多一个 import：`com.ecommerce.common.test.RuntimeConfigRegistry`（`ecommerce-common` 已经是 cart
  模块既有依赖，不需要改 `pom.xml`）。`RuntimeConfigRegistry.getBigDecimal(key, fallback)` 是静态
  方法，查不到覆盖值时回退到原来的类内常量——两个 key 字符串必须跟 `OrderTotalCalculator` 里用的完全
  一致（`"order.free-shipping-threshold"`、`"order.packaging-fee"`），这是"同源"的关键，字符串写错
  或者哪怕大小写不一致都会让两侧继续各读各的。`SHIPPING_FEE`（8.00 那个）保持类内常量不动，不要读
  配置。
- **验收**:
  - `RuntimeConfigRegistry.put("order.free-shipping-threshold", "50.00")` 之后，购物车 itemTotal=80
    的预估 `shippingFee` 应为 0（原来 199 门槛下应该收费，覆盖后免运费）。
  - `RuntimeConfigRegistry.put("order.packaging-fee", "5.00")` 之后，`packagingFee` 应为 5.00。
  - 不覆盖时行为与原来完全一致（itemTotal<199 收 8.00 运费、包装费 2.00）——这是个"读取来源换了、
    默认行为不变"的卡片，不应该让任何既有黑盒用例的默认路径断言发生变化。
