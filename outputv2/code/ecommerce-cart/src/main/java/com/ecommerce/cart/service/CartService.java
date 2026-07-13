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
