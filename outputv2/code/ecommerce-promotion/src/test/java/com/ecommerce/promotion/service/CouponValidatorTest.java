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
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.catchThrowableOfType;
import static org.mockito.Mockito.when;

/**
 * Tests for {@link CouponValidator}.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("CouponValidator")
class CouponValidatorTest {

    @Mock
    private CouponTemplateRepository couponTemplateRepository;

    @Mock
    private UserCouponRepository userCouponRepository;

    @Spy
    private ObjectMapper objectMapper = new ObjectMapper();

    @InjectMocks
    private CouponValidator couponValidator;

    // -----------------------------------------------------------------------
    // Shared test data
    // -----------------------------------------------------------------------

    private static final BigDecimal ORDER_AMOUNT = new BigDecimal("100.00");
    private static final List<Long> SKU_IDS = List.of(1L, 2L);

    private UserCoupon validUserCoupon;
    private CouponTemplate existingTemplate;
    private CouponTemplate expiredTemplate;

    @BeforeEach
    void setUp() {
        existingTemplate = new CouponTemplate();
        existingTemplate.setId(1L);
        existingTemplate.setName("Active Coupon");
        existingTemplate.setType(CouponType.AMOUNT_OFF);
        existingTemplate.setDiscountValue(new BigDecimal("10.00"));
        existingTemplate.setStatus("ACTIVE");
        existingTemplate.setStartTime(LocalDateTime.now().minusDays(7));
        existingTemplate.setEndTime(LocalDateTime.now().plusDays(7));

        expiredTemplate = new CouponTemplate();
        expiredTemplate.setId(2L);
        expiredTemplate.setName("Expired Coupon");
        expiredTemplate.setType(CouponType.DISCOUNT);
        expiredTemplate.setDiscountValue(new BigDecimal("0.8"));
        expiredTemplate.setStatus("ACTIVE");
        expiredTemplate.setStartTime(LocalDateTime.now().minusDays(30));
        expiredTemplate.setEndTime(LocalDateTime.now().minusDays(1));

        validUserCoupon = new UserCoupon();
        validUserCoupon.setId(10L);
        validUserCoupon.setUserId(1L);
        validUserCoupon.setCouponTemplateId(1L);
        validUserCoupon.setCouponCode("CPN-TEST001");
        validUserCoupon.setStatus(CouponStatus.AVAILABLE);
    }

    @AfterEach
    void tearDown() {
        SystemClockService.reset();
    }

    // -----------------------------------------------------------------------
    // Validate tests
    // -----------------------------------------------------------------------

    @Nested
    @DisplayName("validate")
    class Validate {

        @Test
        @DisplayName("testValidate_existingCoupon_returnsTrue")
        void testValidate_existingCoupon_returnsTrue() {
            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            assertThatCode(() -> couponValidator.validate(validUserCoupon, ORDER_AMOUNT, SKU_IDS))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("testValidate_nonExistentCoupon_returnsFalse: " +
                "throws ResourceNotFoundException when template does not exist")
        void testValidate_nonExistentCoupon_returnsFalse() {
            validUserCoupon.setCouponTemplateId(999L);
            when(couponTemplateRepository.findById(999L)).thenReturn(Optional.empty());

            assertThatThrownBy(() -> couponValidator.validate(validUserCoupon, ORDER_AMOUNT, SKU_IDS))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .hasMessageContaining("CouponTemplate");
        }

        @Test
        @DisplayName("testValidate_expiredCoupon_throwsCouponExpired: " +
                "a coupon whose template validity window has passed is rejected")
        void testValidate_expiredCoupon_throwsCouponExpired() {
            UserCoupon expiredUserCoupon = new UserCoupon();
            expiredUserCoupon.setId(20L);
            expiredUserCoupon.setUserId(1L);
            expiredUserCoupon.setCouponTemplateId(2L);
            expiredUserCoupon.setCouponCode("CPN-EXPIRED");
            expiredUserCoupon.setStatus(CouponStatus.AVAILABLE);

            when(couponTemplateRepository.findById(2L)).thenReturn(Optional.of(expiredTemplate));

            BusinessException ex = catchThrowableOfType(
                    () -> couponValidator.validate(expiredUserCoupon, ORDER_AMOUNT, SKU_IDS),
                    BusinessException.class);
            assertThat(ex.getCode()).isEqualTo("COUPON_EXPIRED");
        }

        @Test
        @DisplayName("testValidate_usedCoupon_throwsCouponAlreadyUsed: " +
                "a USED coupon can no longer be applied")
        void testValidate_usedCoupon_throwsCouponAlreadyUsed() {
            UserCoupon usedCoupon = new UserCoupon();
            usedCoupon.setId(30L);
            usedCoupon.setUserId(1L);
            usedCoupon.setCouponTemplateId(1L);
            usedCoupon.setCouponCode("CPN-USED");
            usedCoupon.setStatus(CouponStatus.USED);

            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            BusinessException ex = catchThrowableOfType(
                    () -> couponValidator.validate(usedCoupon, ORDER_AMOUNT, SKU_IDS),
                    BusinessException.class);
            assertThat(ex.getCode()).isEqualTo("COUPON_ALREADY_USED");
        }

        @Test
        @DisplayName("testValidate_nullCoupon_throwsException")
        void testValidate_nullCoupon_throwsException() {
            assertThatThrownBy(() -> couponValidator.validate(null, ORDER_AMOUNT, SKU_IDS))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .hasMessageContaining("Coupon not found");
        }

        @Test
        @DisplayName("testValidate_couponWithFutureStartTime_throwsCouponExpired: " +
                "a coupon that has not started yet is rejected")
        void testValidate_couponWithFutureStartTime_throwsCouponExpired() {
            CouponTemplate futureTemplate = new CouponTemplate();
            futureTemplate.setId(3L);
            futureTemplate.setName("Future Coupon");
            futureTemplate.setType(CouponType.AMOUNT_OFF);
            futureTemplate.setDiscountValue(new BigDecimal("5.00"));
            futureTemplate.setStatus("ACTIVE");
            futureTemplate.setStartTime(LocalDateTime.now().plusDays(7));
            futureTemplate.setEndTime(LocalDateTime.now().plusDays(14));

            UserCoupon futureUserCoupon = new UserCoupon();
            futureUserCoupon.setId(40L);
            futureUserCoupon.setUserId(1L);
            futureUserCoupon.setCouponTemplateId(3L);
            futureUserCoupon.setCouponCode("CPN-FUTURE");
            futureUserCoupon.setStatus(CouponStatus.AVAILABLE);

            when(couponTemplateRepository.findById(3L)).thenReturn(Optional.of(futureTemplate));

            BusinessException ex = catchThrowableOfType(
                    () -> couponValidator.validate(futureUserCoupon, ORDER_AMOUNT, SKU_IDS),
                    BusinessException.class);
            assertThat(ex.getCode()).isEqualTo("COUPON_EXPIRED");
        }

        @Test
        @DisplayName("testValidate_belowThreshold_throwsCouponThresholdNotMet")
        void testValidate_belowThreshold_throwsCouponThresholdNotMet() {
            existingTemplate.setThresholdAmount(new BigDecimal("200.00"));
            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            BusinessException ex = catchThrowableOfType(
                    () -> couponValidator.validate(validUserCoupon, new BigDecimal("100.00"), SKU_IDS),
                    BusinessException.class);
            assertThat(ex.getCode()).isEqualTo("COUPON_THRESHOLD_NOT_MET");
        }

        @Test
        @DisplayName("testValidate_meetsThreshold_passes")
        void testValidate_meetsThreshold_passes() {
            existingTemplate.setThresholdAmount(new BigDecimal("200.00"));
            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            assertThatCode(() -> couponValidator.validate(validUserCoupon, new BigDecimal("200.00"), SKU_IDS))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("testValidate_notApplicableToSkus_throwsCouponNotApplicable")
        void testValidate_notApplicableToSkus_throwsCouponNotApplicable() {
            existingTemplate.setApplicableProductIds("[999]");
            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            BusinessException ex = catchThrowableOfType(
                    () -> couponValidator.validate(validUserCoupon, ORDER_AMOUNT, List.of(1L, 2L)),
                    BusinessException.class);
            assertThat(ex.getCode()).isEqualTo("COUPON_NOT_APPLICABLE");
        }

        @Test
        @DisplayName("testValidate_applicableToSkus_passesWhenSkuMatches")
        void testValidate_applicableToSkus_passesWhenSkuMatches() {
            existingTemplate.setApplicableProductIds("[1,2,3]");
            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            assertThatCode(() -> couponValidator.validate(validUserCoupon, ORDER_AMOUNT, List.of(2L)))
                    .doesNotThrowAnyException();
        }

        @Test
        @DisplayName("testValidate_noProductRestriction_appliesToAnySku")
        void testValidate_noProductRestriction_appliesToAnySku() {
            // applicableProductIds left null — no restriction configured
            when(couponTemplateRepository.findById(1L)).thenReturn(Optional.of(existingTemplate));

            assertThatCode(() -> couponValidator.validate(validUserCoupon, ORDER_AMOUNT, List.of(12345L)))
                    .doesNotThrowAnyException();
        }
    }
}
