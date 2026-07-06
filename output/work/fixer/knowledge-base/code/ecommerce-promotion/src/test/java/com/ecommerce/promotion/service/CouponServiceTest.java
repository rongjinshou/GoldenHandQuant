package com.ecommerce.promotion.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.promotion.entity.CouponStatus;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.CouponType;
import com.ecommerce.promotion.entity.UserCoupon;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.ecommerce.promotion.repository.UserCouponRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link CouponService}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("CouponService")
class CouponServiceTest {

    @Mock
    private CouponTemplateRepository couponTemplateRepository;

    @Mock
    private UserCouponRepository userCouponRepository;

    @InjectMocks
    private CouponService couponService;

    @Captor
    private ArgumentCaptor<UserCoupon> userCouponCaptor;

    @Captor
    private ArgumentCaptor<CouponTemplate> templateCaptor;

    // -----------------------------------------------------------------------
    // calculateDiscount tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("calculateDiscount")
    class CalculateDiscount {

        private CouponTemplate discountCoupon;
        private CouponTemplate amountOffCoupon;
        private CouponTemplate thresholdCoupon;

        @BeforeEach
        void setUp() {
            discountCoupon = new CouponTemplate();
            discountCoupon.setId(1L);
            discountCoupon.setName("80% Off Discount");
            discountCoupon.setType(CouponType.DISCOUNT);
            discountCoupon.setDiscountValue(new BigDecimal("0.8"));
            discountCoupon.setStatus("ACTIVE");

            amountOffCoupon = new CouponTemplate();
            amountOffCoupon.setId(2L);
            amountOffCoupon.setName("$10 Off");
            amountOffCoupon.setType(CouponType.AMOUNT_OFF);
            amountOffCoupon.setDiscountValue(new BigDecimal("10.00"));
            amountOffCoupon.setStatus("ACTIVE");

            thresholdCoupon = new CouponTemplate();
            thresholdCoupon.setId(3L);
            thresholdCoupon.setName("$30 Off Over $300");
            thresholdCoupon.setType(CouponType.THRESHOLD_OFF);
            thresholdCoupon.setDiscountValue(new BigDecimal("30.00"));
            thresholdCoupon.setThresholdAmount(new BigDecimal("300.00"));
            thresholdCoupon.setStatus("ACTIVE");
        }

        @Test
        @DisplayName("testCalculateDiscount_discountCoupon: " +
                "an 80%-price (\"8折\") coupon on 100.00 discounts 20.00, per design-docs/10 §2")
        void testCalculateDiscount_discountCoupon_80percentOff() {
            BigDecimal price = new BigDecimal("100.00");
            BigDecimal result = couponService.calculateDiscount(price, discountCoupon);

            // discountAmount = price * (1 - discountValue) = 100 * (1 - 0.8) = 20.00
            assertThat(result).isEqualByComparingTo(new BigDecimal("20.00"));
        }

        @Test
        @DisplayName("testCalculateDiscount_amountOffCoupon: fixed amount off")
        void testCalculateDiscount_amountOffCoupon() {
            BigDecimal price = new BigDecimal("100.00");
            BigDecimal result = couponService.calculateDiscount(price, amountOffCoupon);

            // AMOUNT_OFF simply returns the discount value
            assertThat(result).isEqualByComparingTo(new BigDecimal("10.00"));
        }

        @Test
        @DisplayName("testCalculateDiscount_amountOffCoupon_exceedsPrice")
        void testCalculateDiscount_amountOffCoupon_exceedsPrice() {
            // When amount off exceeds price, the discount is capped at the price
            amountOffCoupon.setDiscountValue(new BigDecimal("150.00"));
            BigDecimal price = new BigDecimal("100.00");
            BigDecimal result = couponService.calculateDiscount(price, amountOffCoupon);

            assertThat(result).isEqualByComparingTo(new BigDecimal("100.00"));
        }

        @Test
        @DisplayName("testCalculateDiscount_thresholdCoupon: threshold met")
        void testCalculateDiscount_thresholdCoupon() {
            BigDecimal price = new BigDecimal("350.00");
            BigDecimal result = couponService.calculateDiscount(price, thresholdCoupon);

            // price >= 300 threshold, discount = 30.00
            assertThat(result).isEqualByComparingTo(new BigDecimal("30.00"));
        }

        @Test
        @DisplayName("testCalculateDiscount_thresholdCoupon_thresholdNotMet")
        void testCalculateDiscount_thresholdCoupon_thresholdNotMet() {
            BigDecimal price = new BigDecimal("250.00");
            BigDecimal result = couponService.calculateDiscount(price, thresholdCoupon);

            // price < 300 threshold, no discount
            assertThat(result).isEqualByComparingTo(BigDecimal.ZERO);
        }

