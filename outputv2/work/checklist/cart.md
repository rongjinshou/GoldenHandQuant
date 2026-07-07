# checklist: ecommerce-cart

依据：`design-docs/07-购物车服务设计.md`、附录 A/B/C。

## 存储形态（设计：Caffeine 缓存，7 天 TTL，从不落库）

- [ ] 购物车经 `CartCacheManager`（Caffeine，`CartCacheConfig` 已配 7 天 TTL）读写 `CartData`/`CartItemData`——**不用 JPA `@Entity` 落 H2 表**。
- [ ] JPA 实体 `Cart`/`CartItem`/`CartStatus` 与 `CartRepository`/`CartItemRepository` 已删除（保留会重新落库，违背设计）。

## 加购物车

- [ ] 同一 SKU 重复加入是**累加**数量（`quantity = quantity + request.quantity`），**不是**覆盖；累加后重新校验库存/上限。

## 价格预估

- [ ] `discountAmount` 走真实 `PromotionCalculationService`（**不是**硬编码 `ZERO`）；`ecommerce-cart/pom.xml` 有 `ecommerce-promotion` 依赖。
- [ ] `pointsDeductionAmount` 等字段按设计映射，不恒为 0。

## 错误码

- [ ] 校验不可售 SKU 时错误码为 `PRODUCT_NOT_FOR_SALE`（与 product 一致，**不是** `SKU_NOT_AVAILABLE`）。
