package com.ecommerce.loyalty.event;

import com.ecommerce.common.event.ReviewApprovedEvent;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.loyalty.service.LoyaltyPointService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

/**
 * Listens for {@link ReviewApprovedEvent} and awards review reward points.
 *
 * <p>This is the {@code com.ecommerce.common.event.ReviewApprovedEvent}
 * published by ecommerce-review once a review passes moderation
 * (design-docs/附录D §5). loyalty previously defined and listened to its
 * own module-local shadow of this event, so Spring never routed the real,
 * review-published event here and review reward points were never actually
 * awarded; that shadow class has been removed and this listener now depends
 * on the shared common type.
 */
@Component
public class ReviewApprovedEventListener {

    private static final Logger log = LoggerFactory.getLogger(ReviewApprovedEventListener.class);

    /**
     * Default review reward points per approved review, used when
     * {@code loyalty.review-reward-points} has no runtime override
     * (design-docs/附录B §1: default 20).
     */
    private static final int REVIEW_REWARD_POINTS = 20;

    private final LoyaltyPointService loyaltyPointService;

    public ReviewApprovedEventListener(LoyaltyPointService loyaltyPointService) {
        this.loyaltyPointService = loyaltyPointService;
    }

    @EventListener
    public void onReviewApproved(ReviewApprovedEvent event) {
        log.info("Received ReviewApprovedEvent: reviewId={}, userId={}, orderId={}, productId={}",
                event.getReviewId(), event.getUserId(), event.getOrderId(), event.getProductId());

        try {
            int rewardPoints = RuntimeConfigRegistry.getInt(
                    "loyalty.review-reward-points", REVIEW_REWARD_POINTS);
            loyaltyPointService.earnPoints(
                    event.getUserId(), rewardPoints, "REVIEW",
                    event.getReviewId().toString(),
                    "Review reward, reviewId=" + event.getReviewId());
            log.info("Awarded {} review reward points for reviewId={}, userId={}",
                    rewardPoints, event.getReviewId(), event.getUserId());
        } catch (Exception e) {
            // Failure only logged, never persisted for retry
            log.error("Failed to award review points for reviewId={}: {}",
                    event.getReviewId(), e.getMessage(), e);
        }
    }
}
