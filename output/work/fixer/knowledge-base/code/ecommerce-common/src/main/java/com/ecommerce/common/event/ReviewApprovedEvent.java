package com.ecommerce.common.event;

/**
 * Published by ecommerce-review when a review passes moderation.
 * Listened to by ecommerce-loyalty (design-docs/附录D section 5). Lives in
 * common because loyalty (which only depends on ecommerce-common) must be
 * able to listen to it via {@code @EventListener} without a cross-module
 * dependency on ecommerce-review.
 */
public class ReviewApprovedEvent extends AbstractDomainEvent {

    private final Long reviewId;
    private final Long userId;
    private final Long orderId;
    private final Long productId;

    public ReviewApprovedEvent(Object source, Long reviewId, Long userId, Long orderId,
                                Long productId, String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.reviewId = reviewId;
        this.userId = userId;
        this.orderId = orderId;
        this.productId = productId;
    }

    public Long getReviewId() { return reviewId; }
    public Long getUserId() { return userId; }
    public Long getOrderId() { return orderId; }
    public Long getProductId() { return productId; }
}
