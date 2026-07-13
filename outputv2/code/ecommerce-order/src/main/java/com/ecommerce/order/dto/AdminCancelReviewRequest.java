package com.ecommerce.order.dto;

/**
 * Request DTO for admin cancellation review.
 *
 * <p>Two request-body forms are accepted for the frozen endpoint
 * {@code POST /api/v1/admin/orders/{orderId}/cancel-review}:
 * the black-box test harness ({@code OrderFixture#cancelReview}) sends
 * {@code {"approved": boolean}}, while the original admin form sends
 * {@code {"decision": "APPROVE"|"REJECT"}}. Both fields are therefore
 * optional here (no bean-validation constraint); the controller resolves
 * the effective decision, preferring the explicit {@code approved} flag.
 */
public class AdminCancelReviewRequest {

    private String decision;

    private Boolean approved;

    private String comment;

    public AdminCancelReviewRequest() {
    }

    public String getDecision() {
        return decision;
    }

    public void setDecision(String decision) {
        this.decision = decision;
    }

    public Boolean getApproved() {
        return approved;
    }

    public void setApproved(Boolean approved) {
        this.approved = approved;
    }

    public String getComment() {
        return comment;
    }

    public void setComment(String comment) {
        this.comment = comment;
    }
}
