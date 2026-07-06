package com.ecommerce.loyalty.event;

import com.ecommerce.common.event.ReviewApprovedEvent;
import com.ecommerce.common.test.RuntimeConfigRegistry;
import com.ecommerce.loyalty.service.LoyaltyPointService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link ReviewApprovedEventListener}.
 *
 * <p>The listener must react to
 * {@code com.ecommerce.common.event.ReviewApprovedEvent} — the class
 * actually published by ecommerce-review — rather than a module-local
 * shadow (design spec §6.9 item 3).
 */
@ExtendWith(MockitoExtension.class)
class ReviewApprovedEventListenerTest {

    @Mock
    private LoyaltyPointService loyaltyPointService;

    private ReviewApprovedEventListener listener;

    @BeforeEach
    void setUp() {
        listener = new ReviewApprovedEventListener(loyaltyPointService);
    }

    @AfterEach
    void tearDown() {
        RuntimeConfigRegistry.clear();
    }

    private ReviewApprovedEvent commonEvent(Long reviewId, Long userId) {
        return new ReviewApprovedEvent(new Object(), reviewId, userId, 1234L, 5678L,
                "review-" + reviewId, "trace-" + reviewId);
    }

    /**
     * Verifies that when a review is approved, the listener awards the
     * default 20 points via {@link LoyaltyPointService#earnPoints}.
     */
    @Test
    void testReviewApproved_awards20Points() {
        Long reviewId = 999L;
        Long userId = 888L;

        ReviewApprovedEvent event = commonEvent(reviewId, userId);

        listener.onReviewApproved(event);

        verify(loyaltyPointService).earnPoints(
                eq(userId),
                eq(20),
                eq("REVIEW"),
                eq(reviewId.toString()),
                eq("Review reward, reviewId=" + reviewId));
    }

    /**
     * Verifies the REVIEW_REWARD_POINTS constant is exactly 20
     * by checking the value via reflection.
     */
    @Test
    void testReviewRewardPointsConstant_is20() throws Exception {
        java.lang.reflect.Field field = ReviewApprovedEventListener.class
                .getDeclaredField("REVIEW_REWARD_POINTS");
        field.setAccessible(true);
        int value = field.getInt(null);
        assertEquals(20, value, "Review reward points constant should be 20");
    }

    /**
     * design spec §6.9 item 8: the reward amount must honor a
     * {@code loyalty.review-reward-points} RuntimeConfigRegistry override
     * instead of being permanently hardcoded to 20.
     */
    @Test
    void testReviewRewardPoints_honorsRuntimeConfigOverride() {
        Long reviewId = 111L;
        Long userId = 222L;
        RuntimeConfigRegistry.put("loyalty.review-reward-points", 50);

        listener.onReviewApproved(commonEvent(reviewId, userId));

        verify(loyaltyPointService).earnPoints(
                eq(userId), eq(50), eq("REVIEW"),
                eq(reviewId.toString()),
                eq("Review reward, reviewId=" + reviewId));
    }
}
