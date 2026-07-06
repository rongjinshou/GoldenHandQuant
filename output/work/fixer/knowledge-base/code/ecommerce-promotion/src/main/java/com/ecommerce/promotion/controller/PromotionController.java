package com.ecommerce.promotion.controller;

import com.ecommerce.promotion.dto.CouponClaimRequest;
import com.ecommerce.promotion.dto.CouponResponse;
import com.ecommerce.promotion.dto.PromotionCalculateRequest;
import com.ecommerce.promotion.dto.PromotionCalculateResponse;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.CouponType;
import com.ecommerce.promotion.entity.UserCoupon;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.ecommerce.promotion.repository.UserCouponRepository;
import com.ecommerce.promotion.service.CouponService;
import com.ecommerce.promotion.service.PromotionCalculationService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * User-facing promotion endpoints.
 */
@RestController
@RequestMapping("/api/v1/promotions")
public class PromotionController {

    private static final Logger log = LoggerFactory.getLogger(PromotionController.class);

    private final CouponService couponService;
    private final UserCouponRepository userCouponRepository;
    private final CouponTemplateRepository couponTemplateRepository;
    private final PromotionCalculationService promotionCalculationService;

    public PromotionController(CouponService couponService,
                                UserCouponRepository userCouponRepository,
                                CouponTemplateRepository couponTemplateRepository,
                                PromotionCalculationService promotionCalculationService) {
        this.couponService = couponService;
        this.userCouponRepository = userCouponRepository;
        this.couponTemplateRepository = couponTemplateRepository;
        this.promotionCalculationService = promotionCalculationService;
    }

    /**
     * Claim a coupon.
     * POST /api/v1/promotions/coupons/claim → 201 Created
     */
    @PostMapping("/coupons/claim")
    public ResponseEntity<UserCoupon> claimCoupon(@Valid @RequestBody CouponClaimRequest request) {
        Long userId = extractUserId();
        UserCoupon claimed = couponService.claim(userId, request.getCouponTemplateId());
        return ResponseEntity.status(HttpStatus.CREATED).body(claimed);
    }

    /**
     * Get current user's coupons.
     * GET /api/v1/promotions/coupons/my → 200 OK
     */
    @GetMapping("/coupons/my")
    public ResponseEntity<List<CouponResponse>> getMyCoupons() {
        Long userId = extractUserId();
        List<UserCoupon> userCoupons = userCouponRepository.findByUserId(userId);
        List<CouponResponse> responses = new ArrayList<>();

        for (UserCoupon uc : userCoupons) {
            Optional<CouponTemplate> templateOpt =
                    couponTemplateRepository.findById(uc.getCouponTemplateId());
            CouponResponse resp = new CouponResponse();
            resp.setUserCouponId(uc.getId());
            resp.setCouponCode(uc.getCouponCode());
            resp.setStatus(uc.getStatus());

            if (templateOpt.isPresent()) {
                CouponTemplate t = templateOpt.get();
                resp.setName(t.getName());
                resp.setType(t.getType());
                resp.setDiscountValue(t.getDiscountValue());
                resp.setThresholdAmount(t.getThresholdAmount());
                resp.setMaxDiscount(t.getMaxDiscount());
                resp.setEndTime(t.getEndTime());
            }

            responses.add(resp);
        }

        return ResponseEntity.ok(responses);
    }

    /**
     * Calculate promotions for an order.
     * POST /api/v1/promotions/calculate → 200 OK
     */
    @PostMapping("/calculate")
    public ResponseEntity<PromotionCalculateResponse> calculate(
            @Valid @RequestBody PromotionCalculateRequest request) {
        // Ensure userId is set if not provided
        if (request.getUserId() == null) {
            request.setUserId(extractUserId());
        }
        PromotionCalculateResponse response = promotionCalculationService.calculate(request);
        return ResponseEntity.ok(response);
    }

    /**
     * Extracts the current user's ID from the Spring Security context.
     */
    private Long extractUserId() {
        String principal = SecurityContextHolder.getContext().getAuthentication().getName();
        try {
            return Long.parseLong(principal);
        } catch (NumberFormatException e) {
            log.warn("Failed to parse user ID from principal '{}'", principal);
            throw new com.ecommerce.common.exception.AuthorizationException(
                    "UNAUTHORIZED", "Invalid user principal: " + principal);
        }
    }
}
