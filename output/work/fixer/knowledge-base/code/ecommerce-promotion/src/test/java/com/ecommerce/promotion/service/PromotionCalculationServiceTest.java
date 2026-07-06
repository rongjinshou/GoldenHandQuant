package com.ecommerce.promotion.service;

import com.ecommerce.common.money.MonetaryUtil;
import com.ecommerce.promotion.dto.PromotionCalculateRequest;
import com.ecommerce.promotion.dto.PromotionCalculateResponse;
import com.ecommerce.promotion.entity.CouponStatus;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.CouponType;
import com.ecommerce.promotion.entity.FullReductionActivity;
import com.ecommerce.promotion.entity.UserCoupon;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.ecommerce.promotion.repository.UserCouponRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link PromotionCalculationService}.
 *
 * <p>The stacking order is fixed per design-docs/10 §3: full-reduction →
 * coupon → member, each step applied to the result of the previous one.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("PromotionCalculationService")
class PromotionCalculationServiceTest {

    @Mock
    private FullReductionService fullReductionService;

    @Mock
    private CouponService couponService;

    @Mock
    private CouponValidator couponValidator;

    @Mock
    private UserCouponRepository userCouponRepository;

    @Mock
    private CouponTemplateRepository couponTemplateRepository;

    @InjectMocks
    private PromotionCalculationService promotionCalculationService;

    // -----------------------------------------------------------------------
    // Shared test data
    // -----------------------------------------------------------------------

    private PromotionCalculateRequest request;
    private PromotionCalculateRequest.CalculateItem item;
    private CouponTemplate discountTemplate;
    private UserCoupon userCoupon;
    private FullReductionActivity fullReductionActivity;

    @BeforeEach
    void setUp() {
        // Default item: price=100, qty=1 → itemTotal=100
        item = new PromotionCalculateRequest.CalculateItem();
        item.setSkuId(1L);
        item.setPrice(new BigDecimal("100.00"));
        item.setQuantity(1);

        request = new PromotionCalculateRequest();
        request.setItems(List.of(item));
        request.setUserId(1L);
        request.setCouponIds(List.of(1L));

        // DISCOUNT coupon with 0.8 rate
        discountTemplate = new CouponTemplate();
        discountTemplate.setId(100L);
        discountTemplate.setName("80% Off");
        discountTemplate.setType(CouponType.DISCOUNT);
        discountTemplate.setDiscountValue(new BigDecimal("0.8"));
        discountTemplate.setStatus("ACTIVE");

        // UserCoupon linking to the template
        userCoupon = new UserCoupon();
        userCoupon.setId(1L);
        userCoupon.setUserId(1L);
        userCoupon.setCouponTemplateId(100L);
        userCoupon.setCouponCode("CPN-DISC80");
        userCoupon.setStatus(CouponStatus.AVAILABLE);

        // Full-reduction: spend 90, get 10 off
        fullReductionActivity = new FullReductionActivity();
        fullReductionActivity.setId(1L);
        fullReductionActivity.setName("Spend 90 Get 10 Off");
        fullReductionActivity.setThresholdAmount(new BigDecimal("90.00"));
        fullReductionActivity.setReductionAmount(new BigDecimal("10.00"));
        fullReductionActivity.setStatus("ACTIVE");
    }

    // -----------------------------------------------------------------------
    // Calculate tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("calculate")
    class Calculate {

        @Test
        @DisplayName("testCalculate_appliesFullReductionThenCouponThenMember: " +
                "calculation order is fullReduction→coupon→member, per design-docs/10 §3")
        void testCalculate_appliesFullReductionThenCouponThenMember() {
            /*
             * Trace through the calculation:
             *
             * STEP 1 - Full reduction (on the raw item total, 100.00):
             *   100.00 >= 90.00 threshold → reduction = 10.00
             *   afterFullReduction = subtract(100.00, 10.00) = 90.00
             *
             * STEP 2 - Coupon DISCOUNT 0.8 (on 90.00):
             *   discountRate = 1 - 0.8 = 0.2
             *   couponDiscount = multiply(90.00, 0.2) = 18.00
             *   afterCoupon = subtract(90.00, 18.00) = 72.00
             *
             * STEP 3 - Member discount (5%, rate=0.95, on 72.00):
             *   afterMember = multiply(72.00, 0.95) = 68.40
             *   memberDiscount = subtract(72.00, 68.40) = 3.60
             *
             * RESULT:
             *   finalAmount = 68.40
             *   totalDiscount = 100.00 - 68.40 = 31.60
             */
            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.of(new BigDecimal("10.00")));
            when(userCouponRepository.findById(1L)).thenReturn(Optional.of(userCoupon));
            when(couponTemplateRepository.findById(100L)).thenReturn(Optional.of(discountTemplate));
            // Simulate the corrected CouponService.calculateDiscount behavior for DISCOUNT 0.8:
            // discountAmount = price * (1 - discountValue).
            when(couponService.calculateDiscount(any(BigDecimal.class), any(CouponTemplate.class)))
                    .thenAnswer(invocation -> {
                        BigDecimal price = invocation.getArgument(0);
                        CouponTemplate ct = invocation.getArgument(1);
                        if (ct.getType() == CouponType.DISCOUNT) {
                            BigDecimal discountRate = BigDecimal.ONE.subtract(ct.getDiscountValue());
                            return MonetaryUtil.multiply(price, discountRate);
                        }
                        return BigDecimal.ZERO;
                    });

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("100.00"));

