package com.ecommerce.payment.entity;

/**
 * Invoice states, aligned verbatim with design-docs/附录C-数据模型.md
 * {@code invoices.status}: ISSUED/VOIDED.
 */
public enum InvoiceStatus {
    ISSUED,
    VOIDED
}