        @Test
        @DisplayName("testCalculateDiscount_nullPrice_returnsZero")
        void testCalculateDiscount_nullPrice_returnsZero() {
            BigDecimal result = couponService.calculateDiscount(null, discountCoupon);
            assertThat(result).isEqualByComparingTo(BigDecimal.ZERO);
        }

        @Test
        @DisplayName("testCalculateDiscount_nullCoupon_returnsZero")
        void testCalculateDiscount_nullCoupon_returnsZero() {
            BigDecimal result = couponService.calculateDiscount(new BigDecimal("100.00"), null);
            assertThat(result).isEqualByComparingTo(BigDecimal.ZERO);
        }

        @Test
        @DisplayName("testCalculateDiscount_discountCoupon_withMaxDiscount")
        void testCalculateDiscount_discountCoupon_withMaxDiscount() {
            // DISCOUNT with maxDiscount cap
            // price=100, discountValue=0.8, maxDiscount=10
            // raw discount = 100*(1-0.8) = 20.00, capped at maxDiscount=10.00
            discountCoupon.setMaxDiscount(new BigDecimal("10.00"));
            BigDecimal price = new BigDecimal("100.00");
            BigDecimal result = couponService.calculateDiscount(price, discountCoupon);

            assertThat(result).isEqualByComparingTo(new BigDecimal("10.00"));
        }

        @Test
        @DisplayName("testCalculateDiscount_discountCoupon_withMaxDiscountNotExceeded")
        void testCalculateDiscount_discountCoupon_withMaxDiscountNotExceeded() {
            // DISCOUNT with maxDiscount that is higher than raw discount
            // price=100, discountValue=0.8, maxDiscount=90
            // raw discount = 100*(1-0.8) = 20.00, not capped
            discountCoupon.setMaxDiscount(new BigDecimal("90.00"));
            BigDecimal price = new BigDecimal("100.00");
            BigDecimal result = couponService.calculateDiscount(price, discountCoupon);

            assertThat(result).isEqualByComparingTo(new BigDecimal("20.00"));
        }
    }

    // -----------------------------------------------------------------------
    // claim tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("claim")
    class Claim {

        private CouponTemplate template;
        private final Long userId = 42L;
        private final Long templateId = 1L;

        @BeforeEach
        void setUp() {
            template = new CouponTemplate();
            template.setId(templateId);
            template.setName("Test Coupon");
            template.setType(CouponType.AMOUNT_OFF);
            template.setDiscountValue(new BigDecimal("10.00"));
            template.setStatus("ACTIVE");
            template.setTotalQuantity(100);
            template.setIssuedQuantity(0);
            template.setPerUserLimit(5);
        }

        @Test
        @DisplayName("testClaimCoupon_assignsToUser: successfully claims coupon for user")
        void testClaimCoupon_assignsToUser() {
            when(couponTemplateRepository.findById(templateId)).thenReturn(Optional.of(template));
            when(userCouponRepository.countByUserIdAndCouponTemplateId(userId, templateId)).thenReturn(0L);
            when(couponTemplateRepository.save(any(CouponTemplate.class))).thenReturn(template);
            when(userCouponRepository.save(any(UserCoupon.class))).thenAnswer(invocation -> {
                UserCoupon uc = invocation.getArgument(0);
                uc.setId(100L);
                return uc;
            });

            UserCoupon result = couponService.claim(userId, templateId);

            assertThat(result).isNotNull();
            assertThat(result.getUserId()).isEqualTo(userId);
            assertThat(result.getCouponTemplateId()).isEqualTo(templateId);
            assertThat(result.getStatus()).isEqualTo(CouponStatus.AVAILABLE);
            assertThat(result.getCouponCode()).isNotNull();
            assertThat(result.getCouponCode()).startsWith("CPN-");
            assertThat(result.getClaimedAt()).isNotNull();

            // Verify issued quantity was incremented and saved
            verify(couponTemplateRepository).save(templateCaptor.capture());
            assertThat(templateCaptor.getValue().getIssuedQuantity()).isEqualTo(1);

            verify(userCouponRepository).save(userCouponCaptor.capture());
            UserCoupon saved = userCouponCaptor.getValue();
            assertThat(saved.getUserId()).isEqualTo(userId);
            assertThat(saved.getCouponTemplateId()).isEqualTo(templateId);
        }

        @Test
        @DisplayName("testClaimCoupon_exceededQuantity_throwsException: " +
                "throws COUPON_EXHAUSTED when issuedQuantity >= totalQuantity")
        void testClaimCoupon_exceededQuantity_throwsException() {
            template.setIssuedQuantity(100); // equals totalQuantity
            when(couponTemplateRepository.findById(templateId)).thenReturn(Optional.of(template));

            assertThatThrownBy(() -> couponService.claim(userId, templateId))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("Coupon has been fully claimed");

            verify(userCouponRepository, never()).save(any(UserCoupon.class));
        }

