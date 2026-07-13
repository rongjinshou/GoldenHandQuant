package com.ecommerce.payment.entity;

/**
 * Payment status values, per design-docs/附录C-数据模型.md §5 (payments.status:
 * CREATED/SUCCESS/FAILED/CLOSED).
 */
public enum PaymentStatus {
    CREATED,
    SUCCESS,
    FAILED,
    CLOSED
}
