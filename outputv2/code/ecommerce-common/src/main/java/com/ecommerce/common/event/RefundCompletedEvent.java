package com.ecommerce.common.event;

import java.math.BigDecimal;

/**
 * Published by ecommerce-payment when a refund completes (after warehouse
 * acceptance). Listened to by ecommerce-order (design-docs/02 §5: "更新售后状态"
 * — transition the order to REFUNDED) and notification (handled synchronously
 * within {@code RefundService} itself, not via this event). Lives in common
 * because ecommerce-order cannot depend on ecommerce-payment (payment already
 * depends on order via OrderQueryService — the reverse would be circular), so
 * order could not otherwise reference the publisher's event class from an
 * {@code @EventListener}.
 */
public class RefundCompletedEvent extends AbstractDomainEvent {

    private final String refundNo;
    private final String paymentNo;
    private final Long orderId;
    private final Long userId;
    private final BigDecimal refundAmount;

    public RefundCompletedEvent(Object source, String refundNo, String paymentNo,
                                Long orderId, Long userId, BigDecimal refundAmount,
                                String traceId) {
        super(source, refundNo, traceId);
        this.refundNo = refundNo;
        this.paymentNo = paymentNo;
        this.orderId = orderId;
        this.userId = userId;
        this.refundAmount = refundAmount;
    }

    public String getRefundNo() { return refundNo; }
    public String getPaymentNo() { return paymentNo; }
    public Long getOrderId() { return orderId; }
    public Long getUserId() { return userId; }
    public BigDecimal getRefundAmount() { return refundAmount; }
}
