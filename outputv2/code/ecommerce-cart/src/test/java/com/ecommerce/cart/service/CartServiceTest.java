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
