package com.ecommerce.payment.entity;

/**
 * Refund lifecycle states, aligned verbatim with design-docs/附录C-数据模型.md
 * {@code refunds.status}: APPLIED/REVIEWED/ACCEPTED/REFUNDED/REJECTED.
 *
 * <ul>
 *   <li>{@code APPLIED}  — refund application submitted, awaiting merchant review</li>
 *   <li>{@code REVIEWED} — merchant approved, waiting on warehouse acceptance</li>
 *   <li>{@code ACCEPTED} — warehouse accepted the returned goods</li>
 *   <li>{@code REFUNDED} — financial refund executed (terminal)</li>
 *   <li>{@code REJECTED} — rejected at merchant review or warehouse inspection (terminal)</li>
 * </ul>
 *
 * <p>Note: the README §7 error code string {@code REFUND_WAITING_WAREHOUSE_ACCEPT}
 * is a frozen API contract and is unrelated to these enum constant names.
 */
public enum RefundStatus {
    APPLIED,
    REVIEWED,
    ACCEPTED,
    REFUNDED,
    REJECTED
}
