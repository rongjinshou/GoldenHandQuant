package com.ecommerce.promotion.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.promotion.entity.CouponStatus;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.UserCoupon;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.ecommerce.promotion.repository.UserCouponRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Validates whether a coupon can be applied to an order.
 *
 * <p>Implements the coupon validation order from design-docs/10 §2: existence →
 * validity period → spend threshold → item applicability → used status. Coupon
 * ownership (whether {@code userCoupon} actually belongs to the requesting user)
 * is checked by the caller ({@link PromotionCalculationService#calculateCouponDiscount})
 * before this method is invoked, and is intentionally handled as a silent skip
 * rather than a thrown exception here, so a user cannot probe for the existence
 * of another user's coupon IDs via error responses.
 */
@Service
public class CouponValidator {

    private final CouponTemplateRepository couponTemplateRepository;
    private final UserCouponRepository userCouponRepository;
    private final ObjectMapper objectMapper;

    public CouponValidator(CouponTemplateRepository couponTemplateRepository,
                            UserCouponRepository userCouponRepository,
                            ObjectMapper objectMapper) {
        this.couponTemplateRepository = couponTemplateRepository;
        this.userCouponRepository = userCouponRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Validate that a coupon is applicable to the given order.
     *
     * @param userCoupon  the claimed coupon instance to validate
     * @param orderAmount the order subtotal the coupon would apply against
     * @param skuIds      SKU IDs being purchased in this order
     * @throws ResourceNotFoundException if the coupon or its template does not exist
     * @throws BusinessException         if the coupon fails any applicability check
     *                                   ({@code COUPON_EXPIRED}, {@code COUPON_THRESHOLD_NOT_MET},
     *                                   {@code COUPON_NOT_APPLICABLE}, or {@code COUPON_ALREADY_USED})
     */
    public void validate(UserCoupon userCoupon, BigDecimal orderAmount, List<Long> skuIds) {
        if (userCoupon == null) {
            throw new ResourceNotFoundException("Coupon not found");
        }
        CouponTemplate template = couponTemplateRepository.findById(userCoupon.getCouponTemplateId())
                .orElseThrow(() -> new ResourceNotFoundException("CouponTemplate", userCoupon.getCouponTemplateId()));

        LocalDateTime now = SystemClockService.now();
        if ((template.getStartTime() != null && now.isBefore(template.getStartTime()))
                || (template.getEndTime() != null && now.isAfter(template.getEndTime()))) {
            throw new BusinessException("COUPON_EXPIRED", "Coupon is not within its valid time window");
        }
        if (template.getThresholdAmount() != null
                && (orderAmount == null || orderAmount.compareTo(template.getThresholdAmount()) < 0)) {
            throw new BusinessException("COUPON_THRESHOLD_NOT_MET", "Order amount below coupon threshold");
        }
        if (!isApplicableToSkus(template, skuIds)) {
            throw new BusinessException("COUPON_NOT_APPLICABLE", "Coupon does not apply to the purchased items");
        }
        if (userCoupon.getStatus() != CouponStatus.AVAILABLE) {
            throw new BusinessException("COUPON_ALREADY_USED", "Coupon has already been used or is unavailable");
        }
    }

    /**
     * A coupon with no {@code applicableProductIds} configured applies to all
     * products. Otherwise, at least one purchased SKU must be in the configured set.
     */
    private boolean isApplicableToSkus(CouponTemplate template, List<Long> skuIds) {
        String json = template.getApplicableProductIds();
        if (json == null || json.isBlank()) {
            return true; // no restriction configured
        }
        List<Long> applicableIds = parseIds(json);
        if (applicableIds == null || applicableIds.isEmpty()) {
            return true;
        }
        return skuIds != null && skuIds.stream().anyMatch(applicableIds::contains);
    }

    private List<Long> parseIds(String json) {
        try {
            return objectMapper.readValue(json, new TypeReference<List<Long>>() {
            });
        } catch (JsonProcessingException e) {
            // Malformed data should never happen (we control serialization), but
            // fail open rather than blocking checkout on a data-quality issue.
            return null;
        }
    }
}
