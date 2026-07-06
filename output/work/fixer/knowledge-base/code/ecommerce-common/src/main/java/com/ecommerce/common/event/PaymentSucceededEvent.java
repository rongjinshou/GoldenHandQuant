package com.ecommerce.common.event;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Published by payment-service when a payment succeeds.
 * Listeners (order, inventory, logistics, loyalty, notification) must not
 * roll back the payment transaction on failure.
 *
 * <p>Payload per design-docs/附录D §3: paymentNo, orderId, paidAmount, paidAt.
 * Lives in ecommerce-common so the real publisher's class is the one Spring
 * dispatches to, rather than a module-local shadow copy.
 */
public class PaymentSucceededEvent extends AbstractDomainEvent {

    private final String paymentNo;
    private final Long orderId;
    private final BigDecimal paidAmount;
    private final LocalDateTime paidAt;

    public PaymentSucceededEvent(Object source, String paymentNo, Long orderId,
                                 BigDecimal paidAmount, LocalDateTime paidAt,
                                 String aggregateId, String traceId) {
        super(source, aggregateId, traceId);
        this.paymentNo = paymentNo;
        this.orderId = orderId;
        this.paidAmount = paidAmount;
        this.paidAt = paidAt;
    }

    public String getPaymentNo() {
        return paymentNo;
    }

    public Long getOrderId() {
        return orderId;
    }

    public BigDecimal getPaidAmount() {
        return paidAmount;
    }

    public LocalDateTime getPaidAt() {
        return paidAt;
    }
}