            // Full reduction applied FIRST, on the raw item total.
            assertThat(response.getFullReductionDiscount()).isEqualByComparingTo(new BigDecimal("10.00"));

            // Coupon applied SECOND, on the post-full-reduction amount (90.00).
            assertThat(response.getCouponDiscount()).isEqualByComparingTo(new BigDecimal("18.00"));

            // Member discount applied LAST, on the post-coupon amount (72.00).
            assertThat(response.getMemberDiscount()).isEqualByComparingTo(new BigDecimal("3.60"));

            assertThat(response.getTotalDiscount()).isEqualByComparingTo(new BigDecimal("31.60"));
            assertThat(response.getFinalAmount()).isEqualByComparingTo(new BigDecimal("68.40"));
        }

        @Test
        @DisplayName("testCalculate_matchesDesignDocWorkedExample: " +
                "300 -30(fullReduction) x0.8(coupon) x0.95(member) = 205.20, per design-docs/10 §3")
        void testCalculate_matchesDesignDocWorkedExample() {
            item.setPrice(new BigDecimal("300.00"));

            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.of(new BigDecimal("30.00")));
            when(userCouponRepository.findById(1L)).thenReturn(Optional.of(userCoupon));
            when(couponTemplateRepository.findById(100L)).thenReturn(Optional.of(discountTemplate));
            when(couponService.calculateDiscount(any(BigDecimal.class), any(CouponTemplate.class)))
                    .thenAnswer(invocation -> {
                        BigDecimal price = invocation.getArgument(0);
                        CouponTemplate ct = invocation.getArgument(1);
                        BigDecimal discountRate = BigDecimal.ONE.subtract(ct.getDiscountValue());
                        return MonetaryUtil.multiply(price, discountRate);
                    });

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("300.00"));
            assertThat(response.getFullReductionDiscount()).isEqualByComparingTo(new BigDecimal("30.00"));
            assertThat(response.getCouponDiscount()).isEqualByComparingTo(new BigDecimal("54.00"));
            assertThat(response.getMemberDiscount()).isEqualByComparingTo(new BigDecimal("10.80"));
            assertThat(response.getFinalAmount()).isEqualByComparingTo(new BigDecimal("205.20"));
        }

        @Test
        @DisplayName("testCalculate_totalDiscountNeverExceedsItemTotal: " +
                "an overshooting full-reduction is clamped, not allowed to push totalDiscount past itemTotal")
        void testCalculate_totalDiscountNeverExceedsItemTotal() {
            request.setUserId(null);
            request.setCouponIds(null);

            // Force a discount larger than the item total to exercise the clamp.
            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.of(new BigDecimal("200.00")));

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            assertThat(response.getFinalAmount()).isEqualByComparingTo(BigDecimal.ZERO);
            assertThat(response.getTotalDiscount()).isEqualByComparingTo(response.getItemTotal());
        }

        @Test
        @DisplayName("testCalculate_noDiscounts_appliesNone: " +
                "no userId, no coupons, no full reductions — returns item total as final")
        void testCalculate_noDiscounts_appliesNone() {
            // Null userId → member discount returns 0
            request.setUserId(null);
            request.setCouponIds(null);

            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.empty());

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("100.00"));
            assertThat(response.getMemberDiscount()).isEqualByComparingTo(BigDecimal.ZERO);
            assertThat(response.getFullReductionDiscount()).isEqualByComparingTo(BigDecimal.ZERO);
            assertThat(response.getCouponDiscount()).isEqualByComparingTo(BigDecimal.ZERO);
            assertThat(response.getTotalDiscount()).isEqualByComparingTo(BigDecimal.ZERO);
            assertThat(response.getFinalAmount()).isEqualByComparingTo(new BigDecimal("100.00"));
        }

        @Test
        @DisplayName("testCalculate_multipleCoupons_appliesEach: " +
                "each coupon discount is applied independently to the same base amount")
        void testCalculate_multipleCoupons_appliesEach() {
            /*
             * Two DISCOUNT coupons, each at 0.8, applied to the same base = 90.00
             * (after full reduction of 10.00 from the 100.00 item total).
             *
             * Coupon 1 on 90.00: discount = 18.00
             * Coupon 2 on 90.00: discount = 18.00
             * Total coupon discount = 36.00
             * afterCoupon = 90.00 - 36.00 = 54.00
             * Member (5% of 54.00) = 2.70
             * finalAmount = 54.00 - 2.70 = 51.30
             * totalDiscount = 100.00 - 51.30 = 48.70
             */

            request.setCouponIds(List.of(1L, 2L));

            // Second user coupon
            UserCoupon userCoupon2 = new UserCoupon();
            userCoupon2.setId(2L);
            userCoupon2.setUserId(1L);
            userCoupon2.setCouponTemplateId(200L);
            userCoupon2.setCouponCode("CPN-DISC80-2");
            userCoupon2.setStatus(CouponStatus.AVAILABLE);

            // Second coupon template (same as first)
            CouponTemplate discountTemplate2 = new CouponTemplate();
            discountTemplate2.setId(200L);
            discountTemplate2.setName("80% Off #2");
            discountTemplate2.setType(CouponType.DISCOUNT);
            discountTemplate2.setDiscountValue(new BigDecimal("0.8"));
            discountTemplate2.setStatus("ACTIVE");

            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.of(new BigDecimal("10.00")));
            when(userCouponRepository.findById(1L)).thenReturn(Optional.of(userCoupon));
            when(userCouponRepository.findById(2L)).thenReturn(Optional.of(userCoupon2));
            when(couponTemplateRepository.findById(100L)).thenReturn(Optional.of(discountTemplate));
            when(couponTemplateRepository.findById(200L)).thenReturn(Optional.of(discountTemplate2));
            when(couponService.calculateDiscount(any(BigDecimal.class), any(CouponTemplate.class)))
                    .thenAnswer(invocation -> {
                        BigDecimal price = invocation.getArgument(0);
                        CouponTemplate ct = invocation.getArgument(1);
                        if (ct.getType() == CouponType.DISCOUNT) {
                            BigDecimal discountRate = BigDecimal.ONE.subtract(ct.getDiscountValue());
                            return MonetaryUtil.multiply(price, discountRate);
                        }
                        return BigDecimal.ZERO;
                    });

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("100.00"));
            assertThat(response.getFullReductionDiscount()).isEqualByComparingTo(new BigDecimal("10.00"));
            assertThat(response.getCouponDiscount()).isEqualByComparingTo(new BigDecimal("36.00"));
            assertThat(response.getMemberDiscount()).isEqualByComparingTo(new BigDecimal("2.70"));
            assertThat(response.getTotalDiscount()).isEqualByComparingTo(new BigDecimal("48.70"));
            assertThat(response.getFinalAmount()).isEqualByComparingTo(new BigDecimal("51.30"));
        }

        @Test
        @DisplayName("testCalculate_multipleItems_sumsCorrectly")
        void testCalculate_multipleItems_sumsCorrectly() {
            PromotionCalculateRequest.CalculateItem item2 = new PromotionCalculateRequest.CalculateItem();
            item2.setSkuId(2L);
            item2.setPrice(new BigDecimal("50.00"));
            item2.setQuantity(2); // line total = 100

            request.setItems(List.of(item, item2));
            request.setUserId(null);
            request.setCouponIds(null);

            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.empty());

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            // 100 * 1 + 50 * 2 = 200
            assertThat(response.getItemTotal()).isEqualByComparingTo(new BigDecimal("200.00"));
            assertThat(response.getFinalAmount()).isEqualByComparingTo(new BigDecimal("200.00"));
        }

        @Test
        @DisplayName("testCalculate_emptyCouponIds_skipsCoupons")
        void testCalculate_emptyCouponIds_skipsCoupons() {
            request.setCouponIds(Collections.emptyList());

            when(fullReductionService.calculateBestReduction(any(BigDecimal.class)))
                    .thenReturn(Optional.of(new BigDecimal("10.00")));

            PromotionCalculateResponse response = promotionCalculationService.calculate(request);

            // afterFullReduction = 100.00 - 10.00 = 90.00; no coupon; member 5% of 90.00 = 4.50
            assertThat(response.getCouponDiscount()).isEqualByComparingTo(BigDecimal.ZERO);
            assertThat(response.getMemberDiscount()).isEqualByComparingTo(new BigDecimal("4.50"));
            assertThat(response.getFullReductionDiscount()).isEqualByComparingTo(new BigDecimal("10.00"));
        }
    }

    // -----------------------------------------------------------------------
    // calculateCouponDiscount tests (package-private, tested directly)
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("calculateCouponDiscount")
    class CalculateCouponDiscount {

        @Test
        @DisplayName("calculateCouponDiscount: a coupon belonging to a different user is silently skipped")
        void testCalculateCouponDiscount_couponBelongsToDifferentUser_isSkipped() {
            UserCoupon othersCoupon = new UserCoupon();
            othersCoupon.setId(1L);
            othersCoupon.setUserId(999L); // not the requesting user (1L)
            othersCoupon.setCouponTemplateId(100L);
            othersCoupon.setCouponCode("CPN-NOT-MINE");
            othersCoupon.setStatus(CouponStatus.AVAILABLE);

            when(userCouponRepository.findById(1L)).thenReturn(Optional.of(othersCoupon));

            BigDecimal discount = promotionCalculationService.calculateCouponDiscount(
                    1L, List.of(1L), new BigDecimal("100.00"), List.of(1L));

            assertThat(discount).isEqualByComparingTo(BigDecimal.ZERO);
            // Never even reaches validation/template lookup for a coupon that isn't the caller's.
            verify(couponValidator, never()).validate(any(), any(), any());
            verify(couponTemplateRepository, never()).findById(any());
        }
    }
}
