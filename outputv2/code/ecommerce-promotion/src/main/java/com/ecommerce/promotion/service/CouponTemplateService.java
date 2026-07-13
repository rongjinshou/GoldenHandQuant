package com.ecommerce.promotion.service;

import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.exception.ValidationException;
import com.ecommerce.promotion.dto.CouponCreateRequest;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.CouponType;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

/**
 * Administrative service for managing coupon templates.
 */
@Service
public class CouponTemplateService {

    private final CouponTemplateRepository couponTemplateRepository;
    private final ObjectMapper objectMapper;

    public CouponTemplateService(CouponTemplateRepository couponTemplateRepository,
                                  ObjectMapper objectMapper) {
        this.couponTemplateRepository = couponTemplateRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Create a new coupon template. ADMIN only.
     */
    @Transactional
    public CouponTemplate create(CouponCreateRequest request) {
        validateCreateRequest(request);

        CouponTemplate template = new CouponTemplate();
        template.setName(request.getName());
        template.setType(request.getType());
        template.setDiscountValue(request.getDiscountValue());
        template.setThresholdAmount(request.getThresholdAmount());
        template.setMaxDiscount(request.getMaxDiscount());
        template.setTotalQuantity(request.getTotalQuantity());
        template.setIssuedQuantity(0);
        template.setStartTime(request.getStartTime());
        template.setEndTime(request.getEndTime());
        template.setPerUserLimit(request.getPerUserLimit() != null ? request.getPerUserLimit() : 1);
        template.setStatus("ACTIVE");

        if (request.getApplicableCategoryIds() != null && !request.getApplicableCategoryIds().isEmpty()) {
            template.setApplicableCategoryIds(toJson(request.getApplicableCategoryIds()));
        }
        if (request.getApplicableProductIds() != null && !request.getApplicableProductIds().isEmpty()) {
            template.setApplicableProductIds(toJson(request.getApplicableProductIds()));
        }

        return couponTemplateRepository.save(template);
    }

    /**
     * List all active coupon templates.
     */
    @Transactional(readOnly = true)
    public List<CouponTemplate> listActive() {
        return couponTemplateRepository.findByStatusOrderByCreatedAtDesc("ACTIVE");
    }

    private void validateCreateRequest(CouponCreateRequest request) {
        if (request.getType() == null) {
            throw new ValidationException("type", "Coupon type is required");
        }
        if (request.getType() == CouponType.DISCOUNT && request.getDiscountValue() == null) {
            throw new ValidationException("discountValue", "Discount value is required for DISCOUNT coupon");
        }
        if (request.getType() == CouponType.THRESHOLD_OFF && request.getThresholdAmount() == null) {
            throw new ValidationException("thresholdAmount", "Threshold amount is required for THRESHOLD_OFF coupon");
        }
        validateDiscountValueRange(request);
    }

    /**
     * Range-check {@code discountValue} so a mis-configured template can never
     * produce a negative discount that raises the payable amount (design-docs/03
     * §1: 优惠金额不得小于 0). Per design-docs/10 §2, for DISCOUNT the value is a
     * rate (8 折 = 0.8) and must be within (0, 1]; for AMOUNT_OFF/THRESHOLD_OFF
     * it is the amount taken off and must be positive when present.
     */
    private void validateDiscountValueRange(CouponCreateRequest request) {
        BigDecimal discountValue = request.getDiscountValue();
        if (discountValue == null) {
            return;
        }
        if (request.getType() == CouponType.DISCOUNT) {
            if (discountValue.compareTo(BigDecimal.ZERO) <= 0
                    || discountValue.compareTo(BigDecimal.ONE) > 0) {
                throw new ValidationException("discountValue",
                        "Discount rate must be within (0, 1] for DISCOUNT coupon");
            }
        } else if (discountValue.compareTo(BigDecimal.ZERO) <= 0) {
            throw new ValidationException("discountValue",
                    "Discount value must be greater than 0 for " + request.getType() + " coupon");
        }
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to serialize to JSON", e);
        }
    }
}
