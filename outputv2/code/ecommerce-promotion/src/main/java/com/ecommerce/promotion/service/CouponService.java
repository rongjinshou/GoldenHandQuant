package com.ecommerce.promotion.service;

import com.ecommerce.common.exception.BusinessException;
import com.ecommerce.common.exception.ResourceNotFoundException;
import com.ecommerce.common.exception.ValidationException;
import com.ecommerce.common.money.MonetaryUtil;
import com.ecommerce.common.test.SystemClockService;
import com.ecommerce.promotion.entity.CouponStatus;
import com.ecommerce.promotion.entity.CouponTemplate;
import com.ecommerce.promotion.entity.CouponType;
import com.ecommerce.promotion.entity.UserCoupon;
import com.ecommerce.promotion.repository.CouponTemplateRepository;
import com.ecommerce.promotion.repository.UserCouponRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.UUID;

/**
 * Service for coupon claiming and discount calculation.
 */
@Service
public class CouponService {

    private final CouponTemplateRepository couponTemplateRepository;
    private final UserCouponRepository userCouponRepository;

    public CouponService(CouponTemplateRepository couponTemplateRepository,
                          UserCouponRepository userCouponRepository) {
        this.couponTemplateRepository = couponTemplateRepository;
        this.userCouponRepository = userCouponRepository;
    }

    /**
     * Claim a coupon for a user.
     */
    @Transactional
    public UserCoupon claim(Long userId, Long templateId) {
        CouponTemplate template = couponTemplateRepository.findById(templateId)
                .orElseThrow(() -> new ResourceNotFoundException("CouponTemplate", templateId));

        if (!"ACTIVE".equals(template.getStatus())) {
            throw new BusinessException("COUPON_INACTIVE", "Coupon template is not active");
        }

        // Check per-user limit
        long userClaimCount = userCouponRepository.countByUserIdAndCouponTemplateId(userId, templateId);
        if (template.getPerUserLimit() != null && userClaimCount >= template.getPerUserLimit()) {
            throw new BusinessException("COUPON_LIMIT_EXCEEDED",
                    "You have already claimed the maximum number of this coupon");
        }

        // Check total quantity
        if (template.getTotalQuantity() != null && template.getIssuedQuantity() != null
                && template.getIssuedQuantity() >= template.getTotalQuantity()) {
            throw new BusinessException("COUPON_EXHAUSTED", "Coupon has been fully claimed");
        }

        // Increment issued quantity
        template.setIssuedQuantity(
                template.getIssuedQuantity() != null ? template.getIssuedQuantity() + 1 : 1);
        couponTemplateRepository.save(template);

        UserCoupon userCoupon = new UserCoupon();
        userCoupon.setUserId(userId);
        userCoupon.setCouponTemplateId(templateId);
        userCoupon.setCouponCode(generateCouponCode());
        userCoupon.setStatus(CouponStatus.AVAILABLE);
        userCoupon.setClaimedAt(SystemClockService.now());

        return userCouponRepository.save(userCoupon);
    }

    /**
     * Calculate the discount amount for applying a coupon to a given price.
     */
    public BigDecimal calculateDiscount(BigDecimal price, CouponTemplate coupon) {
        if (price == null || coupon == null) {
            return BigDecimal.ZERO;
        }

        switch (coupon.getType()) {
            case DISCOUNT:
                // discountAmount = price * (1 - discountValue), per design-docs/10 §2.
                // e.g. an 80%-price ("8折") coupon on 100.00 yields a 20.00 discount.
                BigDecimal discountRate = BigDecimal.ONE.subtract(coupon.getDiscountValue());
                BigDecimal discountAmount = MonetaryUtil.multiply(price, discountRate);
                if (coupon.getMaxDiscount() != null && discountAmount.compareTo(coupon.getMaxDiscount()) > 0) {
                    return coupon.getMaxDiscount();
                }
                return discountAmount;

            case AMOUNT_OFF:
                BigDecimal amountOff = coupon.getDiscountValue();
                if (amountOff != null) {
                    if (amountOff.compareTo(price) > 0) {
                        return price;
                    }
                    return amountOff;
                }
                return BigDecimal.ZERO;

            case THRESHOLD_OFF:
                if (coupon.getThresholdAmount() != null
                        && price.compareTo(coupon.getThresholdAmount()) >= 0) {
                    BigDecimal off = coupon.getDiscountValue();
                    if (off != null) {
                        if (off.compareTo(price) > 0) {
                            return price;
                        }
                        return off;
                    }
                }
                return BigDecimal.ZERO;

            default:
                return BigDecimal.ZERO;
        }
    }

    /**
     * Mark a claimed coupon as used against a successfully-created order.
     * Called by the order module after an order that applied this coupon
     * has been persisted (never before, so a failed order never consumes it).
     *
     * <p>The coupon is only consumed when it actually belongs to {@code userId}.
     * A coupon that is not the ordering user's is silently skipped — mirroring
     * the calculation side ({@code PromotionCalculationService#calculateCouponDiscount},
     * which already ignores non-owned coupons) — so listing another user's
     * {@code userCouponId} in a create-order request can never consume it.
     */
    @Transactional
    public void markUsed(Long userCouponId, Long orderId, Long userId) {
        UserCoupon userCoupon = userCouponRepository.findById(userCouponId)
                .orElseThrow(() -> new ResourceNotFoundException("UserCoupon", userCouponId));
        if (userId != null && !userId.equals(userCoupon.getUserId())) {
            return;
        }
        userCoupon.setStatus(CouponStatus.USED);
        userCoupon.setUsedOrderId(orderId);
        userCoupon.setUsedAt(SystemClockService.now());
        userCouponRepository.save(userCoupon);
    }

    /**
     * Give back every coupon consumed by a cancelled order: each USED coupon
     * whose {@code usedOrderId} matches becomes AVAILABLE again, with the
     * consumption bookkeeping ({@code usedOrderId}/{@code usedAt}) cleared.
     * The inverse of {@link #markUsed}, called by the order module on the
     * successful-cancellation paths.
     *
     * <p>Deliberately a no-op for orders that consumed no coupon, and never
     * throws in normal operation — a release failure must not block the
     * cancellation itself. Whether the coupon is still inside its validity
     * window is not re-checked here: the validator enforces the template
     * window again at next use.
     */
    @Transactional
    public void releaseForOrder(Long orderId) {
        if (orderId == null) {
            return;
        }
        for (UserCoupon userCoupon
                : userCouponRepository.findByStatusAndUsedOrderId(CouponStatus.USED, orderId)) {
            userCoupon.setStatus(CouponStatus.AVAILABLE);
            userCoupon.setUsedOrderId(null);
            userCoupon.setUsedAt(null);
            userCouponRepository.save(userCoupon);
        }
    }

    private String generateCouponCode() {
        return "CPN-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
    }
}
