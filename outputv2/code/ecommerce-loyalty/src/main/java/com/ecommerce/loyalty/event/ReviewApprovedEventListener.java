package com.ecommerce.loyalty.event;

import com.ecommerce.common.event.ReviewApprovedEvent;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.loyalty.service.LoyaltyPointService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

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

    // Reports swallowed listener failures to the local event-failure table
    // (design-docs/03 §8). Field-injected + null-guarded so the direct-construction
    // unit tests keep working without this collaborator; Spring wires it in production.
    @org.springframework.beans.factory.annotation.Autowired(required = false)
    private com.ecommerce.common.event.DomainEventPublisher failureRecorder;

    public ReviewApprovedEventListener(LoyaltyPointService loyaltyPointService) {
        this.loyaltyPointService = loyaltyPointService;
    }

    // AFTER_COMMIT + REQUIRES_NEW: review reward points are a non-critical
    // post-approval action and must not roll back the review-approval
    // transaction if awarding fails (design-docs/02 §5, 03 §8).
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
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
            log.error("Failed to award review points for reviewId={}: {}",
                    event.getReviewId(), e.getMessage(), e);
            if (failureRecorder != null) {
                failureRecorder.recordListenerFailure(event, "loyalty.ReviewApprovedEventListener", e);
            }
        }
    }
}