        @Test
        @DisplayName("testClaimCoupon_exceededPerUserLimit_throwsException")
        void testClaimCoupon_exceededPerUserLimit_throwsException() {
            template.setPerUserLimit(3);
            when(couponTemplateRepository.findById(templateId)).thenReturn(Optional.of(template));
            when(userCouponRepository.countByUserIdAndCouponTemplateId(userId, templateId)).thenReturn(3L);

            assertThatThrownBy(() -> couponService.claim(userId, templateId))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("maximum number");

            verify(couponTemplateRepository, never()).save(any(CouponTemplate.class));
        }

        @Test
        @DisplayName("testClaimCoupon_inactiveTemplate_throwsException")
        void testClaimCoupon_inactiveTemplate_throwsException() {
            template.setStatus("INACTIVE");
            when(couponTemplateRepository.findById(templateId)).thenReturn(Optional.of(template));

            assertThatThrownBy(() -> couponService.claim(userId, templateId))
                    .isInstanceOf(BusinessException.class)
                    .hasMessageContaining("not active");

            verify(userCouponRepository, never()).save(any(UserCoupon.class));
        }

        @Test
        @DisplayName("testClaimCoupon_templateNotFound_throwsException")
        void testClaimCoupon_templateNotFound_throwsException() {
            when(couponTemplateRepository.findById(templateId)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> couponService.claim(userId, templateId))
                    .isInstanceOf(ResourceNotFoundException.class);
        }

        @Test
        @DisplayName("testClaimCoupon_nullIssuedQuantity_initializesTo1")
        void testClaimCoupon_nullIssuedQuantity_initializesTo1() {
            template.setIssuedQuantity(null);
            when(couponTemplateRepository.findById(templateId)).thenReturn(Optional.of(template));
            when(userCouponRepository.countByUserIdAndCouponTemplateId(userId, templateId)).thenReturn(0L);
            when(couponTemplateRepository.save(any(CouponTemplate.class))).thenReturn(template);
            when(userCouponRepository.save(any(UserCoupon.class))).thenAnswer(invocation -> {
                UserCoupon uc = invocation.getArgument(0);
                uc.setId(200L);
                return uc;
            });

            couponService.claim(userId, templateId);

            verify(couponTemplateRepository).save(templateCaptor.capture());
            assertThat(templateCaptor.getValue().getIssuedQuantity()).isEqualTo(1);
        }
    }

    // -----------------------------------------------------------------------
    // markUsed tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("markUsed")
    class MarkUsed {

        private final Long userCouponId = 55L;
        private final Long orderId = 900L;
        private UserCoupon userCoupon;

        @BeforeEach
        void setUp() {
            userCoupon = new UserCoupon();
            userCoupon.setId(userCouponId);
            userCoupon.setUserId(42L);
            userCoupon.setCouponTemplateId(1L);
            userCoupon.setCouponCode("CPN-TOUSE");
            userCoupon.setStatus(CouponStatus.AVAILABLE);
        }

        @AfterEach
        void tearDown() {
            SystemClockService.reset();
        }

        @Test
        @DisplayName("markUsed: sets status to USED and records the order ID and usedAt")
        void testMarkUsed_setsStatusUsedAndRecordsOrderId() {
            LocalDateTime fixedNow = LocalDateTime.of(2026, 1, 1, 12, 0);
            SystemClockService.setFixed(fixedNow);

            when(userCouponRepository.findById(userCouponId)).thenReturn(Optional.of(userCoupon));
            when(userCouponRepository.save(any(UserCoupon.class)))
                    .thenAnswer(invocation -> invocation.getArgument(0));

            couponService.markUsed(userCouponId, orderId);

            verify(userCouponRepository).save(userCouponCaptor.capture());
            UserCoupon saved = userCouponCaptor.getValue();
            assertThat(saved.getStatus()).isEqualTo(CouponStatus.USED);
            assertThat(saved.getUsedOrderId()).isEqualTo(orderId);
            assertThat(saved.getUsedAt()).isEqualTo(fixedNow);
        }

        @Test
        @DisplayName("markUsed: throws ResourceNotFoundException when the coupon does not exist")
        void testMarkUsed_notFound_throwsException() {
            when(userCouponRepository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> couponService.markUsed(999L, orderId))
                    .isInstanceOf(ResourceNotFoundException.class);

            verify(userCouponRepository, never()).save(any(UserCoupon.class));
        }
    }
}
