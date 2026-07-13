package com.ecommerce.promotion.service;

import com.ecommerce.common.money.MonetaryUtil;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.promotion.dto.PromotionCalculateRequest;
import com.ecommerce.promotion.dto.PromotionCalculateResponse;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.UserCoupon;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.ecommerce.promotion.repository.UserCouponRepository;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Primary calculation service used by cart and order modules to compute
 * the final payable amount after all promotions.
 */
@Service
public class PromotionCalculationService {

    private final FullReductionService fullReductionService;
    private final CouponService couponService;
    private final CouponValidator couponValidator;
    private final UserCouponRepository userCouponRepository;
    private final CouponTemplateRepository couponTemplateRepository;

    public PromotionCalculationService(FullReductionService fullReductionService,
                                        CouponService couponService,
                                        CouponValidator couponValidator,
                                        UserCouponRepository userCouponRepository,
                                        CouponTemplateRepository couponTemplateRepository) {
        this.fullReductionService = fullReductionService;
        this.couponService = couponService;
        this.couponValidator = couponValidator;
        this.userCouponRepository = userCouponRepository;
        this.couponTemplateRepository = couponTemplateRepository;
    }

    /**
     * Calculate all applicable promotions for an order.
     *
     * <p>Stacking order is fixed per design-docs/10 §3: full-reduction → coupon
     * → member, each step applied to the result of the previous one.
     */
    public PromotionCalculateResponse calculate(PromotionCalculateRequest request) {
        BigDecimal itemTotal = computeItemTotal(request.getItems());
        List<Long> skuIds = computeSkuIds(request.getItems());

        // Step 1: full reduction, based on the raw item total.
        BigDecimal fullReductionDiscount =
                fullReductionService.calculateBestReduction(itemTotal)
                        .orElse(BigDecimal.ZERO);
        BigDecimal afterFullReduction = MonetaryUtil.subtract(itemTotal, fullReductionDiscount);

        // Step 2: coupon discount, based on the full-reduction result. Coupons that
        // pass validation and actually discount something are collected into the
        // response's applicable-coupon list (design-docs/07 §3 item 3).
        List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons = new ArrayList<>();
        BigDecimal couponDiscount = calculateCouponDiscount(request.getUserId(),
                request.getCouponIds(), afterFullReduction, skuIds, applicableCoupons);
        BigDecimal afterCoupon = MonetaryUtil.subtract(afterFullReduction, couponDiscount);

        // Step 3: member discount, applied last, based on the coupon result.
        BigDecimal memberDiscount = calculateMemberDiscount(request.getUserId(), afterCoupon);

        BigDecimal finalAmount = MonetaryUtil.subtract(afterCoupon, memberDiscount);
        if (finalAmount.compareTo(BigDecimal.ZERO) < 0) {
            finalAmount = BigDecimal.ZERO;
        }
        // Derive totalDiscount from the clamped finalAmount so it can never
        // exceed itemTotal, even if the individual discounts would overshoot.
        BigDecimal totalDiscount = MonetaryUtil.subtract(itemTotal, finalAmount);

        PromotionCalculateResponse response = new PromotionCalculateResponse();
        response.setItemTotal(itemTotal);
        response.setFullReductionDiscount(fullReductionDiscount);
        response.setCouponDiscount(couponDiscount);
        response.setMemberDiscount(memberDiscount);
        response.setTotalDiscount(totalDiscount);
        response.setFinalAmount(finalAmount);
        response.setApplicableCoupons(applicableCoupons);

        return response;
    }

    private BigDecimal computeItemTotal(List<PromotionCalculateRequest.CalculateItem> items) {
        BigDecimal total = BigDecimal.ZERO;
        for (PromotionCalculateRequest.CalculateItem item : items) {
            BigDecimal lineTotal = MonetaryUtil.multiply(item.getPrice(),
                    BigDecimal.valueOf(item.getQuantity()));
            total = MonetaryUtil.add(total, lineTotal);
        }
        return total;
    }

    private List<Long> computeSkuIds(List<PromotionCalculateRequest.CalculateItem> items) {
        if (items == null) {
            return List.of();
        }
        return items.stream()
                .map(PromotionCalculateRequest.CalculateItem::getSkuId)
                .collect(Collectors.toList());
    }

    /**
     * Calculate member-level discount.
     * In a real implementation, this would look up the user's member level
     * and apply the corresponding discount rate.
     * For now, returns a fixed 5% for demonstration.
     */
    private BigDecimal calculateMemberDiscount(Long userId, BigDecimal amount) {
        if (userId == null || amount == null
                || amount.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }
        BigDecimal memberRate = RuntimeConfigRegistry.getBigDecimal(
                "member.discount-rate", new BigDecimal("0.95"));
        BigDecimal afterDiscount = MonetaryUtil.multiply(amount, memberRate);
        return MonetaryUtil.subtract(amount, afterDiscount);
    }

    /**
     * Calculate the total discount across all requested coupons.
     * Package-private (rather than private) so it can be unit tested directly.
     *
     * <p>Every coupon that passes validation and yields a discount greater than
     * zero is additionally appended to {@code applicableCoupons} (design-docs/07
     * §3 item 3 "优惠券可用列表"); skipped or zero-discount coupons are not.
     */
    BigDecimal calculateCouponDiscount(Long userId, List<Long> couponIds,
                                        BigDecimal currentAmount, List<Long> skuIds,
                                        List<PromotionCalculateResponse.ApplicableCoupon> applicableCoupons) {
        if (userId == null || couponIds == null || couponIds.isEmpty()
                || currentAmount == null || currentAmount.compareTo(BigDecimal.ZERO) <= 0) {
            return BigDecimal.ZERO;
        }

        BigDecimal totalCouponDiscount = BigDecimal.ZERO;
        // De-duplicate: a coupon listed twice in the same request must be counted
        // at most once (10§2 / CouponStatus.USED — a coupon is consumed once per
        // order). Without this, [10, 10] would double-count coupon 10's discount.
        for (Long couponId : couponIds.stream().distinct().collect(Collectors.toList())) {
            Optional<UserCoupon> userCouponOpt = userCouponRepository.findById(couponId);
            if (!userCouponOpt.isPresent()) {
                continue;
            }
            UserCoupon userCoupon = userCouponOpt.get();

            if (!userId.equals(userCoupon.getUserId())) {
                // Not this user's coupon — silently skip rather than leaking
                // its existence to a caller who doesn't own it via an error.
                continue;
            }

            couponValidator.validate(userCoupon, currentAmount, skuIds);

            Optional<CouponTemplate> templateOpt =
                    couponTemplateRepository.findById(userCoupon.getCouponTemplateId());
            if (!templateOpt.isPresent()) {
                continue;
            }
            CouponTemplate template = templateOpt.get();

            BigDecimal discount = couponService.calculateDiscount(currentAmount, template);
            totalCouponDiscount = MonetaryUtil.add(totalCouponDiscount, discount);

            if (discount.compareTo(BigDecimal.ZERO) > 0) {
                PromotionCalculateResponse.ApplicableCoupon applicable =
                        new PromotionCalculateResponse.ApplicableCoupon();
                applicable.setCouponId(userCoupon.getId());
                applicable.setCouponCode(userCoupon.getCouponCode());
                applicable.setName(template.getName());
                applicable.setDiscountAmount(discount);
                applicableCoupons.add(applicable);
            }
        }
        return totalCouponDiscount;
    }
}
